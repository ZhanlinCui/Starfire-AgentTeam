"""Load skill packages from the workspace config directory."""

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    from builtin_tools.security_scan import SkillSecurityError, scan_skill_dependencies
    _SECURITY_SCAN_AVAILABLE = True
except ImportError:  # lightweight test environments without tools/ on sys.path
    _SECURITY_SCAN_AVAILABLE = False


@dataclass
class SkillMetadata:
    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


@dataclass
class LoadedSkill:
    metadata: SkillMetadata
    instructions: str
    tools: list[Any] = field(default_factory=list)


def parse_skill_frontmatter(skill_md_path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a SKILL.md file."""
    content = skill_md_path.read_text()

    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return frontmatter, body


def load_skill_tools(tools_dir: Path) -> list[Any]:
    """Dynamically load tool functions from a skill's scripts/ directory.

    (Legacy `tools/` dir is no longer supported — skills must use the
    agentskills.io spec layout with `scripts/`.)
    """
    tools = []
    if not tools_dir.exists():
        return tools

    # Import langchain only when we actually have scripts to process.
    # Keeps test environments (and empty skills) from needing langchain.
    from langchain_core.tools import BaseTool

    for py_file in sorted(tools_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        module_name = f"skill_tool_{py_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Look for functions decorated with @tool (BaseTool instances)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, BaseTool):
                tools.append(attr)

    return tools


def load_skills(config_path: str, skill_names: list[str]) -> list[LoadedSkill]:
    """Load all skills specified in the config."""
    skills_dir = Path(config_path) / "skills"
    loaded = []

    # Resolve security scan mode once before the loop
    scan_mode = "warn"
    if _SECURITY_SCAN_AVAILABLE:
        try:
            from config import load_config
            _cfg = load_config(config_path)
            scan_mode = _cfg.security_scan.mode
        except Exception:
            pass  # use default "warn" — never block on config error

    for skill_name in skill_names:
        skill_path = skills_dir / skill_name
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            print(f"Warning: SKILL.md not found for {skill_name}, skipping")
            continue

        # --- Security scan before loading any code from the skill ------------
        if _SECURITY_SCAN_AVAILABLE and scan_mode != "off":
            try:
                scan_skill_dependencies(skill_name, skill_path, scan_mode)
            except SkillSecurityError as exc:
                print(f"Skipping skill '{skill_name}': blocked by security scan — {exc}")
                continue

        frontmatter, instructions = parse_skill_frontmatter(skill_md)

        metadata = SkillMetadata(
            id=skill_name,
            name=frontmatter.get("name", skill_name),
            description=frontmatter.get("description", ""),
            tags=frontmatter.get("tags", []),
            examples=frontmatter.get("examples", []),
        )

        # Executables live under scripts/ per the agentskills.io spec.
        tools = load_skill_tools(skill_path / "scripts")

        loaded.append(LoadedSkill(
            metadata=metadata,
            instructions=instructions,
            tools=tools,
        ))

    return loaded
