#!/usr/bin/env python3
"""Claude Code A2A Bridge — registers as a workspace and receives messages from agents.

Runs a lightweight HTTP server on port 9999 that accepts A2A JSON-RPC messages.
Incoming messages are written to a queue file for Claude Code to process.
Responses can be sent by writing to a response file.

Usage:
  python3 scripts/claude-code-bridge.py          # Start the bridge
  python3 scripts/claude-code-bridge.py --stop   # Stop the bridge

The bridge:
1. Registers as a workspace named "Claude Code Advisor" with the platform
2. Listens on port 9999 for A2A messages from other workspaces
3. Writes incoming messages to .claude-bridge/inbox.jsonl
4. Reads responses from .claude-bridge/outbox.jsonl
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from pathlib import Path

import httpx
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("claude-bridge")

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://localhost:8080")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "9999"))
BRIDGE_DIR = Path(".claude-bridge")
INBOX = BRIDGE_DIR / "inbox.jsonl"
OUTBOX = BRIDGE_DIR / "outbox.jsonl"
PID_FILE = BRIDGE_DIR / "bridge.pid"
WORKSPACE_ID_FILE = BRIDGE_DIR / "workspace_id"

# Create bridge directory
BRIDGE_DIR.mkdir(exist_ok=True)


class A2AHandler(BaseHTTPRequestHandler):
    """Handles incoming A2A JSON-RPC requests from agents."""

    def log_message(self, format, *args):
        logger.info(f"A2A: {args[0]}")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        method = request.get("method", "")
        req_id = request.get("id", str(uuid.uuid4()))

        if method == "message/send":
            # Extract the message text
            params = request.get("params", {})
            message = params.get("message", {})
            parts = message.get("parts", [])
            text = parts[0].get("text", "") if parts else ""
            sender = self.headers.get("X-Workspace-ID", "unknown")

            logger.info(f"Message from {sender}: {text[:100]}")

            # Write to inbox for Claude Code to process
            entry = {
                "id": req_id,
                "sender": sender,
                "text": text,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "responded": False,
            }
            with open(INBOX, "a") as f:
                f.write(json.dumps(entry) + "\n")

            # Check if there's a pre-written response in the outbox
            response_text = self._check_outbox(req_id)
            if not response_text:
                response_text = (
                    f"Message received. Claude Code will review and respond. "
                    f"(Queue position: {self._inbox_count()})"
                )

            # Return A2A response
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "kind": "message",
                    "messageId": str(uuid.uuid4()),
                    "role": "agent",
                    "parts": [{"kind": "text", "text": response_text}],
                },
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        elif method == "agent/card":
            card = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "name": "Claude Code Advisor",
                    "description": "CEO's technical advisor — code review, architecture, bug fixes",
                    "version": "1.0.0",
                    "skills": ["code-review", "architecture", "debugging", "optimization"],
                    "capabilities": {"streaming": False, "pushNotifications": False},
                },
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(card).encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not supported: {method}"},
            }).encode())

    def _inbox_count(self):
        if not INBOX.exists():
            return 0
        return sum(1 for line in INBOX.read_text().splitlines() if line.strip())

    def _check_outbox(self, req_id):
        if not OUTBOX.exists():
            return None
        lines = OUTBOX.read_text().splitlines()
        for line in lines:
            try:
                entry = json.loads(line)
                if entry.get("id") == req_id:
                    return entry.get("text", "")
            except json.JSONDecodeError:
                continue
        return None


def register_workspace():
    """Register as a workspace in the platform."""
    workspace_id = None
    if WORKSPACE_ID_FILE.exists():
        workspace_id = WORKSPACE_ID_FILE.read_text().strip()
        # Check if it still exists
        try:
            resp = httpx.get(f"{PLATFORM_URL}/workspaces/{workspace_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") != "removed":
                    logger.info(f"Reusing existing workspace: {workspace_id}")
                    return workspace_id
        except Exception:
            pass

    # Create new workspace
    resp = httpx.post(
        f"{PLATFORM_URL}/workspaces",
        json={
            "name": "Claude Code Advisor",
            "role": "CEO technical advisor — code review, architecture, debugging, optimization",
            "tier": 3,
            "runtime": "claude-code",
        },
        timeout=10,
    )
    data = resp.json()
    workspace_id = data.get("id", "")
    if not workspace_id:
        logger.error(f"Failed to create workspace: {data}")
        sys.exit(1)

    WORKSPACE_ID_FILE.write_text(workspace_id)
    logger.info(f"Created workspace: {workspace_id}")

    # Register with our local URL so agents can reach us
    httpx.post(
        f"{PLATFORM_URL}/registry/register",
        json={
            "workspace_id": workspace_id,
            "agent_card": {
                "name": "Claude Code Advisor",
                "description": "CEO technical advisor — code review, architecture, debugging",
                "version": "1.0.0",
                "url": f"http://host.docker.internal:{BRIDGE_PORT}",
                "skills": ["code-review", "architecture", "debugging"],
                "capabilities": {"streaming": False, "pushNotifications": False},
            },
        },
        timeout=10,
    )
    logger.info(f"Registered with platform at http://host.docker.internal:{BRIDGE_PORT}")
    return workspace_id


def start_heartbeat(workspace_id):
    """Send periodic heartbeats to keep the workspace online."""
    def heartbeat_loop():
        while True:
            try:
                httpx.post(
                    f"{PLATFORM_URL}/registry/heartbeat",
                    json={
                        "workspace_id": workspace_id,
                        "error_rate": 0,
                        "sample_error": "",
                        "uptime_seconds": int(time.time() - start_time),
                        "active_tasks": 0,
                        "current_task": "",
                    },
                    timeout=5,
                )
            except Exception:
                pass
            time.sleep(30)

    start_time = time.time()
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()
    return t


def main():
    if "--stop" in sys.argv:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Stopped bridge (PID {pid})")
            except ProcessLookupError:
                logger.info("Bridge was not running")
            PID_FILE.unlink(missing_ok=True)
        return

    # Write PID
    PID_FILE.write_text(str(os.getpid()))

    # Register with platform
    workspace_id = register_workspace()

    # Start heartbeat
    start_heartbeat(workspace_id)

    # Start A2A server
    server = HTTPServer(("0.0.0.0", BRIDGE_PORT), A2AHandler)
    logger.info(f"Claude Code A2A Bridge listening on :{BRIDGE_PORT}")
    logger.info(f"Workspace ID: {workspace_id}")
    logger.info(f"Inbox: {INBOX}")
    logger.info("Agents can now discover and message me via list_peers + delegate_task")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
