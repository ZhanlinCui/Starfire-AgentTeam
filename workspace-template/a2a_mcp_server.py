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

import httpx

logger = logging.getLogger(__name__)

WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")
PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")


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
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                target_url,
                json={
                    "jsonrpc": "2.0",
                    "id": f"delegate-{WORKSPACE_ID[:8]}",
                    "method": "message/send",
                    "params": {
                        "message": {
                            "role": "user",
                            "parts": [{"type": "text", "text": message}],
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
        "description": "Delegate a task to another workspace via A2A protocol. The target must be a peer (sibling or parent/child). Use list_peers to find available targets.",
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

        # Send A2A message
        result = await send_a2a_message(target_url, task)
        return result

    elif name == "list_peers":
        peers = await get_peers()
        if not peers:
            return "No peers available (this workspace may be isolated)"
        lines = []
        for p in peers:
            status = p.get("status", "unknown")
            role = p.get("role", "")
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
            buffer += chunk.decode()

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
