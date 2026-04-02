"""Shell execution tool for the coding agent."""

import asyncio
import os
import re
from langchain_core.tools import tool

WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", "/workspace")
MAX_OUTPUT = 10_000  # characters

# Commands that would kill the agent process or destroy the container
BLOCKED_PATTERNS = [
    r"\bkill\s+-9\s+1\b",       # kill init/PID 1
    r"\bkill\s+-9\s+\$\$",      # kill self
    r"\brm\s+-rf\s+/\s*$",      # rm -rf /
    r"\brm\s+-rf\s+/\s+",       # rm -rf / (with trailing)
    r"\bmkfs\b",                 # format filesystem
    r"\bdd\s+.*of=/dev/",       # write to raw device
    r":.*\(\)\s*\{.*\|.*\}",   # fork bomb
]


@tool
async def run_shell(command: str, max_seconds: int = 60) -> dict:
    """Execute a shell command in the workspace and return stdout/stderr.

    Args:
        command: The shell command to execute.
        max_seconds: Maximum seconds to wait (default 60, max 300).
    """
    effective_timeout = min(max_seconds, 300)

    # Block dangerous commands
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command):
            return {
                "command": command,
                "error": "Command blocked: potentially destructive operation",
                "exit_code": -1,
            }

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORKSPACE_DIR,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=effective_timeout)

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        truncated = False
        if len(stdout_str) > MAX_OUTPUT:
            stdout_str = stdout_str[:MAX_OUTPUT] + "\n... (truncated)"
            truncated = True
        if len(stderr_str) > MAX_OUTPUT:
            stderr_str = stderr_str[:MAX_OUTPUT] + "\n... (truncated)"
            truncated = True

        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "truncated": truncated,
        }

    except asyncio.TimeoutError:
        # Kill the subprocess on timeout
        try:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass
        return {
            "command": command,
            "error": f"Command timed out after {effective_timeout}s (process killed)",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "command": command,
            "error": str(e),
            "exit_code": -1,
        }
