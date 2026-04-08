"""Claude Code adapter — wraps the Claude Code CLI as an agent runtime."""

import os
import logging

from adapters.base import BaseAdapter, AdapterConfig
from a2a.server.agent_execution import AgentExecutor

logger = logging.getLogger(__name__)


class ClaudeCodeAdapter(BaseAdapter):

    @staticmethod
    def name() -> str:
        return "claude-code"

    @staticmethod
    def display_name() -> str:
        return "Claude Code"

    @staticmethod
    def description() -> str:
        return "Claude Code CLI — full agentic coding with hooks, CLAUDE.md, auto-memory, and MCP support"

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {"type": "string", "description": "Claude model (e.g. sonnet, opus, haiku)", "default": "sonnet"},
            "auth_token_file": {"type": "string", "description": "OAuth token file path", "default": ".auth-token"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (0 = no timeout)", "default": 0},
        }

    async def setup(self, config: AdapterConfig) -> None:
        import shutil
        cmd = config.runtime_config.get("command", "claude")
        if not shutil.which(cmd):
            logger.warning(f"Claude Code CLI '{cmd}' not found in PATH")

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        from cli_executor import CLIAgentExecutor

        # Load system prompt if exists
        system_prompt = config.system_prompt
        if not system_prompt:
            prompt_file = os.path.join(config.config_path, "system-prompt.md")
            if os.path.exists(prompt_file):
                with open(prompt_file) as f:
                    system_prompt = f.read()

        from config import RuntimeConfig

        # Convert dict back to RuntimeConfig dataclass if needed
        rc = config.runtime_config
        if isinstance(rc, dict):
            rc = RuntimeConfig(**{k: v for k, v in rc.items() if k in RuntimeConfig.__dataclass_fields__})

        return CLIAgentExecutor(
            runtime="claude-code",
            runtime_config=rc,
            system_prompt=system_prompt,
            config_path=config.config_path,
            heartbeat=config.heartbeat,
        )
