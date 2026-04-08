"""HMA memory tools for agents.

Hierarchical Memory Architecture:
- LOCAL: private to this workspace, invisible to others
- TEAM: shared with parent + siblings (same team)
- GLOBAL: readable by all, writable by root workspaces only
"""

import json
import os
from types import SimpleNamespace
from typing import Any

from langchain_core.tools import tool
from tools.awareness_client import build_awareness_client

try:  # pragma: no cover - optional runtime dependency in lightweight test envs
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = SimpleNamespace(AsyncClient=None)

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
            result = await awareness_client.commit(content, scope)
        except Exception as e:
            return {"success": False, "error": str(e)}
    else:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/memories",
                    json={"content": content, "scope": scope},
                )
                if resp.status_code == 201:
                    result = {"success": True, "id": resp.json().get("id"), "scope": scope}
                else:
                    result = {"success": False, "error": resp.json().get("error", resp.text)}
            except Exception as e:
                return {"success": False, "error": str(e)}

    if result.get("success"):
        await _maybe_log_skill_promotion(content, scope, result)

    return result


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


def _parse_promotion_packet(content: str) -> dict[str, Any] | None:
    """Return a structured memory packet when content looks like promotion metadata."""
    text = content.strip()
    if not text.startswith("{"):
        return None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    if not payload.get("promote_to_skill"):
        return None

    return payload


async def _maybe_log_skill_promotion(content: str, scope: str, memory_result: dict) -> None:
    """Best-effort activity log for durable memory entries that should become skills."""
    packet = _parse_promotion_packet(content)
    if packet is None:
        return

    workspace_id = WORKSPACE_ID.strip()
    platform_url = PLATFORM_URL.strip().rstrip("/")
    if not workspace_id or not platform_url:
        return

    repetition_signal = packet.get("repetition_signal")
    summary = (
        packet.get("summary")
        or packet.get("title")
        or packet.get("what changed")
        or "Repeatable workflow promoted to skill candidate"
    )
    metadata: dict[str, Any] = {
        "source": "memory-curation",
        "scope": scope,
        "memory_id": memory_result.get("id"),
        "promote_to_skill": True,
        "repetition_signal": repetition_signal,
        "memory_packet": packet,
    }

    payload = {
        "activity_type": "skill_promotion",
        "method": "memory/skill-promotion",
        "summary": summary,
        "status": "ok",
        "source_id": workspace_id,
        "request_body": packet,
        "metadata": metadata,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{platform_url}/workspaces/{workspace_id}/activity",
                json=payload,
            )
    except Exception:
        # Best-effort observability only. Memory commits must never fail because
        # the promotion log could not be written.
        return
