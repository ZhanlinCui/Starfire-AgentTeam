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
    parse_skill_md,
    validate_manifest,
    validate_plugin,
    validate_skill,
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


# ---------------------------------------------------------------------------
# agentskills.io SKILL.md validation
# ---------------------------------------------------------------------------


def _write_skill(dir: Path, name: str, content: str) -> Path:
    skill = dir / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(content)
    return skill


def test_parse_skill_md_missing_file(tmp_path: Path):
    fm, body, errs = parse_skill_md(tmp_path / "missing.md")
    assert fm == {}
    assert any("not found" in e for e in errs)


def test_parse_skill_md_missing_frontmatter(tmp_path: Path):
    p = tmp_path / "SKILL.md"
    p.write_text("no frontmatter at all")
    fm, body, errs = parse_skill_md(p)
    assert fm == {}
    assert any("frontmatter" in e for e in errs)


def test_parse_skill_md_malformed_frontmatter(tmp_path: Path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: foo\n")
    _, _, errs = parse_skill_md(p)
    assert any("malformed" in e for e in errs)


def test_parse_skill_md_yaml_parse_error(tmp_path: Path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\n: bad\nfoo: [unclosed\n---\nbody")
    _, _, errs = parse_skill_md(p)
    assert any("yaml parse error" in e for e in errs)


def test_parse_skill_md_non_mapping_frontmatter(tmp_path: Path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\n- a\n- b\n---\nbody")
    _, _, errs = parse_skill_md(p)
    assert any("mapping" in e for e in errs)


def test_validate_skill_accepts_minimal(tmp_path: Path):
    skill = _write_skill(tmp_path, "good-skill", "---\nname: good-skill\ndescription: Does something useful.\n---\nbody")
    assert validate_skill(skill) == []


def test_validate_skill_requires_name(tmp_path: Path):
    skill = _write_skill(tmp_path, "foo", "---\ndescription: x\n---\n")
    errs = validate_skill(skill)
    assert any("name" in e and "required" in e for e in errs)


def test_validate_skill_requires_description(tmp_path: Path):
    skill = _write_skill(tmp_path, "foo", "---\nname: foo\n---\n")
    errs = validate_skill(skill)
    assert any("description" in e and "required" in e for e in errs)


def test_validate_skill_name_must_match_dir(tmp_path: Path):
    skill = _write_skill(tmp_path, "dir-name", "---\nname: different\ndescription: x\n---\n")
    errs = validate_skill(skill)
    assert any("match directory name" in e for e in errs)


def test_validate_skill_name_uppercase_rejected(tmp_path: Path):
    skill = _write_skill(tmp_path, "BadName", "---\nname: BadName\ndescription: x\n---\n")
    errs = validate_skill(skill)
    assert any("lowercase" in e for e in errs)


def test_validate_skill_name_leading_hyphen_rejected(tmp_path: Path):
    skill = _write_skill(tmp_path, "-foo", "---\nname: -foo\ndescription: x\n---\n")
    errs = validate_skill(skill)
    assert any("hyphen" in e for e in errs)


def test_validate_skill_name_consecutive_hyphens_rejected(tmp_path: Path):
    skill = _write_skill(tmp_path, "foo--bar", "---\nname: foo--bar\ndescription: x\n---\n")
    errs = validate_skill(skill)
    assert any("hyphen" in e for e in errs)


def test_validate_skill_name_too_long(tmp_path: Path):
    long = "a" * 65
    skill = _write_skill(tmp_path, long, f"---\nname: {long}\ndescription: x\n---\n")
    errs = validate_skill(skill)
    assert any("length" in e for e in errs)


def test_validate_skill_description_too_long(tmp_path: Path):
    long_desc = "x" * 1025
    skill = _write_skill(tmp_path, "foo", f"---\nname: foo\ndescription: {long_desc}\n---\n")
    errs = validate_skill(skill)
    assert any("1024" in e for e in errs)


def test_validate_skill_compatibility_too_long(tmp_path: Path):
    long = "x" * 501
    skill = _write_skill(tmp_path, "foo", f"---\nname: foo\ndescription: x\ncompatibility: {long}\n---\n")
    errs = validate_skill(skill)
    assert any("compatibility" in e.lower() and "500" in e for e in errs)


def test_validate_skill_accepts_all_optional_fields(tmp_path: Path):
    content = """---
name: full-skill
description: Does everything.
license: MIT
compatibility: Requires Python 3.14+
metadata:
  author: test
  version: "1.0"
allowed-tools: Bash(git:*) Read
---
body
"""
    skill = _write_skill(tmp_path, "full-skill", content)
    assert validate_skill(skill) == []


def test_validate_skill_metadata_must_be_mapping(tmp_path: Path):
    skill = _write_skill(tmp_path, "foo", "---\nname: foo\ndescription: x\nmetadata: str\n---\n")
    errs = validate_skill(skill)
    assert any("metadata" in e and "mapping" in e for e in errs)


def test_validate_skill_allowed_tools_must_be_string(tmp_path: Path):
    skill = _write_skill(tmp_path, "foo", "---\nname: foo\ndescription: x\nallowed-tools:\n  - Read\n---\n")
    errs = validate_skill(skill)
    assert any("allowed-tools" in e for e in errs)


def test_validate_skill_rejects_missing_dir(tmp_path: Path):
    errs = validate_skill(tmp_path / "nonexistent")
    assert any("not a directory" in e for e in errs)


def test_validate_plugin_walks_all_skills(tmp_path: Path):
    plugin = tmp_path / "p"
    plugin.mkdir()
    (plugin / "plugin.yaml").write_text("name: p\n")
    (plugin / "skills" / "good").mkdir(parents=True)
    (plugin / "skills" / "good" / "SKILL.md").write_text("---\nname: good\ndescription: ok\n---\n")
    (plugin / "skills" / "bad").mkdir()
    (plugin / "skills" / "bad" / "SKILL.md").write_text("---\nname: wrong-name\ndescription: ok\n---\n")

    results = validate_plugin(plugin)
    assert "plugin.yaml" not in results
    assert "skills/good" not in results
    assert "skills/bad" in results
    assert any("match" in e for e in results["skills/bad"])


def test_validate_plugin_empty_when_all_valid(tmp_path: Path):
    plugin = tmp_path / "p"
    plugin.mkdir()
    (plugin / "plugin.yaml").write_text("name: p\n")
    assert validate_plugin(plugin) == {}


def test_first_party_plugins_are_spec_compliant():
    """Every plugin in this repo must pass full agentskills.io validation."""
    repo_root = Path(__file__).resolve().parents[3]
    plugins_dir = repo_root / "plugins"
    if not plugins_dir.is_dir():
        import pytest
        pytest.skip("not in a checkout with first-party plugins")
    failures: dict = {}
    for plugin in sorted(plugins_dir.iterdir()):
        if not plugin.is_dir():
            continue
        results = validate_plugin(plugin)
        if results:
            failures[plugin.name] = results
    assert not failures, f"Spec failures: {failures}"
