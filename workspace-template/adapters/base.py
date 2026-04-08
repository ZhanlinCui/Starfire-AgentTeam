"""Base adapter interface for agent infrastructure providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from a2a.server.agent_execution import AgentExecutor


@dataclass
class AdapterConfig:
    """Standardized config passed to every adapter."""
    model: str                              # e.g. "anthropic:claude-sonnet-4-6" or "openrouter:google/gemini-2.5-flash"
    system_prompt: str | None = None        # Assembled system prompt text
    tools: list[str] = field(default_factory=list)  # Tool names from config.yaml
    runtime_config: dict[str, Any] = field(default_factory=dict)  # Raw runtime_config block
    config_path: str = "/configs"           # Path to configs directory
    workspace_id: str = ""                  # Workspace identifier
    prompt_files: list[str] = field(default_factory=list)  # Ordered prompt file names
    a2a_port: int = 8000                    # Port for A2A server
    heartbeat: Any = None                   # HeartbeatLoop instance


class BaseAdapter(ABC):
    """Interface every agent infrastructure adapter must implement.

    To add a new agent infra:
    1. Create workspace-template/adapters/<your_infra>/
    2. Implement adapter.py with a class extending BaseAdapter
    3. Add requirements.txt with your infra's dependencies
    4. Export as Adapter in __init__.py
    5. Submit a PR
    """

    @staticmethod
    @abstractmethod
    def name() -> str:
        """Return the runtime identifier (e.g. 'langgraph', 'crewai').
        This must match the 'runtime' field in config.yaml."""
        ...

    @staticmethod
    @abstractmethod
    def display_name() -> str:
        """Human-readable name for UI display."""
        ...

    @staticmethod
    @abstractmethod
    def description() -> str:
        """Short description of what this adapter provides."""
        ...

    @staticmethod
    def get_config_schema() -> dict:
        """Return JSON Schema for runtime_config fields this adapter supports.
        Used by the Config tab UI to render the right form fields.
        Override in subclasses for adapter-specific settings."""
        return {}

    @abstractmethod
    async def setup(self, config: AdapterConfig) -> None:
        """One-time setup: validate config, prepare internal state.
        Called after deps are installed but before create_executor().
        Raise RuntimeError if setup fails (missing deps, bad config, etc.)."""
        ...

    @abstractmethod
    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        """Create and return an AgentExecutor ready for A2A integration.
        The returned executor's execute() method will be called by the
        A2A server's DefaultRequestHandler."""
        ...
