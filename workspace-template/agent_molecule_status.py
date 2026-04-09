#!/usr/bin/env python3
"""Update workspace task status on the canvas.

Usage (from any script, cron job, or shell inside the container):

  # Set current task (shows on canvas card)
  python3 /app/agent_molecule_status.py "Running weekly SEO audit..."

  # Clear task (removes banner from canvas)
  python3 /app/agent_molecule_status.py ""

  # Or use the shell alias:
  agent-molecule-status "Analyzing competitor data..."
  agent-molecule-status ""

The status appears as an amber banner on the workspace card in the canvas,
visible to the project owner in real-time.
"""

import os
import sys

import httpx

WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")
PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")


def set_status(task: str):
    """Push current_task to platform via heartbeat."""
    try:
        httpx.post(
            f"{PLATFORM_URL}/registry/heartbeat",
            json={
                "workspace_id": WORKSPACE_ID,
                "current_task": task,
                "active_tasks": 1 if task else 0,
                "error_rate": 0,
                "sample_error": "",
                "uptime_seconds": 0,
            },
            timeout=5.0,
        )
        if task:
            # Also log as activity for traceability
            httpx.post(
                f"{PLATFORM_URL}/workspaces/{WORKSPACE_ID}/activity",
                json={
                    "activity_type": "task_update",
                    "source_id": WORKSPACE_ID,
                    "summary": task,
                    "status": "ok",
                },
                timeout=5.0,
            )
    except Exception as e:
        print(f"agent-molecule-status: failed to update: {e}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) < 2:
        print("Usage: agent-molecule-status 'task description'")
        print("       agent-molecule-status ''  # clear")
        sys.exit(1)

    set_status(sys.argv[1])
