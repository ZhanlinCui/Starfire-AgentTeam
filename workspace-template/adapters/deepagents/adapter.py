"""DeepAgents adapter — LangChain deep research agent with full platform integration.

Uses `deepagents.create_deep_agent()` which provides:
- Task planning via write_todos tool
- Filesystem access (read_file, write_file, edit_file, ls, glob, grep)
- Sub-agent spawning via task tool
- Shell execution via execute tool
- Auto-summarization for long contexts
- Permission system for filesystem access
- Memory persistence across runs

All platform tools (delegation, memory, sandbox, approval), skills, plugins,
and coordinator support are included via _common_setup().

Supports all LangChain chat model providers: anthropic, openai, openrouter,
groq, google_genai, ollama, and any provider via init_chat_model.
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
        return "LangChain DeepAgents — deep research with planning, sub-agents, filesystem, and shell execution"

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {
                "type": "string",
                "description": "provider:model (e.g. google_genai:gemini-2.5-flash, anthropic:claude-sonnet-4-6, openai:gpt-4o)",
                "default": "google_genai:gemini-2.5-flash",
            },
            "skills": {"type": "array", "items": {"type": "string"}, "description": "Skill folder names to load"},
            "tools": {"type": "array", "items": {"type": "string"}, "description": "Built-in tools"},
        }

    def _create_llm(self, model_str: str):
        """Create a LangChain LLM instance from a provider:model string.

        Supports all providers that agent.py supports, plus a fallback to
        init_chat_model for any provider LangChain knows about.
        """
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
            api_key = os.environ.get("OPENROUTER_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
            max_tokens = int(os.environ.get("MAX_TOKENS", "2048"))
            return ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                max_tokens=max_tokens,
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

        elif provider == "google_genai":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=model_name)

        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(model=model_name)

        else:
            # Fallback: try init_chat_model which supports many providers
            try:
                from langchain.chat_models import init_chat_model
                return init_chat_model(model_str)
            except Exception:
                from langchain_openai import ChatOpenAI
                logger.warning("Unknown provider %s, falling back to OpenAI", provider)
                return ChatOpenAI(model=model_name)

    async def setup(self, config: AdapterConfig) -> None:
        try:
            from deepagents import create_deep_agent
        except ImportError:
            raise RuntimeError("deepagents not installed. Ensure adapters/deepagents/requirements.txt is correct.")

        # Full platform setup: plugins, skills, tools, coordinator, system prompt
        result = await self._common_setup(config)
        logger.info(f"DeepAgents tools: {[t.name for t in result.langchain_tools]}")

        # DeepAgents uses LangChain tools natively — no conversion needed.
        # create_deep_agent adds its own built-in tools (write_todos, filesystem,
        # execute, task) on top of the platform tools we pass here.
        #
        # Pass a pre-initialized LLM so we control the exact provider. Also
        # pass it as the model string for DeepAgents' internal middleware
        # (summarization, sub-agents) so they use the same provider instead
        # of defaulting to Anthropic.
        llm = self._create_llm(config.model)

        # Build middleware with the same LLM for summarization, avoiding the
        # DeepAgents default which uses Anthropic.
        middleware = []
        try:
            from deepagents.middleware import SummarizationMiddleware
            from deepagents.backends import InMemoryBackend
            middleware.append(SummarizationMiddleware(model=llm, backend=InMemoryBackend()))
            logger.info("DeepAgents: summarization middleware using %s", config.model)
        except Exception as e:
            logger.warning("DeepAgents: could not configure summarization middleware: %s", e)

        self.agent = create_deep_agent(
            model=llm,
            tools=result.langchain_tools,
            system_prompt=result.system_prompt,
            middleware=middleware,
        )
        logger.info("DeepAgents agent created with %d platform tools + built-in tools", len(result.langchain_tools))

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        from a2a_executor import LangGraphA2AExecutor
        return LangGraphA2AExecutor(self.agent, heartbeat=config.heartbeat, model=config.model)
