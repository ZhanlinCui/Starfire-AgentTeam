"""AutoGen adapter — Microsoft's multi-agent framework with A2A delegation.

Uses AutoGen's AssistantAgent with OpenAIChatCompletionClient,
includes A2A delegation as a callable tool.

Requires: pip install autogen-agentchat autogen-ext[openai]
"""

import os
import logging

from adapters.base import BaseAdapter, AdapterConfig
from a2a.server.agent_execution import AgentExecutor

logger = logging.getLogger(__name__)


class AutoGenAdapter(BaseAdapter):

    def __init__(self):
        self.system_prompt = None
        self.peers_info = ""

    @staticmethod
    def name() -> str:
        return "autogen"

    @staticmethod
    def display_name() -> str:
        return "AutoGen"

    @staticmethod
    def description() -> str:
        return "Microsoft AutoGen — conversable agents with tool use and multi-agent orchestration"

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {"type": "string", "description": "OpenAI model (e.g. openai:gpt-4.1-mini)"},
        }

    async def setup(self, config: AdapterConfig) -> None:
        try:
            from autogen_agentchat.agents import AssistantAgent  # noqa: F401
            logger.info("AutoGen AgentChat loaded")
        except ImportError:
            raise RuntimeError("autogen-agentchat not installed.")

        prompt_file = os.path.join(config.config_path, "system-prompt.md")
        if os.path.exists(prompt_file):
            with open(prompt_file) as f:
                self.system_prompt = f.read()

        from tools.a2a_tools import get_peers_summary
        self.peers_info = await get_peers_summary()

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        return AutoGenA2AExecutor(
            model=config.model,
            system_prompt=self.system_prompt,
            peers_info=self.peers_info,
        )


class AutoGenA2AExecutor(AgentExecutor):
    """Wraps AutoGen's AssistantAgent with A2A delegation tools."""

    def __init__(self, model: str, system_prompt: str | None, peers_info: str):
        self.model = model
        self.system_prompt = system_prompt
        self.peers_info = peers_info

    async def execute(self, context, event_queue):
        from a2a.utils import new_agent_text_message

        text_parts = []
        if context.message and context.message.parts:
            for part in context.message.parts:
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
                elif hasattr(part, "root") and hasattr(part.root, "text"):
                    text_parts.append(part.root.text)
        user_message = " ".join(text_parts).strip()

        if not user_message:
            await event_queue.enqueue_event(new_agent_text_message("No message provided"))
            return

        try:
            from autogen_agentchat.agents import AssistantAgent
            from autogen_ext.models.openai import OpenAIChatCompletionClient
            from tools.a2a_tools import delegate_task, list_peers

            # AutoGen tool functions
            async def delegate_to_peer(workspace_id: str, task: str) -> str:
                """Delegate a task to a peer workspace via A2A protocol."""
                return await delegate_task(workspace_id, task)

            async def list_available_peers() -> str:
                """List all peer workspaces this agent can communicate with."""
                peers = await list_peers()
                return "\n".join(f"- {p.get('name','')} (ID: {p.get('id','')}) — {p.get('role','')}" for p in peers) or "No peers"

            model_str = self.model
            if ":" in model_str:
                _, model_name = model_str.split(":", 1)
            else:
                model_name = model_str

            sys_msg = self.system_prompt or "You are a helpful assistant."
            if self.peers_info:
                sys_msg += f"\n\n## Peers\n{self.peers_info}\nUse delegate_to_peer tool to communicate with them."

            client = OpenAIChatCompletionClient(model=model_name)
            agent = AssistantAgent(
                name="agent",
                model_client=client,
                system_message=sys_msg,
                tools=[delegate_to_peer, list_available_peers],
            )

            result = await agent.run(task=user_message)

            reply = ""
            if hasattr(result, "messages") and result.messages:
                for msg in reversed(result.messages):
                    if hasattr(msg, "content") and isinstance(msg.content, str):
                        reply = msg.content
                        break
            if not reply:
                reply = str(result)

        except Exception as e:
            reply = f"AutoGen error: {e}"

        await event_queue.enqueue_event(new_agent_text_message(reply))

    async def cancel(self, context, event_queue):
        pass
