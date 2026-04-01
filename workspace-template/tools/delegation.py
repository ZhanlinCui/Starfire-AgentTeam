"""Delegation tool for sending tasks to peer workspaces via A2A."""

import asyncio
import os

import httpx
from langchain_core.tools import tool

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")


@tool
async def delegate_to_workspace(
    workspace_id: str,
    task: str,
) -> dict:
    """Delegate a task to a peer workspace via A2A protocol.

    Args:
        workspace_id: The ID of the target workspace to delegate to.
        task: The task description to send to the peer.

    Returns:
        A dict with the result or error information.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Discover the target workspace URL
        try:
            discover_resp = await client.get(
                f"{PLATFORM_URL}/registry/discover/{workspace_id}",
                headers={"X-Workspace-ID": WORKSPACE_ID},
            )
            if discover_resp.status_code == 403:
                return {
                    "success": False,
                    "error": f"Not authorized to communicate with {workspace_id}",
                }
            if discover_resp.status_code == 404:
                return {
                    "success": False,
                    "error": f"Workspace {workspace_id} not found",
                }
            if discover_resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"Discovery failed with status {discover_resp.status_code}",
                }

            target_url = discover_resp.json().get("url")
            if not target_url:
                return {
                    "success": False,
                    "error": f"Workspace {workspace_id} has no URL",
                }
        except Exception as e:
            return {"success": False, "error": f"Discovery error: {e}"}

        # Send A2A message/send
        last_error = None
        for attempt in range(3):
            try:
                a2a_resp = await client.post(
                    f"{target_url}/a2a",
                    json={
                        "jsonrpc": "2.0",
                        "method": "message/send",
                        "id": f"delegation-{workspace_id}-{attempt}",
                        "params": {
                            "message": {
                                "role": "user",
                                "parts": [{"kind": "text", "text": task}],
                                "messageId": f"msg-{workspace_id}-{attempt}",
                            }
                        },
                    },
                )

                if a2a_resp.status_code == 200:
                    result = a2a_resp.json()
                    if "result" in result:
                        task_result = result["result"]
                        # Extract text from artifacts
                        artifacts = task_result.get("artifacts", [])
                        texts = []
                        for artifact in artifacts:
                            for part in artifact.get("parts", []):
                                if part.get("kind") == "text":
                                    texts.append(part["text"])
                        return {
                            "success": True,
                            "response": "\n".join(texts) if texts else str(task_result),
                            "workspace_id": workspace_id,
                        }
                    if "error" in result:
                        last_error = result["error"].get("message", str(result["error"]))
                        break  # Don't retry explicit errors

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = str(e)
                if attempt < 2:
                    await asyncio.sleep(5.0 * (attempt + 1))
                continue

        return {
            "success": False,
            "error": last_error,
            "workspace_id": workspace_id,
            "message": f"Delegation to {workspace_id} failed after 3 attempts.",
        }


