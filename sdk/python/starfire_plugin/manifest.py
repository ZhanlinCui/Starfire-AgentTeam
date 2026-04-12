"""Plugin manifest schema + validator.

Matches what workspace-template/plugins.py:PluginManifest parses, so a
plugin that validates locally will also load cleanly in the platform.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PLUGIN_YAML_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "author": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "skills": {"type": "array", "items": {"type": "string"}},
        "rules": {"type": "array", "items": {"type": "string"}},
        "prompt_fragments": {"type": "array", "items": {"type": "string"}},
        "runtimes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Declared supported runtimes (e.g. claude_code, deepagents).",
        },
    },
}


def validate_manifest(path: str | Path) -> list[str]:
    """Return a list of validation error messages. Empty list = valid.

    Deliberately simple — no jsonschema dependency so SDK consumers don't
    pick up an extra transitive dep just to lint their plugin.
    """
    path = Path(path)
    if not path.is_file():
        return [f"manifest not found: {path}"]

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        return [f"yaml parse error: {exc}"]

    errors: list[str] = []
    if not isinstance(raw, dict):
        return ["manifest root must be a mapping"]

    if "name" not in raw or not isinstance(raw.get("name"), str) or not raw["name"].strip():
        errors.append("`name` is required and must be a non-empty string")

    for field_name in ("tags", "skills", "rules", "prompt_fragments", "runtimes"):
        if field_name in raw and not isinstance(raw[field_name], list):
            errors.append(f"`{field_name}` must be a list")

    if "runtimes" in raw and isinstance(raw["runtimes"], list):
        known = {"claude_code", "deepagents", "langgraph", "crewai", "autogen", "openclaw"}
        for r in raw["runtimes"]:
            if not isinstance(r, str):
                errors.append(f"`runtimes` entry must be string, got {type(r).__name__}")
            elif r.replace("-", "_") not in known:
                errors.append(
                    f"unknown runtime '{r}' — supported: {sorted(known)} "
                    f"(use underscore form, e.g. 'claude_code')"
                )

    return errors
