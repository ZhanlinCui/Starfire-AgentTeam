#!/usr/bin/env python3
"""A2A CLI — command-line tools for inter-workspace communication.

Provides A2A delegation as simple shell commands that ANY agent runtime can use
(not just MCP-compatible ones). The workspace runtime injects these as available
commands in the container.

Usage:
  python a2a_cli.py delegate <workspace_id> <task>
  python a2a_cli.py peers
  python a2a_cli.py info

Environment variables (set by the workspace container):
  WORKSPACE_ID  — this workspace's ID
  PLATFORM_URL  — platform API base URL
"""

import asyncio
import json
import os
import sys
import uuid

import httpx

WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")
PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")


async def delegate(target_id: str, task: str):
    """Delegate a task to another workspace."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Discover target
        resp = await client.get(
            f"{PLATFORM_URL}/registry/discover/{target_id}",
            headers={"X-Workspace-ID": WORKSPACE_ID},
        )
        if resp.status_code != 200:
            print(f"Error: cannot reach workspace {target_id} (access denied or offline)", file=sys.stderr)
            sys.exit(1)

        target_url = resp.json().get("url", "")
        if not target_url:
            print(f"Error: workspace {target_id} has no URL", file=sys.stderr)
            sys.exit(1)

    # Send A2A message
    async with httpx.AsyncClient(timeout=120.0) as client:
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
                        "parts": [{"kind": "text", "text": task}],
                    }
                },
            },
        )
        data = resp.json()
        if "result" in data:
            parts = data["result"].get("parts", [])
            print(parts[0].get("text", "(no response)") if parts else "(no response)")
        elif "error" in data:
            print(f"Error: {data['error'].get('message', 'unknown')}", file=sys.stderr)
            sys.exit(1)


async def peers():
    """List available peers."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{PLATFORM_URL}/registry/{WORKSPACE_ID}/peers")
        if resp.status_code != 200:
            print("Error: could not fetch peers", file=sys.stderr)
            sys.exit(1)

        for p in resp.json():
            status = p.get("status", "?")
            role = p.get("role", "")
            print(f"{p['id']}  {p['name']:30s}  {status:10s}  {role}")


async def info():
    """Get this workspace's info."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}")
        if resp.status_code == 200:
            d = resp.json()
            print(f"ID:     {d['id']}")
            print(f"Name:   {d['name']}")
            print(f"Role:   {d.get('role', '')}")
            print(f"Tier:   {d['tier']}")
            print(f"Status: {d['status']}")
            print(f"Parent: {d.get('parent_id', '(root)')}")
        else:
            print("Error: could not fetch workspace info", file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print("Usage: a2a <command> [args]")
        print("Commands:")
        print("  delegate <workspace_id> <task>  — Send a task to a peer")
        print("  peers                           — List available peers")
        print("  info                            — Show this workspace's info")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "delegate":
        if len(sys.argv) < 4:
            print("Usage: a2a delegate <workspace_id> <task>", file=sys.stderr)
            sys.exit(1)
        asyncio.run(delegate(sys.argv[2], " ".join(sys.argv[3:])))
    elif cmd == "peers":
        asyncio.run(peers())
    elif cmd == "info":
        asyncio.run(info())
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
