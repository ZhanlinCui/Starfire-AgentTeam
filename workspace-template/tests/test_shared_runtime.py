"""Tests for shared runtime helpers used by A2A-backed executors."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from adapters.shared_runtime import (
    append_peer_guidance,
    build_peer_section,
    build_task_text,
    brief_task,
    extract_history,
    extract_message_text,
    format_conversation_history,
    summarize_peer_cards,
    set_current_task,
)


def _make_context(parts=None, metadata=None):
    context = MagicMock()
    context.message.parts = parts or []
    context.metadata = metadata or {}
    return context


def test_extract_message_text_prefers_text_then_root_text():
    part1 = MagicMock()
    part1.text = "Hello"
    part2 = MagicMock(spec=[])
    part2.root = SimpleNamespace(text="World")
    assert extract_message_text(_make_context([part1, part2])) == "Hello World"


def test_extract_message_text_supports_dict_parts():
    parts = [{"text": "Hello"}, {"root": {"text": "World"}}]
    assert extract_message_text(parts) == "Hello World"


def test_extract_history_and_formatting():
    ctx = _make_context(
        metadata={
            "history": [
                {"role": "user", "parts": [{"text": "First"}]},
                {"role": "agent", "parts": [{"text": "Second"}]},
            ]
        }
    )

    history = extract_history(ctx)

    assert history == [("human", "First"), ("ai", "Second")]
    assert format_conversation_history(history) == "User: First\nAgent: Second"
    assert (
        build_task_text("Current request", history)
        == "Conversation so far:\nUser: First\nAgent: Second\n\nCurrent request: Current request"
    )


def test_append_peer_guidance_is_optional():
    assert append_peer_guidance(None, "", default_text="Base", tool_name="delegate") == "Base"
    assert (
        append_peer_guidance("Base", "Peer A", default_text="Base", tool_name="delegate")
        == "Base\n\n## Peers\nPeer A\nUse delegate to communicate with them."
    )


def test_summarize_peer_cards_and_render_section():
    peers = [
        {
            "id": "peer-1",
            "status": "online",
            "agent_card": {
                "name": "Alpha",
                "skills": [{"name": "research"}, {"id": "write"}],
            },
        },
        {"id": "peer-2", "status": "offline", "agent_card": None},
    ]

    assert summarize_peer_cards(peers) == [
        {
            "id": "peer-1",
            "name": "Alpha",
            "status": "online",
            "skills": ["research", "write"],
        }
    ]

    section = build_peer_section(peers)
    assert "## Your Peers" in section
    assert "**Alpha** (id: `peer-1`, status: online)" in section
    assert "Skills: research, write" in section
    assert "delegate_to_workspace" in section


def test_brief_task_truncates_at_sixty_chars():
    assert brief_task("x" * 59) == "x" * 59
    assert brief_task("x" * 60) == "x" * 60
    assert brief_task("x" * 61) == ("x" * 60) + "..."


@pytest.mark.asyncio
async def test_set_current_task_updates_heartbeat():
    heartbeat = SimpleNamespace(current_task="", active_tasks=0)

    await set_current_task(heartbeat, "Working")
    assert heartbeat.current_task == "Working"
    assert heartbeat.active_tasks == 1

    await set_current_task(heartbeat, "")
    assert heartbeat.current_task == ""
    assert heartbeat.active_tasks == 0


@pytest.mark.asyncio
async def test_set_current_task_is_noop_for_none():
    await set_current_task(None, "Working")
