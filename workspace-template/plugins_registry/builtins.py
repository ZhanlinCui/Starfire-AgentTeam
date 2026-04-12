"""Generic built-in plugin adaptors for the common install patterns.

Most platform plugins fit one of two shapes:

* **Rule plugin** — ships ``rules/*.md`` that should be appended to the runtime's
  long-lived memory file (CLAUDE.md for Claude Code and DeepAgents), plus
  optional ``prompt_fragments`` also appended to memory.
* **Skill plugin** — ships ``skills/<skill_name>/`` directories (SKILL.md +
  ``tools/*.py``) that the workspace runtime already discovers via a
  filesystem scan. Install step copies the skill dirs to
  ``/configs/skills/<name>/`` so both Claude Code (which reloads that dir)
  and DeepAgents (which globs for tools) pick them up.

Most plugins are "mixed" — they have both rules and skills. :class:`GenericPluginAdaptor`
handles all three cases with the same code path; individual plugins just
import it as their per-runtime adaptor:

.. code-block:: python

    # plugins/<name>/adapters/claude_code.py
    from plugins_registry.builtins import GenericPluginAdaptor as Adaptor

Plugins that need runtime-specific behavior (e.g. a DeepAgents plugin that
registers a sub-agent) ship a custom adaptor instead.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .protocol import InstallContext, InstallResult


def _read_md_files(directory: Path) -> list[tuple[str, str]]:
    """Return [(filename, content)] for all *.md files in directory, sorted."""
    if not directory.is_dir():
        return []
    out: list[tuple[str, str]] = []
    for p in sorted(directory.iterdir()):
        if p.is_file() and p.suffix == ".md":
            out.append((p.name, p.read_text().strip()))
    return out


class GenericPluginAdaptor:
    """Filesystem-based adaptor that mirrors what the legacy
    ``claude_code.inject_plugins()`` did, but runtime-agnostic.

    On ``install()``:
      1. Rules (``rules/*.md``) → append to ``/configs/<memory_filename>``.
         Idempotent: each rule block is wrapped in a ``# Plugin: <name>`` header
         that is checked for before re-appending.
      2. Prompt fragments (``*.md`` at plugin root, excl. README/CHANGELOG/etc.)
         → same treatment.
      3. Skills (``skills/<skill_name>/``) → copied to
         ``/configs/skills/<skill_name>/`` so both Claude Code's skill loader
         and DeepAgents' ``**/*.py`` tool discovery see them.

    Uninstall reverses the file copies and strips the rule/fragment block by
    marker (best-effort — if the user edited CLAUDE.md manually, only the
    marker line itself is removed).
    """

    # Files at the plugin root that are never treated as prompt fragments.
    _SKIP_ROOT_MD = frozenset({"readme.md", "changelog.md", "license.md", "contributing.md"})

    def __init__(self, plugin_name: str, runtime: str) -> None:
        self.plugin_name = plugin_name
        self.runtime = runtime

    # ------------------------------------------------------------------
    # install
    # ------------------------------------------------------------------

    async def install(self, ctx: InstallContext) -> InstallResult:
        result = InstallResult(
            plugin_name=self.plugin_name,
            runtime=self.runtime,
            source="plugin",  # overridden by registry caller if source==registry
        )

        # 1. Rules — append to memory file.
        rules = _read_md_files(ctx.plugin_root / "rules")
        # 2. Prompt fragments — any *.md at plugin root except skip list.
        root_fragments: list[tuple[str, str]] = []
        if ctx.plugin_root.is_dir():
            for p in sorted(ctx.plugin_root.iterdir()):
                if p.is_file() and p.suffix == ".md" and p.name.lower() not in self._SKIP_ROOT_MD:
                    content = p.read_text().strip()
                    if content:
                        root_fragments.append((p.name, content))

        memory_blocks: list[str] = []
        for filename, content in rules:
            memory_blocks.append(f"# Plugin: {self.plugin_name} / rule: {filename}\n\n{content}")
        for filename, content in root_fragments:
            memory_blocks.append(f"# Plugin: {self.plugin_name} / fragment: {filename}\n\n{content}")

        if memory_blocks:
            joined = "\n\n".join(memory_blocks)
            ctx.append_to_memory("CLAUDE.md", joined)
            ctx.logger.info(
                "%s: injected %d rule+fragment block(s) into CLAUDE.md",
                self.plugin_name, len(memory_blocks),
            )

        # 3. Skills — copy each skill dir to /configs/skills/.
        src_skills_dir = ctx.plugin_root / "skills"
        if src_skills_dir.is_dir():
            dst_skills_root = ctx.configs_dir / "skills"
            dst_skills_root.mkdir(parents=True, exist_ok=True)
            copied = 0
            for entry in sorted(src_skills_dir.iterdir()):
                if not entry.is_dir():
                    continue
                dst = dst_skills_root / entry.name
                if dst.exists():
                    ctx.logger.info("%s: skill %s already present, skipping", self.plugin_name, entry.name)
                    continue
                shutil.copytree(entry, dst)
                copied += 1
                for p in dst.rglob("*"):
                    if p.is_file():
                        result.files_written.append(str(p.relative_to(ctx.configs_dir)))
            if copied:
                ctx.logger.info("%s: copied %d skill dir(s) to %s", self.plugin_name, copied, dst_skills_root)

        return result

    # ------------------------------------------------------------------
    # uninstall
    # ------------------------------------------------------------------

    async def uninstall(self, ctx: InstallContext) -> None:
        # Remove copied skill dirs.
        src_skills_dir = ctx.plugin_root / "skills"
        if src_skills_dir.is_dir():
            for entry in src_skills_dir.iterdir():
                dst = ctx.configs_dir / "skills" / entry.name
                if dst.exists() and dst.is_dir():
                    shutil.rmtree(dst)
                    ctx.logger.info("%s: removed %s", self.plugin_name, dst)

        # Best-effort strip of our markers from CLAUDE.md. Users can always
        # edit manually; we only guarantee the injected block's first line
        # is removed so re-install re-adds cleanly.
        memory_path = ctx.configs_dir / "CLAUDE.md"
        if not memory_path.exists():
            return
        text = memory_path.read_text()
        prefix = f"# Plugin: {self.plugin_name} / "
        lines = text.splitlines(keepends=True)
        kept = [line for line in lines if not line.startswith(prefix)]
        if len(kept) != len(lines):
            memory_path.write_text("".join(kept))
            ctx.logger.info("%s: stripped markers from CLAUDE.md", self.plugin_name)
