"""DeepAgents adapter — LangChain deep research agent with planning and sub-agents.

Uses `deepagents.create_deep_agent()` which provides automatic task planning,
filesystem access, and sub-agent spawning on top of LangGraph.

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
        self.system_prompt = None

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
        }

    async def setup(self, config: AdapterConfig) -> None:
        try:
            from deepagents import create_deep_agent  # noqa: F401
        except ImportError:
            raise RuntimeError("deepagents not installed. Ensure adapters/deepagents/requirements.txt is correct.")

        from tools.a2a_tools import get_peers_summary
        self.peers_info = await get_peers_summary()

        # Load system prompt
        prompt_file = os.path.join(config.config_path, "system-prompt.md")
        if os.path.exists(prompt_file):
            with open(prompt_file) as f:
                self.system_prompt = f.read()

        # Create the LLM (same logic as agent.py)
        from agent import create_agent
        # We don't use create_agent directly — we use deepagents' own create_deep_agent
        # But we need the LLM instance
        model_str = config.model
        if ":" in model_str:
            provider, model_name = model_str.split(":", 1)
        else:
            provider, model_name = "openai", model_str

        if provider == "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model_name)
        elif provider == "openrouter":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name,
                openai_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                openai_api_base="https://openrouter.ai/api/v1",
            )
        elif provider == "groq":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name,
                openai_api_key=os.environ.get("GROQ_API_KEY", ""),
                openai_api_base="https://api.groq.com/openai/v1",
            )
        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model=model_name)
        else:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model_name)

        prompt = self.system_prompt or "You are a deep research agent."
        if hasattr(self, 'peers_info') and self.peers_info:
            prompt += f"\n\n## Peers\n{self.peers_info}"

        from tools.delegation import delegate_to_workspace
        from tools.memory import commit_memory, search_memory

        self.agent = create_deep_agent(
            model=llm,
            tools=[delegate_to_workspace, commit_memory, search_memory],
            system_prompt=prompt,
        )
        logger.info("DeepAgents agent created")

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        from a2a_executor import LangGraphA2AExecutor
        return LangGraphA2AExecutor(self.agent)
