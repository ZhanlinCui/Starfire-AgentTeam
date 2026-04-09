"""Base adapter interface for agent infrastructure providers."""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from a2a.server.agent_execution import AgentExecutor

logger = logging.getLogger(__name__)


@dataclass
class SetupResult:
    """Result from the shared _common_setup() pipeline."""
    system_prompt: str
    loaded_skills: list          # LoadedSkill instances
    langchain_tools: list        # LangChain BaseTool instances
    is_coordinator: bool
    children: list               # child workspace dicts


@dataclass
class AdapterConfig:
    """Standardized config passed to every adapter."""
    model: str                              # e.g. "anthropic:claude-sonnet-4-6" or "openrouter:google/gemini-2.5-flash"
    system_prompt: str | None = None        # Assembled system prompt text
    tools: list[str] = field(default_factory=list)  # Tool names from config.yaml
    runtime_config: dict[str, Any] = field(default_factory=dict)  # Raw runtime_config block
    config_path: str = "/configs"           # Path to configs directory
    workspace_id: str = ""                  # Workspace identifier
    prompt_files: list[str] = field(default_factory=list)  # Ordered prompt file names
    a2a_port: int = 8000                    # Port for A2A server
    heartbeat: Any = None                   # HeartbeatLoop instance


class BaseAdapter(ABC):
    """Interface every agent infrastructure adapter must implement.

    To add a new agent infra:
    1. Create workspace-template/adapters/<your_infra>/
    2. Implement adapter.py with a class extending BaseAdapter
    3. Add requirements.txt with your infra's dependencies
    4. Export as Adapter in __init__.py
    5. Submit a PR
    """

    @staticmethod
    @abstractmethod
    def name() -> str:  # pragma: no cover
        """Return the runtime identifier (e.g. 'langgraph', 'crewai').
        This must match the 'runtime' field in config.yaml."""
        ...

    @staticmethod
    @abstractmethod
    def display_name() -> str:  # pragma: no cover
        """Human-readable name for UI display."""
        ...

    @staticmethod
    @abstractmethod
    def description() -> str:  # pragma: no cover
        """Short description of what this adapter provides."""
        ...

    @staticmethod
    def get_config_schema() -> dict:
        """Return JSON Schema for runtime_config fields this adapter supports.
        Used by the Config tab UI to render the right form fields.
        Override in subclasses for adapter-specific settings."""
        return {}

    async def _common_setup(self, config: AdapterConfig) -> SetupResult:
        """Shared setup pipeline — loads plugins, skills, tools, coordinator, and builds system prompt.

        All adapters can call this to get the full platform feature set.
        Returns a SetupResult with LangChain BaseTool instances that adapters
        convert to their native format if needed.
        """
        from plugins import load_plugins
        from skills.loader import load_skills
        from coordinator import get_children, get_parent_context, build_children_description
        from prompt import build_system_prompt, get_peer_capabilities
        from tools.approval import request_approval
        from tools.delegation import delegate_to_workspace
        from tools.memory import commit_memory, search_memory
        from tools.sandbox import run_code

        platform_url = os.environ.get("PLATFORM_URL", "http://platform:8080")

        # Load plugins
        plugins = load_plugins()
        if plugins.plugin_names:
            logger.info(f"Plugins: {', '.join(plugins.plugin_names)}")

        # Load skills (workspace + plugin skills, deduped)
        loaded_skills = load_skills(config.config_path, config.tools)
        seen_skill_ids = {s.metadata.id for s in loaded_skills}
        for plugin_skills_dir in plugins.skill_dirs:
            plugin_skill_names = [
                d for d in os.listdir(plugin_skills_dir)
                if os.path.isdir(os.path.join(plugin_skills_dir, d))
            ]
            for skill in load_skills(plugin_skills_dir, plugin_skill_names):
                if skill.metadata.id not in seen_skill_ids:
                    loaded_skills.append(skill)
                    seen_skill_ids.add(skill.metadata.id)
        logger.info(f"Loaded {len(loaded_skills)} skills: {[s.metadata.id for s in loaded_skills]}")

        # Assemble tools: 5 core + skill tools
        all_tools = [delegate_to_workspace, request_approval, commit_memory, search_memory, run_code]
        for skill in loaded_skills:
            all_tools.extend(skill.tools)

        # Coordinator mode: detect children and add routing tool
        children = await get_children()
        is_coordinator = len(children) > 0
        if is_coordinator:
            from coordinator import route_task_to_team
            logger.info(f"Coordinator mode: {len(children)} children")
            all_tools.append(route_task_to_team)

        # Parent context (if this is a child workspace)
        parent_context = await get_parent_context()

        # Build system prompt with all context
        peers = await get_peer_capabilities(platform_url, config.workspace_id)
        coordinator_prompt = build_children_description(children) if is_coordinator else ""
        extra_prompts = list(plugins.prompt_fragments)
        if coordinator_prompt:
            extra_prompts.append(coordinator_prompt)

        system_prompt = build_system_prompt(
            config.config_path, config.workspace_id, loaded_skills, peers,
            prompt_files=config.prompt_files,
            plugin_rules=plugins.rules,
            plugin_prompts=extra_prompts,
            parent_context=parent_context,
        )

        return SetupResult(
            system_prompt=system_prompt,
            loaded_skills=loaded_skills,
            langchain_tools=all_tools,
            is_coordinator=is_coordinator,
            children=children,
        )

    @abstractmethod
    async def setup(self, config: AdapterConfig) -> None:
        """One-time setup: validate config, prepare internal state.
        Called after deps are installed but before create_executor().
        Raise RuntimeError if setup fails (missing deps, bad config, etc.)."""
        ...  # pragma: no cover

    @abstractmethod
    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        """Create and return an AgentExecutor ready for A2A integration.
        The returned executor's execute() method will be called by the
        A2A server's DefaultRequestHandler."""
        ...  # pragma: no cover
