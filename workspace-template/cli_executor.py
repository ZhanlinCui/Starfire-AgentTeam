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
import json
import logging
import os
import shlex
import shutil
import tempfile
from pathlib import Path

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from config import RuntimeConfig

logger = logging.getLogger(__name__)

# Built-in runtime presets
RUNTIME_PRESETS: dict[str, dict] = {
    "claude-code": {
        "command": "claude",
        "base_args": ["--print", "--dangerously-skip-permissions", "--bare"],
        "prompt_flag": "-p",
        "model_flag": "--model",
        "system_prompt_flag": "--system-prompt",
        "auth_pattern": "apiKeyHelper",  # uses --settings '{"apiKeyHelper":"<path>"}'
        "default_auth_env": "CLAUDE_AUTH_TOKEN",
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
    ):
        self.runtime = runtime
        self.config = runtime_config
        self.system_prompt = system_prompt
        self.config_path = config_path

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

        if self._auth_token and self.preset.get("auth_pattern") == "apiKeyHelper":
            self._auth_helper_path = self._create_auth_helper(self._auth_token)

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
        helper_path = os.path.join(tempfile.gettempdir(), "agent-auth-helper.sh")
        with open(helper_path, "w") as f:
            f.write(f"#!/bin/sh\necho {shlex.quote(token)}\n")
        os.chmod(helper_path, 0o700)
        return helper_path

    def _get_a2a_instructions(self) -> str:
        """Generate instructions for A2A delegation based on available peers."""
        # For non-MCP runtimes, inject CLI-based delegation instructions
        # MCP runtimes get the a2a MCP server instead (tools are auto-discovered)
        if self.preset.get("auth_pattern") == "apiKeyHelper":
            # MCP-compatible runtime — delegation available via MCP tools
            return ""

        # For non-MCP runtimes (ollama, custom), provide CLI instructions
        return """## Inter-Agent Communication
You can delegate tasks to other workspaces using the a2a CLI:
  python3 /app/a2a_cli.py peers                          # List available peers
  python3 /app/a2a_cli.py delegate <workspace_id> <task>  # Send task to a peer
  python3 /app/a2a_cli.py info                            # Your workspace info

Only delegate to peers listed by the peers command (access control enforced)."""

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

        # Model
        model = self.config.model or None
        model_flag = self.preset.get("model_flag")
        if model and model_flag:
            args.extend([model_flag, model])
        elif model and self.runtime == "ollama":
            # Ollama: model is positional after "run"
            args.append(model)

        # System prompt — re-read each time for hot-reload
        # Inject A2A delegation instructions into the system prompt
        system_prompt = self._get_system_prompt() or ""
        a2a_instructions = self._get_a2a_instructions()
        if a2a_instructions:
            system_prompt = f"{system_prompt}\n\n{a2a_instructions}" if system_prompt else a2a_instructions

        system_flag = self.preset.get("system_prompt_flag")
        if system_prompt and system_flag:
            args.extend([system_flag, system_prompt])

        # Auth (apiKeyHelper pattern for claude-code)
        auth_settings = {}
        if self._auth_helper_path and self.preset.get("auth_pattern") == "apiKeyHelper":
            auth_settings["apiKeyHelper"] = self._auth_helper_path

        # MCP server for A2A delegation (Claude Code / Codex)
        if self.preset.get("auth_pattern") == "apiKeyHelper":
            # Write MCP config file for this invocation
            mcp_config = {
                "mcpServers": {
                    "a2a": {
                        "command": "python3",
                        "args": ["/app/a2a_mcp_server.py"],
                    }
                }
            }
            mcp_config_path = os.path.join(tempfile.gettempdir(), "a2a-mcp-config.json")
            with open(mcp_config_path, "w") as f:
                json.dump(mcp_config, f)
            args.extend(["--mcp-config", mcp_config_path])

        if auth_settings:
            args.extend(["--settings", json.dumps(auth_settings)])

        # Prompt
        prompt_flag = self.preset.get("prompt_flag")
        if prompt_flag:
            args.extend([prompt_flag, message])
        else:
            # Positional prompt (ollama)
            args.append(message)

        # Extra args from config
        args.extend(self.config.args)

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

        logger.info("CLI execute [%s]: %s", self.runtime, user_input[:200])

        cmd = self._build_command(user_input)
        timeout = self.config.timeout or 300

        try:
            # Build env — pass through auth env var if using env pattern
            env = dict(os.environ)
            if self._auth_token and self.preset.get("auth_pattern") == "env":
                auth_env = self.config.auth_token_env or self.preset.get("default_auth_env", "")
                if auth_env:
                    env[auth_env] = self._auth_token

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            if proc.returncode == 0:
                result = stdout.decode().strip()
                if result:
                    await event_queue.enqueue_event(
                        new_agent_text_message(result)
                    )
                else:
                    await event_queue.enqueue_event(
                        new_agent_text_message("(no response generated)")
                    )
            else:
                error_msg = stderr.decode().strip() or f"Exit code {proc.returncode}"
                logger.error("CLI agent error [%s]: %s", self.runtime, error_msg[:500])
                await event_queue.enqueue_event(
                    new_agent_text_message(f"Agent error: {error_msg[:500]}")
                )

        except asyncio.TimeoutError:
            logger.error("CLI agent timeout [%s] after %ds", self.runtime, timeout)
            await event_queue.enqueue_event(
                new_agent_text_message(f"Agent timed out after {timeout}s")
            )
        except Exception as e:
            logger.error("CLI agent exception [%s]: %s", self.runtime, e)
            await event_queue.enqueue_event(
                new_agent_text_message(f"Agent error: {e}")
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Cancel a running task."""
        pass
