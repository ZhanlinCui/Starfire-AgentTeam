"""Create the Deep Agent with model + skills + tools."""

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

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    return agent
