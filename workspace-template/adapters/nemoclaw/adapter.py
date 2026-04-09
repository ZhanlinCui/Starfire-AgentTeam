"""NemoClaw adapter — NVIDIA NemoClaw sandboxed runtime with OpenClaw execution.

NemoClaw provides sandboxed execution (Landlock + seccomp + network namespace),
lifecycle management, and routed inference on top of OpenClaw. This adapter:
1. Validates Docker access (requires T4 tier with Docker socket mount)
2. Installs NemoClaw if not present (via official installer)
3. Onboards non-interactively to create the sandbox
4. Connects to the sandbox
5. Reuses the OpenClaw A2A execution path for task handling

Requirements:
  - Tier 4 workspace (Docker socket at /var/run/docker.sock)
  - Docker daemon accessible from the container
  - Network access for NemoClaw onboarding (pulls sandbox image ~2.4GB)

Docs: https://docs.nvidia.com/nemoclaw/latest/
"""

import logging
import os
import shutil
import subprocess

from adapters.base import AdapterConfig
from adapters.openclaw.adapter import OpenClawAdapter

logger = logging.getLogger(__name__)

_SANDBOX_NAME = "starfire-agent"


class NemoClawAdapter(OpenClawAdapter):
    @staticmethod
    def name() -> str:
        return "nemoclaw"

    @staticmethod
    def display_name() -> str:
        return "NemoClaw"

    @staticmethod
    def description() -> str:
        return "NVIDIA NemoClaw runtime — sandboxed OpenClaw with lifecycle management and routed inference"

    @staticmethod
    def get_config_schema() -> dict:
        return {
            "model": {"type": "string", "description": "Model ID (e.g. openai:gpt-4.1-mini)"},
            "provider_url": {"type": "string", "description": "LLM provider base URL", "default": "https://openrouter.ai/api/v1"},
            "gateway_port": {"type": "integer", "description": "OpenClaw gateway port", "default": 18789},
            "force_onboard": {"type": "boolean", "description": "Force NemoClaw onboarding on every startup", "default": False},
        }

    def _check_docker(self) -> None:
        """Validate Docker is available. NemoClaw needs Docker for its sandbox."""
        # Check Docker socket exists (T4 tier mounts it)
        if not os.path.exists("/var/run/docker.sock"):
            raise RuntimeError(
                "NemoClaw requires Docker access. This workspace must be Tier 4 (Full Host) "
                "with Docker socket mounted at /var/run/docker.sock. "
                "Change the workspace tier to T4 and restart."
            )

        # Try docker directly, then with sudo (macOS Docker Desktop needs root)
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            # Try with sudo (agent user has passwordless sudo for docker)
            result = subprocess.run(
                ["sudo", "docker", "info"], capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                self._docker_prefix = ["sudo"]
                logger.info("Docker access via sudo (macOS Docker Desktop)")
            else:
                raise RuntimeError(
                    f"Docker is not accessible: {result.stderr[:300]}. "
                    "Ensure Docker Desktop is running and workspace is Tier 4."
                )
        else:
            self._docker_prefix = []
            logger.info("Docker access verified (T4 tier)")

    def _ensure_nemoclaw_cli(self) -> None:
        """Install NemoClaw CLI if not already available."""
        if shutil.which("nemoclaw"):
            version = subprocess.run(
                ["nemoclaw", "--version"], capture_output=True, text=True, timeout=10,
            )
            logger.info("NemoClaw CLI already installed: %s", version.stdout.strip())
            return

        logger.info("Installing NemoClaw via official installer...")
        env = {**os.environ, "NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE": "1"}
        result = subprocess.run(
            ["bash", "-c", "curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash"],
            capture_output=True, text=True, timeout=300, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(f"NemoClaw install failed: {result.stderr[:500]}")

        # Update PATH if installer used nvm
        bashrc = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc):
            source_result = subprocess.run(
                ["bash", "-c", f"source {bashrc} && which nemoclaw"],
                capture_output=True, text=True,
            )
            if source_result.returncode == 0:
                nemoclaw_dir = os.path.dirname(source_result.stdout.strip())
                os.environ["PATH"] = f"{nemoclaw_dir}:{os.environ.get('PATH', '')}"

        if not shutil.which("nemoclaw"):
            raise RuntimeError("NemoClaw installed but CLI not found in PATH")
        logger.info("NemoClaw CLI installed successfully")

    def _onboard_sandbox(self, force: bool = False) -> None:
        """Create the NemoClaw sandbox (non-interactive)."""
        creds_file = os.path.expanduser("~/.nemoclaw/credentials.json")
        if not force and os.path.exists(creds_file):
            logger.info("NemoClaw already onboarded (credentials exist)")
            return

        logger.info("Onboarding NemoClaw sandbox (non-interactive)...")
        env = {
            **os.environ,
            "NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE": "1",
            "NODE_NO_WARNINGS": "1",
        }
        # Use sudo -E if Docker requires it (preserve env vars through sudo)
        cmd_prefix = getattr(self, "_docker_prefix", [])
        if cmd_prefix:
            # sudo -E preserves environment (NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE)
            cmd = ["sudo", "-E", "nemoclaw", "onboard", "--non-interactive", "--yes-i-accept-third-party-software"]
        else:
            cmd = ["nemoclaw", "onboard", "--non-interactive"]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"NemoClaw onboard failed: {result.stderr[:500]}\n"
                f"stdout: {result.stdout[:300]}"
            )
        logger.info("NemoClaw sandbox onboarded successfully")

    def _connect_sandbox(self) -> None:
        """Connect to the NemoClaw sandbox."""
        logger.info("Connecting to NemoClaw sandbox '%s'...", _SANDBOX_NAME)
        cmd_prefix = getattr(self, "_docker_prefix", [])
        result = subprocess.run(
            [*cmd_prefix, "nemoclaw", _SANDBOX_NAME, "connect"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.warning(
                "NemoClaw connect returned %d (may need initial onboard): %s",
                result.returncode, result.stderr[:200],
            )
        else:
            logger.info("Connected to NemoClaw sandbox")

    async def setup(self, config: AdapterConfig) -> None:
        """Full NemoClaw setup: Docker check → install → onboard → connect → OpenClaw."""
        # Step 1: Validate Docker access (T4 required)
        self._check_docker()

        # Step 2: Ensure NemoClaw CLI is installed
        self._ensure_nemoclaw_cli()

        # Step 3: Onboard sandbox
        force = bool(config.runtime_config.get("force_onboard", False))
        self._onboard_sandbox(force=force)

        # Step 4: Connect to sandbox
        self._connect_sandbox()

        # Step 5: Set up OpenClaw execution path inside the sandbox
        await super().setup(config)
