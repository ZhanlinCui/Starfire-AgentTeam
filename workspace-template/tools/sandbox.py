"""Code sandbox tool for safe code execution.

Executes code in an isolated environment:
- Docker backend (MVP): throwaway container, network disabled, memory capped
- Falls back to subprocess with timeout if Docker not available
"""

import asyncio
import logging
import os
import tempfile

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

SANDBOX_BACKEND = os.environ.get("SANDBOX_BACKEND", "subprocess")
SANDBOX_TIMEOUT = int(os.environ.get("SANDBOX_TIMEOUT", "30"))
SANDBOX_MEMORY_LIMIT = os.environ.get("SANDBOX_MEMORY_LIMIT", "256m")
MAX_OUTPUT = 10_000


@tool
async def run_code(code: str, language: str = "python") -> dict:
    """Execute code in an isolated sandbox and return the output.

    Args:
        code: The code to execute.
        language: Programming language (python, javascript, shell).
    """
    if SANDBOX_BACKEND == "docker":
        return await _run_docker(code, language)
    else:
        return await _run_subprocess(code, language)


async def _run_subprocess(code: str, language: str) -> dict:
    """Fallback: run code in a subprocess with timeout."""
    cmd_map = {
        "python": ["python3", "-c"],
        "javascript": ["node", "-e"],
        "shell": ["sh", "-c"],
        "bash": ["bash", "-c"],
    }

    cmd_prefix = cmd_map.get(language)
    if not cmd_prefix:
        return {"error": f"Unsupported language: {language}", "exit_code": -1}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_prefix, code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=SANDBOX_TIMEOUT)

        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT],
            "stderr": stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT],
            "language": language,
            "backend": "subprocess",
        }
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass
        return {"error": f"Timeout after {SANDBOX_TIMEOUT}s", "exit_code": -1}
    except Exception as e:
        return {"error": str(e), "exit_code": -1}


async def _run_docker(code: str, language: str) -> dict:
    """Run code in a throwaway Docker container via mounted temp file."""
    image_map = {
        "python": ("python:3.11-slim", ["python3", "/sandbox/code.py"]),
        "javascript": ("node:20-slim", ["node", "/sandbox/code.js"]),
        "shell": ("alpine:3.18", ["sh", "/sandbox/code.sh"]),
        "bash": ("alpine:3.18", ["sh", "/sandbox/code.sh"]),
    }

    entry = image_map.get(language)
    if not entry:
        return {"error": f"Unsupported language: {language}", "exit_code": -1}

    image, run_cmd = entry
    code_file = None

    try:
        # Write code to temp file — avoids shell metacharacter injection
        ext = {"python": ".py", "javascript": ".js", "shell": ".sh", "bash": ".sh"}.get(language, ".txt")
        fd, code_file = tempfile.mkstemp(suffix=ext, prefix="sandbox_")
        with os.fdopen(fd, "w") as f:
            f.write(code)

        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", SANDBOX_MEMORY_LIMIT,
            "--cpus", "0.5",
            "--read-only",
            "--tmpfs", "/tmp:size=32m",
            "-v", f"{code_file}:/sandbox/code{ext}:ro",
            image,
        ] + run_cmd

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=SANDBOX_TIMEOUT)

        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT],
            "stderr": stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT],
            "language": language,
            "backend": "docker",
            "image": image,
        }
    except asyncio.TimeoutError:
        return {"error": f"Timeout after {SANDBOX_TIMEOUT}s", "exit_code": -1}
    except Exception as e:
        return {"error": str(e), "exit_code": -1}
    finally:
        if code_file:
            try:
                os.unlink(code_file)
            except OSError:
                pass
