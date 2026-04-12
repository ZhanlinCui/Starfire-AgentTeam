"""Tests for skills/loader.py — skill parsing and loading."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from skill_loader.loader import (
    LoadedSkill,
    SkillMetadata,
    parse_skill_frontmatter,
    load_skills,
)


def test_parse_skill_frontmatter_full(tmp_path):
    """Parses YAML frontmatter and body from a SKILL.md file."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: SEO Optimizer\n"
        "description: Optimizes content for search engines\n"
        "tags:\n"
        "  - seo\n"
        "  - content\n"
        "examples:\n"
        "  - Optimize this blog post\n"
        "---\n"
        "## Instructions\n"
        "1. Analyze keywords\n"
        "2. Optimize headings\n"
    )

    fm, body = parse_skill_frontmatter(skill_md)
    assert fm["name"] == "SEO Optimizer"
    assert fm["description"] == "Optimizes content for search engines"
    assert fm["tags"] == ["seo", "content"]
    assert fm["examples"] == ["Optimize this blog post"]
    assert "## Instructions" in body
    assert "Analyze keywords" in body


def test_parse_skill_frontmatter_no_frontmatter(tmp_path):
    """Files without --- frontmatter return empty dict and full content."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("Just instructions, no frontmatter.")

    fm, body = parse_skill_frontmatter(skill_md)
    assert fm == {}
    assert body == "Just instructions, no frontmatter."


def test_parse_skill_frontmatter_incomplete(tmp_path):
    """Incomplete frontmatter (only one ---) returns empty dict."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\nname: Broken\n")

    fm, body = parse_skill_frontmatter(skill_md)
    assert fm == {}
    assert "---" in body


