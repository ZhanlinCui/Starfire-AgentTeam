---
id: mem_20260401_001614_1c2e
type: documentation
session_id: ses_1775027710541_ydl963
agent_role: builder_agent
tags: [plan, documentation, prd, "cross-reference", "claude-md"]
created_at: "2026-04-01T07:16:14.017Z"
updated_at: "2026-04-01T07:16:14.017Z"
source: mcp
status: active
related: []
---

## What changed

Rewrote PLAN.md after cross-referencing against ALL 29 docs files, PRD features F1-F8, and actual codebase state.

### New phases added:
- **Phase 5: Agent Management** — POST/PATCH/DELETE /workspaces/:id/agent, agent/move (PRD F4)
- **Phase 9: Hierarchical Memory Architecture** — L1/L2/L3 memory, pgvector, agent_memories table, search/commit tools (docs/architecture/memory.md)
- **Phase 12: Code Sandbox** — Tier 3 run_code tool, Docker-in-Docker/Firecracker/E2B backends (docs/development/code-sandbox.md)
- **Phase 13: Workspace Runtime Enhancements** — Hot-reload, WebSocket subscription, system prompt rebuild on peer events
- **Phase 15: SaaS Preparation** — Auth, multi-tenancy, billing, managed infra (docs/product/saas-upgrade.md)

### Items added to existing phases:
- Phase 3: Added 9d (GET /registry/discover/:id as done), 9h (workspace forwarding)
- Phase 5: Event type annotations (AGENT_ASSIGNED/REMOVED/REPLACED/MOVED)
- Phase 7: Event annotations (WORKSPACE_EXPANDED/COLLAPSED), collapse API, scoped registry, delete team
- Phase 8: 14f configurable approval rules (PRD F6.5)
- Phase 11: 17p connection breakage visualization (PRD F1.13), 17q ClawHub integration (PRD F4.4), separated platform endpoint items (17r/17s)

### Factual corrections:
- Step 7 references socket.ts not useSocket.ts
- 6 migration files not 5
- Phase 11 tracks all 11 done canvas features individually (17a-17k)
- Phase numbering now consistent (no more step/item number confusion)

### CLAUDE.md also updated:
- Added 3 missing API routes: /workspaces/:id/config, /workspaces/:id/memory, /workspaces/:id/memory/:key
- Fixed migration count from 5 to 6

### Final counts: 15 phases, 107 tracked items (23 done, 83 todo)
