"""NemoClaw adapter — a NemoClaw-managed runtime that reuses OpenClaw execution.

NemoClaw provides the sandbox/lifecycle layer. This adapter keeps the existing
OpenClaw CLI execution path for A2A task handling so the first integration stays
small and predictable.
"""

import os
import shutil
import subprocess

from adapters.base import AdapterConfig
from adapters.openclaw.adapter import OpenClawAdapter


class NemoClawAdapter(OpenClawAdapter):
    @staticmethod
    def name() -> str:
        return "nemoclaw"

    @staticmethod
    def display_name() -> str:
        return "NemoClaw"

    @staticmethod
    def description() -> str:
        return "NVIDIA NemoClaw runtime — sandbox/lifecycle management with OpenClaw-compatible execution"

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {"type": "string", "description": "Model ID (e.g. openai:gpt-4.1-mini)"},
            "provider_url": {"type": "string", "description": "LLM provider base URL", "default": "https://openrouter.ai/api/v1"},
            "gateway_port": {"type": "integer", "description": "OpenClaw gateway port", "default": 18789},
            "force_onboard": {"type": "boolean", "description": "Force NemoClaw onboarding on every startup", "default": False},
        }

    async def setup(self, config: AdapterConfig) -> None:
        """Install NemoClaw, onboard it, then reuse the OpenClaw setup flow."""
        npm_prefix = os.path.expanduser("~/.local")
        os.environ["PATH"] = f"{npm_prefix}/bin:{os.environ.get('PATH', '')}"

        if not shutil.which("nemoclaw"):
            result = subprocess.run(
                ["npm", "install", "--prefix", npm_prefix, "-g", "nemoclaw"],
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, "npm_config_prefix": npm_prefix},
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to install NemoClaw: {result.stderr[:500]}")

        nemo_root = os.path.expanduser("~/.nemoclaw")
        creds_file = os.path.join(nemo_root, "credentials.json")
        force_onboard = bool(config.runtime_config.get("force_onboard", False))
        if force_onboard or not os.path.exists(creds_file):
            onboard_env = {
                **os.environ,
                "NODE_NO_WARNINGS": "1",
                "NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE": "1",
            }
            result = subprocess.run(
                ["nemoclaw", "onboard", "--non-interactive"],
                capture_output=True,
                text=True,
                timeout=180,
                env=onboard_env,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to onboard NemoClaw: {result.stderr[:500]}")

        # Reuse the proven OpenClaw setup and A2A execution flow underneath.
        await super().setup(config)
