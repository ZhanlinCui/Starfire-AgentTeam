"""Tests for a2a_executor.py — LangGraph-to-A2A bridge."""

from unittest.mock import AsyncMock, MagicMock

import pytest

# conftest.py pre-mocks the a2a SDK modules so this import works
from a2a_executor import LangGraphA2AExecutor


def _make_context(parts, context_id="ctx-test"):
    """Helper to build a mock RequestContext."""
    context = MagicMock()
    context.message.parts = parts
    context.context_id = context_id
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
    assert messages[0] == ("user", "Hello World")


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
    assert messages[0] == ("user", "Root text")


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
