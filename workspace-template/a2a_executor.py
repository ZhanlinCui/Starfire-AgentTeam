"""Bridge between LangGraph agent and A2A protocol."""

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message


class LangGraphA2AExecutor(AgentExecutor):
    """Bridges LangGraph streaming to A2A event model."""

    def __init__(self, agent):
        self.agent = agent  # Compiled LangGraph graph

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        """Execute a task from an A2A request."""
        # Extract text from message parts
        user_input = " ".join(
            part.text
            for part in context.message.parts
            if hasattr(part, "text")
        )

        # Stream through LangGraph agent
        async for chunk in self.agent.astream(
            {"messages": [{"role": "user", "content": user_input}]},
            config={"configurable": {"thread_id": context.context_id}},
        ):
            if "messages" in chunk:
                last_msg = chunk["messages"][-1]
                content = getattr(last_msg, "content", str(last_msg))
                if isinstance(content, str) and content.strip():
                    await event_queue.enqueue_event(
                        new_agent_text_message(content)
                    )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Cancel a running task."""
        pass  # LangGraph interrupt not easily exposed; no-op for Phase 1
