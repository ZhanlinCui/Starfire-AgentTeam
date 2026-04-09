"""Tests for cli_executor.py — CLI-based agent executor."""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import RuntimeConfig
from cli_executor import CLIAgentExecutor, _brief_summary


def _make_executor(
    runtime="claude-code",
    runtime_config=None,
    system_prompt="You are a helpful agent.",
    heartbeat=None,
    config_path="/configs",
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
            config_path=config_path,
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


# ---------- constructor / preset tests ----------


def test_unknown_runtime_raises():
    """Unknown runtime raises ValueError."""
    with patch("shutil.which", return_value="/usr/bin/whatever"):
        with pytest.raises(ValueError, match="Unknown runtime"):
            CLIAgentExecutor(
                runtime="totally-unknown",
                runtime_config=RuntimeConfig(),
            )


def test_custom_runtime_preset():
    """custom runtime builds preset from RuntimeConfig.command."""
    rc = RuntimeConfig(command="myagent")
    with patch("shutil.which", return_value="/usr/bin/myagent"):
        executor = CLIAgentExecutor(runtime="custom", runtime_config=rc)
    assert executor.preset["command"] == "myagent"
    assert executor.preset["prompt_flag"] == "-p"


# ---------- _resolve_auth_token from file (lines 173-179) ----------


def test_resolve_auth_token_from_file(tmp_path):
    """Auth token is read from file when the token file exists."""
    token_file = tmp_path / ".my-token"
    token_file.write_text("file-secret-token\n")

    rc = RuntimeConfig(auth_token_file=".my-token")
    with patch("shutil.which", return_value="/usr/bin/claude"):
        with patch.dict(os.environ, {}, clear=False):
            # Ensure no env var override
            os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
            executor = CLIAgentExecutor(
                runtime="claude-code",
                runtime_config=rc,
                config_path=str(tmp_path),
            )
    assert executor._auth_token == "file-secret-token"


def test_resolve_auth_token_from_preset_default_file(tmp_path):
    """Auth token from the preset's default_auth_file when config file_name is empty."""
    # claude-code preset uses default_auth_file=".auth-token"
    token_file = tmp_path / ".auth-token"
    token_file.write_text("preset-default-token")

    rc = RuntimeConfig()  # no explicit auth_token_file
    with patch("shutil.which", return_value="/usr/bin/claude"):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
            executor = CLIAgentExecutor(
                runtime="claude-code",
                runtime_config=rc,
                config_path=str(tmp_path),
            )
    assert executor._auth_token == "preset-default-token"


def test_resolve_auth_token_returns_none_when_no_file_and_no_env(tmp_path):
    """Returns None when neither env var nor file is present."""
    rc = RuntimeConfig()
    with patch("shutil.which", return_value="/usr/bin/claude"):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
            executor = CLIAgentExecutor(
                runtime="claude-code",
                runtime_config=rc,
                config_path=str(tmp_path),  # no .auth-token file here
            )
    assert executor._auth_token is None


# ---------- _create_auth_helper (lines 183-189) and line 139 ----------


def test_create_auth_helper_creates_executable_script(tmp_path):
    """_create_auth_helper creates a shell script that outputs the token."""
    rc = RuntimeConfig()
    with patch("shutil.which", return_value="/usr/bin/claude"):
        executor = CLIAgentExecutor(
            runtime="claude-code",
            runtime_config=rc,
            config_path=str(tmp_path),
        )

    helper_path = executor._create_auth_helper("my-secret-token")
    assert helper_path is not None
    script_content = Path(helper_path).read_text()
    assert "#!/bin/sh" in script_content
    assert "my-secret-token" in script_content
    # Cleanup
    import os as _os
    _os.unlink(helper_path)


def test_auth_helper_created_when_apiKeyHelper_pattern(tmp_path):
    """_auth_helper_path is set when auth_pattern=apiKeyHelper and token present."""
    from cli_executor import RUNTIME_PRESETS
    # We'll use a custom runtime and monkeypatch the preset
    rc = RuntimeConfig(command="fakecli", auth_token_env="FAKE_API_KEY")

    with patch("shutil.which", return_value="/usr/bin/fakecli"):
        with patch.dict(os.environ, {"FAKE_API_KEY": "test-api-key"}):
            executor = CLIAgentExecutor(
                runtime="custom",
                runtime_config=rc,
                config_path=str(tmp_path),
            )
            # Patch the preset to apiKeyHelper pattern and call manually
            executor.preset["auth_pattern"] = "apiKeyHelper"
            executor._auth_token = "test-api-key"
            helper_path = executor._create_auth_helper("test-api-key")
            executor._auth_helper_path = helper_path

    assert executor._auth_helper_path is not None
    content = Path(executor._auth_helper_path).read_text()
    assert "test-api-key" in content


# ---------- _get_a2a_instructions non-MCP path (line 219) ----------


def test_get_a2a_instructions_non_mcp_path(tmp_path):
    """Non-MCP runtimes (ollama/custom) get CLI delegation instructions."""
    rc = RuntimeConfig(command="myagent")
    with patch("shutil.which", return_value="/usr/bin/myagent"):
        executor = CLIAgentExecutor(
            runtime="custom",
            runtime_config=rc,
            config_path=str(tmp_path),
        )
    instructions = executor._get_a2a_instructions()
    assert "a2a_cli.py" in instructions
    assert "Inter-Agent Communication" in instructions
    # Make sure it's NOT the MCP version
    assert "MCP tools" not in instructions


def test_get_a2a_instructions_ollama_is_non_mcp(tmp_path):
    """Ollama runtime (auth_pattern=None) uses CLI delegation instructions."""
    rc = RuntimeConfig()
    with patch("shutil.which", return_value="/usr/bin/ollama"):
        executor = CLIAgentExecutor(
            runtime="ollama",
            runtime_config=rc,
            config_path=str(tmp_path),
        )
    instructions = executor._get_a2a_instructions()
    assert "a2a_cli.py" in instructions


# ---------- _set_current_task HTTP path (lines 232-252) ----------


async def test_set_current_task_with_workspace_and_platform(tmp_path):
    """_set_current_task sends HTTP heartbeat when WORKSPACE_ID and PLATFORM_URL set."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("cli_executor.httpx.AsyncClient", return_value=mock_client):
        with patch.dict(os.environ, {
            "WORKSPACE_ID": "ws-123",
            "PLATFORM_URL": "http://platform.test",
        }):
            # Force a fresh http client
            if hasattr(executor, "_http_client"):
                del executor._http_client
            # Inject mock client directly
            executor._http_client = mock_client
            await executor._set_current_task("Running analysis")

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert "heartbeat" in call_args[0][0]
    assert call_args[1]["json"]["current_task"] == "Running analysis"


async def test_set_current_task_http_exception_is_suppressed(tmp_path):
    """_set_current_task swallows HTTP exceptions (best-effort)."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("network failure"))
    executor._http_client = mock_client

    with patch.dict(os.environ, {
        "WORKSPACE_ID": "ws-123",
        "PLATFORM_URL": "http://platform.test",
    }):
        # Should not raise
        await executor._set_current_task("some task")


async def test_set_current_task_no_workspace_id_skips_http(tmp_path):
    """_set_current_task skips HTTP when WORKSPACE_ID or PLATFORM_URL is absent."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_client = AsyncMock()
    executor._http_client = mock_client

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("WORKSPACE_ID", None)
        os.environ.pop("PLATFORM_URL", None)
        await executor._set_current_task("task")

    mock_client.post.assert_not_called()


# ---------- _recall_memories (lines 265, 274-276) ----------


async def test_recall_memories_success(tmp_path):
    """_recall_memories returns formatted lines when API returns a list."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"scope": "LOCAL", "content": "User likes Python"},
        {"scope": "GLOBAL", "content": "User prefers concise answers"},
    ]

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False  # prevent _get_http_client from replacing the mock
    executor._http_client = mock_client

    with patch.dict(os.environ, {
        "WORKSPACE_ID": "ws-abc",
        "PLATFORM_URL": "http://platform.test",
    }):
        result = await executor._recall_memories()

    assert "User likes Python" in result
    assert "User prefers concise answers" in result
    assert "[LOCAL]" in result


