"""Bridge between LangGraph agent and A2A protocol."""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from adapters.shared_runtime import (
    extract_history as _extract_history,
    extract_message_text,
    brief_task,
    set_current_task,
)

logger = logging.getLogger(__name__)


class LangGraphA2AExecutor(AgentExecutor):
    """Bridges LangGraph agent to A2A event model."""

    def __init__(self, agent, heartbeat=None):
        self.agent = agent  # Compiled LangGraph graph
        self._heartbeat = heartbeat

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        """Execute a task from an A2A request."""
        user_input = extract_message_text(context)
        if not user_input:
            parts = getattr(getattr(context, "message", None), "parts", None)
            logger.warning("A2A execute: no text content in message parts: %s", parts)
            await event_queue.enqueue_event(
                new_agent_text_message("Error: message contained no text content.")
            )
            return

        logger.info("A2A execute: user_input=%s", user_input[:200])

        # Show current task on canvas
        await set_current_task(self._heartbeat, brief_task(user_input))

        try:
            # Build message list with conversation history if provided
            messages = _extract_history(context)

            # Append current user message
            messages.append(("human", user_input))

            # Use ainvoke (not astream) for reliable response across all models
            result = await self.agent.ainvoke(
                {"messages": messages},
                config={
                    "configurable": {"thread_id": context.context_id},
                    "run_name": f"a2a-{context.context_id[:8]}",
                },
            )

            # Extract the last AI message (skip tool/human messages)
            result_messages = result.get("messages", [])
            final_content = ""
            for msg in reversed(result_messages):
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
        finally:
            await set_current_task(self._heartbeat, "")

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Cancel a running task."""
        pass
