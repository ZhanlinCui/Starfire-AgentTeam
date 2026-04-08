"""CLI-based agent executor for A2A protocol.

Supports any CLI agent that accepts a prompt and outputs a response:
- Claude Code: claude --print --bare -p "..."
- OpenAI Codex: codex --print -p "..."
- Ollama: ollama run <model> "..."
- Custom: any command that reads stdin or accepts -p

The runtime is selected via config.yaml:
  runtime: claude-code | codex | ollama | custom
  runtime_config:
    command: "claude"       # for custom
    args: ["--extra-flag"]  # additional CLI args
    auth_token_env: "CLAUDE_AUTH_TOKEN"
    auth_token_file: ".auth-token"
    timeout: 300
    model: "sonnet"
"""

import asyncio
import atexit
import json
import logging
import os
import shlex
import shutil
import tempfile
from pathlib import Path

import httpx

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from config import RuntimeConfig

logger = logging.getLogger(__name__)


def _brief_summary(text: str, max_len: int = 80) -> str:
    """Extract a brief one-line task summary for the canvas card display."""
    for line in text.split("\n"):
        line = line.strip()
        # Strip markdown headers (# ## ###)
        while line.startswith("#"):
            line = line[1:]
        line = line.strip()
        if not line or line.startswith("```") or line == "---":
            continue
        # Remove markdown bold/italic markers
        line = line.replace("**", "").replace("__", "")
        if len(line) > max_len:
            line = line[:max_len - 3] + "..."
        return line
    return text[:max_len]


# Built-in runtime presets
RUNTIME_PRESETS: dict[str, dict] = {
    "claude-code": {
        "command": "claude",
        # Required for unattended agent operation — workspace tier controls access at the platform level
        "base_args": ["--print", "--dangerously-skip-permissions", "--allowed-tools", "Bash"],
        "prompt_flag": "-p",
        "model_flag": "--model",
        "system_prompt_flag": "--system-prompt",
        "auth_pattern": "env",  # OAuth token via CLAUDE_CODE_OAUTH_TOKEN (--bare disables OAuth)
        "default_auth_env": "CLAUDE_CODE_OAUTH_TOKEN",
        "default_auth_file": ".auth-token",
    },
    "codex": {
        "command": "codex",
        "base_args": ["--print", "--dangerously-skip-permissions"],
        "prompt_flag": "-p",
        "model_flag": "--model",
        "system_prompt_flag": "--system-prompt",
        "auth_pattern": "env",  # uses OPENAI_API_KEY env var
        "default_auth_env": "OPENAI_API_KEY",
        "default_auth_file": "",
    },
    "ollama": {
        "command": "ollama",
        "base_args": ["run"],
        "prompt_flag": None,  # prompt is positional
        "model_flag": None,   # model is positional after "run"
        "system_prompt_flag": "--system",
        "auth_pattern": None,  # no auth needed
        "default_auth_env": "",
        "default_auth_file": "",
    },
}


