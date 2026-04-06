#!/usr/bin/env python3
"""A2A CLI — command-line tools for inter-workspace communication.

Supports both synchronous and asynchronous delegation:
  a2a delegate <id> <task>        — Send task, wait for response (sync)
  a2a delegate --async <id> <task> — Send task, return task ID immediately
  a2a status <task_id>            — Check task status / get result
  a2a peers                       — List available peers
  a2a info                        — Show this workspace's info

Environment variables:
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


async def discover(target_id: str) -> dict | None:
    """Discover a peer workspace's URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{PLATFORM_URL}/registry/discover/{target_id}",
            headers={"X-Workspace-ID": WORKSPACE_ID},
        )
        if resp.status_code == 200:
            return resp.json()
        return None


async def delegate(target_id: str, task: str, async_mode: bool = False):
    """Delegate a task to another workspace."""
    peer = await discover(target_id)
    if not peer:
        print(f"Error: cannot reach workspace {target_id} (access denied or offline)", file=sys.stderr)
        sys.exit(1)

    target_url = peer.get("url", "")
    if not target_url:
        print(f"Error: workspace {target_id} has no URL", file=sys.stderr)
        sys.exit(1)

    task_id = str(uuid.uuid4())

    if async_mode:
        # Async: send and return immediately, don't wait for response
        # Use a background task that fires and forgets
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Send with a short timeout — just confirm receipt
                resp = await client.post(
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
                # Even if we timeout, the task is queued on the target
                print(json.dumps({
                    "task_id": task_id,
                    "target": target_id,
                    "status": "submitted",
                    "target_url": target_url,
                }))
            except httpx.TimeoutException:
                # Task was sent but we didn't wait for completion
                print(json.dumps({
                    "task_id": task_id,
                    "target": target_id,
                    "status": "submitted_timeout",
                    "note": "Task sent but response timed out. Use 'a2a status' to check later.",
                }))
        return

    # Sync: wait for full response
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
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
        data = resp.json()
        if "result" in data:
            parts = data["result"].get("parts", [])
            print(parts[0].get("text", "(no response)") if parts else "(no response)")
        elif "error" in data:
            print(f"Error: {data['error'].get('message', 'unknown')}", file=sys.stderr)
            sys.exit(1)


async def check_status(target_id: str, task_id: str):
    """Check the status of an async task."""
    peer = await discover(target_id)
    if not peer:
        print(f"Error: cannot reach workspace {target_id}", file=sys.stderr)
        sys.exit(1)

    target_url = peer.get("url", "")
    async with httpx.AsyncClient(timeout=30.0) as client:
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
            task = data["result"]
            status = task.get("status", {}).get("state", "unknown")
            print(f"Status: {status}")
            if status == "completed":
                artifacts = task.get("artifacts", [])
                for a in artifacts:
                    for p in a.get("parts", []):
                        if p.get("text"):
                            print(p["text"])
        elif "error" in data:
            print(f"Error: {data['error'].get('message', 'unknown')}")


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


def main():
    if len(sys.argv) < 2:
        print("Usage: a2a <command> [args]")
        print("Commands:")
        print("  delegate <workspace_id> <task>        — Send task, wait for response")
        print("  delegate --async <workspace_id> <task> — Send task, return immediately")
        print("  status <workspace_id> <task_id>       — Check async task status")
        print("  peers                                 — List available peers")
        print("  info                                  — Show workspace info")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "delegate":
        async_mode = "--async" in sys.argv
        args = [a for a in sys.argv[2:] if a != "--async"]
        if len(args) < 2:
            print("Usage: a2a delegate [--async] <workspace_id> <task>", file=sys.stderr)
            sys.exit(1)
        asyncio.run(delegate(args[0], " ".join(args[1:]), async_mode))
    elif cmd == "status":
        if len(sys.argv) < 4:
            print("Usage: a2a status <workspace_id> <task_id>", file=sys.stderr)
            sys.exit(1)
        asyncio.run(check_status(sys.argv[2], sys.argv[3]))
    elif cmd == "peers":
        asyncio.run(peers())
    elif cmd == "info":
        asyncio.run(info())
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