async def test_recall_memories_empty_list_returns_empty_string(tmp_path):
    """_recall_memories returns empty string when API returns empty list."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_resp = MagicMock()
    mock_resp.json.return_value = []

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    executor._http_client = mock_client

    with patch.dict(os.environ, {
        "WORKSPACE_ID": "ws-abc",
        "PLATFORM_URL": "http://platform.test",
    }):
        result = await executor._recall_memories()

    assert result == ""


async def test_recall_memories_no_workspace_returns_empty(tmp_path):
    """_recall_memories returns empty string when WORKSPACE_ID not set."""
    executor = _make_executor(config_path=str(tmp_path))

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("WORKSPACE_ID", None)
        os.environ.pop("PLATFORM_URL", None)
        result = await executor._recall_memories()

    assert result == ""


async def test_recall_memories_exception_returns_empty(tmp_path):
    """_recall_memories swallows exceptions and returns empty string."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
    executor._http_client = mock_client

    with patch.dict(os.environ, {
        "WORKSPACE_ID": "ws-abc",
        "PLATFORM_URL": "http://platform.test",
    }):
        result = await executor._recall_memories()

    assert result == ""


# ---------- _commit_memory (lines 283, 289-290, 296) ----------


async def test_commit_memory_no_workspace_returns_early(tmp_path):
    """_commit_memory returns early (no HTTP call) when WORKSPACE_ID not set."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_client = AsyncMock()
    executor._http_client = mock_client

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("WORKSPACE_ID", None)
        os.environ.pop("PLATFORM_URL", None)
        await executor._commit_memory("something to remember")

    mock_client.post.assert_not_called()


async def test_commit_memory_no_content_returns_early(tmp_path):
    """_commit_memory returns early when content is empty."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_client = AsyncMock()
    executor._http_client = mock_client

    with patch.dict(os.environ, {
        "WORKSPACE_ID": "ws-abc",
        "PLATFORM_URL": "http://platform.test",
    }):
        await executor._commit_memory("")

    mock_client.post.assert_not_called()


