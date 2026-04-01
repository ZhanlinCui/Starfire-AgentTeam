"""Create the Deep Agent with model + skills + tools."""

from langchain_core.language_models import init_chat_model
from langgraph.prebuilt import create_react_agent


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

    llm = init_chat_model(model_name, model_provider=provider)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    return agent
