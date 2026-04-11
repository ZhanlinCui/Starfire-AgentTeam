"""Tests for claude_sdk_executor.py — Claude Agent SDK based executor.

The claude_agent_sdk module is stubbed session-wide in conftest.py so that
`import claude_agent_sdk` at the top of claude_sdk_executor.py resolves to
a fake module. Tests override individual SDK attributes (notably query())
via patch().
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# claude_agent_sdk is stubbed in conftest.py — import the fake classes from
# the stub so tests can use them by identity with isinstance() checks inside
# the executor.
import claude_agent_sdk as _sdk_stub

_FakeTextBlock = _sdk_stub.TextBlock
_FakeAssistantMessage = _sdk_stub.AssistantMessage
_FakeResultMessage = _sdk_stub.ResultMessage

from claude_sdk_executor import ClaudeSDKExecutor, QueryResult  # noqa: E402


# ---------- Helpers ----------

def _make_context(text_parts):
    parts = []
    for t in text_parts:
        p = MagicMock()
        p.text = t
        # The extract_message_text helper checks for `.root.text` as a fallback;
        # ensure that path doesn't accidentally double-up.
        del p.root
        parts.append(p)
    ctx = MagicMock()
    ctx.message.parts = parts
    return ctx


def _make_event_queue():
    return AsyncMock()


def _make_executor(model="sonnet"):
    return ClaudeSDKExecutor(
        system_prompt="You are a helpful agent.",
        config_path="/configs",
        heartbeat=MagicMock(current_task="", active_tasks=0),
        model=model,
    )


# ---------- Construction ----------


def test_constructor_sets_fields():
    hb = MagicMock()
    e = ClaudeSDKExecutor(
        system_prompt="sys",
        config_path="/cfg",
        heartbeat=hb,
        model="opus",
    )
    assert e.system_prompt == "sys"
    assert e.config_path == "/cfg"
    assert e.heartbeat is hb
    assert e.model == "opus"
    assert e._session_id is None


def test_resolve_cwd_prefers_workspace_when_populated(tmp_path, monkeypatch):
    e = _make_executor()
    with patch("os.path.isdir", return_value=True), \
         patch("os.listdir", return_value=["repo.txt"]):
        assert e._resolve_cwd() == "/workspace"


def test_resolve_cwd_falls_back_to_configs_when_workspace_empty():
    e = _make_executor()
    with patch("os.path.isdir", return_value=True), \
         patch("os.listdir", return_value=[]):
        assert e._resolve_cwd() == "/configs"


def test_build_system_prompt_combines_base_and_a2a():
    e = _make_executor()
    with patch("claude_sdk_executor.get_system_prompt", return_value="BASE"), \
         patch("claude_sdk_executor.get_a2a_instructions", return_value="A2A"):
        prompt = e._build_system_prompt()
    assert prompt is not None
    assert "BASE" in prompt
    assert "A2A" in prompt


# ---------- execute() ----------


@pytest.mark.asyncio
async def test_execute_empty_message_emits_error():
    e = _make_executor()
    ctx = _make_context([""])
    eq = _make_event_queue()
    await e.execute(ctx, eq)
    eq.enqueue_event.assert_called_once()
    msg = eq.enqueue_event.call_args[0][0]
    # new_agent_text_message returns a Message; check it has a text part
    assert "no text content" in str(msg).lower() or "no text" in repr(msg).lower()


@pytest.mark.asyncio
async def test_execute_collects_assistant_text_blocks():
    e = _make_executor()
    ctx = _make_context(["Hello"])
    eq = _make_event_queue()

    async def fake_query(prompt, options):
        assert prompt == "Hello"
        yield _FakeAssistantMessage([_FakeTextBlock("Hi "), _FakeTextBlock("there")])
        yield _FakeResultMessage(session_id="sess-xyz")

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    assert e._session_id == "sess-xyz"
    eq.enqueue_event.assert_called_once()


@pytest.mark.asyncio
async def test_execute_injects_delegation_results():
    e = _make_executor()
    ctx = _make_context(["Original"])
    eq = _make_event_queue()
    captured = {}

    async def fake_query(prompt, options):
        captured["prompt"] = prompt
        yield _FakeAssistantMessage([_FakeTextBlock("done")])
        yield _FakeResultMessage(session_id="s1")

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results",
               return_value="- [ok] sub-task complete"), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    assert "Delegation results" in captured["prompt"]
    assert "Original" in captured["prompt"]


@pytest.mark.asyncio
async def test_execute_injects_memories_on_first_turn():
    e = _make_executor()
    assert e._session_id is None  # first turn
    ctx = _make_context(["Q"])
    eq = _make_event_queue()
    captured = {}

    async def fake_query(prompt, options):
        captured["prompt"] = prompt
        yield _FakeAssistantMessage([_FakeTextBlock("a")])
        yield _FakeResultMessage(session_id="s2")

    with patch("claude_sdk_executor.recall_memories",
               new=AsyncMock(return_value="- [LOCAL] previous fact")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    assert "Prior context from memory" in captured["prompt"]
    assert "previous fact" in captured["prompt"]


@pytest.mark.asyncio
async def test_execute_skips_memory_recall_after_session_established():
    e = _make_executor()
    e._session_id = "already-resumed"  # not first turn
    ctx = _make_context(["Q"])
    eq = _make_event_queue()
    recall_mock = AsyncMock(return_value="- [LOCAL] should not appear")

    async def fake_query(prompt, options):
        # Memory should NOT have been injected
        assert "Prior context" not in prompt
        yield _FakeAssistantMessage([_FakeTextBlock("ok")])
        yield _FakeResultMessage(session_id="already-resumed")

    with patch("claude_sdk_executor.recall_memories", new=recall_mock), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    recall_mock.assert_not_called()


@pytest.mark.asyncio
async def test_execute_passes_options_with_resume_when_session_present():
    e = _make_executor()
    e._session_id = "sess-prev"
    ctx = _make_context(["q"])
    eq = _make_event_queue()
    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield _FakeAssistantMessage([_FakeTextBlock("a")])
        yield _FakeResultMessage(session_id="sess-prev")

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    opts = captured["options"]
    assert opts.kwargs.get("resume") == "sess-prev"
    assert opts.kwargs.get("model") == "sonnet"
    assert opts.kwargs.get("permission_mode") == "bypassPermissions"
    assert "a2a" in opts.kwargs.get("mcp_servers", {})
    # No allowed_tools restriction — bypass permission mode grants full access,
    # matching the old CLI `--dangerously-skip-permissions` behavior.
    assert "allowed_tools" not in opts.kwargs


@pytest.mark.asyncio
async def test_execute_handles_sdk_exception_gracefully():
    """A raised exception becomes a sanitized user message (no raw `e`)."""
    e = _make_executor()
    ctx = _make_context(["q"])
    eq = _make_event_queue()

    class SecretLeak(RuntimeError):
        pass

    async def boom_query(prompt, options):
        if False:
            yield  # pragma: no cover — makes the function an async generator
        raise SecretLeak("token=abc-123-XYZ leaking")

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()) as commit, \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()) as set_task, \
         patch("claude_agent_sdk.query", new=boom_query):
        await e.execute(ctx, eq)

    # Error reported, but sanitized — the exception class is visible,
    # the secret-laden body is not.
    eq.enqueue_event.assert_called_once()
    msg = eq.enqueue_event.call_args[0][0]
    rendered = str(msg)
    assert "SecretLeak" in rendered
    assert "abc-123-XYZ" not in rendered
    assert "workspace logs" in rendered
    # Cleanup still ran
    commit.assert_called_once()
    # set_current_task called twice: once with summary, once with ""
    assert set_task.call_count == 2
    assert set_task.call_args_list[-1].args[1] == ""


@pytest.mark.asyncio
async def test_execute_commits_memory_with_original_input():
    e = _make_executor()
    ctx = _make_context(["Build me a thing"])
    eq = _make_event_queue()

    async def fake_query(prompt, options):
        yield _FakeAssistantMessage([_FakeTextBlock("done")])
        yield _FakeResultMessage(session_id="s")

    commit_mock = AsyncMock()
    with patch("claude_sdk_executor.recall_memories",
               new=AsyncMock(return_value="- [LOCAL] noise")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=commit_mock), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    commit_mock.assert_called_once()
    saved = commit_mock.call_args[0][0]
    # Original user text is in the saved memory, not the prepended memory block
    assert "Build me a thing" in saved
    assert "noise" not in saved


@pytest.mark.asyncio
async def test_execute_prefers_result_message_text_over_assistant_chunks():
    """When ResultMessage.result is set, use it (avoids double-emitting
    pre-tool reasoning + post-tool summary the way concat would)."""
    e = _make_executor()
    ctx = _make_context(["q"])
    eq = _make_event_queue()

    async def fake_query(prompt, options):
        # Pre-tool reasoning
        yield _FakeAssistantMessage([_FakeTextBlock("Let me check...")])
        # Post-tool summary
        yield _FakeAssistantMessage([_FakeTextBlock("FINAL_ANSWER")])
        # Result with the canonical final text
        yield _FakeResultMessage(session_id="s", result="FINAL_ANSWER")

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    msg = eq.enqueue_event.call_args[0][0]
    rendered = str(msg)
    assert "FINAL_ANSWER" in rendered
    # The pre-tool "Let me check..." text must NOT leak through
    assert "Let me check" not in rendered


@pytest.mark.asyncio
async def test_execute_falls_back_to_assistant_chunks_when_result_missing():
    """If ResultMessage has no .result, concatenate AssistantMessage text."""
    e = _make_executor()
    ctx = _make_context(["q"])
    eq = _make_event_queue()

    async def fake_query(prompt, options):
        yield _FakeAssistantMessage([_FakeTextBlock("hello ")])
        yield _FakeAssistantMessage([_FakeTextBlock("world")])
        yield _FakeResultMessage(session_id="s", result=None)

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    msg = eq.enqueue_event.call_args[0][0]
    assert "hello world" in str(msg)


@pytest.mark.asyncio
async def test_execute_emits_placeholder_when_no_text():
    e = _make_executor()
    ctx = _make_context(["q"])
    eq = _make_event_queue()

    async def empty_query(prompt, options):
        # No AssistantMessage at all, just a result
        yield _FakeResultMessage(session_id="s")

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=empty_query):
        await e.execute(ctx, eq)

    eq.enqueue_event.assert_called_once()
    msg = eq.enqueue_event.call_args[0][0]
    assert "no response" in str(msg).lower()


# ---------- Empty-string result vs None (regression: `or` vs `is not None`) ----------


@pytest.mark.asyncio
async def test_execute_empty_string_result_is_respected_over_chunks():
    """If ResultMessage.result is an explicit empty string, honor it —
    do NOT fall back to concatenated assistant chunks (Python `or` bug)."""
    e = _make_executor()
    ctx = _make_context(["q"])
    eq = _make_event_queue()

    async def fake_query(prompt, options):
        yield _FakeAssistantMessage([_FakeTextBlock("chatter that should be suppressed")])
        yield _FakeResultMessage(session_id="s", result="")

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    msg = eq.enqueue_event.call_args[0][0]
    rendered = str(msg)
    assert "chatter" not in rendered
    # Empty response_text → placeholder
    assert "no response" in rendered.lower()


# ---------- Delegation injection does NOT pollute the memory record ----------


@pytest.mark.asyncio
async def test_execute_memory_commit_excludes_delegation_preamble():
    """original_input is captured BEFORE delegation injection so the
    committed memory is the user's real message, not the prepended block."""
    e = _make_executor()
    ctx = _make_context(["Genuine user question"])
    eq = _make_event_queue()

    async def fake_query(prompt, options):
        yield _FakeResultMessage(session_id="s", result="ok")

    commit_mock = AsyncMock()
    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results",
               return_value="- [done] Sub-agent finished the sync query"), \
         patch("claude_sdk_executor.commit_memory", new=commit_mock), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=fake_query):
        await e.execute(ctx, eq)

    saved = commit_mock.call_args[0][0]
    assert "Genuine user question" in saved
    assert "Delegation results" not in saved
    assert "Sub-agent finished" not in saved


