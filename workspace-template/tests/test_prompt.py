"""Tests for prompt.py — system prompt construction."""

from pathlib import Path

from skills.loader import LoadedSkill, SkillMetadata
from prompt import build_system_prompt


def test_build_system_prompt_with_prompt_files(tmp_path):
    """Prompt files are loaded in order and concatenated."""
    (tmp_path / "SOUL.md").write_text("You are a helpful agent.")
    (tmp_path / "TOOLS.md").write_text("You have these tools.")

    result = build_system_prompt(
        config_path=str(tmp_path),
        workspace_id="ws-1",
        loaded_skills=[],
        peers=[],
        prompt_files=["SOUL.md", "TOOLS.md"],
    )

    assert "You are a helpful agent." in result
    assert "You have these tools." in result
    # SOUL.md should appear before TOOLS.md
    assert result.index("helpful agent") < result.index("these tools")


def test_build_system_prompt_default_fallback(tmp_path):
    """Without prompt_files, falls back to system-prompt.md."""
    (tmp_path / "system-prompt.md").write_text("Default system prompt content.")

    result = build_system_prompt(
        config_path=str(tmp_path),
        workspace_id="ws-1",
        loaded_skills=[],
        peers=[],
    )

    assert "Default system prompt content." in result


def test_build_system_prompt_missing_file(tmp_path):
    """Missing prompt files are skipped with a warning (no crash)."""
    result = build_system_prompt(
        config_path=str(tmp_path),
        workspace_id="ws-1",
        loaded_skills=[],
        peers=[],
        prompt_files=["nonexistent.md"],
    )

    # Should still contain the delegation failure section
    assert "Handling delegation failures" in result


def test_plugin_rules_injection(tmp_path):
    """Plugin rules are injected under '## Platform Rules'."""
    (tmp_path / "system-prompt.md").write_text("Base prompt.")

    result = build_system_prompt(
        config_path=str(tmp_path),
        workspace_id="ws-1",
        loaded_skills=[],
        peers=[],
        plugin_rules=["Always be concise.", "Never reveal secrets."],
    )

    assert "## Platform Rules" in result
    assert "Always be concise." in result
    assert "Never reveal secrets." in result


def test_plugin_prompts_injection(tmp_path):
    """Plugin prompts are injected under '## Platform Guidelines'."""
    (tmp_path / "system-prompt.md").write_text("Base prompt.")

    result = build_system_prompt(
        config_path=str(tmp_path),
        workspace_id="ws-1",
        loaded_skills=[],
        peers=[],
        plugin_prompts=["Use markdown formatting."],
    )

    assert "## Platform Guidelines" in result
    assert "Use markdown formatting." in result


def test_skills_listing(tmp_path):
    """Loaded skills appear with name, description, and instructions."""
    (tmp_path / "system-prompt.md").write_text("Base.")

    skills = [
        LoadedSkill(
            metadata=SkillMetadata(
                id="seo",
                name="SEO Optimization",
                description="Optimize content for search engines.",
                tags=["seo"],
                examples=["Optimize this blog post"],
            ),
            instructions="1. Analyze keywords\n2. Optimize headings",
        ),
        LoadedSkill(
            metadata=SkillMetadata(
                id="writing",
                name="Creative Writing",
                description="",
            ),
            instructions="Write creatively.",
        ),
    ]

    result = build_system_prompt(
        config_path=str(tmp_path),
        workspace_id="ws-1",
        loaded_skills=skills,
        peers=[],
    )

    assert "## Your Skills" in result
    assert "### SEO Optimization" in result
    assert "Optimize content for search engines." in result
    assert "1. Analyze keywords" in result
    assert "### Creative Writing" in result
    assert "Write creatively." in result


def test_peer_capabilities_format(tmp_path):
    """Peers appear with name, id, status, and skills."""
    (tmp_path / "system-prompt.md").write_text("Base.")

    peers = [
        {
            "id": "peer-1",
            "name": "Echo Agent",
            "status": "online",
            "agent_card": {
                "name": "Echo Agent",
                "skills": [
                    {"name": "echo", "id": "echo"},
                    {"name": "repeat", "id": "repeat"},
                ],
            },
        },
        {
            "id": "peer-2",
            "name": "Silent Agent",
            "status": "offline",
            "agent_card": None,
        },
    ]

    result = build_system_prompt(
        config_path=str(tmp_path),
        workspace_id="ws-1",
        loaded_skills=[],
        peers=peers,
    )

    assert "## Your Peers" in result
    assert "**Echo Agent** (id: `peer-1`, status: online)" in result
    assert "Skills: echo, repeat" in result
    assert "delegate_to_workspace" in result
    # peer-2 has no agent_card so it's skipped
    assert "Silent Agent" not in result


def test_peer_with_json_string_agent_card(tmp_path):
    """agent_card as a JSON string is parsed correctly."""
    import json

    (tmp_path / "system-prompt.md").write_text("Base.")

    peers = [
        {
            "id": "peer-3",
            "name": "JSON Peer",
            "status": "online",
            "agent_card": json.dumps({
                "name": "JSON Peer",
                "skills": [{"name": "parse"}],
            }),
        },
    ]

    result = build_system_prompt(
        config_path=str(tmp_path),
        workspace_id="ws-1",
        loaded_skills=[],
        peers=peers,
    )

    assert "**JSON Peer** (id: `peer-3`, status: online)" in result
    assert "Skills: parse" in result


def test_delegation_failure_section_always_present(tmp_path):
    """The delegation failure handling section is always appended."""
    (tmp_path / "system-prompt.md").write_text("Base.")

    result = build_system_prompt(
        config_path=str(tmp_path),
        workspace_id="ws-1",
        loaded_skills=[],
        peers=[],
    )

    assert "## Handling delegation failures" in result
    assert "Retry transient failures" in result
