"""Shell execution tool for the coding agent."""

import asyncio
import os
from langchain_core.tools import tool

WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", "/workspace")
MAX_OUTPUT = 10_000  # characters


@tool
async def run_shell(command: str, timeout: int = 60) -> dict:
    """Execute a shell command in the workspace and return stdout/stderr.

    Args:
        command: The shell command to execute.
        timeout: Maximum seconds to wait (default 60, max 300).
    """
    timeout = min(timeout, 300)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORKSPACE_DIR,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        # Truncate long output
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
        return {
            "command": command,
            "error": f"Command timed out after {timeout}s",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "command": command,
            "error": str(e),
            "exit_code": -1,
        }
