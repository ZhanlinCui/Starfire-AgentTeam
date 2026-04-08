---
id: kc_mnpf80aq_8a24b898
category: decision
confidence: 0.98
tags: [codex, mcp, awareness, configuration]
created_at: 2026-04-08T02:20:26.114Z
---

# Register awareness in global Codex MCP config

Codex CLI in this environment reads external MCP servers from ~/.codex/config.toml via `codex mcp add`, not from the repository `.mcp.json` alone. To make awareness tools available to the session, the server must be registered globally with a project-scoped command that points at the repo path.
