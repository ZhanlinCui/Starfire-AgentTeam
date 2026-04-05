"""Tests for skills/loader.py — skill parsing and loading."""

from pathlib import Path

from skills.loader import (
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

    with patch("skills.loader.load_skill_tools", return_value=[]):
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

    with patch("skills.loader.load_skill_tools", return_value=[]):
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

    with patch("skills.loader.load_skill_tools", return_value=[]):
        loaded = load_skills(str(tmp_path), ["alpha", "beta"])

    assert len(loaded) == 2
    assert loaded[0].metadata.id == "alpha"
    assert loaded[1].metadata.id == "beta"
    assert loaded[0].metadata.name == "Alpha"
    assert loaded[1].metadata.name == "Beta"