# ---------- cancel() ----------


@pytest.mark.asyncio
async def test_cancel_no_active_stream_is_noop():
    e = _make_executor()
    assert e._active_stream is None
    await e.cancel(context=MagicMock(), event_queue=_make_event_queue())
    # Still None, no exception raised
    assert e._active_stream is None


@pytest.mark.asyncio
async def test_cancel_closes_active_stream():
    e = _make_executor()
    stream = MagicMock()
    stream.aclose = AsyncMock()
    e._active_stream = stream
    await e.cancel(context=MagicMock(), event_queue=_make_event_queue())
    stream.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_aclose_exception_is_logged_not_raised():
    e = _make_executor()
    stream = MagicMock()
    stream.aclose = AsyncMock(side_effect=RuntimeError("already closed"))
    e._active_stream = stream
    # Must not raise
    await e.cancel(context=MagicMock(), event_queue=_make_event_queue())


@pytest.mark.asyncio
async def test_cancel_stream_without_aclose_is_noop():
    e = _make_executor()
    # A stream object that does not expose aclose (e.g. synchronous iterator)
    e._active_stream = MagicMock(spec=["__iter__"])
    # Must not raise
    await e.cancel(context=MagicMock(), event_queue=_make_event_queue())


# ---------- _build_system_prompt / _prepare_prompt direct unit tests ----------


