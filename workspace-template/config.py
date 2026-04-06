"""Load workspace configuration from config.yaml."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class DelegationConfig:
    retry_attempts: int = 3
    retry_delay: float = 5.0
    timeout: float = 120.0
    escalate: bool = True


@dataclass
class A2AConfig:
    port: int = 8000
    streaming: bool = True
    push_notifications: bool = True


@dataclass
class SandboxConfig:
    backend: str = "subprocess"  # subprocess | docker
    memory_limit: str = "256m"
    timeout: int = 30

@dataclass
class RuntimeConfig:
    """Configuration for CLI-based agent runtimes (claude-code, codex, ollama, custom)."""
    command: str = ""          # e.g. "claude", "codex", "ollama run llama3"
    args: list[str] = field(default_factory=list)  # additional CLI args
    auth_token_env: str = ""   # env var name for auth token
    auth_token_file: str = ""  # file path for auth token (relative to config dir)
    timeout: int = 300         # seconds
    model: str = ""            # model override for the CLI


@dataclass
class WorkspaceConfig:
    name: str = "Workspace"
    description: str = ""
    version: str = "1.0.0"
    tier: int = 1
    model: str = "anthropic:claude-sonnet-4-6"
    runtime: str = "langgraph"  # langgraph | claude-code | codex | ollama | custom
    runtime_config: RuntimeConfig = field(default_factory=RuntimeConfig)
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    prompt_files: list[str] = field(default_factory=list)
    shared_context: list[str] = field(default_factory=list)
    a2a: A2AConfig = field(default_factory=A2AConfig)
    delegation: DelegationConfig = field(default_factory=DelegationConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    sub_workspaces: list[dict] = field(default_factory=list)


def load_config(config_path: Optional[str] = None) -> WorkspaceConfig:
    """Load config from WORKSPACE_CONFIG_PATH or the given path."""
    if config_path is None:
        config_path = os.environ.get("WORKSPACE_CONFIG_PATH", "/configs")

    config_file = Path(config_path) / "config.yaml"
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    with open(config_file) as f:
        raw = yaml.safe_load(f)

    # Override model from env if provided
    model = os.environ.get("MODEL_PROVIDER", raw.get("model", "anthropic:claude-sonnet-4-6"))

    runtime = raw.get("runtime", "langgraph")
    runtime_raw = raw.get("runtime_config", {})

    a2a_raw = raw.get("a2a", {})
    delegation_raw = raw.get("delegation", {})
    sandbox_raw = raw.get("sandbox", {})

    return WorkspaceConfig(
        name=raw.get("name", "Workspace"),
        description=raw.get("description", ""),
        version=raw.get("version", "1.0.0"),
        tier=int(raw.get("tier", 1)),
        model=model,
        runtime=runtime,
        runtime_config=RuntimeConfig(
            command=runtime_raw.get("command", ""),
            args=runtime_raw.get("args", []),
            auth_token_env=runtime_raw.get("auth_token_env", ""),
            auth_token_file=runtime_raw.get("auth_token_file", ""),
            timeout=runtime_raw.get("timeout", 300),
            model=runtime_raw.get("model", ""),
        ),
        skills=raw.get("skills", []),
        tools=raw.get("tools", []),
        prompt_files=raw.get("prompt_files", []),
        shared_context=raw.get("shared_context", []),
        a2a=A2AConfig(
            port=a2a_raw.get("port", 8000),
            streaming=a2a_raw.get("streaming", True),
            push_notifications=a2a_raw.get("push_notifications", True),
        ),
        delegation=DelegationConfig(
            retry_attempts=delegation_raw.get("retry_attempts", 3),
            retry_delay=delegation_raw.get("retry_delay", 5.0),
            timeout=delegation_raw.get("timeout", 120.0),
            escalate=delegation_raw.get("escalate", True),
        ),
        sandbox=SandboxConfig(
            backend=sandbox_raw.get("backend", "subprocess"),
            memory_limit=sandbox_raw.get("memory_limit", "256m"),
            timeout=sandbox_raw.get("timeout", 30),
        ),
        sub_workspaces=raw.get("sub_workspaces", []),
    )
