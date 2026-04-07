#!/usr/bin/env python3
"""A2A MCP Server — runs inside each workspace container.

Exposes A2A delegation, peer discovery, and workspace info as MCP tools
so CLI-based runtimes (Claude Code, Codex) can communicate with other workspaces.

Launched automatically by main.py for CLI runtimes. Runs on stdio transport
and is configured as a local MCP server for the claude --print invocation.

Environment variables (set by the workspace container):
  WORKSPACE_ID  — this workspace's ID
  PLATFORM_URL  — platform API base URL (e.g. http://platform:8080)
"""

import asyncio
import json
import logging
import os
import sys
import uuid

import httpx

logger = logging.getLogger(__name__)

WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")
PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")

# Cache workspace ID → name mappings (populated by list_peers calls)
_peer_names: dict[str, str] = {}


async def discover_peer(target_id: str) -> dict | None:
    """Discover a peer workspace's URL via the platform registry."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{PLATFORM_URL}/registry/discover/{target_id}",
                headers={"X-Workspace-ID": WORKSPACE_ID},
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Discovery failed for {target_id}: {e}")
            return None


async def send_a2a_message(target_url: str, message: str) -> str:
    """Send an A2A message/send to a target workspace."""
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            resp = await client.post(
                target_url,
                json={
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "message/send",
                    "params": {
                        "message": {
                            "role": "user",
                            "messageId": str(uuid.uuid4()),
                            "parts": [{"kind": "text", "text": message}],
                        }
                    },
                },
            )
            data = resp.json()
            if "result" in data:
                parts = data["result"].get("parts", [])
                return parts[0].get("text", "") if parts else "(no response)"
            elif "error" in data:
                return f"Error: {data['error'].get('message', 'unknown')}"
            return str(data)
        except Exception as e:
            return f"Error: {e}"


async def get_peers() -> list[dict]:
    """Get this workspace's peers from the platform registry."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{PLATFORM_URL}/registry/{WORKSPACE_ID}/peers")
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception:
            return []


async def get_workspace_info() -> dict:
    """Get this workspace's info from the platform."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}")
            if resp.status_code == 200:
                return resp.json()
            return {"error": "not found"}
        except Exception as e:
            return {"error": str(e)}


# --- MCP Server (JSON-RPC over stdio) ---

TOOLS = [
    {
        "name": "delegate_task",
        "description": "Delegate a task to another workspace via A2A protocol and WAIT for the response. Use for quick tasks. The target must be a peer (sibling or parent/child). Use list_peers to find available targets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Target workspace ID (from list_peers)",
                },
                "task": {
                    "type": "string",
                    "description": "The task description to send to the target workspace",
                },
            },
            "required": ["workspace_id", "task"],
        },
    },
    {
        "name": "delegate_task_async",
        "description": "Send a task to another workspace with a short timeout (fire-and-forget). Returns immediately — the target continues processing. Best when you don't need the result right away. Note: check_task_status may not work with all workspace implementations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Target workspace ID (from list_peers)",
                },
                "task": {
                    "type": "string",
                    "description": "The task description to send to the target workspace",
                },
            },
            "required": ["workspace_id", "task"],
        },
    },
    {
        "name": "check_task_status",
        "description": "Check the status of a previously submitted async task via tasks/get. Note: only works if the target workspace's A2A implementation supports task persistence. May return 'not found' for completed tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "The workspace ID the task was sent to",
                },
                "task_id": {
                    "type": "string",
                    "description": "The task_id returned by delegate_task_async",
                },
            },
            "required": ["workspace_id", "task_id"],
        },
    },
    {
        "name": "list_peers",
        "description": "List all workspaces this agent can communicate with (siblings and parent/children). Returns name, ID, status, and role for each peer.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_workspace_info",
        "description": "Get this workspace's own info — ID, name, role, tier, parent, status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


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


async def handle_tool_call(name: str, arguments: dict) -> str:
    """Handle a tool call and return the result as text."""
    if name == "delegate_task":
        target_id = arguments.get("workspace_id", "")
        task = arguments.get("task", "")
        if not target_id or not task:
            return "Error: workspace_id and task are required"

        # Discover the target
        peer = await discover_peer(target_id)
        if not peer:
            return f"Error: workspace {target_id} not found or not accessible (check access control)"

        target_url = peer.get("url", "")
        if not target_url:
            return f"Error: workspace {target_id} has no URL (may be offline)"

        # Report delegation start — include the task text for traceability
        peer_name = peer.get("name") or _peer_names.get(target_id) or target_id[:8]
        _peer_names[target_id] = peer_name  # cache for future use
        # Brief summary for canvas display — just the delegation target
        await report_activity("a2a_send", target_id, f"Delegating to {peer_name}", task_text=task)

        # Send A2A message and log the full round-trip
        result = await send_a2a_message(target_url, task)
        await report_activity(
            "a2a_receive", target_id,
            f"{peer_name} responded ({len(result)} chars)",
            task_text=task, response_text=result,
        )
        return result

    elif name == "delegate_task_async":
        target_id = arguments.get("workspace_id", "")
        task = arguments.get("task", "")
        if not target_id or not task:
            return "Error: workspace_id and task are required"

        peer = await discover_peer(target_id)
        if not peer:
            return f"Error: workspace {target_id} not found or not accessible"

        target_url = peer.get("url", "")
        if not target_url:
            return f"Error: workspace {target_id} has no URL (may be offline)"

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
                    "workspace_id": target_id,
                    "status": "submitted",
                    "note": "Task submitted. Use check_task_status to poll for results.",
                })
            except httpx.TimeoutException:
                return json.dumps({
                    "task_id": task_id,
                    "workspace_id": target_id,
                    "status": "submitted_timeout",
                    "note": "Task sent but confirmation timed out. The target may still be processing. Check status later.",
                })

    elif name == "check_task_status":
        target_id = arguments.get("workspace_id", "")
        task_id = arguments.get("task_id", "")
        if not target_id or not task_id:
            return "Error: workspace_id and task_id are required"

        peer = await discover_peer(target_id)
        if not peer:
            return f"Error: workspace {target_id} not found"

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

    elif name == "list_peers":
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

    elif name == "get_workspace_info":
        info = await get_workspace_info()
        return json.dumps(info, indent=2)

    return f"Unknown tool: {name}"


async def main():
    """Run MCP server on stdio — reads JSON-RPC requests, writes responses."""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())

    async def write_response(response: dict):
        data = json.dumps(response) + "\n"
        writer.write(data.encode())
        await writer.drain()

    buffer = ""
    while True:
        try:
            chunk = await reader.read(65536)
            if not chunk:
                break
            buffer += chunk.decode(errors="replace")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    continue

                req_id = request.get("id")
                method = request.get("method", "")

                if method == "initialize":
                    await write_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {"listChanged": False}},
                            "serverInfo": {"name": "a2a-delegation", "version": "1.0.0"},
                        },
                    })

                elif method == "notifications/initialized":
                    pass  # No response needed

                elif method == "tools/list":
                    await write_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"tools": TOOLS},
                    })

                elif method == "tools/call":
                    params = request.get("params", {})
                    tool_name = params.get("name", "")
                    tool_args = params.get("arguments", {})
                    result_text = await handle_tool_call(tool_name, tool_args)
                    await write_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": result_text}],
                        },
                    })

                else:
                    await write_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    })

        except Exception as e:
            logger.error(f"MCP server error: {e}")
            break


if __name__ == "__main__":
    asyncio.run(main())
