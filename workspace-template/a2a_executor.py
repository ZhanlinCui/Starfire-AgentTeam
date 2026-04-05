"""Bridge between LangGraph agent and A2A protocol."""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

logger = logging.getLogger(__name__)


class LangGraphA2AExecutor(AgentExecutor):
    """Bridges LangGraph agent to A2A event model."""

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

        try:
            # Use ainvoke (not astream) for reliable response across all models
            result = await self.agent.ainvoke(
                {"messages": [("user", user_input)]},
                config={
                    "configurable": {"thread_id": context.context_id},
                    "run_name": f"a2a-{context.context_id[:8]}",
                },
            )

            # Extract the last AI message (skip tool/human messages)
            messages = result.get("messages", [])
            final_content = ""
            for msg in reversed(messages):
                msg_type = getattr(msg, "type", "")
                # Only accept AI/assistant messages, skip tool results and human
                if msg_type not in ("ai", "AIMessage", "assistant"):
                    continue
                content = getattr(msg, "content", "")
                if isinstance(content, list):
                    # Anthropic content blocks — extract only text blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = " ".join(text_parts).strip()
                if isinstance(content, str) and content.strip():
                    final_content = content
                    break

            if final_content:
                await event_queue.enqueue_event(
                    new_agent_text_message(final_content)
                )
            else:
                await event_queue.enqueue_event(
                    new_agent_text_message("(no response generated)")
                )

        except Exception as e:
            logger.error("A2A execute error: %s", e)
            await event_queue.enqueue_event(
                new_agent_text_message(f"Agent error: {e}")
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Cancel a running task."""
        pass
