"""Tests for a2a_executor.py — LangGraph-to-A2A bridge."""

from unittest.mock import AsyncMock, MagicMock

import pytest

# conftest.py pre-mocks the a2a SDK modules so this import works
from a2a_executor import LangGraphA2AExecutor, _extract_history, set_current_task


def _make_context(parts, context_id="ctx-test", metadata=None):
    """Helper to build a mock RequestContext."""
    context = MagicMock()
    context.message.parts = parts
    context.context_id = context_id
    context.metadata = metadata or {}
    return context


def _make_event_queue():
    """Helper to build a mock EventQueue with async enqueue_event."""
    eq = AsyncMock()
    return eq


@pytest.mark.asyncio
async def test_text_extraction_from_parts():
    """Text is extracted from message parts with .text attribute."""
    agent = AsyncMock()
    agent.ainvoke = AsyncMock(return_value={"messages": []})
    executor = LangGraphA2AExecutor(agent)

    part1 = MagicMock()
    part1.text = "Hello"
    part2 = MagicMock()
    part2.text = "World"

    context = _make_context([part1, part2], "ctx-123")
    eq = _make_event_queue()

    await executor.execute(context, eq)

    agent.ainvoke.assert_called_once()
    call_args = agent.ainvoke.call_args
    messages = call_args[0][0]["messages"]
    assert messages[0] == ("human", "Hello World")


@pytest.mark.asyncio
async def test_text_extraction_from_root():
    """Text is extracted from part.root.text when part.text is absent."""
    agent = AsyncMock()
    agent.ainvoke = AsyncMock(return_value={"messages": []})
    executor = LangGraphA2AExecutor(agent)

    part = MagicMock(spec=[])  # no .text attribute
    part.root = MagicMock()
    part.root.text = "Root text"

    context = _make_context([part], "ctx-456")
    eq = _make_event_queue()

    await executor.execute(context, eq)

    agent.ainvoke.assert_called_once()
    messages = agent.ainvoke.call_args[0][0]["messages"]
    assert messages[0] == ("human", "Root text")


@pytest.mark.asyncio
async def test_empty_message_parts():
    """Empty text content sends an error event without calling the agent."""
    agent = AsyncMock()
    executor = LangGraphA2AExecutor(agent)

    part = MagicMock(spec=[])  # no .text, no .root

    context = _make_context([part])
    eq = _make_event_queue()

    await executor.execute(context, eq)

    agent.ainvoke.assert_not_called()
    eq.enqueue_event.assert_called_once()


@pytest.mark.asyncio
async def test_no_content_generated():
    """When agent returns no AI content, sends '(no response generated)'."""
    human_msg = MagicMock()
    human_msg.type = "human"
    human_msg.content = "user said something"

    agent = AsyncMock()
    agent.ainvoke = AsyncMock(return_value={"messages": [human_msg]})
    executor = LangGraphA2AExecutor(agent)

    part = MagicMock()
    part.text = "Do something"

    context = _make_context([part], "ctx-789")
    eq = _make_event_queue()

    await executor.execute(context, eq)

    eq.enqueue_event.assert_called_once()
    # The arg passed to new_agent_text_message (via side_effect passthrough)
    event_arg = eq.enqueue_event.call_args[0][0]
    assert "(no response generated)" in str(event_arg)


@pytest.mark.asyncio
async def test_agent_error_handling():
    """When agent raises an exception, an error event is enqueued."""
    agent = AsyncMock()
    agent.ainvoke = AsyncMock(side_effect=RuntimeError("model crashed"))
    executor = LangGraphA2AExecutor(agent)

    part = MagicMock()
    part.text = "Break things"

    context = _make_context([part], "ctx-err")
    eq = _make_event_queue()

    await executor.execute(context, eq)

    eq.enqueue_event.assert_called_once()
    error_msg = str(eq.enqueue_event.call_args[0][0])
    assert "model crashed" in error_msg


@pytest.mark.asyncio
async def test_ai_message_content_extraction():
    """AI message with string content is extracted correctly."""
    ai_msg = MagicMock()
    ai_msg.type = "ai"
    ai_msg.content = "Here is your answer."

    agent = AsyncMock()
    agent.ainvoke = AsyncMock(return_value={"messages": [ai_msg]})
    executor = LangGraphA2AExecutor(agent)

    part = MagicMock()
    part.text = "Question"

    context = _make_context([part], "ctx-ai")
    eq = _make_event_queue()

    await executor.execute(context, eq)

    eq.enqueue_event.assert_called_once()
    result = eq.enqueue_event.call_args[0][0]
    assert "Here is your answer." in str(result)