def test_build_system_prompt_combines_base_and_a2a_via_fixture():
    """Direct test bypassing the execute() path."""
    e = _make_executor()
    with patch("claude_sdk_executor.get_system_prompt", return_value="BASE"), \
         patch("claude_sdk_executor.get_a2a_instructions", return_value="A2A"):
        out = e._build_system_prompt()
    assert out == "BASE\n\nA2A"


def test_build_system_prompt_base_only():
    e = _make_executor()
    with patch("claude_sdk_executor.get_system_prompt", return_value="BASE"), \
         patch("claude_sdk_executor.get_a2a_instructions", return_value=""):
        assert e._build_system_prompt() == "BASE"


def test_build_system_prompt_a2a_only():
    e = _make_executor()
    with patch("claude_sdk_executor.get_system_prompt", return_value=None), \
         patch("claude_sdk_executor.get_a2a_instructions", return_value="A2A"):
        assert e._build_system_prompt() == "A2A"


def test_prepare_prompt_no_delegation_returns_unchanged():
    e = _make_executor()
    with patch("claude_sdk_executor.read_delegation_results", return_value=""):
        assert e._prepare_prompt("hi") == "hi"


def test_prepare_prompt_with_delegation_prepends_block():
    e = _make_executor()
    with patch("claude_sdk_executor.read_delegation_results",
               return_value="- [ok] something"):
        out = e._prepare_prompt("hi")
    assert "Delegation results" in out
    assert "- [ok] something" in out
    assert out.endswith("hi")


