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

import json
import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")


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

    lines = ["## Your Team (sub-workspaces you coordinate)\n"]
    lines.append("You are the team coordinator. Route incoming tasks to the most appropriate team member.\n")

    for child in children:
        name = child.get("name", "Unknown")
        child_id = child.get("id", "")
        status = child.get("status", "unknown")
        role = child.get("role")

        card = child.get("agent_card")
        if isinstance(card, str):
            try:
                card = json.loads(card)
            except json.JSONDecodeError:
                card = None

        skills = []
        if card and isinstance(card, dict):
            for s in card.get("skills", []):
                if isinstance(s, dict):
                    skill_name = s.get("name", s.get("id", ""))
                    skill_desc = s.get("description", "")
                    if skill_name:
                        skills.append(f"{skill_name}: {skill_desc}" if skill_desc else skill_name)

        lines.append(f"- **{name}** (id: `{child_id}`, status: {status})")
        if role:
            lines.append(f"  Role: {role}")
        if skills:
            lines.append(f"  Skills: {', '.join(skills)}")
        lines.append("")

    lines.append("""### Coordination Rules
1. Analyze the incoming task to determine which team member is best suited
2. Use `delegate_to_workspace` to send the task to the chosen member
3. If a task requires multiple members, delegate to each and aggregate results
4. If no member is suitable, handle the task yourself
5. If a member is offline, reassign to another member or handle yourself
6. Always report back the result to the caller
""")

    return "\n".join(lines)


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

    # If a specific member is requested, delegate directly
    if preferred_member_id:
        result = await delegate.ainvoke({
            "workspace_id": preferred_member_id,
            "task": task,
        })
        return result

    # Otherwise, fetch children and let the LLM decide
    children = await get_children()
    if not children:
        return {
            "success": False,
            "error": "No team members available. Handle this task yourself.",
        }

    # Return children info so the LLM can make the routing decision
    members = []
    for child in children:
        card = child.get("agent_card", {})
        if isinstance(card, str):
            try:
                card = json.loads(card)
            except json.JSONDecodeError:
                card = {}

        members.append({
            "id": child.get("id"),
            "name": child.get("name"),
            "status": child.get("status"),
            "skills": [s.get("name", s.get("id", "")) for s in (card.get("skills", []) if isinstance(card, dict) else []) if isinstance(s, dict)],
        })

    return {
        "success": True,
        "action": "choose_member",
        "message": f"You have {len(members)} team members. Choose the best one for this task and call delegate_to_workspace with their ID.",
        "task": task,
        "members": members,
    }
