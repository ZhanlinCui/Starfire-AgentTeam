"""DeepAgents adapter — LangChain deep research agent with full platform integration.

Uses `deepagents.create_deep_agent()` which provides automatic task planning,
filesystem access, and sub-agent spawning on top of LangGraph.
All platform tools (delegation, memory, sandbox, approval), skills, plugins,
and coordinator support are included via _common_setup().

Requires: pip install deepagents
"""

import os
import logging

from adapters.base import BaseAdapter, AdapterConfig
from a2a.server.agent_execution import AgentExecutor

logger = logging.getLogger(__name__)


class DeepAgentsAdapter(BaseAdapter):

    def __init__(self):
        self.agent = None

    @staticmethod
    def name() -> str:
        return "deepagents"

    @staticmethod
    def display_name() -> str:
        return "DeepAgents"

    @staticmethod
    def description() -> str:
        return "LangChain DeepAgents — deep research with planning, sub-agents, and filesystem access"

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {"type": "string", "description": "LangChain model string (e.g. openai:gpt-4.1-mini)"},
            "skills": {"type": "array", "items": {"type": "string"}, "description": "Skill folder names to load"},
            "tools": {"type": "array", "items": {"type": "string"}, "description": "Built-in tools"},
        }

    def _create_llm(self, model_str: str):
        """Create a LangChain LLM instance from a provider:model string."""
        if ":" in model_str:
            provider, model_name = model_str.split(":", 1)
        else:
            provider, model_name = "openai", model_str

        if provider == "openai":
            from langchain_openai import ChatOpenAI
            llm_kwargs = {"model": model_name}
            base_url = os.environ.get("OPENAI_BASE_URL", "")
            if base_url:
                llm_kwargs["openai_api_base"] = base_url
            return ChatOpenAI(**llm_kwargs)
        elif provider == "openrouter":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                openai_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                openai_api_base="https://openrouter.ai/api/v1",
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
            llm_kwargs = {"model": model_name}
            base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
            if base_url:
                llm_kwargs["anthropic_api_url"] = base_url
            return ChatAnthropic(**llm_kwargs)
        elif provider in ("nvidia", "nvidia_ai_endpoints", "nim"):
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
            llm_kwargs = {"model": model_name}
            base_url = os.environ.get("NVIDIA_BASE_URL", "")
            if base_url:
                llm_kwargs["base_url"] = base_url
            api_key = os.environ.get("NVIDIA_API_KEY", "")
            if api_key:
                llm_kwargs["api_key"] = api_key
            return ChatNVIDIA(**llm_kwargs)
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_name)

    async def setup(self, config: AdapterConfig) -> None:
        try:
            from deepagents import create_deep_agent
        except ImportError:
            raise RuntimeError("deepagents not installed. Ensure adapters/deepagents/requirements.txt is correct.")

        # Full platform setup: plugins, skills, tools, coordinator, system prompt
        result = await self._common_setup(config)
        logger.info(f"DeepAgents tools: {[t.name for t in result.langchain_tools]}")

        # DeepAgents uses LangChain tools natively — no conversion needed
        llm = self._create_llm(config.model)
        self.agent = create_deep_agent(
            model=llm,
            tools=result.langchain_tools,
            system_prompt=result.system_prompt,
        )
        logger.info("DeepAgents agent created with %d tools", len(result.langchain_tools))

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        from a2a_executor import LangGraphA2AExecutor
        return LangGraphA2AExecutor(self.agent, heartbeat=config.heartbeat)
