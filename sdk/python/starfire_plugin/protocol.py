"""Adaptor protocol — kept in sync with workspace-template/plugins_registry/protocol.py.

SDK authors depend only on this module so their plugin repos don't need to
pull in the full workspace-template package. At runtime the platform's own
``plugins_registry`` loads the adaptor; the two ``InstallContext`` shapes are
structurally identical so the Protocol check passes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable


@dataclass
class InstallContext:
    configs_dir: Path
    workspace_id: str
    runtime: str
    plugin_root: Path
    register_tool: Callable[[str, Callable[..., Any]], None] = field(
        default=lambda name, fn: None
    )
    register_subagent: Callable[[str, dict[str, Any]], None] = field(
        default=lambda name, spec: None
    )
    append_to_memory: Callable[[str, str], None] = field(
        default=lambda filename, content: None
    )
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))


@dataclass
class InstallResult:
    plugin_name: str
    runtime: str
    source: str
    files_written: list[str] = field(default_factory=list)
    tools_registered: list[str] = field(default_factory=list)
    subagents_registered: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class PluginAdaptor(Protocol):
    plugin_name: str
    runtime: str

    async def install(self, ctx: InstallContext) -> InstallResult:
        ...

    async def uninstall(self, ctx: InstallContext) -> None:
        ...