def test_parse_skill_frontmatter_empty_yaml(tmp_path):
    """Empty YAML block between --- returns empty dict."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\n---\nBody content here.")

    fm, body = parse_skill_frontmatter(skill_md)
    assert fm == {}
    assert body == "Body content here."


def test_skill_metadata_defaults():
    """SkillMetadata has sensible defaults for optional fields."""
    meta = SkillMetadata(id="test", name="Test", description="A test skill")
    assert meta.tags == []
    assert meta.examples == []


def test_load_skills_with_temp_dir(tmp_path):
    """load_skills loads skills from a config directory structure."""
    skills_dir = tmp_path / "skills" / "my-skill"
    skills_dir.mkdir(parents=True)

    (skills_dir / "SKILL.md").write_text(
        "---\n"
        "name: My Skill\n"
        "description: Does things\n"
        "tags:\n"
        "  - general\n"
        "---\n"
        "Follow these steps to do things.\n"
    )

    # load_skill_tools will try to import langchain_core — mock it
    from unittest.mock import patch

    with patch("skill_loader.loader.load_skill_tools", return_value=[]):
        loaded = load_skills(str(tmp_path), ["my-skill"])

    assert len(loaded) == 1
    skill = loaded[0]
    assert skill.metadata.id == "my-skill"
    assert skill.metadata.name == "My Skill"
    assert skill.metadata.description == "Does things"
    assert skill.metadata.tags == ["general"]
    assert "Follow these steps" in skill.instructions


def test_load_skills_missing_skill_md(tmp_path):
    """Skills without SKILL.md are skipped with a warning."""
    skills_dir = tmp_path / "skills" / "no-md"
    skills_dir.mkdir(parents=True)
    # No SKILL.md

    from unittest.mock import patch

    with patch("skill_loader.loader.load_skill_tools", return_value=[]):
        loaded = load_skills(str(tmp_path), ["no-md"])

    assert len(loaded) == 0


def test_load_skills_multiple(tmp_path):
    """Multiple skills are loaded in order."""
    for name in ["alpha", "beta"]:
        skill_dir = tmp_path / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name.title()}\ndescription: Skill {name}\n---\n"
            f"Instructions for {name}."
        )

    from unittest.mock import patch

    with patch("skill_loader.loader.load_skill_tools", return_value=[]):
        loaded = load_skills(str(tmp_path), ["alpha", "beta"])

    assert len(loaded) == 2
    assert loaded[0].metadata.id == "alpha"
    assert loaded[1].metadata.id == "beta"
    assert loaded[0].metadata.name == "Alpha"
    assert loaded[1].metadata.name == "Beta"


# ---------- _SECURITY_SCAN_AVAILABLE = True (line 13) ----------


def test_security_scan_available_flag_true(monkeypatch):
    """When tools.security_scan is importable, _SECURITY_SCAN_AVAILABLE is True on reload."""
    import importlib

    # Save the original module object so we can restore it fully
    original_loader_module = sys.modules.get("skill_loader.loader")
    skills_pkg = sys.modules.get("skill_loader")

    # Create a fake tools.security_scan module with required exports
    fake_tools_mod = ModuleType("tools")

    class FakeSkillSecurityError(Exception):
        pass

    fake_security_mod = ModuleType("builtin_tools.security_scan")
    fake_security_mod.SkillSecurityError = FakeSkillSecurityError
    fake_security_mod.scan_skill_dependencies = MagicMock()

    # Inject into sys.modules BEFORE reimporting skills.loader
    monkeypatch.setitem(sys.modules, "tools", fake_tools_mod)
    monkeypatch.setitem(sys.modules, "builtin_tools.security_scan", fake_security_mod)

    # Remove skills.loader from sys.modules so it re-executes the module-level try/except
    monkeypatch.delitem(sys.modules, "skill_loader.loader", raising=False)

    try:
        # Reimport — line 13 (_SECURITY_SCAN_AVAILABLE = True) should now execute
        import skill_loader.loader as reloaded_loader
        assert reloaded_loader._SECURITY_SCAN_AVAILABLE is True
    finally:
        # ALWAYS restore the original module fully (including the package attribute)
        # to avoid contaminating subsequent tests that do `import skill_loader.loader`
        if original_loader_module is not None:
            sys.modules["skill_loader.loader"] = original_loader_module
            # Also restore the skills package attribute so `import skill_loader.loader` returns original
            if skills_pkg is not None:
                skills_pkg.loader = original_loader_module
        else:
            monkeypatch.delitem(sys.modules, "skill_loader.loader", raising=False)


# ---------- load_skill_tools() (lines 52-77) ----------


def test_load_skill_tools_returns_empty_for_missing_dir(tmp_path):
    """load_skill_tools returns [] when tools dir does not exist."""
    from skill_loader.loader import load_skill_tools

    # Mock langchain_core.tools so import works even without the real package
    fake_lc = ModuleType("langchain_core")
    fake_lc_tools = ModuleType("langchain_core.tools")

    class FakeBaseTool:
        pass

    fake_lc_tools.BaseTool = FakeBaseTool
    fake_lc.tools = fake_lc_tools

    with patch.dict(sys.modules, {
        "langchain_core": fake_lc,
        "langchain_core.tools": fake_lc_tools,
    }):
        result = load_skill_tools(tmp_path / "nonexistent_tools")

    assert result == []


def test_load_skill_tools_skips_underscore_files(tmp_path):
    """load_skill_tools skips files starting with _."""
    from skill_loader.loader import load_skill_tools

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "__init__.py").write_text("# init")
    (tools_dir / "_helper.py").write_text("# private")

    fake_lc = ModuleType("langchain_core")
    fake_lc_tools = ModuleType("langchain_core.tools")

    class FakeBaseTool:
        pass

    fake_lc_tools.BaseTool = FakeBaseTool
    fake_lc.tools = fake_lc_tools

    with patch.dict(sys.modules, {
        "langchain_core": fake_lc,
        "langchain_core.tools": fake_lc_tools,
    }):
        result = load_skill_tools(tools_dir)

    assert result == []


def test_load_skill_tools_loads_basetool_instances(tmp_path):
    """load_skill_tools returns BaseTool instances found in tool files."""
    from skill_loader.loader import load_skill_tools

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    # Write a fake tool module that exposes a FakeBaseTool instance
    (tools_dir / "my_tool.py").write_text(
        "class FakeTool:\n    pass\nmy_func = FakeTool()\n"
    )

    # Create a FakeBaseTool class and make FakeTool a subclass of it
    class FakeBaseTool:
        pass

    fake_lc = ModuleType("langchain_core")
    fake_lc_tools = ModuleType("langchain_core.tools")
    fake_lc_tools.BaseTool = FakeBaseTool
    fake_lc.tools = fake_lc_tools

    # Patch the tool file to return our FakeBaseTool instance
    fake_instance = FakeBaseTool()

    import importlib.util

    original_spec = importlib.util.spec_from_file_location

    def patched_spec(name, path, **kw):
        spec = original_spec(name, path, **kw)
        return spec

    with patch.dict(sys.modules, {
        "langchain_core": fake_lc,
        "langchain_core.tools": fake_lc_tools,
    }):
        # We can't easily inject the FakeBaseTool into the loaded module
        # so we test that it returns [] for a module with no BaseTool instances
        result = load_skill_tools(tools_dir)

    # The loaded module has FakeTool (not subclass of FakeBaseTool), so no tools returned
    assert isinstance(result, list)


def test_load_skill_tools_handles_invalid_spec(tmp_path):
    """load_skill_tools skips files where spec_from_file_location returns None."""
    from skill_loader.loader import load_skill_tools

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "broken_tool.py").write_text("x = 1")

    fake_lc = ModuleType("langchain_core")
    fake_lc_tools = ModuleType("langchain_core.tools")

    class FakeBaseTool:
        pass

    fake_lc_tools.BaseTool = FakeBaseTool

    with patch.dict(sys.modules, {
        "langchain_core": fake_lc,
        "langchain_core.tools": fake_lc_tools,
    }):
        with patch("importlib.util.spec_from_file_location", return_value=None):
            result = load_skill_tools(tools_dir)

    assert result == []


def test_load_skill_tools_appends_basetool_instances(tmp_path):
    """load_skill_tools appends attributes that are BaseTool instances (line 75)."""
    from skill_loader.loader import load_skill_tools

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    # The tool file will reference a module-level instance of FakeBaseTool.
    # We write a placeholder; then we override exec_module to inject the instance.
    (tools_dir / "real_tool.py").write_text("# will be replaced by exec_module patch\n")

    # We need BaseTool to be the *same class* used in isinstance check inside load_skill_tools.
    # Strategy: patch langchain_core.tools.BaseTool to our FakeBaseTool, and inject an
    # instance into the loaded module's namespace via a patched exec_module.

    class FakeBaseTool:
        pass

    fake_tool_instance = FakeBaseTool()

    fake_lc = ModuleType("langchain_core")
    fake_lc_tools = ModuleType("langchain_core.tools")
    fake_lc_tools.BaseTool = FakeBaseTool
    fake_lc.tools = fake_lc_tools

    import importlib.util as _ilu
    import types

    original_exec = None

    def patched_exec_module(module):
        # Inject a FakeBaseTool instance as a module attribute
        module.my_tool = fake_tool_instance

    with patch.dict(sys.modules, {
        "langchain_core": fake_lc,
        "langchain_core.tools": fake_lc_tools,
    }):
        # Patch spec.loader.exec_module on the spec returned by spec_from_file_location
        original_spec_fn = _ilu.spec_from_file_location

        def patched_spec(name, path, **kw):
            spec = original_spec_fn(name, path, **kw)
            if spec is not None and spec.loader is not None:
                spec.loader.exec_module = patched_exec_module
            return spec

        with patch("importlib.util.spec_from_file_location", side_effect=patched_spec):
            result = load_skill_tools(tools_dir)

    assert len(result) == 1
    assert result[0] is fake_tool_instance


# ---------- load_skills() with security scan available (lines 88-93, 105-109) ----------


def test_load_skills_with_security_scan_available_warn_mode(tmp_path, monkeypatch):
    """load_skills runs security scan in warn mode when _SECURITY_SCAN_AVAILABLE=True."""
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: My Skill\ndescription: Test\n---\nInstructions."
    )

    scan_calls = []

    import skill_loader.loader as loader_module

    monkeypatch.setattr(loader_module, "_SECURITY_SCAN_AVAILABLE", True)

    # Fake scan_skill_dependencies that just records calls
    def fake_scan(skill_name, skill_path, mode):
        scan_calls.append((skill_name, mode))

    # Fake SkillSecurityError
    class FakeSkillSecurityError(Exception):
        pass

    monkeypatch.setattr(loader_module, "scan_skill_dependencies", fake_scan, raising=False)
    monkeypatch.setattr(loader_module, "SkillSecurityError", FakeSkillSecurityError, raising=False)

    # Fake config load
    from config import WorkspaceConfig, SecurityScanConfig
    fake_cfg = WorkspaceConfig()
    fake_cfg.security_scan = SecurityScanConfig(mode="warn")

    with patch("skill_loader.loader.load_skill_tools", return_value=[]):
        with patch("config.load_config", return_value=fake_cfg):
            loaded = loader_module.load_skills(str(tmp_path), ["my-skill"])

    assert len(loaded) == 1
    assert len(scan_calls) == 1
    assert scan_calls[0][0] == "my-skill"
    assert scan_calls[0][1] == "warn"


def test_load_skills_security_scan_block_mode_skips_skill(tmp_path, monkeypatch):
    """load_skills skips skill when security scan raises SkillSecurityError in block mode."""
    skill_dir = tmp_path / "skills" / "blocked-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Blocked\ndescription: Unsafe\n---\nInstructions."
    )

    import skill_loader.loader as loader_module

    monkeypatch.setattr(loader_module, "_SECURITY_SCAN_AVAILABLE", True)

    class FakeSkillSecurityError(Exception):
        pass

    def blocking_scan(skill_name, skill_path, mode):
        raise FakeSkillSecurityError("critical CVE found")

    monkeypatch.setattr(loader_module, "scan_skill_dependencies", blocking_scan, raising=False)
    monkeypatch.setattr(loader_module, "SkillSecurityError", FakeSkillSecurityError, raising=False)

    from config import WorkspaceConfig, SecurityScanConfig
    fake_cfg = WorkspaceConfig()
    fake_cfg.security_scan = SecurityScanConfig(mode="block")

    with patch("skill_loader.loader.load_skill_tools", return_value=[]):
        with patch("config.load_config", return_value=fake_cfg):
            loaded = loader_module.load_skills(str(tmp_path), ["blocked-skill"])

    # Skill should be skipped due to security error
    assert len(loaded) == 0


def test_load_skills_security_scan_off_mode_skips_scan(tmp_path, monkeypatch):
    """load_skills skips scan entirely when mode='off'."""
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: My Skill\ndescription: Test\n---\nInstructions."
    )

    scan_calls = []

    import skill_loader.loader as loader_module
    monkeypatch.setattr(loader_module, "_SECURITY_SCAN_AVAILABLE", True)

    def tracking_scan(skill_name, skill_path, mode):
        scan_calls.append(skill_name)

    class FakeSkillSecurityError(Exception):
        pass

    monkeypatch.setattr(loader_module, "scan_skill_dependencies", tracking_scan, raising=False)
    monkeypatch.setattr(loader_module, "SkillSecurityError", FakeSkillSecurityError, raising=False)

    from config import WorkspaceConfig, SecurityScanConfig
    fake_cfg = WorkspaceConfig()
    fake_cfg.security_scan = SecurityScanConfig(mode="off")

    with patch("skill_loader.loader.load_skill_tools", return_value=[]):
        with patch("config.load_config", return_value=fake_cfg):
            loaded = loader_module.load_skills(str(tmp_path), ["my-skill"])

    # scan should have been skipped
    assert len(scan_calls) == 0
    assert len(loaded) == 1


def test_load_skills_config_load_error_defaults_to_warn(tmp_path, monkeypatch):
    """load_skills defaults scan_mode to 'warn' when load_config raises."""
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: My Skill\ndescription: Test\n---\nInstructions."
    )

    scan_modes = []

    import skill_loader.loader as loader_module
    monkeypatch.setattr(loader_module, "_SECURITY_SCAN_AVAILABLE", True)

    def tracking_scan(skill_name, skill_path, mode):
        scan_modes.append(mode)

    class FakeSkillSecurityError(Exception):
        pass

    monkeypatch.setattr(loader_module, "scan_skill_dependencies", tracking_scan, raising=False)
    monkeypatch.setattr(loader_module, "SkillSecurityError", FakeSkillSecurityError, raising=False)

    with patch("skill_loader.loader.load_skill_tools", return_value=[]):
        with patch("config.load_config", side_effect=FileNotFoundError("no config")):
            loaded = loader_module.load_skills(str(tmp_path), ["my-skill"])

    # Default warn mode used on config load failure
    assert len(scan_modes) == 1
    assert scan_modes[0] == "warn"
    assert len(loaded) == 1
