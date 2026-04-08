"""Tests for preflight.py — workspace startup checks."""

from config import A2AConfig, RuntimeConfig, WorkspaceConfig
from preflight import run_preflight


def make_config(**overrides):
    """Build a minimal workspace config for preflight tests."""
    base = WorkspaceConfig(
        name="Test Workspace",
        runtime="langgraph",
        runtime_config=RuntimeConfig(),
        skills=[],
        prompt_files=[],
        a2a=A2AConfig(port=8000),
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_run_preflight_supported_runtime_passes(tmp_path):
    """A supported runtime with present files should pass cleanly."""
    (tmp_path / "system-prompt.md").write_text("Base prompt.")
    (tmp_path / "skills").mkdir()

    config = make_config(
        prompt_files=["system-prompt.md"],
        skills=[],
    )

    report = run_preflight(config, str(tmp_path))

    assert report.ok is True
    assert report.failures == []
    assert report.warnings == []


def test_run_preflight_unsupported_runtime_fails(tmp_path):
    """Unsupported runtimes should fail before startup."""
    (tmp_path / "system-prompt.md").write_text("Base prompt.")

    config = make_config(
        runtime="not-a-runtime",
        prompt_files=["system-prompt.md"],
    )

    report = run_preflight(config, str(tmp_path))

    assert report.ok is False
    assert any(issue.title == "Runtime" for issue in report.failures)


def test_run_preflight_missing_auth_token_fails(tmp_path):
    """Missing auth token files should stop startup."""
    (tmp_path / "system-prompt.md").write_text("Base prompt.")

    config = make_config(
        runtime_config=RuntimeConfig(auth_token_file="secrets/token.txt"),
        prompt_files=["system-prompt.md"],
    )

    report = run_preflight(config, str(tmp_path))

    assert report.ok is False
    assert any(issue.title == "Auth token" for issue in report.failures)


def test_run_preflight_missing_prompts_and_skills_warn(tmp_path):
    """Missing prompt files and skills should warn, not fail."""
    config = make_config(
        prompt_files=["missing-prompt.md"],
        skills=["missing-skill"],
    )

    report = run_preflight(config, str(tmp_path))

    assert report.ok is True
    assert report.failures == []
    assert any(issue.title == "Prompt file" for issue in report.warnings)
    assert any(issue.title == "Skill" for issue in report.warnings)


def test_run_preflight_valid_config_passes(tmp_path):
    """A fully populated config should pass with no issues."""
    (tmp_path / "system-prompt.md").write_text("Base prompt.")
    skill_dir = tmp_path / "skills" / "writing"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("Write clearly.")

    config = make_config(
        prompt_files=["system-prompt.md"],
        skills=["writing"],
        runtime_config=RuntimeConfig(auth_token_file=""),
    )

    report = run_preflight(config, str(tmp_path))

    assert report.ok is True
    assert report.failures == []
    assert report.warnings == []
