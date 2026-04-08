"""A2A MCP tool implementations — the body of each tool handler.

Imports shared client functions and constants from a2a_client.
"""

import json
import uuid

import httpx

from a2a_client import (
    PLATFORM_URL,
    WORKSPACE_ID,
    _A2A_ERROR_PREFIX,
    _peer_names,
    discover_peer,
    get_peers,
    get_workspace_info,
    send_a2a_message,
)


async def report_activity(
    activity_type: str, target_id: str = "", summary: str = "", status: str = "ok",
    task_text: str = "", response_text: str = "",
):
    """Report activity to the platform for live progress tracking."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            payload: dict = {
                "activity_type": activity_type,
                "source_id": WORKSPACE_ID,
                "target_id": target_id,
                "method": "message/send",
                "summary": summary,
                "status": status,
            }
            if task_text:
                payload["request_body"] = {"task": task_text}
            if response_text:
                payload["response_body"] = {"result": response_text}
            await client.post(
                f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/activity",
                json=payload,
            )
            # Also push current_task via heartbeat for canvas card display
            if summary:
                await client.post(
                    f"{PLATFORM_URL}/registry/heartbeat",
                    json={
                        "workspace_id": WORKSPACE_ID,
                        "current_task": summary,
                        "active_tasks": 1,
                        "error_rate": 0,
                        "sample_error": "",
                        "uptime_seconds": 0,
                    },
                )
    except Exception:
        pass  # Best-effort — don't block delegation on activity reporting


async def tool_delegate_task(workspace_id: str, task: str) -> str:
    """Delegate a task to another workspace via A2A (synchronous — waits for response)."""
    if not workspace_id or not task:
        return "Error: workspace_id and task are required"

    # Discover the target
    peer = await discover_peer(workspace_id)
    if not peer:
        return f"Error: workspace {workspace_id} not found or not accessible (check access control)"

    target_url = peer.get("url", "")
    if not target_url:
        return f"Error: workspace {workspace_id} has no URL (may be offline)"

    # Report delegation start — include the task text for traceability
    peer_name = peer.get("name") or _peer_names.get(workspace_id) or workspace_id[:8]
    _peer_names[workspace_id] = peer_name  # cache for future use
    # Brief summary for canvas display — just the delegation target
    await report_activity("a2a_send", workspace_id, f"Delegating to {peer_name}", task_text=task)

    # Send A2A message and log the full round-trip
    result = await send_a2a_message(target_url, task)

    # Detect delegation failures — wrap them clearly so the calling agent
    # can decide to retry, use another peer, or handle the task itself.
    is_error = result.startswith(_A2A_ERROR_PREFIX)
    await report_activity(
        "a2a_receive", workspace_id,
        f"{peer_name} responded ({len(result)} chars)" if not is_error else f"{peer_name} failed",
        task_text=task, response_text=result,
        status="error" if is_error else "ok",
    )
    if is_error:
        return (
            f"DELEGATION FAILED to {peer_name}: {result}\n"
            f"You should either: (1) try a different peer, (2) handle this task yourself, "
            f"or (3) inform the user that {peer_name} is unavailable and provide your best answer."
        )
    return result


async def tool_delegate_task_async(workspace_id: str, task: str) -> str:
    """Send a task to another workspace with a short timeout (fire-and-forget)."""
    if not workspace_id or not task:
        return "Error: workspace_id and task are required"

    peer = await discover_peer(workspace_id)
    if not peer:
        return f"Error: workspace {workspace_id} not found or not accessible"

    target_url = peer.get("url", "")
    if not target_url:
        return f"Error: workspace {workspace_id} has no URL (may be offline)"

    # Send with short timeout — just confirm receipt
    task_id = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                target_url,
                json={
                    "jsonrpc": "2.0",
                    "id": task_id,
                    "method": "message/send",
                    "params": {
                        "message": {
                            "role": "user",
                            "messageId": str(uuid.uuid4()),
                            "parts": [{"kind": "text", "text": task}],
                        }
                    },
                },
            )
            return json.dumps({
                "task_id": task_id,
                "workspace_id": workspace_id,
                "status": "submitted",
                "note": "Task submitted. Use check_task_status to poll for results.",
            })
        except httpx.TimeoutException:
            return json.dumps({
                "task_id": task_id,
                "workspace_id": workspace_id,
                "status": "submitted_timeout",
                "note": "Task sent but confirmation timed out. The target may still be processing. Check status later.",
            })


async def tool_check_task_status(workspace_id: str, task_id: str) -> str:
    """Check the status of a previously submitted async task via tasks/get."""
    if not workspace_id or not task_id:
        return "Error: workspace_id and task_id are required"

    peer = await discover_peer(workspace_id)
    if not peer:
        return f"Error: workspace {workspace_id} not found"

    target_url = peer.get("url", "")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                target_url,
                json={
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "tasks/get",
                    "params": {"id": task_id},
                },
            )
            data = resp.json()
            if "result" in data:
                task_data = data["result"]
                status = task_data.get("status", {}).get("state", "unknown")
                result_text = ""
                if status == "completed":
                    for artifact in task_data.get("artifacts", []):
                        for part in artifact.get("parts", []):
                            if part.get("text"):
                                result_text += part["text"] + "\n"
                return json.dumps({
                    "task_id": task_id,
                    "status": status,
                    "result": result_text.strip() if result_text else None,
                })
            elif "error" in data:
                return f"Error: {data['error'].get('message', 'unknown')}"
        except Exception as e:
            return f"Error checking status: {e}"


async def tool_send_message_to_user(message: str) -> str:
    """Send a message directly to the user's canvas chat via WebSocket."""
    if not message:
        return "Error: message is required"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/notify",
                json={"message": message},
            )
            if resp.status_code == 200:
                return "Message sent to user"
            return f"Error: platform returned {resp.status_code}"
    except Exception as e:
        return f"Error sending message: {e}"


