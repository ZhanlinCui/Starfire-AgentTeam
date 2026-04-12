"""Starfire plugin SDK — build plugins installable on any Starfire workspace.

A plugin is a directory containing a ``plugin.yaml`` manifest and one or more
per-runtime adaptors under ``adapters/<runtime>.py``. The Starfire platform
resolves and installs the right adaptor at workspace startup.

This SDK exposes:

* :class:`PluginAdaptor` — the Protocol every adaptor must satisfy.
* :class:`InstallContext`, :class:`InstallResult` — data classes passed to
  ``install()`` and returned from it.
* :class:`GenericPluginAdaptor` — a drop-in adaptor for plugins that only
  ship rules + skill directories (covers the vast majority of cases).
* :data:`PLUGIN_YAML_SCHEMA` — the manifest schema for validation tooling.

Example: a minimal plugin that's installable on Claude Code and DeepAgents

.. code-block:: text

    my-plugin/
    ├── plugin.yaml
    ├── rules/my-rule.md
    ├── skills/my-skill/SKILL.md
    └── adapters/
        ├── claude_code.py   # `from starfire_plugin import GenericPluginAdaptor as Adaptor`
        └── deepagents.py    # same one-liner

Full docs + cookiecutter template: see ``sdk/python/README.md``.
"""

from __future__ import annotations

# Re-export from the runtime registry so plugins have a single import path.
# The workspace-template package is not pip-installable yet; the SDK duplicates
# the Protocol definition so community authors can build against it without
# depending on the runtime. When a plugin is installed in a workspace, the
# runtime's own ``plugins_registry`` is what actually executes the adaptor —
# these types are structurally compatible (duck-typed via Protocol).

from .protocol import (  # noqa: F401
    InstallContext,
    InstallResult,
    PluginAdaptor,
)
from .builtins import GenericPluginAdaptor  # noqa: F401
from .manifest import PLUGIN_YAML_SCHEMA, validate_manifest  # noqa: F401

__version__ = "0.1.0"

__all__ = [
    "GenericPluginAdaptor",
    "InstallContext",
    "InstallResult",
    "PLUGIN_YAML_SCHEMA",
    "PluginAdaptor",
    "validate_manifest",
    "__version__",
]