@pytest.mark.asyncio
async def test_ai_message_content_blocks():
    """AI message with list content blocks extracts text blocks only."""
    ai_msg = MagicMock()
    ai_msg.type = "ai"
    ai_msg.content = [
        {"type": "text", "text": "First part."},
        {"type": "tool_use", "name": "search"},
        {"type": "text", "text": "Second part."},
    ]

    agent = AsyncMock()
    agent.ainvoke = AsyncMock(return_value={"messages": [ai_msg]})
    executor = LangGraphA2AExecutor(agent)

    part = MagicMock()
    part.text = "Question"

    context = _make_context([part], "ctx-blocks")
    eq = _make_event_queue()

    await executor.execute(context, eq)

    eq.enqueue_event.assert_called_once()
    result = str(eq.enqueue_event.call_args[0][0])
    assert "First part." in result
    assert "Second part." in result


# ---------- _extract_history tests ----------


def test_extract_history_basic():
    """History with user and agent messages is extracted correctly."""
    ctx = _make_context([], metadata={
        "history": [
            {"role": "user", "parts": [{"kind": "text", "text": "Hello"}]},
            {"role": "agent", "parts": [{"kind": "text", "text": "Hi there"}]},
        ]
    })
    result = _extract_history(ctx)
    assert result == [("human", "Hello"), ("ai", "Hi there")]


def test_extract_history_empty_metadata():
    """Empty metadata returns empty list."""
    ctx = _make_context([], metadata={})
    assert _extract_history(ctx) == []


def test_extract_history_no_metadata():
    """None metadata returns empty list."""
    ctx = _make_context([])
    ctx.metadata = None
    assert _extract_history(ctx) == []


def test_extract_history_malformed_entries():
    """Malformed history entries (missing parts, empty text) are skipped."""
    ctx = _make_context([], metadata={
        "history": [
            {"role": "user", "parts": []},  # no text
            {"role": "user", "parts": [{"kind": "text", "text": ""}]},  # empty text
            {"role": "agent", "parts": [{"kind": "text", "text": "Valid"}]},  # valid
            "not a dict",  # malformed
        ]
    })
    result = _extract_history(ctx)
    assert result == [("ai", "Valid")]


def test_extract_history_non_list():
    """Non-list history value returns empty list."""
    ctx = _make_context([], metadata={"history": "not a list"})
    assert _extract_history(ctx) == []


# ---------- History prepend in executor ----------


@pytest.mark.asyncio
async def test_history_prepended_to_messages():
    """Conversation history is prepended before the current user message."""
    ai_msg = MagicMock()
    ai_msg.type = "ai"
    ai_msg.content = "Response"

    agent = AsyncMock()
    agent.ainvoke = AsyncMock(return_value={"messages": [ai_msg]})
    executor = LangGraphA2AExecutor(agent)

    part = MagicMock()
    part.text = "Follow up"

    ctx = _make_context([part], "ctx-hist", metadata={
        "history": [
            {"role": "user", "parts": [{"kind": "text", "text": "First question"}]},
            {"role": "agent", "parts": [{"kind": "text", "text": "First answer"}]},
        ]
    })
    eq = _make_event_queue()

    await executor.execute(ctx, eq)

    messages = agent.ainvoke.call_args[0][0]["messages"]
    assert len(messages) == 3
    assert messages[0] == ("human", "First question")
    assert messages[1] == ("ai", "First answer")
    assert messages[2] == ("human", "Follow up")


# ---------- set_current_task tests ----------


@pytest.mark.asyncio
async def test_set_current_task_updates_heartbeat():
    """set_current_task updates heartbeat fields."""
    heartbeat = MagicMock()
    await set_current_task(heartbeat, "Doing work")
    assert heartbeat.current_task == "Doing work"
    assert heartbeat.active_tasks == 1

    await set_current_task(heartbeat, "")
    assert heartbeat.current_task == ""
    assert heartbeat.active_tasks == 0


@pytest.mark.asyncio
async def test_set_current_task_none_heartbeat():
    """set_current_task is a no-op with None heartbeat."""
    await set_current_task(None, "Doing work")  # Should not raise
