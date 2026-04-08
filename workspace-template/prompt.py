"""Build the system prompt for the workspace agent."""

import json
from pathlib import Path

from skills.loader import LoadedSkill

DEFAULT_MEMORY_SNAPSHOT_FILES = ("MEMORY.md", "USER.md")


async def get_peer_capabilities(platform_url: str, workspace_id: str) -> list[dict]:
    """Fetch peer workspace capabilities from the platform."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{platform_url}/registry/{workspace_id}/peers",
                headers={"X-Workspace-ID": workspace_id},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"Warning: could not fetch peers: {e}")
    return []


def build_system_prompt(
    config_path: str,
    workspace_id: str,
    loaded_skills: list[LoadedSkill],
    peers: list[dict],
    prompt_files: list[str] | None = None,
    plugin_rules: list[str] | None = None,
    plugin_prompts: list[str] | None = None,
    parent_context: list[dict] | None = None,
) -> str:
    """Build the complete system prompt.

    Loads prompt files in order from config_path. If prompt_files is specified
    in config.yaml, those files are loaded in order. Otherwise falls back to
    system-prompt.md for backwards compatibility.
    If MEMORY.md or USER.md exist alongside the config, they are appended as a
    frozen memory snapshot without needing to list them explicitly.

    This allows different agent frameworks to use their own file structures:
    - OpenClaw: SOUL.md, BOOTSTRAP.md, AGENTS.md, HEARTBEAT.md, TOOLS.md, USER.md
    - Claude Code: CLAUDE.md
    - Default: system-prompt.md
    """
    parts = []

    # Load prompt files in order
    files_to_load = list(prompt_files or [])
    if not files_to_load:
        # Backwards compatible: fall back to system-prompt.md
        files_to_load = ["system-prompt.md"]

    seen_files = set(files_to_load)

    for filename in files_to_load:
        file_path = Path(config_path) / filename
        if file_path.exists():
            content = file_path.read_text().strip()
            if content:
                parts.append(content)
        else:
            print(f"Warning: prompt file not found: {file_path}")

    # Hermes-style memory snapshot files: load automatically when present.
    # These stay as thin markdown files so the runtime does not need a new storage layer.
    for filename in DEFAULT_MEMORY_SNAPSHOT_FILES:
        if filename in seen_files:
            continue
        file_path = Path(config_path) / filename
        if file_path.exists():
            content = file_path.read_text().strip()
            if content:
                parts.append(content)

    # Inject parent's shared context (if this workspace is a child)
    if parent_context:
        parts.append("\n## Parent Context\n")
        parts.append("The following context was shared by your parent workspace:\n")
        for ctx_file in parent_context:
            path = ctx_file.get("path", "unknown")
            content = ctx_file.get("content", "")
            if content.strip():
                parts.append(f"### {path}")
                parts.append(content.strip())
                parts.append("")

    # Inject plugin rules (always-on guidelines from ECC, Superpowers, etc.)
    if plugin_rules:
        parts.append("\n## Platform Rules\n")
        for rule in plugin_rules:
            parts.append(rule)
            parts.append("")

    # Inject plugin prompt fragments
    if plugin_prompts:
        parts.append("\n## Platform Guidelines\n")
        for fragment in plugin_prompts:
            parts.append(fragment)
            parts.append("")

    # Add skill instructions
    if loaded_skills:
        parts.append("\n## Your Skills\n")
        for skill in loaded_skills:
            parts.append(f"### {skill.metadata.name}")
            if skill.metadata.description:
                parts.append(skill.metadata.description)
            parts.append(skill.instructions)
            parts.append("")

    # Add peer capabilities
    if peers:
        parts.append("\n## Your Peers (workspaces you can delegate to)\n")
        for peer in peers:
            agent_card = peer.get("agent_card")
            if not agent_card:
                continue

            if isinstance(agent_card, str):
                try:
                    agent_card = json.loads(agent_card)
                except json.JSONDecodeError:
                    continue

            name = agent_card.get("name", peer.get("name", "Unknown"))
            peer_id = peer.get("id", "unknown")
            skills = agent_card.get("skills", [])
            status = peer.get("status", "unknown")

            parts.append(f"- **{name}** (id: `{peer_id}`, status: {status})")
            if skills:
                skill_names = [s.get("name", s.get("id", "")) for s in skills if isinstance(s, dict)]
                if skill_names:
                    parts.append(f"  Skills: {', '.join(skill_names)}")
            parts.append("")

        parts.append(
            "Use the `delegate_to_workspace` tool to send tasks to peers. "
            "Only delegate to peers listed above."
        )

    # Add delegation failure handling
    parts.append("""
## Handling delegation failures
If a delegation fails:
1. Check if the task is blocking — if not, continue other work
2. Retry transient failures (connection errors) after 30 seconds
3. For persistent failures, report to the caller with context
4. Never silently drop a failed task
""")

    return "\n".join(parts)
