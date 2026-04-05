"""Approval tool for human-in-the-loop workflows.

When an agent encounters a destructive, expensive, or unauthorized action,
it calls request_approval() which creates a request and polls for decision.

The polling approach is simple but blocks the agent. For production, this
should be replaced with a WebSocket notification. The 5-minute timeout
ensures the agent doesn't hang indefinitely.
"""

import asyncio
import os
import logging

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")
APPROVAL_POLL_INTERVAL = float(os.environ.get("APPROVAL_POLL_INTERVAL", "5"))
APPROVAL_TIMEOUT = float(os.environ.get("APPROVAL_TIMEOUT", "300"))


@tool
async def request_approval(
    action: str,
    reason: str,
) -> dict:
    """Request human approval before proceeding with a sensitive action.

    Use this when you're about to do something destructive, expensive,
    or outside your normal authority. The request is sent to the canvas
    where a human can approve or deny it.

    Args:
        action: Short description of what you want to do
        reason: Why this action is necessary
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/approvals",
                json={"action": action, "reason": reason},
            )
            if resp.status_code != 201:
                return {"approved": False, "error": f"Failed to create request: {resp.status_code}"}
            approval_id = resp.json().get("approval_id")
            logger.info("Approval requested: %s (id=%s)", action, approval_id)
        except Exception as e:
            return {"approved": False, "error": f"Failed to request approval: {e}"}

    # Poll for decision
    elapsed = 0.0
    async with httpx.AsyncClient(timeout=10.0) as client:
        while elapsed < APPROVAL_TIMEOUT:
            await asyncio.sleep(APPROVAL_POLL_INTERVAL)
            elapsed += APPROVAL_POLL_INTERVAL

            try:
                resp = await client.get(
                    f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/approvals",
                )
                if resp.status_code == 200:
                    for a in resp.json():
                        if a.get("id") == approval_id:
                            status = a.get("status")
                            if status == "approved":
                                logger.info("Approval granted: %s", approval_id)
                                return {"approved": True, "approval_id": approval_id, "decided_by": a.get("decided_by")}
                            elif status == "denied":
                                logger.info("Approval denied: %s", approval_id)
                                return {"approved": False, "approval_id": approval_id, "decided_by": a.get("decided_by"), "message": "Denied by human"}
            except Exception:
                pass

    return {"approved": False, "approval_id": approval_id, "error": f"Timed out after {APPROVAL_TIMEOUT}s"}
