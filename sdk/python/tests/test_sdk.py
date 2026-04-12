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


def test_validate_manifest_missing_file(tmp_path: Path):
    errors = validate_manifest(tmp_path / "does-not-exist.yaml")
    assert any("not found" in e for e in errors)


def test_validate_manifest_invalid_yaml(tmp_path: Path):
    p = tmp_path / "plugin.yaml"
    p.write_text("name: demo\n: bad\n")
    errors = validate_manifest(p)
    assert any("yaml parse error" in e for e in errors)


def test_validate_manifest_non_mapping_root(tmp_path: Path):
    p = tmp_path / "plugin.yaml"
    p.write_text("- just\n- a\n- list\n")
    errors = validate_manifest(p)
    assert any("mapping" in e for e in errors)


def test_validate_manifest_list_fields_must_be_lists(tmp_path: Path):
    p = tmp_path / "plugin.yaml"
    p.write_text("name: demo\ntags: not-a-list\n")
    errors = validate_manifest(p)
    assert any("tags" in e and "list" in e for e in errors)


def test_validate_manifest_runtime_entry_must_be_string(tmp_path: Path):
    p = tmp_path / "plugin.yaml"
    p.write_text("name: demo\nruntimes:\n  - 42\n")
    errors = validate_manifest(p)
    assert any("string" in e for e in errors)


async def test_generic_adaptor_installs_rules_and_skills_both(tmp_path: Path):
    """Full shape: rules + root fragment + skills + skip-list files + empty rule file."""
    plugin_root = tmp_path / "demo"
    (plugin_root / "rules").mkdir(parents=True)
    (plugin_root / "rules" / "good.md").write_text("- real content")
    (plugin_root / "rules" / "empty.md").write_text("   \n")  # empty after strip — ignored
    (plugin_root / "skills" / "s1").mkdir(parents=True)
    (plugin_root / "skills" / "s1" / "SKILL.md").write_text("# skill")
    (plugin_root / "skills" / "loose").write_text("not a dir entry")
    (plugin_root / "fragment.md").write_text("extra")
    (plugin_root / "README.md").write_text("SKIPPED")

    configs = tmp_path / "configs"
    configs.mkdir()

    def _append(fn: str, content: str) -> None:
        with open(configs / fn, "a") as f:
            f.write(content + "\n")

    ctx = InstallContext(
        configs_dir=configs, workspace_id="w", runtime="claude_code",
        plugin_root=plugin_root, append_to_memory=_append,
        logger=logging.getLogger("test"),
    )
    adaptor = GenericPluginAdaptor("demo", "claude_code")
    result = await adaptor.install(ctx)

    text = (configs / "CLAUDE.md").read_text()
    assert "# Plugin: demo / rule: good.md" in text
    assert "# Plugin: demo / rule: empty.md" not in text  # empty skipped
    assert "# Plugin: demo / fragment: fragment.md" in text
    assert "# Plugin: demo / fragment: README.md" not in text  # skip-listed
    assert (configs / "skills" / "s1" / "SKILL.md").exists()
    assert len(result.files_written) >= 1

    # Uninstall — strips markers, removes skills.
    await adaptor.uninstall(ctx)
    assert not (configs / "skills" / "s1").exists()
    assert "# Plugin: demo /" not in (configs / "CLAUDE.md").read_text()


async def test_generic_adaptor_skips_existing_skill_dir(tmp_path: Path):
    """Idempotency: a skill dir already at /configs/skills/<name>/ isn't clobbered."""
    plugin_root = tmp_path / "demo"
    (plugin_root / "skills" / "s1").mkdir(parents=True)
    (plugin_root / "skills" / "s1" / "SKILL.md").write_text("# from plugin")

    configs = tmp_path / "configs"
    (configs / "skills" / "s1").mkdir(parents=True)
    (configs / "skills" / "s1" / "SKILL.md").write_text("# user wrote this")

    ctx = InstallContext(
        configs_dir=configs, workspace_id="w", runtime="claude_code",
        plugin_root=plugin_root,
    )
    await GenericPluginAdaptor("demo", "claude_code").install(ctx)
    # Pre-existing content preserved.
    assert (configs / "skills" / "s1" / "SKILL.md").read_text() == "# user wrote this"


async def test_generic_adaptor_uninstall_when_nothing_installed(tmp_path: Path):
    configs = tmp_path / "configs"
    configs.mkdir()
    plugin_root = tmp_path / "bare"
    plugin_root.mkdir()
    ctx = InstallContext(
        configs_dir=configs, workspace_id="w", runtime="claude_code",
        plugin_root=plugin_root,
    )
    # Should not raise even with no CLAUDE.md and no skills/
    await GenericPluginAdaptor("bare", "claude_code").uninstall(ctx)