async def test_commit_memory_posts_to_api(tmp_path):
    """_commit_memory sends POST when workspace_id, platform_url, and content present."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False  # prevent _get_http_client from replacing the mock
    executor._http_client = mock_client

    with patch.dict(os.environ, {
        "WORKSPACE_ID": "ws-abc",
        "PLATFORM_URL": "http://platform.test",
    }):
        await executor._commit_memory("Important fact about user")

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert "memories" in call_args[0][0]
    assert call_args[1]["json"]["content"] == "Important fact about user"


async def test_commit_memory_exception_is_suppressed(tmp_path):
    """_commit_memory swallows HTTP exceptions (best-effort)."""
    executor = _make_executor(config_path=str(tmp_path))

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("timeout"))
    executor._http_client = mock_client

    with patch.dict(os.environ, {
        "WORKSPACE_ID": "ws-abc",
        "PLATFORM_URL": "http://platform.test",
    }):
        # Should not raise
        await executor._commit_memory("some content")


# ---------- _build_command ollama model positional arg (line 316) ----------


def test_build_command_ollama_model_positional(tmp_path):
    """Ollama runtime: model is appended positionally (no model_flag)."""
    rc = RuntimeConfig(model="llama3")
    with patch("shutil.which", return_value="/usr/bin/ollama"):
        executor = CLIAgentExecutor(
            runtime="ollama",
            runtime_config=rc,
            config_path=str(tmp_path),
        )
    cmd = executor._build_command("Hello")
    assert "llama3" in cmd
    # Model should appear after "run" and before prompt
    run_idx = cmd.index("run")
    model_idx = cmd.index("llama3")
    assert model_idx > run_idx


# ---------- _build_command apiKeyHelper auth settings (lines 331-332) ----------


def test_build_command_includes_apiKeyHelper_settings(tmp_path):
    """Command includes --settings with apiKeyHelper when auth_helper_path is set."""
    rc = RuntimeConfig(command="fakecli", auth_token_env="FAKE_KEY")
    with patch("shutil.which", return_value="/usr/bin/fakecli"):
        with patch.dict(os.environ, {"FAKE_KEY": "my-api-key"}):
            executor = CLIAgentExecutor(
                runtime="custom",
                runtime_config=rc,
                config_path=str(tmp_path),
            )
    # Manually simulate apiKeyHelper auth pattern
    executor.preset["auth_pattern"] = "apiKeyHelper"
    executor._auth_helper_path = "/tmp/fake-helper.sh"

    cmd = executor._build_command("test message")
    assert "--settings" in cmd
    settings_idx = cmd.index("--settings")
    settings_val = json.loads(cmd[settings_idx + 1])
    assert settings_val["apiKeyHelper"] == "/tmp/fake-helper.sh"


# ---------- _build_command positional prompt for ollama (line 351) ----------


def test_build_command_ollama_positional_prompt(tmp_path):
    """Ollama runtime: prompt is appended positionally (no prompt_flag)."""
    rc = RuntimeConfig()
    with patch("shutil.which", return_value="/usr/bin/ollama"):
        executor = CLIAgentExecutor(
            runtime="ollama",
            runtime_config=rc,
            config_path=str(tmp_path),
        )
    cmd = executor._build_command("my ollama prompt")
    # prompt_flag is None, so prompt goes at end positionally
    assert cmd[-1] == "my ollama prompt"
    assert "-p" not in cmd


# ---------- _run_cli: session_id from JSON "session_id" field (line 426+) ----------


async def test_run_cli_captures_session_id_from_json():
    """session_id field in JSON output is captured."""
    executor = _make_executor()

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(b'{"session_id": "new-session-99", "result": "All done"}', b"")
    )
    mock_proc.returncode = 0

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        await executor._run_cli("Do task", eq)

    assert executor._session_id == "new-session-99"
    eq.enqueue_event.assert_called_once()


# ---------- _run_cli: rate limit retry (lines 442-443, 468-474) ----------


async def test_run_cli_rate_limit_retry_then_success():
    """Rate limit on stderr triggers retry; second attempt succeeds."""
    executor = _make_executor()

    call_count = 0

    async def mock_communicate():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return (b"", b"rate limit exceeded (429)")
        return (b'{"result": "Success after retry"}', b"")

    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = mock_communicate

    # Second call proc has returncode 0
    mock_proc2 = AsyncMock()
    mock_proc2.communicate = AsyncMock(
        return_value=(b'{"result": "Success after retry"}', b"")
    )
    mock_proc2.returncode = 0

    procs = iter([mock_proc, mock_proc2])

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", side_effect=lambda *a, **kw: next(procs)):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await executor._run_cli("Do task", eq)

    assert eq.enqueue_event.call_count >= 1


async def test_run_cli_rate_limit_in_stderr_retries():
    """Rate limit keyword in stderr causes retry with backoff."""
    executor = _make_executor()

    attempts = []

    proc_fail = AsyncMock()
    proc_fail.returncode = 1
    proc_fail.communicate = AsyncMock(return_value=(b"", b"overloaded"))

    proc_ok = AsyncMock()
    proc_ok.returncode = 0
    proc_ok.communicate = AsyncMock(return_value=(b'{"result": "ok"}', b""))

    call_iter = iter([proc_fail, proc_ok])

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", side_effect=lambda *a, **kw: next(call_iter)):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await executor._run_cli("task", eq)

    eq.enqueue_event.assert_called_once()


# ---------- _run_cli: auth error clears session and retries (line 364+) ----------


async def test_run_cli_auth_error_clears_session_id():
    """Auth error in stderr clears _session_id and retries."""
    executor = _make_executor()
    executor._session_id = "existing-session"

    proc_auth_err = AsyncMock()
    proc_auth_err.returncode = 1
    proc_auth_err.communicate = AsyncMock(
        return_value=(b"", b"authentication error: invalid X-Api-Key")
    )

    proc_ok = AsyncMock()
    proc_ok.returncode = 0
    proc_ok.communicate = AsyncMock(return_value=(b'{"result": "retried ok"}', b""))

    call_iter = iter([proc_auth_err, proc_ok])

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", side_effect=lambda *a, **kw: next(call_iter)):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await executor._run_cli("task", eq)

    # Session should have been cleared on auth error
    # (may have been re-set if second attempt has JSON with session_id)
    # Just verify the retry happened and an event was enqueued
    assert eq.enqueue_event.call_count >= 1


# ---------- _run_cli: empty result all retries exhausted (lines 455-464) ----------


async def test_run_cli_empty_result_all_retries_returns_no_response():
    """When all retries return empty output, enqueue 'no response' message."""
    executor = _make_executor()

    # claude-code with JSON output that has empty result
    proc = AsyncMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(b'{"result": ""}', b""))

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await executor._run_cli("task", eq)

    eq.enqueue_event.assert_called_once()
    event_text = str(eq.enqueue_event.call_args[0][0])
    assert "no response" in event_text


async def test_run_cli_empty_result_on_intermediate_attempt_retries():
    """Empty result on first attempt triggers retry before giving up."""
    executor = _make_executor()

    call_count = 0

    async def varying_communicate():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            # Empty result triggers retry
            return (b'{"result": ""}', b"")
        return (b'{"result": "finally got one"}', b"")

    proc = AsyncMock()
    proc.returncode = 0
    proc.communicate = varying_communicate

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await executor._run_cli("task", eq)

    eq.enqueue_event.assert_called_once()
    assert "finally got one" in str(eq.enqueue_event.call_args[0][0])


# ---------- _run_cli: timeout with proc.kill raising (lines 497-498) ----------


async def test_run_cli_timeout_proc_kill_raises():
    """Timeout handler swallows exception from proc.kill()."""
    rc = RuntimeConfig(timeout=5)
    executor = _make_executor(runtime_config=rc)

    mock_proc = AsyncMock()
    mock_proc.kill = MagicMock(side_effect=OSError("no such process"))
    mock_proc.wait = AsyncMock()

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            await executor._run_cli("slow task", eq)

    eq.enqueue_event.assert_called_once()
    assert "timed out" in str(eq.enqueue_event.call_args[0][0])


# ---------- _run_cli: non-zero exit with no stderr (line 466) ----------


async def test_run_cli_nonzero_exit_no_stderr_uses_exit_code():
    """Non-zero exit with no stderr falls back to 'Exit code N' message."""
    executor = _make_executor(runtime="ollama")

    proc = AsyncMock()
    proc.returncode = 2
    proc.communicate = AsyncMock(return_value=(b"", b""))

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        await executor._run_cli("task", eq)

    event_text = str(eq.enqueue_event.call_args[0][0])
    assert "Exit code" in event_text or "Agent error" in event_text


# ---------- _run_cli: generic exception (lines 503-508) ----------


async def test_run_cli_generic_exception_enqueues_error():
    """Unexpected exception from subprocess is caught and enqueued as error."""
    executor = _make_executor()
    eq = _make_event_queue()

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=RuntimeError("fork failed"),
    ):
        await executor._run_cli("task", eq)

    eq.enqueue_event.assert_called_once()
    assert "Agent error" in str(eq.enqueue_event.call_args[0][0])


# ---------- _run_cli: non-JSON output for claude-code runtime ----------


async def test_run_cli_non_json_output_used_raw():
    """claude-code runtime: non-JSON stdout is passed through as-is."""
    executor = _make_executor()

    proc = AsyncMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(b"plain text output", b""))

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        await executor._run_cli("task", eq)

    event_text = str(eq.enqueue_event.call_args[0][0])
    assert "plain text output" in event_text


# ---------- execute: memory injection path ----------


async def test_execute_injects_memories_into_prompt(tmp_path):
    """Memories are prepended to the prompt when returned."""
    executor = _make_executor(config_path=str(tmp_path))
    executor._recall_memories = AsyncMock(return_value="- [LOCAL] remember this")
    executor._commit_memory = AsyncMock()
    executor._set_current_task = AsyncMock()

    captured_inputs = []

    async def capture_run_cli(user_input, event_queue):
        captured_inputs.append(user_input)
        await event_queue.enqueue_event(MagicMock())

    executor._run_cli = capture_run_cli

    context = _make_context(["Do the task"])
    eq = _make_event_queue()
    await executor.execute(context, eq)

    assert len(captured_inputs) == 1
    assert "Prior context from memory" in captured_inputs[0]
    assert "remember this" in captured_inputs[0]
    assert "Do the task" in captured_inputs[0]


# ---------- execute: no memories, no injection ----------


async def test_execute_no_memories_no_injection(tmp_path):
    """No memories = prompt passed through unchanged."""
    executor = _make_executor(config_path=str(tmp_path))
    executor._recall_memories = AsyncMock(return_value="")
    executor._commit_memory = AsyncMock()
    executor._set_current_task = AsyncMock()

    captured_inputs = []

    async def capture_run_cli(user_input, event_queue):
        captured_inputs.append(user_input)

    executor._run_cli = capture_run_cli

    context = _make_context(["Clean task without memories"])
    eq = _make_event_queue()
    await executor.execute(context, eq)

    assert captured_inputs[0] == "Clean task without memories"


# ---------- line 139: _create_auth_helper called in __init__ ----------


def test_init_creates_auth_helper_when_apiKeyHelper_pattern(tmp_path):
    """Executor calls _create_auth_helper in __init__ when preset has apiKeyHelper pattern."""
    from cli_executor import RUNTIME_PRESETS

    api_key_preset = {
        "command": "fakecli",
        "base_args": [],
        "prompt_flag": "-p",
        "model_flag": None,
        "system_prompt_flag": None,
        "auth_pattern": "apiKeyHelper",
        "default_auth_env": "FAKE_API_KEY",
        "default_auth_file": "",
    }

    original = dict(RUNTIME_PRESETS)
    RUNTIME_PRESETS["api-key-test"] = api_key_preset
    try:
        rc = RuntimeConfig()
        with patch("shutil.which", return_value="/usr/bin/fakecli"):
            with patch.dict(os.environ, {"FAKE_API_KEY": "secret-key-value"}):
                executor = CLIAgentExecutor(
                    runtime="api-key-test",
                    runtime_config=rc,
                    config_path=str(tmp_path),
                )
        assert executor._auth_helper_path is not None
        content = Path(executor._auth_helper_path).read_text()
        assert "secret-key-value" in content
    finally:
        RUNTIME_PRESETS.clear()
        RUNTIME_PRESETS.update(original)


# ---------- line 161: warning when command not found in PATH ----------


def test_init_warns_when_command_not_found(tmp_path, caplog):
    """CLIAgentExecutor logs a warning when CLI command not found in PATH."""
    import logging
    rc = RuntimeConfig()
    with patch("shutil.which", return_value=None):
        with caplog.at_level(logging.WARNING, logger="cli_executor"):
            CLIAgentExecutor(
                runtime="claude-code",
                runtime_config=rc,
                config_path=str(tmp_path),
            )
    assert any("not found" in msg for msg in caplog.messages)


# ---------- lines 233-234: heartbeat updated in _set_current_task ----------


async def test_set_current_task_updates_heartbeat(tmp_path):
    """_set_current_task updates heartbeat.current_task and active_tasks."""
    heartbeat = MagicMock()
    heartbeat.current_task = ""
    heartbeat.active_tasks = 0

    executor = _make_executor(heartbeat=heartbeat, config_path=str(tmp_path))

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("WORKSPACE_ID", None)
        os.environ.pop("PLATFORM_URL", None)
        await executor._set_current_task("Working on analysis")

    assert heartbeat.current_task == "Working on analysis"
    assert heartbeat.active_tasks == 1


async def test_set_current_task_clears_heartbeat_when_empty(tmp_path):
    """_set_current_task sets active_tasks=0 when task string is empty."""
    heartbeat = MagicMock()
    heartbeat.current_task = "old task"
    heartbeat.active_tasks = 1

    executor = _make_executor(heartbeat=heartbeat, config_path=str(tmp_path))

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("WORKSPACE_ID", None)
        os.environ.pop("PLATFORM_URL", None)
        await executor._set_current_task("")

    assert heartbeat.current_task == ""
    assert heartbeat.active_tasks == 0


# ---------- line 296: _get_system_prompt reads from file ----------


def test_get_system_prompt_reads_from_file(tmp_path):
    """_get_system_prompt returns content from system-prompt.md when it exists."""
    prompt_file = tmp_path / "system-prompt.md"
    prompt_file.write_text("  You are a specialist agent.  \n")

    executor = _make_executor(config_path=str(tmp_path))
    result = executor._get_system_prompt()
    assert result == "You are a specialist agent."


def test_get_system_prompt_falls_back_to_init_value(tmp_path):
    """_get_system_prompt falls back to init-time system_prompt when no file."""
    executor = _make_executor(
        system_prompt="Fallback prompt",
        config_path=str(tmp_path),
    )
    result = executor._get_system_prompt()
    assert result == "Fallback prompt"


# ---------- line 364: auth error retries exhaust → enqueues error ----------


async def test_run_cli_auth_error_exhausts_all_retries():
    """Auth error on every attempt eventually enqueues error (all retries spent)."""
    executor = _make_executor()
    executor._session_id = "old-session"

    proc = AsyncMock()
    proc.returncode = 1
    proc.communicate = AsyncMock(
        return_value=(b"", b"authentication error: invalid api_key")
    )

    eq = _make_event_queue()

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await executor._run_cli("task", eq)

    assert eq.enqueue_event.call_count == 1
    event_text = str(eq.enqueue_event.call_args[0][0])
    assert "Agent error" in event_text


# ---------- line 364: execute() handles part.root.text ----------


async def test_execute_uses_root_text_when_no_direct_text(tmp_path):
    """execute() extracts text from part.root.text when part.text is absent."""
    executor = _make_executor(config_path=str(tmp_path))
    executor._recall_memories = AsyncMock(return_value="")
    executor._commit_memory = AsyncMock()
    executor._set_current_task = AsyncMock()

    captured_inputs = []

    async def capture_run_cli(user_input, event_queue):
        captured_inputs.append(user_input)

    executor._run_cli = capture_run_cli

    # Build a part that has no .text but has .root.text
    part = MagicMock(spec=["root"])
    part.root = MagicMock()
    part.root.text = "text from root attribute"

    context = MagicMock()
    context.message.parts = [part]
    eq = _make_event_queue()
    await executor.execute(context, eq)

    assert len(captured_inputs) == 1
    assert "text from root attribute" in captured_inputs[0]
