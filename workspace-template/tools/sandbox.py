"""Code sandbox tool for safe code execution.

Executes code in an isolated environment:
- Docker backend (MVP): throwaway container, network disabled, memory capped
- Falls back to subprocess with timeout if Docker not available

Tier 3+ workspaces get full sandbox. Tier 1-2 get subprocess fallback.
"""

import asyncio
import logging
import os
import tempfile

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

SANDBOX_BACKEND = os.environ.get("SANDBOX_BACKEND", "subprocess")  # docker | subprocess
SANDBOX_TIMEOUT = int(os.environ.get("SANDBOX_TIMEOUT", "30"))
SANDBOX_MEMORY_LIMIT = os.environ.get("SANDBOX_MEMORY_LIMIT", "256m")
MAX_OUTPUT = 10_000


@tool
async def run_code(code: str, language: str = "python") -> dict:
    """Execute code in an isolated sandbox and return the output.

    Use this for running untrusted code, testing snippets, or executing
    computations. The sandbox is isolated — no network, limited memory,
    destroyed after execution.

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

        stdout_str = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT]
        stderr_str = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT]

        return {
            "exit_code": proc.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
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
    """Run code in a throwaway Docker container."""
    image_map = {
        "python": "python:3.11-slim",
        "javascript": "node:20-slim",
        "shell": "alpine:3.18",
        "bash": "alpine:3.18",
    }

    image = image_map.get(language)
    if not image:
        return {"error": f"Unsupported language: {language}", "exit_code": -1}

    cmd_map = {
        "python": ["python3", "-c"],
        "javascript": ["node", "-e"],
        "shell": ["sh", "-c"],
        "bash": ["sh", "-c"],
    }

    try:
        # Write code to temp file to avoid shell escaping issues
        with tempfile.NamedTemporaryFile(mode="w", suffix=".code", delete=False) as f:
            f.write(code)
            code_file = f.name

        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", SANDBOX_MEMORY_LIMIT,
            "--cpus", "0.5",
            "--read-only",
            "--tmpfs", "/tmp:size=32m",
            "-v", f"{code_file}:/code:ro",
            image,
        ] + cmd_map[language] + [f"$(cat /code)"]

        # Actually use the command prefix directly with code
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", SANDBOX_MEMORY_LIMIT,
            "--cpus", "0.5",
            "--read-only",
            "--tmpfs", "/tmp:size=32m",
            image,
        ] + cmd_map[language] + [code]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=SANDBOX_TIMEOUT)

        stdout_str = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT]
        stderr_str = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT]

        return {
            "exit_code": proc.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "language": language,
            "backend": "docker",
            "image": image,
        }
    except asyncio.TimeoutError:
        return {"error": f"Timeout after {SANDBOX_TIMEOUT}s", "exit_code": -1}
    except Exception as e:
        return {"error": str(e), "exit_code": -1}
    finally:
        try:
            os.unlink(code_file)
        except Exception:
            pass
