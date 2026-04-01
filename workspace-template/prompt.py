"""Build the system prompt for the workspace agent."""

import json
from pathlib import Path

import httpx

from skills.loader import LoadedSkill


async def get_peer_capabilities(platform_url: str, workspace_id: str) -> list[dict]:
    """Fetch peer workspace capabilities from the platform."""
    try:
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
) -> str:
    """Build the complete system prompt."""
    parts = []

    # Load the base system prompt
    prompt_file = Path(config_path) / "system-prompt.md"
    if prompt_file.exists():
        parts.append(prompt_file.read_text().strip())

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
