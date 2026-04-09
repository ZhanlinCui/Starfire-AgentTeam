#!/usr/bin/env python3
"""Claude Code A2A Bridge — native external workspace with instant delivery.

Registers as an external workspace (no Docker container) and receives
A2A messages from agents in real-time. Sends macOS notifications for
instant awareness.

Usage:
  python3 scripts/claude-code-bridge.py          # Start
  python3 scripts/claude-code-bridge.py --stop   # Stop
  python3 scripts/claude-code-bridge.py --inbox  # Show unread messages
  python3 scripts/claude-code-bridge.py --clear  # Clear inbox
"""

import json
import logging
import os
import platform
import signal
import subprocess
import sys
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import threading

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [bridge] %(message)s")
logger = logging.getLogger("claude-bridge")

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://localhost:8080")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "9999"))
BRIDGE_DIR = Path(__file__).parent.parent / ".claude-bridge"
INBOX = BRIDGE_DIR / "inbox.jsonl"
PID_FILE = BRIDGE_DIR / "bridge.pid"
WS_ID_FILE = BRIDGE_DIR / "workspace_id"

BRIDGE_DIR.mkdir(exist_ok=True)


def notify(title: str, body: str):
    """Log the message — Claude Code checks inbox via PreToolUse hook."""
    logger.info(f"📬 {title}: {body[:100]}")


def resolve_workspace_name(workspace_id: str) -> str:
    """Look up workspace name from platform."""
    try:
        resp = httpx.get(f"{PLATFORM_URL}/workspaces/{workspace_id}", timeout=3)
        if resp.status_code == 200:
            return resp.json().get("name", workspace_id[:8])
    except Exception:
        pass
    return workspace_id[:8]


class A2AHandler(BaseHTTPRequestHandler):
    """Handles incoming A2A JSON-RPC requests."""

    def log_message(self, format, *args):
        pass  # Suppress default HTTP logging

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400)
            return

        method = request.get("method", "")
        req_id = request.get("id", str(uuid.uuid4()))

        if method == "message/send":
            params = request.get("params", {})
            message = params.get("message", {})
            parts = message.get("parts", [])
            text = parts[0].get("text", "") if parts else ""
            sender_id = self.headers.get("X-Workspace-ID", "")
            sender_name = resolve_workspace_name(sender_id) if sender_id else "canvas"

            logger.info(f"📨 {sender_name}: {text[:80]}")

            # Write to inbox
            entry = {
                "id": req_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "text": text,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "read": False,
            }
            with open(INBOX, "a") as f:
                f.write(json.dumps(entry) + "\n")

            # macOS notification for instant awareness
            notify(f"Message from {sender_name}", text[:100])

            # Acknowledge
            response_text = f"Received by Claude Code. Will review shortly."
            self._send_a2a_response(req_id, response_text)

        elif method == "agent/card":
            self._send_json(200, {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "name": "Claude Code Advisor",
                    "description": "CEO technical advisor — code review, architecture, debugging",
                    "version": "1.0.0",
                    "skills": ["code-review", "architecture", "debugging", "optimization"],
                },
            })
        else:
            self._send_json(200, {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Unsupported: {method}"},
            })

    def _send_a2a_response(self, req_id, text):
        self._send_json(200, {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "kind": "message",
                "messageId": str(uuid.uuid4()),
                "role": "agent",
                "parts": [{"kind": "text", "text": text}],
            },
        })

    def _send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def register_external_workspace() -> str:
    """Register as a native external workspace (no Docker container)."""
    # Reuse existing workspace if still alive
    if WS_ID_FILE.exists():
        ws_id = WS_ID_FILE.read_text().strip()
        try:
            resp = httpx.get(f"{PLATFORM_URL}/workspaces/{ws_id}", timeout=5)
            if resp.status_code == 200 and resp.json().get("status") not in ("removed",):
                # Update URL in case port changed
                httpx.patch(f"{PLATFORM_URL}/workspaces/{ws_id}",
                    json={"url": f"http://127.0.0.1:{BRIDGE_PORT}"},
                    timeout=5)
                logger.info(f"Reusing workspace {ws_id}")
                return ws_id
        except Exception:
            pass

    # Create new external workspace
    resp = httpx.post(f"{PLATFORM_URL}/workspaces", json={
        "name": "Claude Code Advisor",
        "role": "CEO technical advisor — code review, architecture, debugging, optimization",
        "tier": 3,
        "runtime": "external",
        "external": True,
        "url": f"http://127.0.0.1:{BRIDGE_PORT}",
    }, timeout=10)

    data = resp.json()
    ws_id = data.get("id", "")
    if not ws_id:
        logger.error(f"Failed to create workspace: {data}")
        sys.exit(1)

    WS_ID_FILE.write_text(ws_id)
    logger.info(f"Created external workspace: {ws_id}")

    # Register agent card
    httpx.post(f"{PLATFORM_URL}/registry/register", json={
        "workspace_id": ws_id,
        "agent_card": {
            "name": "Claude Code Advisor",
            "description": "CEO technical advisor — code review, architecture, debugging",
            "url": f"http://127.0.0.1:{BRIDGE_PORT}",
            "version": "1.0.0",
            "skills": ["code-review", "architecture", "debugging"],
            "capabilities": {"streaming": False, "pushNotifications": False},
        },
    }, timeout=10)

    return ws_id


def heartbeat_loop(ws_id: str):
    """Keep the workspace online with periodic heartbeats."""
    start = time.time()
    while True:
        try:
            httpx.post(f"{PLATFORM_URL}/registry/heartbeat", json={
                "workspace_id": ws_id,
                "error_rate": 0, "sample_error": "",
                "uptime_seconds": int(time.time() - start),
                "active_tasks": 0, "current_task": "",
            }, timeout=5)
        except Exception:
            pass
        time.sleep(30)


def show_inbox():
    """Print unread messages."""
    if not INBOX.exists():
        print("No messages.")
        return
    unread = 0
    for line in INBOX.read_text().splitlines():
        try:
            entry = json.loads(line)
            if not entry.get("read"):
                unread += 1
                ts = entry.get("timestamp", "")
                sender = entry.get("sender_name", "unknown")
                text = entry.get("text", "")[:120]
                print(f"  [{ts}] {sender}: {text}")
        except json.JSONDecodeError:
            continue
    if unread == 0:
        print("No unread messages.")
    else:
        print(f"\n{unread} unread message(s)")


def main():
    if "--stop" in sys.argv:
        if PID_FILE.exists():
            try:
                os.kill(int(PID_FILE.read_text().strip()), signal.SIGTERM)
                print("Bridge stopped")
            except ProcessLookupError:
                print("Bridge was not running")
            PID_FILE.unlink(missing_ok=True)
        return

    if "--inbox" in sys.argv:
        show_inbox()
        return

    if "--clear" in sys.argv:
        INBOX.unlink(missing_ok=True)
        print("Inbox cleared")
        return

    PID_FILE.write_text(str(os.getpid()))

    ws_id = register_external_workspace()
    threading.Thread(target=heartbeat_loop, args=(ws_id,), daemon=True).start()

    server = HTTPServer(("0.0.0.0", BRIDGE_PORT), A2AHandler)
    logger.info(f"Bridge listening on :{BRIDGE_PORT}")
    logger.info(f"Workspace: {ws_id} (external)")
    logger.info(f"Agents see me as 'Claude Code Advisor' in list_peers")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
