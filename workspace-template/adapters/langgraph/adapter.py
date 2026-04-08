"""LangGraph adapter — Python-based ReAct agent with skills, tools, and plugins."""

import os
import logging

from adapters.base import BaseAdapter, AdapterConfig
from a2a.server.agent_execution import AgentExecutor

logger = logging.getLogger(__name__)


class LangGraphAdapter(BaseAdapter):

    @staticmethod
    def name() -> str:
        return "langgraph"

    @staticmethod
    def display_name() -> str:
        return "LangGraph"

    @staticmethod
    def description() -> str:
        return "LangGraph ReAct agent — Python-based with skills, tools, plugins, and peer coordination"

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {"type": "string", "description": "LangChain model string (e.g. openrouter:google/gemini-2.5-flash)"},
            "skills": {"type": "array", "items": {"type": "string"}, "description": "Skill folder names to load"},
            "tools": {"type": "array", "items": {"type": "string"}, "description": "Built-in tools (web_search, filesystem, etc.)"},
        }

    def __init__(self):
        self.loaded_skills = []
        self.all_tools = []
        self.system_prompt = None

    async def setup(self, config: AdapterConfig) -> None:
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

        # Load skills
        self.loaded_skills = load_skills(config.config_path, config.tools)
        seen_skill_ids = {s.metadata.id for s in self.loaded_skills}

        for plugin_skills_dir in plugins.skill_dirs:
            plugin_skill_names = [
                d for d in os.listdir(plugin_skills_dir)
                if os.path.isdir(os.path.join(plugin_skills_dir, d))
            ]
            for skill in load_skills(plugin_skills_dir, plugin_skill_names):
                if skill.metadata.id not in seen_skill_ids:
                    self.loaded_skills.append(skill)
                    seen_skill_ids.add(skill.metadata.id)

        logger.info(f"Loaded {len(self.loaded_skills)} skills: {[s.metadata.id for s in self.loaded_skills]}")

        # Gather tools
        self.all_tools = [delegate_to_workspace, request_approval, commit_memory, search_memory, run_code]
        for skill in self.loaded_skills:
            self.all_tools.extend(skill.tools)

        # Coordinator check
        children = await get_children()
        is_coordinator = len(children) > 0
        if is_coordinator:
            from coordinator import route_task_to_team
            logger.info(f"Coordinator mode: {len(children)} children")
            self.all_tools.append(route_task_to_team)

        # Parent context
        parent_context = await get_parent_context()

        # Build system prompt
        peers = await get_peer_capabilities(platform_url, config.workspace_id)
        coordinator_prompt = build_children_description(children) if is_coordinator else ""
        extra_prompts = list(plugins.prompt_fragments)
        if coordinator_prompt:
            extra_prompts.append(coordinator_prompt)

        self.system_prompt = build_system_prompt(
            config.config_path, config.workspace_id, self.loaded_skills, peers,
            prompt_files=config.prompt_files,
            plugin_rules=plugins.rules,
            plugin_prompts=extra_prompts,
            parent_context=parent_context,
        )

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        from agent import create_agent
        from a2a_executor import LangGraphA2AExecutor

        agent = create_agent(config.model, self.all_tools, self.system_prompt)
        return LangGraphA2AExecutor(agent)