class CLIAgentExecutor(AgentExecutor):
    """Executes agent tasks by invoking a CLI tool.

    Works with any CLI agent that accepts a prompt and outputs text.
    """

    def __init__(
        self,
        runtime: str,
        runtime_config: RuntimeConfig,
        system_prompt: str | None = None,
        config_path: str = "/configs",
        heartbeat: "HeartbeatLoop | None" = None,
    ):
        self.runtime = runtime
        self.config = runtime_config
        self._session_id: str | None = None  # Claude Code session ID for conversation continuity
        self.system_prompt = system_prompt
        self.config_path = config_path
        self._heartbeat = heartbeat

        # Resolve preset or use custom
        if runtime in RUNTIME_PRESETS:
            self.preset = RUNTIME_PRESETS[runtime]
        elif runtime == "custom":
            self.preset = {
                "command": runtime_config.command,
                "base_args": [],  # args go in config.args, appended at end
                "prompt_flag": "-p",
                "model_flag": None,
                "system_prompt_flag": None,
                "auth_pattern": None,
                "default_auth_env": "",
                "default_auth_file": "",
            }
        else:
            raise ValueError(f"Unknown runtime: {runtime}. Use: {', '.join(RUNTIME_PRESETS.keys())}, custom")

        # Resolve auth token
        self._auth_token = self._resolve_auth_token()
        self._auth_helper_path: str | None = None
        self._temp_files: list[str] = []  # Track temp files for cleanup

        if self._auth_token and self.preset.get("auth_pattern") == "apiKeyHelper":
            self._auth_helper_path = self._create_auth_helper(self._auth_token)

        # Create MCP config once (reuse across invocations)
        self._mcp_config_path: str | None = None
        if self.preset.get("auth_pattern") in ("apiKeyHelper", "env"):
            mcp_config = json.dumps({
                "mcpServers": {
                    "a2a": {"command": "python3", "args": ["/app/a2a_mcp_server.py"]}
                }
            })
            fd, self._mcp_config_path = tempfile.mkstemp(suffix=".json", prefix="a2a-mcp-")
            self._temp_files.append(self._mcp_config_path)  # Track immediately
            os.close(fd)
            with open(self._mcp_config_path, "w") as f:
                f.write(mcp_config)

        # Register cleanup for reliable temp file removal (atexit is more reliable than __del__)
        atexit.register(self._cleanup_temp_files)

        # Verify command exists
        cmd = self.config.command or self.preset["command"]
        if not shutil.which(cmd):
            logger.warning(f"CLI command '{cmd}' not found in PATH")

    def _resolve_auth_token(self) -> str | None:
        """Resolve auth token from env var or file."""
        # 1. Explicit env var from config
        env_name = self.config.auth_token_env or self.preset.get("default_auth_env", "")
        if env_name:
            token = os.environ.get(env_name)
            if token:
                return token

        # 2. Token file from config
        file_name = self.config.auth_token_file or self.preset.get("default_auth_file", "")
        if file_name:
            token_path = Path(self.config_path) / file_name
            if token_path.exists():
                return token_path.read_text().strip()

        return None

    def _create_auth_helper(self, token: str) -> str:
        """Create a shell script that outputs the auth token (for apiKeyHelper pattern)."""
        fd, helper_path = tempfile.mkstemp(suffix=".sh", prefix="agent-auth-")
        self._temp_files.append(helper_path)  # Track immediately before any exception can leak
        os.close(fd)
        with open(helper_path, "w") as f:
            f.write(f"#!/bin/sh\necho {shlex.quote(token)}\n")
        os.chmod(helper_path, 0o700)
        return helper_path

    def _get_a2a_instructions(self) -> str:
        """Generate A2A delegation instructions injected into every system prompt."""
        if self.preset.get("auth_pattern") in ("apiKeyHelper", "env"):
            # MCP-compatible runtime — use MCP tools for delegation
            return """## Inter-Agent Communication
You have MCP tools for communicating with other workspaces:
- list_peers: discover available peer workspaces (name, ID, status, role)
- delegate_task: send a task and WAIT for the response (for quick tasks)
- delegate_task_async: send a task and return immediately with a task_id (for long tasks)
- check_task_status: poll an async task's status and get results when done
- get_workspace_info: get your own workspace info

For quick questions, use delegate_task (synchronous).
For long-running work (building pages, running audits), use delegate_task_async + check_task_status.
Always use list_peers first to discover available workspace IDs.
Access control is enforced — you can only reach siblings and parent/children."""

        # For non-MCP runtimes (ollama, custom), provide CLI instructions
        return """## Inter-Agent Communication
You can delegate tasks to other workspaces using the a2a command:
  python3 /app/a2a_cli.py peers                                  # List available peers
  python3 /app/a2a_cli.py delegate <workspace_id> <task>          # Sync: wait for response
  python3 /app/a2a_cli.py delegate --async <workspace_id> <task>  # Async: return task_id
  python3 /app/a2a_cli.py status <workspace_id> <task_id>         # Check async task
  python3 /app/a2a_cli.py info                                    # Your workspace info

For quick questions, use sync delegate. For long tasks, use --async + status.
Only delegate to peers listed by the peers command (access control enforced)."""

    async def _set_current_task(self, task: str):
        """Update current task on heartbeat and push immediately via platform API."""
        if self._heartbeat:
            self._heartbeat.current_task = task
            self._heartbeat.active_tasks = 1 if task else 0
        # Push immediately via platform API for real-time canvas update
        workspace_id = os.environ.get("WORKSPACE_ID", "")
        platform_url = os.environ.get("PLATFORM_URL", "")
        if workspace_id and platform_url:
            try:
                await self._get_http_client().post(
                    f"{platform_url}/registry/heartbeat",
                    json={
                        "workspace_id": workspace_id,
                        "current_task": task,
                        "active_tasks": 1 if task else 0,
                        "error_rate": 0,
                        "sample_error": "",
                        "uptime_seconds": 0,
                    },
                )
            except Exception:
                pass  # Best-effort

    def _get_http_client(self) -> httpx.AsyncClient:
        """Lazy-init a shared httpx client for platform API calls."""
        if not hasattr(self, "_http_client") or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    async def _recall_memories(self) -> str:
        """Recall recent memories from platform API. Returns formatted string or empty."""
        workspace_id = os.environ.get("WORKSPACE_ID", "")
        platform_url = os.environ.get("PLATFORM_URL", "")
        if not workspace_id or not platform_url:
            return ""
        try:
            resp = await self._get_http_client().get(
                f"{platform_url}/workspaces/{workspace_id}/memories",
            )
            data = resp.json()
            if isinstance(data, list) and data:
                lines = [f"- [{m.get('scope', '?')}] {m.get('content', '')}" for m in data[-10:]]
                return "\n".join(lines)
        except Exception:
            pass
        return ""

    async def _commit_memory(self, content: str):
        """Save a memory to platform API. Best-effort, no error propagation."""
        workspace_id = os.environ.get("WORKSPACE_ID", "")
        platform_url = os.environ.get("PLATFORM_URL", "")
        if not workspace_id or not platform_url or not content:
            return
        try:
            await self._get_http_client().post(
                f"{platform_url}/workspaces/{workspace_id}/memories",
                json={"content": content, "scope": "LOCAL"},
            )
        except Exception:
            pass

    def _get_system_prompt(self) -> str | None:
        """Get system prompt — re-read from file each time (supports hot-reload)."""
        prompt_file = Path(self.config_path) / "system-prompt.md"
        if prompt_file.exists():
            return prompt_file.read_text().strip()
        return self.system_prompt  # fall back to init-time value

    def _build_command(self, message: str) -> list[str]:
        """Build the full CLI command from preset + config + message."""
        cmd = self.config.command or self.preset["command"]
        args = list(self.preset.get("base_args", []))

        # Session continuity — resume previous conversation if we have a session ID
        # Only for claude-code which supports --resume
        if self._session_id and self.runtime == "claude-code":
            args.extend(["--resume", self._session_id])

        # Model
        model = self.config.model or None
        model_flag = self.preset.get("model_flag")
        if model and model_flag:
            args.extend([model_flag, model])
        elif model and self.runtime == "ollama":
            # Ollama: model is positional after "run"
            args.append(model)

        # System prompt — only on first message (resumed sessions already have it)
        if not self._session_id:
            system_prompt = self._get_system_prompt() or ""
            a2a_instructions = self._get_a2a_instructions()
            if a2a_instructions:
                system_prompt = f"{system_prompt}\n\n{a2a_instructions}" if system_prompt else a2a_instructions

            system_flag = self.preset.get("system_prompt_flag")
            if system_prompt and system_flag:
                args.extend([system_flag, system_prompt])

        # Auth (apiKeyHelper pattern for claude-code)
        if self._auth_helper_path and self.preset.get("auth_pattern") == "apiKeyHelper":
            settings = json.dumps({"apiKeyHelper": self._auth_helper_path})
            args.extend(["--settings", settings])

        # A2A MCP server — inject for MCP-compatible runtimes (created once in __init__)
        if self._mcp_config_path:
            args.extend(["--mcp-config", self._mcp_config_path])

        # JSON output for claude-code to capture session ID
        if self.runtime == "claude-code":
            args.extend(["--output-format", "json"])

        # Extra args from config (before prompt so flags are parsed correctly)
        args.extend(self.config.args)

        # Prompt (must be last — some CLIs treat final arg as the prompt)
        prompt_flag = self.preset.get("prompt_flag")
        if prompt_flag:
            args.extend([prompt_flag, message])
        else:
            # Positional prompt (ollama)
            args.append(message)

        return [cmd] + args

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        """Execute a task by invoking the CLI agent."""
        # Extract text from message parts
        parts = context.message.parts
        text_parts = []
        for part in parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
            elif hasattr(part, "root") and hasattr(part.root, "text"):
                text_parts.append(part.root.text)

        user_input = " ".join(text_parts).strip()
        if not user_input:
            await event_queue.enqueue_event(
                new_agent_text_message("Error: message contained no text content.")
            )
            return

        # Show current task on canvas — extract a brief one-line summary
        await self._set_current_task(_brief_summary(user_input))

        logger.info("CLI execute [%s]: %s", self.runtime, user_input[:200])

        # Auto-recall: inject prior memories into the prompt on first message (no session yet)
        if not self._session_id:
            memories = await self._recall_memories()
            if memories:
                user_input = f"[Prior context from memory]\n{memories}\n\n[Current request]\n{user_input}"

        try:
            await self._run_cli(user_input, event_queue)
        finally:
            await self._set_current_task("")
            # Auto-commit: save a brief memory of this interaction
            await self._commit_memory(f"User asked: {user_input[:200]}")

    async def _run_cli(self, user_input: str, event_queue: EventQueue):
        """Run the CLI subprocess and enqueue the result."""
        cmd = self._build_command(user_input)
        timeout = self.config.timeout or None  # None = no timeout (wait until agent finishes)
        max_retries = 3
        base_delay = 5  # seconds

        # Build env — pass through auth env var if using env pattern
        env = dict(os.environ)
        if self._auth_token and self.preset.get("auth_pattern") == "env":
            auth_env = self.config.auth_token_env or self.preset.get("default_auth_env", "")
            if auth_env:
                env[auth_env] = self._auth_token

        for attempt in range(max_retries):
            proc = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                if timeout:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout
                    )
                else:
                    stdout, stderr = await proc.communicate()

                stdout_text = stdout.decode().strip()
                stderr_text = stderr.decode().strip()

                if proc.returncode != 0:
                    logger.error("CLI agent [%s] exit=%d stdout=%s stderr=%s",
                                 self.runtime, proc.returncode,
                                 stdout_text[:200] if stdout_text else "(empty)",
                                 stderr_text[:500] if stderr_text else "(empty)")

                # Parse JSON output from claude-code to extract session_id and result text
                if self.runtime == "claude-code" and stdout_text:
                    try:
                        out = json.loads(stdout_text)
                        if isinstance(out, dict):
                            # Capture session ID for conversation continuity
                            sid = out.get("session_id")
                            if sid:
                                self._session_id = sid
                            # Extract the text result
                            stdout_text = out.get("result", "") or ""
                    except json.JSONDecodeError:
                        pass  # Not JSON — use raw output

                if proc.returncode == 0 or stdout_text:
                    # Success, or non-zero exit but produced output (some CLIs exit 1 with valid output)
                    result = stdout_text
                    if result:
                        await event_queue.enqueue_event(
                            new_agent_text_message(result)
                        )
                        return
                    else:
                        # Empty response — likely rate limited, retry with backoff
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning("CLI agent [%s] returned empty (attempt %d/%d), retrying in %ds",
                                           self.runtime, attempt + 1, max_retries, delay)
                            await asyncio.sleep(delay)
                            continue
                        await event_queue.enqueue_event(
                            new_agent_text_message("(no response generated after retries)")
                        )
                        return
                else:
                    error_msg = stderr_text or f"Exit code {proc.returncode}"
                    # Check for rate limit errors
                    if "rate" in error_msg.lower() or "429" in error_msg or "overloaded" in error_msg.lower():
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning("CLI agent [%s] rate limited (attempt %d/%d), retrying in %ds",
                                           self.runtime, attempt + 1, max_retries, delay)
                            await asyncio.sleep(delay)
                            continue
                    logger.error("CLI agent error [%s]: %s", self.runtime, error_msg[:500])
                    await event_queue.enqueue_event(
                        new_agent_text_message(f"Agent error: {error_msg[:500]}")
                    )
                    return

            except asyncio.TimeoutError:
                logger.error("CLI agent timeout [%s] after %ds", self.runtime, timeout)
                if proc:
                    try:
                        proc.kill()
                        await proc.wait()
                    except Exception:
                        pass
                await event_queue.enqueue_event(
                    new_agent_text_message(f"Agent timed out after {timeout}s")
                )
                return
            except Exception as e:
                logger.error("CLI agent exception [%s]: %s", self.runtime, e)
                await event_queue.enqueue_event(
                    new_agent_text_message(f"Agent error: {e}")
                )
                return

    def _cleanup_temp_files(self):
        """Clean up temp files. Called via atexit for reliable cleanup."""
        for f in self._temp_files:
            try:
                os.unlink(f)
            except OSError:
                pass
        if self._auth_helper_path:
            try:
                os.unlink(self._auth_helper_path)
            except OSError:
                pass

    def __del__(self):
        """Clean up temp files (fallback — prefer atexit-registered _cleanup_temp_files)."""
        for f in self._temp_files:
            try:
                os.unlink(f)
            except OSError:
                pass
        if self._auth_helper_path:
            try:
                os.unlink(self._auth_helper_path)
            except OSError:
                pass

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Cancel a running task."""
        pass
