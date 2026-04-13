"""Hermes adapter — NousResearch Hermes 3 via Nous Portal or OpenRouter.

Both providers speak the OpenAI chat-completions wire protocol.
Set NOUS_API_KEY (primary) or OPENROUTER_API_KEY (fallback) as a workspace secret.
"""

import logging
import os

from adapters.base import BaseAdapter, AdapterConfig
from adapters.shared_runtime import (
    brief_task, build_task_text, extract_history,
    extract_message_text, set_current_task,
)
from a2a.server.agent_execution import AgentExecutor

logger = logging.getLogger(__name__)

_NOUS_BASE_URL = "https://api.nousresearch.com/v1"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_NOUS_MODEL = "nous-hermes-3"
_DEFAULT_OPENROUTER_MODEL = "nousresearch/hermes-3-llama-3.1-405b"


class HermesAdapter(BaseAdapter):

    def __init__(self):
        self.system_prompt: str | None = None
        self._api_key: str = ""
        self._base_url: str = ""
        self._model: str = ""

    @staticmethod
    def name() -> str:
        return "hermes"

    @staticmethod
    def display_name() -> str:
        return "Hermes (NousResearch)"

    @staticmethod
    def description() -> str:
        return "NousResearch Hermes 3 via Nous Portal or OpenRouter. Requires NOUS_API_KEY or OPENROUTER_API_KEY."

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {"type": "string", "description": "Model ID (default: nous-hermes-3 / nousresearch/hermes-3-llama-3.1-405b)"},
            "skills": {"type": "array", "items": {"type": "string"}, "description": "Skill folder names"},
            "tools": {"type": "array", "items": {"type": "string"}, "description": "Built-in tools to enable"},
        }

    async def setup(self, config: AdapterConfig) -> None:
        nous_key = os.environ.get("NOUS_API_KEY", "")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        hermes_model = os.environ.get("HERMES_MODEL", "")

        if not nous_key and not openrouter_key:
            raise RuntimeError(
                "Hermes adapter requires NOUS_API_KEY (Nous Portal) or "
                "OPENROUTER_API_KEY (OpenRouter). Set at least one as a workspace secret."
            )

        if nous_key:
            self._api_key, self._base_url = nous_key, _NOUS_BASE_URL
            self._model = hermes_model or _DEFAULT_NOUS_MODEL
        else:
            self._api_key, self._base_url = openrouter_key, _OPENROUTER_BASE_URL
            self._model = hermes_model or _DEFAULT_OPENROUTER_MODEL

        logger.info("Hermes: base_url=%s model=%s", self._base_url, self._model)
        result = await self._common_setup(config)
        self.system_prompt = result.system_prompt

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        return HermesA2AExecutor(
            api_key=self._api_key, base_url=self._base_url,
            model=self._model, system_prompt=self.system_prompt,
            heartbeat=config.heartbeat,
        )


class HermesA2AExecutor(AgentExecutor):
    """Calls NousResearch Hermes via the OpenAI-compatible chat completions API."""

    def __init__(self, api_key, base_url, model, system_prompt, heartbeat=None):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self.system_prompt = system_prompt
        self._heartbeat = heartbeat

    async def execute(self, context, event_queue) -> None:
        from a2a.utils import new_agent_text_message

        user_message = extract_message_text(context)
        if not user_message:
            await event_queue.enqueue_event(new_agent_text_message("No message provided."))
            return

        await set_current_task(self._heartbeat, brief_task(user_message))
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            for role, content in extract_history(context):
                messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": build_task_text(user_message, [])})
            response = await client.chat.completions.create(model=self._model, messages=messages)
            reply = response.choices[0].message.content or ""
        except Exception as exc:
            logger.exception("Hermes execution error")
            reply = f"Hermes error: {exc}"
        finally:
            await set_current_task(self._heartbeat, "")

        await event_queue.enqueue_event(new_agent_text_message(reply))

    async def cancel(self, context, event_queue) -> None:  # pragma: no cover
        pass
