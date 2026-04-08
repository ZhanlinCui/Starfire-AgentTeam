"""Coordinator pattern for team workspaces.

When a workspace is expanded into a team, the parent agent becomes a
coordinator that routes incoming tasks to the appropriate child workspace
based on the task content and children's capabilities.

The coordinator:
1. Fetches its children's Agent Cards (skills, capabilities)
2. Analyzes each incoming task to determine which child is best suited
3. Delegates to the chosen child via the delegation tool
4. Aggregates responses if a task requires multiple children
5. Falls back to handling the task itself if no child is appropriate
"""

import logging
import os

import httpx
from langchain_core.tools import tool
from adapters.shared_runtime import build_peer_section
from policies.routing import build_team_routing_payload

logger = logging.getLogger(__name__)

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")


async def get_parent_context() -> list[dict]:
    """Fetch shared context files from this workspace's parent.

    Returns a list of {"path": str, "content": str} dicts.
    Returns empty list if no parent, parent unreachable, or no shared context.
    """
    parent_id = os.environ.get("PARENT_ID", "")
    if not parent_id:
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{PLATFORM_URL}/workspaces/{parent_id}/shared-context",
                headers={"X-Workspace-ID": WORKSPACE_ID},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning("Failed to fetch parent context: %s", e)
    return []


async def get_children() -> list[dict]:
    """Fetch this workspace's children from the platform."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{PLATFORM_URL}/registry/{WORKSPACE_ID}/peers",
                headers={"X-Workspace-ID": WORKSPACE_ID},
            )
            if resp.status_code == 200:
                peers = resp.json()
                # Filter to only children (parent_id == our ID)
                return [p for p in peers if p.get("parent_id") == WORKSPACE_ID]
    except Exception as e:
        logger.warning("Failed to fetch children: %s", e)
    return []


def build_children_description(children: list[dict]) -> str:
    """Build a description of children's capabilities for the coordinator prompt."""
    if not children:
        return ""

    team_section = build_peer_section(
        children,
        heading="## Your Team (sub-workspaces you coordinate)",
        instruction=(
            "Use the `delegate_to_workspace` tool to send tasks to the chosen member. "
            "Only delegate to members listed above."
        ),
    )

    return "\n".join(
        [
            team_section,
            "",
            "### Coordination Rules",
            "1. Analyze the incoming task to determine which team member is best suited",
            "2. Use `delegate_to_workspace` to send the task to the chosen member",
            "3. If a task requires multiple members, delegate to each and aggregate results",
            "4. If no member is suitable, handle the task yourself",
            "5. If a member is offline, reassign to another member or handle yourself",
            "6. Always report back the result to the caller",
        ]
    )


@tool
async def route_task_to_team(
    task: str,
    preferred_member_id: str = "",
) -> dict:
    """Route a task to the most appropriate team member.

    As the team coordinator, analyze the task and delegate to the best-suited
    child workspace. If preferred_member_id is provided, delegate directly to
    that member.

    Args:
        task: The task description to route.
        preferred_member_id: Optional — directly delegate to this member.
    """
    from tools.delegation import delegate_to_workspace as delegate

    children = await get_children()
    decision = build_team_routing_payload(
        children,
        task=task,
        preferred_member_id=preferred_member_id,
    )

    if decision.get("action") == "delegate_to_preferred_member":
        return await delegate.ainvoke(
            {
                "workspace_id": decision["preferred_member_id"],
                "task": task,
            }
        )

    return decision