@pytest.mark.asyncio
async def test_inject_memories_if_first_turn_skips_resumed_session():
    e = _make_executor()
    e._session_id = "existing"
    with patch("claude_sdk_executor.recall_memories",
               new=AsyncMock(return_value="- [LOCAL] anything")) as recall:
        out = await e._inject_memories_if_first_turn("hello")
    recall.assert_not_called()
    assert out == "hello"


@pytest.mark.asyncio
async def test_inject_memories_if_first_turn_no_memories():
    e = _make_executor()
    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")):
        out = await e._inject_memories_if_first_turn("hello")
    assert out == "hello"


# ---------- Concurrency: _run_lock serializes turns ----------


@pytest.mark.asyncio
async def test_concurrent_execute_calls_serialize_strictly():
    """Two execute() calls on the same executor must be mutually exclusive.

    Before the lock, `_session_id` and `_active_stream` were mutated without
    coordination and concurrent turns clobbered each other. We verify:

    1. The second turn's query() entry is strictly AFTER the first turn's
       query() exit (timestamp-based, not just "it runs eventually").
    2. Both turns complete and enqueue exactly one response each.
    3. `_active_stream` is None at the end — no dangling reference.
    4. `_session_id` reflects the LAST turn to set it (the one with the
       highest monotonic timestamp at exit).
    """
    e = _make_executor()
    ctx1 = _make_context(["first prompt"])
    ctx2 = _make_context(["second prompt"])
    eq1 = _make_event_queue()
    eq2 = _make_event_queue()

    # Each query() call records {"enter": t0, "exit": t1} keyed by prompt.
    timings: dict[str, dict[str, float]] = {}

    async def timed_query(prompt, options):
        # Capture the user's original message text from the prompt. The
        # executor may prepend delegation/memory sections, so strip to the
        # trailing line.
        key = prompt.strip().split("\n")[-1]
        timings[key] = {"enter": time.monotonic()}
        # Hold the lock long enough that any concurrency violation would
        # show up as entry1_time ≈ entry2_time.
        await asyncio.sleep(0.05)
        timings[key]["exit"] = time.monotonic()
        yield _FakeAssistantMessage([_FakeTextBlock("chunk")])
        yield _FakeResultMessage(
            session_id=f"sess-for-{key}",
            result=f"done-{key}",
        )

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=timed_query):
        # Fire both concurrently — the lock must serialize them.
        await asyncio.gather(
            e.execute(ctx1, eq1),
            e.execute(ctx2, eq2),
        )

    # Each turn produced exactly one response
    eq1.enqueue_event.assert_called_once()
    eq2.enqueue_event.assert_called_once()

    # Both turns recorded timings (so the query() body actually ran for each)
    assert "first prompt" in timings
    assert "second prompt" in timings

    # Whichever turn acquired the lock first must have FULLY EXITED query()
    # before the other turn ENTERED query(). Find the earlier-entry turn and
    # assert ordering.
    first, second = sorted(timings.items(), key=lambda kv: kv[1]["enter"])
    first_key, first_times = first
    second_key, second_times = second
    assert second_times["enter"] >= first_times["exit"], (
        f"Concurrency bug: {second_key} entered query() at "
        f"{second_times['enter']} before {first_key} exited at "
        f"{first_times['exit']}"
    )

    # The stream reference is cleared after each turn
    assert e._active_stream is None

    # The last turn to finish wrote the persisted session_id
    assert e._session_id == f"sess-for-{second_key}"


