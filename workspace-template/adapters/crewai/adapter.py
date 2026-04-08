"""CrewAI adapter — role-based multi-agent framework with A2A delegation.

Creates a CrewAI Agent + Task + Crew with delegation tools,
wraps the kickoff() result in an A2A executor.

Requires: pip install crewai
"""

import os
import logging
import asyncio

from adapters.base import BaseAdapter, AdapterConfig
from adapters.shared_runtime import (
    append_peer_guidance,
    build_task_text,
    brief_task,
    extract_history,
    extract_message_text,
    set_current_task,
)
from a2a.server.agent_execution import AgentExecutor

logger = logging.getLogger(__name__)


class CrewAIAdapter(BaseAdapter):

    def __init__(self):
        self.system_prompt = None
        self.peers_info = ""

    @staticmethod
    def name() -> str:
        return "crewai"

    @staticmethod
    def display_name() -> str:
        return "CrewAI"

    @staticmethod
    def description() -> str:
        return "CrewAI — role-based agent framework with task delegation and crew orchestration"

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {"type": "string", "description": "LLM model (e.g. openai:gpt-4.1-mini)"},
        }

    async def setup(self, config: AdapterConfig) -> None:
        try:
            import crewai  # noqa: F401
            logger.info(f"CrewAI version: {crewai.__version__}")
        except ImportError:
            raise RuntimeError("crewai not installed.")

        # Load system prompt
        prompt_file = os.path.join(config.config_path, "system-prompt.md")
        if os.path.exists(prompt_file):
            with open(prompt_file) as f:
                self.system_prompt = f.read()

        # Get peer info for injection into prompts
        from tools.a2a_tools import get_peers_summary
        self.peers_info = await get_peers_summary()

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        return CrewAIA2AExecutor(
            model=config.model,
            system_prompt=self.system_prompt,
            peers_info=self.peers_info,
            heartbeat=config.heartbeat,
        )


class CrewAIA2AExecutor(AgentExecutor):
    """Wraps CrewAI's Agent + Crew.kickoff() with A2A delegation tools."""

    def __init__(self, model: str, system_prompt: str | None, peers_info: str, heartbeat=None):
        self.model = model
        self.system_prompt = system_prompt
        self.peers_info = peers_info
        self._heartbeat = heartbeat

    async def execute(self, context, event_queue):
        from a2a.utils import new_agent_text_message

        user_message = extract_message_text(context)

        if not user_message:
            await event_queue.enqueue_event(new_agent_text_message("No message provided"))
            return

        await set_current_task(self._heartbeat, brief_task(user_message))

        try:
            from crewai import Agent, Task, Crew
            from crewai.tools import tool as crewai_tool
            from tools.a2a_tools import delegate_task, list_peers

            # Create CrewAI-compatible delegation tools
            @crewai_tool("delegate_to_peer")
            def delegate_to_peer(workspace_id: str, task: str) -> str:
                """Delegate a task to a peer workspace via A2A protocol. Use list_peers first to find available peers."""
                return asyncio.get_event_loop().run_until_complete(delegate_task(workspace_id, task))

            @crewai_tool("list_available_peers")
            def list_available_peers() -> str:
                """List all peer workspaces this agent can communicate with."""
                peers = asyncio.get_event_loop().run_until_complete(list_peers())
                return "\n".join(f"- {p.get('name','')} (ID: {p.get('id','')}) — {p.get('role','')}" for p in peers) or "No peers"

            model_str = self.model
            if model_str.startswith("openai:"):
                model_str = model_str.replace("openai:", "openai/")

            backstory = append_peer_guidance(
                self.system_prompt,
                self.peers_info,
                default_text="You are a helpful AI agent.",
                tool_name="delegate_to_peer",
            )

            # Include conversation history in the task description
            task_desc = build_task_text(user_message, extract_history(context))

            agent = Agent(
                role=backstory.split("\n")[0][:100],
                goal="Help the user and coordinate with peer agents when needed",
                backstory=backstory,
                llm=model_str,
                tools=[delegate_to_peer, list_available_peers],
                verbose=False,
            )

            task = Task(
                description=task_desc,
                expected_output="A helpful response",
                agent=agent,
            )

            crew = Crew(agents=[agent], tasks=[task], verbose=False)
            result = await asyncio.to_thread(crew.kickoff)
            reply = str(result)

        except Exception as e:
            reply = f"CrewAI error: {e}"
        finally:
            await set_current_task(self._heartbeat, "")

        await event_queue.enqueue_event(new_agent_text_message(reply))

    async def cancel(self, context, event_queue):
        pass
