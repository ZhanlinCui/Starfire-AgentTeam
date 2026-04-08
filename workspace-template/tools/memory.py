"""HMA memory tools for agents.

Hierarchical Memory Architecture:
- LOCAL: private to this workspace, invisible to others
- TEAM: shared with parent + siblings (same team)
- GLOBAL: readable by all, writable by root workspaces only
"""

import os

import httpx
from langchain_core.tools import tool
from tools.awareness_client import build_awareness_client

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")


@tool
async def commit_memory(content: str, scope: str = "LOCAL") -> dict:
    """Store a fact in memory with a specific scope.

    Args:
        content: The fact or knowledge to remember.
        scope: Memory scope — LOCAL (private), TEAM (shared with team), or GLOBAL (company-wide, root only).
    """
    scope = scope.upper()
    if scope not in ("LOCAL", "TEAM", "GLOBAL"):
        return {"error": "scope must be LOCAL, TEAM, or GLOBAL"}

    awareness_client = build_awareness_client()
    if awareness_client is not None:
        try:
            return await awareness_client.commit(content, scope)
        except Exception as e:
            return {"success": False, "error": str(e)}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/memories",
                json={"content": content, "scope": scope},
            )
            if resp.status_code == 201:
                return {"success": True, "id": resp.json().get("id"), "scope": scope}
            return {"success": False, "error": resp.json().get("error", resp.text)}
        except Exception as e:
            return {"success": False, "error": str(e)}


@tool
async def search_memory(query: str = "", scope: str = "") -> dict:
    """Search stored memories.

    Args:
        query: Text to search for (empty returns all).
        scope: Filter by scope — LOCAL, TEAM, GLOBAL, or empty for all accessible.
    """
    scope = scope.upper()
    if scope and scope not in ("LOCAL", "TEAM", "GLOBAL"):
        return {"error": "scope must be LOCAL, TEAM, GLOBAL, or empty"}

    awareness_client = build_awareness_client()
    if awareness_client is not None:
        try:
            return await awareness_client.search(query, scope)
        except Exception as e:
            return {"success": False, "error": str(e)}

    params = {}
    if query:
        params["q"] = query
    if scope:
        params["scope"] = scope.upper()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/memories",
                params=params,
            )
            if resp.status_code == 200:
                memories = resp.json()
                return {
                    "success": True,
                    "count": len(memories),
                    "memories": memories,
                }
            return {"success": False, "error": resp.json().get("error", resp.text)}
        except Exception as e:
            return {"success": False, "error": str(e)}
