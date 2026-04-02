"""Bridge between LangGraph agent and A2A protocol."""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

logger = logging.getLogger(__name__)


class LangGraphA2AExecutor(AgentExecutor):
    """Bridges LangGraph streaming to A2A event model."""

    def __init__(self, agent):
        self.agent = agent  # Compiled LangGraph graph

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        """Execute a task from an A2A request."""
        # Extract text from message parts
        parts = context.message.parts
        text_parts = []
        for part in parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
            elif hasattr(part, "root") and hasattr(part.root, "text"):
                text_parts.append(part.root.text)

        user_input = " ".join(text_parts).strip()
        if not user_input:
            logger.warning("A2A execute: no text content in message parts: %s", parts)
            await event_queue.enqueue_event(
                new_agent_text_message("Error: message contained no text content.")
            )
            return

        logger.info("A2A execute: user_input=%s", user_input[:200])

        # Stream through LangGraph agent
        final_content = ""
        async for chunk in self.agent.astream(
            {"messages": [("user", user_input)]},
            config={"configurable": {"thread_id": context.context_id}},
        ):
            if "messages" in chunk:
                last_msg = chunk["messages"][-1]
                content = getattr(last_msg, "content", str(last_msg))
                if isinstance(content, str) and content.strip():
                    final_content = content

        if final_content:
            await event_queue.enqueue_event(
                new_agent_text_message(final_content)
            )
        else:
            await event_queue.enqueue_event(
                new_agent_text_message("(no response generated)")
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Cancel a running task."""
        pass
