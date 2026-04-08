"""Tests for cli_executor.py — CLI-based agent executor."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import RuntimeConfig
from cli_executor import CLIAgentExecutor, _brief_summary


def _make_executor(
    runtime="claude-code",
    runtime_config=None,
    system_prompt="You are a helpful agent.",
    heartbeat=None,
):
    """Build a CLIAgentExecutor with mocked externals."""
    if runtime_config is None:
        runtime_config = RuntimeConfig()
    with patch("shutil.which", return_value="/usr/bin/claude"):
        executor = CLIAgentExecutor(
            runtime=runtime,
            runtime_config=runtime_config,
            system_prompt=system_prompt,
            heartbeat=heartbeat,
        )
    return executor


def _make_context(text_parts, context_id="ctx-test"):
    """Helper to build a mock RequestContext."""
    parts = []
    for t in text_parts:
        p = MagicMock()
        p.text = t
        parts.append(p)
    context = MagicMock()
    context.message.parts = parts
    context.context_id = context_id
    return context


def _make_event_queue():
    """Helper to build a mock EventQueue with async enqueue_event."""
    return AsyncMock()


# ---------- _build_command tests ----------


def test_build_command_claude_code():
    """Verify correct flags for claude-code runtime."""
    executor = _make_executor()
    cmd = executor._build_command("Hello world")

    assert cmd[0] == "claude"
    assert "--print" in cmd
    assert "--dangerously-skip-permissions" in cmd
    assert "--output-format" in cmd
    assert "json" in cmd
    # Prompt flag and message at the end
    assert "-p" in cmd
    idx = cmd.index("-p")
    assert cmd[idx + 1] == "Hello world"


def test_build_command_claude_code_with_session():
    """Verify --resume flag when session_id exists."""
    executor = _make_executor()
    executor._session_id = "session-abc-123"

    cmd = executor._build_command("Follow up question")

    assert "--resume" in cmd
    idx = cmd.index("--resume")
    assert cmd[idx + 1] == "session-abc-123"


def test_build_command_model_flag():
    """Verify --model flag is included when model is set."""
    rc = RuntimeConfig(model="opus")
    executor = _make_executor(runtime_config=rc)

    cmd = executor._build_command("Test")

    assert "--model" in cmd
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "opus"


def test_build_command_no_model_flag_when_empty():
    """Verify --model flag is NOT included when model is empty."""
    rc = RuntimeConfig(model="")
    executor = _make_executor(runtime_config=rc)

    cmd = executor._build_command("Test")

    assert "--model" not in cmd


def test_system_prompt_only_first_message():
    """Verify system prompt not sent when session_id exists (resumed session)."""
    executor = _make_executor(system_prompt="Be helpful")

    # First message — system prompt should appear
    cmd_first = executor._build_command("First message")
    assert "--system-prompt" in cmd_first

    # Simulate session continuity
    executor._session_id = "session-xyz"

    # Second message — system prompt should NOT appear
    cmd_second = executor._build_command("Second message")
    assert "--system-prompt" not in cmd_second


# ---------- execute tests ----------


@pytest.mark.asyncio
async def test_set_current_task_on_execute():
    """Verify heartbeat is updated during execution."""
    heartbeat = MagicMock()
    heartbeat.current_task = ""
    heartbeat.active_tasks = 0

    executor = _make_executor(heartbeat=heartbeat)

    # Track heartbeat updates
    task_values = []
    original_set = executor._set_current_task

    async def tracking_set(task):
        task_values.append(task)
        # Just update heartbeat directly without HTTP call
        if heartbeat:
            heartbeat.current_task = task
            heartbeat.active_tasks = 1 if task else 0

    executor._set_current_task = tracking_set

    # Mock _run_cli to avoid subprocess
    executor._run_cli = AsyncMock()

    part = MagicMock()
    part.text = "Build the feature"
    context = MagicMock()
    context.message.parts = [part]
    eq = _make_event_queue()

    await executor.execute(context, eq)

    # Should have set task at start and cleared at end
    assert len(task_values) == 2
    assert task_values[0] != ""  # set to brief summary
    assert task_values[1] == ""  # cleared


@pytest.mark.asyncio
async def test_empty_message_rejected():
    """Verify empty message returns error event."""
    executor = _make_executor()

    # Part with no text
    part = MagicMock(spec=[])  # no .text attribute

    context = MagicMock()
    context.message.parts = [part]
    eq = _make_event_queue()

    await executor.execute(context, eq)

    eq.enqueue_event.assert_called_once()
    event_arg = eq.enqueue_event.call_args[0][0]
    assert "Error" in str(event_arg) or "no text" in str(event_arg)


# ---------- _brief_summary tests ----------


def test_brief_summary_simple():
    """Simple single-line text is returned as-is."""
    assert _brief_summary("Hello world") == "Hello world"


def test_brief_summary_truncation():
    """Long text is truncated with ellipsis."""
    long_text = "A" * 100
    result = _brief_summary(long_text, max_len=80)
    assert len(result) == 80
    assert result.endswith("...")


def test_brief_summary_strips_markdown_headers():
    """Markdown headers (# ## ###) are stripped."""
    assert _brief_summary("## Build the feature") == "Build the feature"
    assert _brief_summary("### Deploy to prod") == "Deploy to prod"


def test_brief_summary_skips_empty_and_code_fences():
    """Empty lines and code fence markers are skipped; first non-skippable line returned."""
    text = "\n\n```python\nActual summary"
    assert _brief_summary(text) == "Actual summary"


def test_brief_summary_strips_bold_italic():
    """Markdown bold/italic markers are removed."""
    assert _brief_summary("**Important** task") == "Important task"
    assert _brief_summary("__Urgent__ fix") == "Urgent fix"


def test_brief_summary_skips_hr():
    """Horizontal rules (---) are skipped."""
    text = "---\nReal content"
    assert _brief_summary(text) == "Real content"


def test_brief_summary_fallback():
    """When all lines are empty/fences/hr, falls back to truncated raw text."""
    text = "\n\n---\n```\n"
    result = _brief_summary(text)
    # All lines are skippable, so falls back to text[:max_len]
    assert result == text[:80]


# ---------- _run_cli tests ----------


@pytest.mark.asyncio
async def test_run_cli_success():
    """Successful CLI execution enqueues the output."""
    executor = _make_executor()

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(b'{"session_id": "s1", "result": "Done!"}', b"")
    )
    mock_proc.returncode = 0

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        await executor._run_cli("Do something", eq)

    eq.enqueue_event.assert_called_once()
    event_arg = eq.enqueue_event.call_args[0][0]
    assert "Done!" in str(event_arg)
    # Session ID should be captured
    assert executor._session_id == "s1"


@pytest.mark.asyncio
async def test_run_cli_timeout():
    """CLI timeout enqueues a timeout error message."""
    rc = RuntimeConfig(timeout=10)
    executor = _make_executor(runtime_config=rc)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_proc.kill = AsyncMock()
    mock_proc.wait = AsyncMock()

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            await executor._run_cli("Slow task", eq)

    eq.enqueue_event.assert_called_once()
    event_arg = eq.enqueue_event.call_args[0][0]
    assert "timed out" in str(event_arg)


@pytest.mark.asyncio
async def test_run_cli_extra_args():
    """Extra args from RuntimeConfig are included in the command."""
    rc = RuntimeConfig(args=["--verbose", "--no-cache"])
    executor = _make_executor(runtime_config=rc)

    cmd = executor._build_command("Test task")
    assert "--verbose" in cmd
    assert "--no-cache" in cmd
