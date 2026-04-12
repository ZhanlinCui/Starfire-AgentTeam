"""Built-in sub-type adapters for the SDK.

One class per agent shape. Currently ships :class:`AgentskillsAdaptor`
(the `agentskills.io <https://agentskills.io>`_-format default); more
will be added as new shapes emerge in the ecosystem
(``MCPServerAdaptor``, ``DeepAgentsSubagentAdaptor``, ``RAGPipelineAdaptor``,
etc.).

SDK authors pick a sub-type by import:

.. code-block:: python

    # adapters/claude_code.py
    from starfire_plugin import AgentskillsAdaptor as Adaptor

Plugins whose shape doesn't match any built-in ship a custom adapter
class in Python — unlimited expressiveness, no framework constraint.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .protocol import InstallContext, InstallResult


class AgentskillsAdaptor:
    """Sub-type adaptor for `agentskills.io <https://agentskills.io>`_-format skills.

    The default adapter for the "skills + rules" shape — installs
    ``skills/<name>/SKILL.md`` into ``/configs/skills/`` (where native
    agentskills runtimes like Claude Code activate them automatically)
    and appends Starfire-level ``rules/*.md`` + root prompt fragments to
    the runtime memory file.

    Matches the behaviour of the workspace runtime's
    ``plugins_registry.builtins.AgentskillsAdaptor``. Kept as a separate
    copy here so SDK users can unit-test their plugins without installing
    the full workspace runtime.
    """

    _SKIP_ROOT_MD = frozenset({"readme.md", "changelog.md", "license.md", "contributing.md"})

    def __init__(self, plugin_name: str, runtime: str) -> None:
        self.plugin_name = plugin_name
        self.runtime = runtime

    async def install(self, ctx: InstallContext) -> InstallResult:
        result = InstallResult(plugin_name=self.plugin_name, runtime=self.runtime, source="plugin")

        rules_dir = ctx.plugin_root / "rules"
        blocks: list[str] = []
        if rules_dir.is_dir():
            for p in sorted(rules_dir.iterdir()):
                if p.is_file() and p.suffix == ".md":
                    content = p.read_text().strip()
                    if content:
                        blocks.append(f"# Plugin: {self.plugin_name} / rule: {p.name}\n\n{content}")

        if ctx.plugin_root.is_dir():
            for p in sorted(ctx.plugin_root.iterdir()):
                if p.is_file() and p.suffix == ".md" and p.name.lower() not in self._SKIP_ROOT_MD:
                    content = p.read_text().strip()
                    if content:
                        blocks.append(f"# Plugin: {self.plugin_name} / fragment: {p.name}\n\n{content}")

        if blocks:
            ctx.append_to_memory("CLAUDE.md", "\n\n".join(blocks))

        src_skills = ctx.plugin_root / "skills"
        if src_skills.is_dir():
            dst_root = ctx.configs_dir / "skills"
            dst_root.mkdir(parents=True, exist_ok=True)
            for entry in sorted(src_skills.iterdir()):
                if not entry.is_dir():
                    continue
                dst = dst_root / entry.name
                if dst.exists():
                    continue
                shutil.copytree(entry, dst)
                for p in dst.rglob("*"):
                    if p.is_file():
                        result.files_written.append(str(p.relative_to(ctx.configs_dir)))

        return result

    async def uninstall(self, ctx: InstallContext) -> None:
        src_skills = ctx.plugin_root / "skills"
        if src_skills.is_dir():
            for entry in src_skills.iterdir():
                dst = ctx.configs_dir / "skills" / entry.name
                if dst.exists() and dst.is_dir():
                    shutil.rmtree(dst)

        memory_path = ctx.configs_dir / "CLAUDE.md"
        if memory_path.exists():
            prefix = f"# Plugin: {self.plugin_name} / "
            kept = [ln for ln in memory_path.read_text().splitlines(keepends=True) if not ln.startswith(prefix)]
            memory_path.write_text("".join(kept))


