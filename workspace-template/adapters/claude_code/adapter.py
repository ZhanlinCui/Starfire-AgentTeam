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

    async def inject_plugins(self, config, plugins) -> None:
        """Claude Code: append plugin rules to CLAUDE.md, copy plugin skills to /configs/skills/."""
        import shutil

        if not plugins.rules and not plugins.skill_dirs:
            return

        # Append rules to CLAUDE.md (idempotent — skip if already injected)
        if plugins.rules:
            claude_md = os.path.join(config.config_path, "CLAUDE.md")
            os.makedirs(os.path.dirname(claude_md), exist_ok=True)
            existing = ""
            if os.path.exists(claude_md):
                existing = open(claude_md).read()
            if "# Plugin Rules" not in existing:
                with open(claude_md, "a") as f:
                    f.write("\n\n# Plugin Rules\n")
                    for rule in plugins.rules:
                        f.write(f"\n{rule}\n")
                logger.info("Claude Code: injected %d plugin rules into CLAUDE.md", len(plugins.rules))
            else:
                logger.info("Claude Code: plugin rules already present in CLAUDE.md, skipping")

        # Copy plugin skills into /configs/skills/ for hot-reload
        skills_dst = os.path.join(config.config_path, "skills")
        try:
            os.makedirs(skills_dst, exist_ok=True)
            copied = 0
            for skill_dir in plugins.skill_dirs:
                for skill_name in sorted(os.listdir(skill_dir)):
                    src = os.path.join(skill_dir, skill_name)
                    dst = os.path.join(skills_dst, skill_name)
                    if os.path.isdir(src) and not os.path.exists(dst):
                        shutil.copytree(src, dst)
                        copied += 1
            if copied:
                logger.info("Claude Code: copied %d plugin skills to %s", copied, skills_dst)
        except PermissionError:
            logger.warning("Claude Code: cannot copy plugin skills to %s (permission denied) — skills remain in plugin dir", skills_dst)

    async def setup(self, config: AdapterConfig) -> None:
        import shutil

        # Load and inject plugins before CLI setup
        from plugins import load_plugins
        workspace_plugins_dir = os.path.join(config.config_path, "plugins")
        plugins = load_plugins(
            workspace_plugins_dir=workspace_plugins_dir,
            shared_plugins_dir=os.environ.get("PLUGINS_DIR", "/plugins"),
        )
        await self.inject_plugins(config, plugins)

        cmd = config.runtime_config.get("command") or "claude"
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
