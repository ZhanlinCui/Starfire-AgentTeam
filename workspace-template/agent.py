"""Create the Deep Agent with model + skills + tools."""

import os
import logging

from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)


def create_agent(model_str: str, tools: list, system_prompt: str):
    """Create a LangGraph ReAct agent.

    Args:
        model_str: LangChain-compatible model string (e.g., 'anthropic:claude-sonnet-4-6')
        tools: List of tool functions
        system_prompt: The system prompt for the agent
    """
    # Parse provider:model format
    if ":" in model_str:
        provider, model_name = model_str.split(":", 1)
    else:
        provider = "anthropic"
        model_name = model_str

    try:
        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model=model_name)
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model_name)
        elif provider == "google_genai":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model=model_name)
        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            llm = ChatOllama(model=model_name)
        else:
            raise ValueError(f"Unsupported model provider: {provider}")
    except ImportError as e:
        raise ImportError(
            f"Provider '{provider}' requires package 'langchain-{provider}'. "
            f"Install it with: pip install langchain-{provider}"
        ) from e

    # Auto-inject Langfuse tracing if env vars are present
    callbacks = _setup_langfuse()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    return agent


def _setup_langfuse():
    """Set up Langfuse tracing if LANGFUSE_* env vars are present.

    Returns list of callbacks to pass to agent invocations, or empty list.
    """
    langfuse_host = os.environ.get("LANGFUSE_HOST")
    langfuse_public = os.environ.get("LANGFUSE_PUBLIC_KEY")
    langfuse_secret = os.environ.get("LANGFUSE_SECRET_KEY")

    if not (langfuse_host and langfuse_public and langfuse_secret):
        return []

    try:
        from langfuse.callback import CallbackHandler

        handler = CallbackHandler(
            host=langfuse_host,
            public_key=langfuse_public,
            secret_key=langfuse_secret,
        )
        logger.info("Langfuse tracing enabled: %s", langfuse_host)

        # Also set LANGSMITH_TRACING for LangGraph native integration
        os.environ.setdefault("LANGSMITH_TRACING", "true")

        return [handler]
    except ImportError:
        logger.warning("Langfuse env vars set but langfuse package not installed")
        return []
    except Exception as e:
        logger.warning("Langfuse setup failed: %s", e)
        return []
