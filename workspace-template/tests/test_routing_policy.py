"""Tests for coordinator routing policy."""

from policies.routing import build_team_routing_payload, decide_team_route, summarize_children


def test_summarize_children_extracts_skills():
    children = [
        {
            "id": "child-1",
            "name": "Alpha",
            "status": "online",
            "agent_card": {"skills": [{"name": "research"}, {"id": "write"}]},
        }
    ]

    assert summarize_children(children) == [
        {
            "id": "child-1",
            "name": "Alpha",
            "status": "online",
            "skills": ["research", "write"],
        }
    ]


def test_build_team_routing_payload_handles_empty_children():
    payload = build_team_routing_payload([], "Investigate the issue")

    assert payload["success"] is False
    assert "No team members available" in payload["error"]


def test_decide_team_route_prefers_direct_member():
    payload = decide_team_route(
        [{"id": "child-1"}],
        task="Investigate the issue",
        preferred_member_id="child-2",
    )

    assert payload["action"] == "delegate_to_preferred_member"
    assert payload["preferred_member_id"] == "child-2"
