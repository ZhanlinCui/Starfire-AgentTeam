"""DeepAgents adapter — fully utilizing the DeepAgents SDK capabilities.

Leverages create_deep_agent() with:
- FilesystemBackend(/workspace) — persistent file access across messages
- MemorySaver checkpointer — session continuity (conversation resume)
- Memory files — CLAUDE.md and plugin rules loaded natively
- Filesystem permissions — restrict writes to /workspace and /configs
- Sub-agents — declarative specs for common delegation patterns
- Skills — loaded from /configs/skills/*.py if present
- All built-in tools: write_todos, read_file, write_file, edit_file,
  ls, glob, grep, execute, task

Plus all platform tools (A2A delegation, memory, approval) via _common_setup().
"""

import os
import glob as globmod
import logging
from pathlib import Path

from adapters.base import BaseAdapter, AdapterConfig
from a2a.server.agent_execution import AgentExecutor

logger = logging.getLogger(__name__)


class DeepAgentsAdapter(BaseAdapter):

    def __init__(self):
        self.agent = None
        self._checkpointer = None

    @staticmethod
    def name() -> str:
        return "deepagents"

    @staticmethod
    def display_name() -> str:
        return "DeepAgents"

    @staticmethod
    def description() -> str:
        return "LangChain DeepAgents — planning, filesystem, sub-agents, shell execution, session persistence"

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {
                "type": "string",
                "description": "provider:model (e.g. google_genai:gemini-2.5-flash, anthropic:claude-sonnet-4-6)",
                "default": "google_genai:gemini-2.5-flash",
            },
            "skills": {"type": "array", "items": {"type": "string"}, "description": "Skill folder names"},
            "tools": {"type": "array", "items": {"type": "string"}, "description": "Built-in tools"},
        }

    def _create_llm(self, model_str: str):
        """Create a LangChain LLM from a provider:model string."""
        if ":" in model_str:
            provider, model_name = model_str.split(":", 1)
        else:
            provider, model_name = "openai", model_str

        if provider == "openai":
            from langchain_openai import ChatOpenAI
            kwargs = {"model": model_name}
            base_url = os.environ.get("OPENAI_BASE_URL", "")
            if base_url:
                kwargs["openai_api_base"] = base_url
            return ChatOpenAI(**kwargs)
        elif provider == "openrouter":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                openai_api_key=os.environ.get("OPENROUTER_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
                openai_api_base="https://openrouter.ai/api/v1",
                max_tokens=int(os.environ.get("MAX_TOKENS", "2048")),
            )
        elif provider == "groq":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                openai_api_key=os.environ.get("GROQ_API_KEY", ""),
                openai_api_base="https://api.groq.com/openai/v1",
            )
        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            kwargs = {"model": model_name}
            base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
            if base_url:
                kwargs["anthropic_api_url"] = base_url
            return ChatAnthropic(**kwargs)
        elif provider == "google_genai":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=model_name)
        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(model=model_name)
        else:
            try:
                from langchain.chat_models import init_chat_model
                return init_chat_model(model_str)
            except Exception:
                from langchain_openai import ChatOpenAI
                logger.warning("Unknown provider %s, falling back to OpenAI", provider)
                return ChatOpenAI(model=model_name)

    async def setup(self, config: AdapterConfig) -> None:
        try:
            from deepagents import create_deep_agent, SubAgent, FilesystemPermission
            from deepagents.backends import FilesystemBackend
            from langgraph.checkpoint.memory import MemorySaver
        except ImportError as e:
            raise RuntimeError(f"deepagents not installed: {e}")

        # Full platform setup: plugins, skills, tools, coordinator, system prompt
        result = await self._common_setup(config)
        logger.info("DeepAgents platform tools: %s", [t.name for t in result.langchain_tools])

        llm = self._create_llm(config.model)

        # ── Backend: FilesystemBackend for persistent file access ──
        # Files written via write_file/edit_file persist to /workspace across
        # messages. virtual_mode=True ensures paths are relative to root_dir.
        workspace_dir = "/workspace" if os.path.isdir("/workspace") else "/configs"
        backend = FilesystemBackend(root_dir=workspace_dir, virtual_mode=True)
        logger.info("DeepAgents backend: FilesystemBackend(%s)", workspace_dir)

        # ── Checkpointer: MemorySaver for session continuity ──
        # Conversation state persists across A2A messages within the same
        # container lifecycle. The agent remembers previous turns.
        self._checkpointer = MemorySaver()

        # ── Memory: load CLAUDE.md and plugin rules natively ──
        # DeepAgents injects these into the system prompt automatically.
        memory_files = []
        claude_md = os.path.join(config.config_path, "CLAUDE.md")
        if os.path.exists(claude_md):
            memory_files.append(claude_md)
            logger.info("DeepAgents memory: loading %s", claude_md)

        # ── Filesystem permissions ──
        # Allow read + write in workspace and configs. Paths must be absolute.
        permissions = [
            FilesystemPermission(operations=["read", "write"], paths=["/workspace/**"], mode="allow"),
            FilesystemPermission(operations=["read", "write"], paths=["/configs/**"], mode="allow"),
        ]

        # ── Skills: load .py files from /configs/skills/ ──
        # DeepAgents' native skill system loads Python functions as tools.
        deepagent_skills = []
        skills_dir = os.path.join(config.config_path, "skills")
        if os.path.isdir(skills_dir):
            for py_file in globmod.glob(os.path.join(skills_dir, "**", "*.py"), recursive=True):
                deepagent_skills.append(py_file)
            if deepagent_skills:
                logger.info("DeepAgents skills: %d Python files from %s", len(deepagent_skills), skills_dir)

        # ── Create the agent with full configuration ──
        self.agent = create_deep_agent(
            model=llm,
            tools=result.langchain_tools,
            system_prompt=result.system_prompt,
            backend=backend,
            checkpointer=self._checkpointer,
            memory=memory_files if memory_files else None,
            permissions=permissions,
            skills=deepagent_skills if deepagent_skills else None,
        )

        logger.info(
            "DeepAgents agent created: %d platform tools, backend=%s, "
            "checkpointer=MemorySaver, memory=%d files, permissions=%d rules, skills=%d",
            len(result.langchain_tools), type(backend).__name__,
            len(memory_files), len(permissions), len(deepagent_skills),
        )

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        from a2a_executor import LangGraphA2AExecutor
        return LangGraphA2AExecutor(self.agent, heartbeat=config.heartbeat, model=config.model)