@pytest.mark.asyncio
async def test_cancel_unwinds_async_generator_with_finally_cleanup():
    """A cancel while a turn is in-flight must close the stream and run
    its cleanup (finally block).

    We use a real async generator with a cancellable `asyncio.Future` as
    the blocking primitive. When cancel() calls `aclose()`, the generator
    receives GeneratorExit and its finally block runs — proving the actual
    cleanup semantics the SDK's query() generator would exhibit.
    """
    e = _make_executor()
    ctx = _make_context(["q"])
    eq = _make_event_queue()

    inside_query = asyncio.Event()
    finally_ran = asyncio.Event()
    blocker: asyncio.Future[None] = asyncio.get_event_loop().create_future()

    async def cancellable_query(prompt, options):
        try:
            yield _FakeAssistantMessage([_FakeTextBlock("starting")])
            inside_query.set()
            await blocker  # cancel() will cancel this future via aclose
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            finally_ran.set()

    with patch("claude_sdk_executor.recall_memories", new=AsyncMock(return_value="")), \
         patch("claude_sdk_executor.read_delegation_results", return_value=""), \
         patch("claude_sdk_executor.commit_memory", new=AsyncMock()), \
         patch("claude_sdk_executor.set_current_task", new=AsyncMock()), \
         patch("claude_agent_sdk.query", new=cancellable_query):
        turn = asyncio.create_task(e.execute(ctx, eq))
        await inside_query.wait()
        # Cancel the future so aclose() can complete without hanging
        blocker.cancel()
        await e.cancel(context=ctx, event_queue=eq)
        await turn

    # The generator's finally block executed — proves cleanup propagated
    assert finally_ran.is_set()
    # The turn still emits a response (partial text or placeholder) and does
    # not leak an active stream reference
    eq.enqueue_event.assert_called_once()
    assert e._active_stream is None
