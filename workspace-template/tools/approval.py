"""Approval tool for human-in-the-loop workflows.

When an agent encounters a destructive, expensive, or unauthorized action,
it calls request_approval() which pauses execution until a human approves
or denies the request via the canvas UI.
"""

import asyncio
import os

import httpx
from langchain_core.tools import tool

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")
APPROVAL_POLL_INTERVAL = 5.0  # seconds
APPROVAL_TIMEOUT = 300.0  # 5 minutes max wait


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
        action: Short description of what you want to do (e.g., "delete production database")
        reason: Why this action is necessary
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Create the approval request
        try:
            resp = await client.post(
                f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/approvals",
                json={
                    "action": action,
                    "reason": reason,
                    "context": {
                        "workspace_id": WORKSPACE_ID,
                    },
                },
            )
            if resp.status_code != 201:
                return {
                    "approved": False,
                    "error": f"Failed to create approval request: {resp.status_code}",
                }

            approval_id = resp.json().get("approval_id")
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
                    params={"status": ""},  # get all
                )
                if resp.status_code == 200:
                    for approval in resp.json():
                        if approval.get("id") == approval_id:
                            status = approval.get("status")
                            if status == "approved":
                                return {
                                    "approved": True,
                                    "approval_id": approval_id,
                                    "decided_by": approval.get("decided_by"),
                                }
                            elif status == "denied":
                                return {
                                    "approved": False,
                                    "approval_id": approval_id,
                                    "decided_by": approval.get("decided_by"),
                                    "message": "Request was denied by human operator",
                                }
            except Exception:
                pass  # Network error — keep polling

    return {
        "approved": False,
        "approval_id": approval_id,
        "error": f"Approval timed out after {APPROVAL_TIMEOUT}s",
    }
