"""Smoke tests for the starfire_plugin SDK.

Runs without the workspace runtime — SDK consumers should be able to
lint/unit-test their plugins with only `pip install starfire-plugin`.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_SDK_ROOT = Path(__file__).resolve().parents[1]
if str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

from starfire_plugin import (  # noqa: E402
    GenericPluginAdaptor,
    InstallContext,
    PluginAdaptor,
    validate_manifest,
)


def test_generic_adaptor_satisfies_protocol():
    adaptor = GenericPluginAdaptor("p", "claude_code")
    assert isinstance(adaptor, PluginAdaptor)


async def test_generic_adaptor_installs_skills_and_rules(tmp_path: Path):
    plugin_root = tmp_path / "demo"
    (plugin_root / "rules").mkdir(parents=True)
    (plugin_root / "rules" / "r1.md").write_text("- be kind")
    (plugin_root / "skills" / "s1").mkdir(parents=True)
    (plugin_root / "skills" / "s1" / "SKILL.md").write_text("# skill")

    configs = tmp_path / "configs"
    configs.mkdir()

    def _append(fn: str, content: str) -> None:
        with open(configs / fn, "a") as f:
            f.write(content + "\n")

    ctx = InstallContext(
        configs_dir=configs,
        workspace_id="ws",
        runtime="claude_code",
        plugin_root=plugin_root,
        append_to_memory=_append,
        logger=logging.getLogger("test"),
    )

    result = await GenericPluginAdaptor("demo", "claude_code").install(ctx)
    assert result.plugin_name == "demo"
    assert (configs / "skills" / "s1" / "SKILL.md").exists()
    assert "# Plugin: demo" in (configs / "CLAUDE.md").read_text()


def test_validate_manifest_accepts_minimal(tmp_path: Path):
    p = tmp_path / "plugin.yaml"
    p.write_text("name: demo\n")
    assert validate_manifest(p) == []


def test_validate_manifest_rejects_unknown_runtime(tmp_path: Path):
    p = tmp_path / "plugin.yaml"
    p.write_text("name: demo\nruntimes: [martian]\n")
    errors = validate_manifest(p)
    assert any("unknown runtime" in e for e in errors)


def test_validate_manifest_accepts_hyphen_form(tmp_path: Path):
    p = tmp_path / "plugin.yaml"
    p.write_text("name: demo\nruntimes: [claude-code]\n")
    assert validate_manifest(p) == []


def test_validate_manifest_requires_name(tmp_path: Path):
    p = tmp_path / "plugin.yaml"
    p.write_text("version: 1.0\n")
    errors = validate_manifest(p)
    assert any("name" in e for e in errors)