async def tool_list_peers() -> str:
    """List all workspaces this agent can communicate with."""
    peers = await get_peers()
    if not peers:
        return "No peers available (this workspace may be isolated)"
    lines = []
    for p in peers:
        status = p.get("status", "unknown")
        role = p.get("role", "")
        # Cache name for use in delegate_task
        _peer_names[p["id"]] = p["name"]
        lines.append(f"- {p['name']} (ID: {p['id']}, status: {status}, role: {role})")
    return "\n".join(lines)


async def tool_get_workspace_info() -> str:
    """Get this workspace's own info."""
    info = await get_workspace_info()
    return json.dumps(info, indent=2)


async def tool_commit_memory(content: str, scope: str = "LOCAL") -> str:
    """Save important information to persistent memory."""
    if not content:
        return "Error: content is required"
    scope = scope.upper()
    if scope not in ("LOCAL", "TEAM", "GLOBAL"):
        scope = "LOCAL"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/memories",
                json={"content": content, "scope": scope},
            )
            data = resp.json()
            if resp.status_code in (200, 201):
                return json.dumps({"success": True, "id": data.get("id"), "scope": scope})
            return f"Error: {data.get('error', resp.text)}"
    except Exception as e:
        return f"Error saving memory: {e}"


async def tool_recall_memory(query: str = "", scope: str = "") -> str:
    """Search persistent memory for previously saved information."""
    params = {}
    if query:
        params["q"] = query
    if scope:
        params["scope"] = scope.upper()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/memories",
                params=params,
            )
            data = resp.json()
            if isinstance(data, list):
                if not data:
                    return "No memories found."
                lines = []
                for m in data:
                    lines.append(f"[{m.get('scope', '?')}] {m.get('content', '')}")
                return "\n".join(lines)
            return json.dumps(data)
    except Exception as e:
        return f"Error recalling memory: {e}"
