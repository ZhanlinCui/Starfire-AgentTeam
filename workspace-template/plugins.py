"""Plugin system for loading shared skills, rules, and prompt fragments.

Plugins are directories in /plugins/ (inside the container) that contain
skills, rules, and prompt files from external agent frameworks like
Everything Claude Code and Superpowers.

The plugin loader:
1. Scans /plugins/ for installed plugins
2. Loads rules/*.md as always-on guidelines injected into every prompt
3. Loads skills with tools that are available to all workspaces
4. Returns them for merging into the workspace's own skills/prompt
"""

import logging
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

PLUGINS_DIR = os.environ.get("PLUGINS_DIR", "/plugins")


@dataclass
class Plugin:
    name: str
    path: str
    rules: list[str] = field(default_factory=list)  # rule content strings
    prompt_fragments: list[str] = field(default_factory=list)  # extra prompt content
    skills_dir: str = ""  # path to skills/ inside plugin


@dataclass
class LoadedPlugins:
    rules: list[str] = field(default_factory=list)
    prompt_fragments: list[str] = field(default_factory=list)
    skill_dirs: list[str] = field(default_factory=list)  # dirs to scan for extra skills
    plugin_names: list[str] = field(default_factory=list)


def load_plugins(plugins_dir: str | None = None) -> LoadedPlugins:
    """Scan plugins directory and load all installed plugins."""
    base = plugins_dir or PLUGINS_DIR
    result = LoadedPlugins()

    if not os.path.isdir(base):
        return result

    for entry in sorted(os.listdir(base)):
        plugin_path = os.path.join(base, entry)
        if not os.path.isdir(plugin_path):
            continue

        plugin = Plugin(name=entry, path=plugin_path)

        # Load rules
        rules_dir = os.path.join(plugin_path, "rules")
        if os.path.isdir(rules_dir):
            for rule_file in sorted(os.listdir(rules_dir)):
                if rule_file.endswith(".md"):
                    content = Path(os.path.join(rules_dir, rule_file)).read_text().strip()
                    if content:
                        plugin.rules.append(content)
                        logger.info("Plugin %s: loaded rule %s", entry, rule_file)

        # Load prompt fragments (any .md in root of plugin)
        for f in sorted(os.listdir(plugin_path)):
            if f.endswith(".md") and os.path.isfile(os.path.join(plugin_path, f)):
                # Skip README and non-prompt files
                if f.lower() in ("readme.md", "changelog.md", "license.md", "contributing.md"):
                    continue
                content = Path(os.path.join(plugin_path, f)).read_text().strip()
                if content and len(content) > 50:  # skip trivially small files
                    plugin.prompt_fragments.append(content)
                    logger.info("Plugin %s: loaded prompt fragment %s", entry, f)

        # Register skills directory
        skills_dir = os.path.join(plugin_path, "skills")
        if os.path.isdir(skills_dir):
            plugin.skills_dir = skills_dir
            result.skill_dirs.append(skills_dir)
            skill_count = len([d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d))])
            logger.info("Plugin %s: found %d skills", entry, skill_count)

        result.rules.extend(plugin.rules)
        result.prompt_fragments.extend(plugin.prompt_fragments)
        result.plugin_names.append(entry)

    if result.plugin_names:
        logger.info("Loaded %d plugins: %s", len(result.plugin_names), ", ".join(result.plugin_names))

    return result
