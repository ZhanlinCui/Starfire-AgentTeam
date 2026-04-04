# PLAN.md — Starfire Build Plan

> Cross-referenced against all docs in `/docs`, PRD, and current codebase state.
> Updated: 2026-04-01

## Status Legend

- [x] Done — code exists and works
- [~] Partial — skeleton or some parts exist
- [ ] Not started

---

## Phase 1: Core Loop — DONE

The foundational loop is complete: workspace registers → canvas shows it → heartbeat keeps it alive → goes offline → canvas grays it out.

- [x] **1. Infrastructure** — `docker-compose.infra.yml`, `setup.sh`, `nuke.sh`
- [x] **2. Database Migrations** — 6 migration files in `platform/migrations/` (001–005 per build-order + 006_workspace_config_memory)
- [x] **3. Platform API Skeleton** — Go/Gin server (`cmd/server/main.go`), router, CORS, Postgres + Redis connections
- [x] **4. Registry Endpoints** — register, heartbeat, update-card, Redis TTL, keyspace notifications (`handlers/registry.go`)
- [x] **5. Workspace Runtime (Python)** — `main.py`, `config.py`, `agent.py`, `a2a_executor.py`, `heartbeat.py`, skill loader, A2A server wrapping
- [x] **6. Canvas Skeleton** — Next.js 15, React Flow (xyflow v12), Zustand (`store/canvas.ts`), WorkspaceNode, initial hydration, edge rendering from hierarchy
- [x] **7. WebSocket Live Updates** — `handlers/socket.go`, Redis pub/sub broadcaster, `store/socket.ts` (ReconnectingSocket with exponential backoff + re-hydration on reconnect)

---

## Phase 2: End-to-End Validation — TODO

> **Goal:** Prove the full loop works with a real agent, not just test scripts.

- [x] **8a.** Write `workspace-configs-templates/seo-agent/` with real `config.yaml`, `system-prompt.md`, and at least one skill
- [x] **8b.** Build workspace-template Docker image
- [x] **8c.** Deploy SEO agent container on `agent-molecule-net`
- [x] **8d.** **Verify end-to-end:** container starts → registers → appears online with Agent Card → skills visible
- [~] **8e.** Send an A2A `message/send` to the running agent — pipeline works end-to-end (proxy → agent → Claude API), blocked by subscription rate limits during testing

> **Note:** Echo and Summarizer templates exist in `workspace-configs-templates/` with `config.yaml` + `system-prompt.md` but have not been deployed and tested as running containers. This step validates the full container lifecycle.

---

## Phase 3: Hierarchy & Communication — PARTIAL

> **Goal:** Workspaces can discover peers, communicate via A2A, and respect hierarchy access rules.

- [x] **9a. `CanCommunicate()` access check** — `registry/access.go` implemented
- [x] **9b. `GET /registry/:id/peers`** — discovery endpoint (`handlers/discovery.go`)
- [x] **9c. `POST /registry/check-access`** — endpoint exists
- [x] **9d. `GET /registry/discover/:id`** — resolve workspace URL with scoped access (`handlers/discovery.go`)
- [x] **9e. Canvas drag-to-nest** — drag a node onto another to set `parent_id`, green ring drop target highlight, un-nest on drop to canvas background, circular hierarchy prevention
- [ ] **9f. Delegation tool testing** — `workspace-template/tools/delegation.py` exists but needs e2e test: Agent A delegates to Agent B via A2A, platform enforces access
- [ ] **9g. Delegation failure handling** — 3x retry + exponential backoff + optional fallback workspace (PRD F3.7, `docs/agent-runtime/config-format.md` delegation config)
- [ ] **9h. Workspace forwarding** — `forwarded_to` column for version replacement, team expansion routing, reorganization (per `docs/api-protocol/registry-and-heartbeat.md`)

---

## Phase 4: Provisioner — TODO

> **Goal:** Platform can deploy workspace containers on demand (per `docs/architecture/provisioner.md`).

- [x] **10a. `platform/internal/provisioner/` package** — Docker SDK integration to start/stop workspace containers (Start, Stop, IsRunning)
- [x] **10b. Container networking** — Join `agent-molecule-net`, container named `ws-{id}`, tier-1 read-only rootfs
- [x] **10c. Secret injection** — Read from `workspace_secrets` table, pass as env vars (AES-256 decryption deferred to Phase 14)
- [x] **10d. Volume mounts** — Config directory bind-mounted at `/configs:ro`
- [~] **10e. Tier-based Docker flags** — Tier 1 (`ReadonlyRootfs` + tmpfs), Tier 2-4 not yet differentiated
- [x] **10f. Lifecycle transitions** — `provisioning` → wait for heartbeat → `online` (via register); timeout 3min → `failed` with `WORKSPACE_PROVISION_FAILED` event
- [x] **10g. Retry on failure** — `POST /workspaces/:id/retry` resets to provisioning and re-triggers provisioner

---

## Phase 5: Agent Management — TODO

> **Goal:** Assign, replace, and move agents between workspaces (PRD F4, `docs/api-protocol/platform-api.md`).

- [x] **11a. `POST /workspaces/:id/agent`** — Assign agent (emits `AGENT_ASSIGNED`, prevents duplicate active agents)
- [x] **11b. `PATCH /workspaces/:id/agent`** — Replace model (emits `AGENT_REPLACED` with old_model, deactivates previous)
- [x] **11c. `DELETE /workspaces/:id/agent`** — Remove agent (emits `AGENT_REMOVED`)
- [x] **11d. `POST /workspaces/:id/agent/move`** — Move agent to different workspace (emits `AGENT_MOVED` on both source and target)
- [x] **11e. Canvas agent management UI** — AgentManager in DetailsTab: assign/replace/remove model, shows current model

---

## Phase 6: Bundle Export/Import — TODO

> **Goal:** Workspaces are portable — export as `.bundle.json`, import anywhere (per `docs/agent-runtime/bundle-system.md`).

- [x] **12a. `platform/internal/bundle/exporter.go`** — Serialize running workspace → bundle JSON (config, prompts, skills, sub-workspaces recursively)
- [x] **12b. `platform/internal/bundle/importer.go`** — Parse bundle JSON → create workspace records → trigger provisioner, recursive sub-workspaces
- [x] **12c. API endpoints** — `GET /bundles/export/:id`, `POST /bundles/import`
- [x] **12d. `bundle-compile.sh`** — Script to compile workspace-configs-templates/ into .bundle.json (tested: 4 templates compiled)
- [ ] **12e. Canvas BundleDropZone** — Drag `.bundle.json` onto canvas to import
- [ ] **12f. Canvas right-click export** — Right-click node → "Export as bundle" → downloads file
- [ ] **12g. Canvas duplicate node** — Right-click → "Duplicate" (export + re-import with new IDs)
- [ ] **12h. Recursive sub-workspaces** — Import walks `sub_workspaces[]` tree, provisions each
- [ ] **12i. Partial failure handling** — Failed sub-workspace doesn't block parent; red node + retry
- [ ] **12j. Round-trip test** — Export → delete → import → workspace reappears with same config

---

## Phase 7: Team Expansion (PRD F2) — TODO

> **Goal:** Any workspace node can "expand" into a sub-team while keeping its single A2A interface (per `docs/agent-runtime/team-expansion.md`).

- [ ] **13a. Expand API** — `POST /workspaces/:id/expand` reads team definition from `sub_workspaces` in config, creates child workspaces (emits `WORKSPACE_EXPANDED`)
- [ ] **13b. Collapse API** — `POST /workspaces/:id/collapse` — subs write handoff docs to memory, get stopped/removed (emits `WORKSPACE_COLLAPSED`)
- [ ] **13c. Coordinator pattern** — Parent agent stays as team lead, routes incoming A2A to appropriate children based on capabilities
- [ ] **13d. Scoped registry** — Sub-workspaces register with `parent_id`, private scope enforced (outside gets 403)
- [ ] **13e. Canvas expand UX** — Right-click node → "Expand to team" → children appear inside a group box
- [ ] **13f. Canvas collapse view** — Toggle between expanded (see children) and collapsed (single node with team badge)
- [ ] **13g. Canvas zoom-in** — Clicking expanded node reveals sub-workspace nodes; from top-level, team appears as single node
- [ ] **13h. Delete team** — Warn listing sub-workspaces, allow drag-out before confirm, cascade delete on confirm

---

## Phase 8: Human-in-the-Loop Approval Chain (PRD F6) — TODO

> **Goal:** Agents can pause for human approval; requests escalate up the hierarchy (per `docs/agent-runtime/system-prompt-structure.md`).

- [ ] **14a. LangGraph interrupt integration** — Workspace runtime uses LangGraph `interrupt` to pause execution
- [ ] **14b. Approval request propagation** — Child sends approval request to parent via A2A `input-required` status
- [ ] **14c. Escalation chain** — Parent decides: approve, deny, or escalate up to its own parent, continuing to root
- [ ] **14d. Root node → Canvas UI** — When root receives approval request, canvas shows approval card (approve/deny/escalate)
- [ ] **14e. Result propagation** — Approval/denial flows back down the hierarchy, triggers resume/abort
- [ ] **14f. Configurable approval rules** — Per-workspace config for which actions require approval (destructive, expensive, unauthorized) (PRD F6.5)

---

## Phase 9: Hierarchical Memory Architecture — TODO

> **Goal:** Org-chart-driven memory isolation with three scopes (per `docs/architecture/memory.md`).

- [ ] **15a. `agent_memories` table + pgvector** — Schema with workspace_id, content, embedding, scope (LOCAL/TEAM/GLOBAL)
- [ ] **15b. L1: Local Memory** — Isolated per-workspace scratchpad, invisible to other agents
- [ ] **15c. L2: Team Shared Memory** — Parent + direct children only, `commit_memory(scope='TEAM')`, `search_memory(scope='TEAM')`
- [ ] **15d. L3: Global Corporate Memory** — Readable by all, writable by admin/root only
- [ ] **15e. Access control enforcement** — Postgres RLS + `CanCommunicate()` rules for memory queries
- [ ] **15f. A2A memory tools** — `search_memory` and `commit_memory` tool definitions for agent use
- [ ] **15g. Consolidation loop** — Background thread summarizes local scratchpad into dense knowledge when agent idle

---

## Phase 10: Observability (PRD F7) — TODO

> **Goal:** Unified Langfuse tracing across all workspaces (per `docs/development/observability.md`).

- [ ] **16a. Langfuse auto-injection** — Workspace runtime detects `LANGFUSE_*` env vars and auto-instruments LangGraph
- [ ] **16b. Cross-workspace trace linking** — A2A delegation passes `parent_task_id` to link child traces to parent span
- [ ] **16c. Canvas trace preview (future)** — Click node → see recent LLM calls inline

---

## Phase 11: Canvas Polish & UX — PARTIAL

> **Goal:** Canvas becomes the full control plane, not just a viewer.

- [x] **17a. Node selection** — Click node → blue ring highlight, pane click deselects
- [x] **17b. Node detail panel** — SidePanel (420px right) with 5 tabs: Details, Chat, Config, Memory, Events
- [x] **17c. Status indicators** — Green (online), yellow (degraded), gray (offline), red (failed), blue pulse (provisioning)
- [x] **17d. Config editor** — ConfigTab in SidePanel (JSON editor with save/reset/reload)
- [x] **17e. Event log** — EventsTab in SidePanel (workspace-scoped, color-coded, auto-refresh 10s)
- [x] **17f. Create workspace dialog** — FAB "New Workspace" button + modal (name, role, tier, parent ID)
- [x] **17g. Chat with agent** — ChatTab sends A2A messages via platform proxy (`POST /workspaces/:id/a2a`)
- [x] **17h. Memory browser** — MemoryTab browses/adds/deletes key-value entries with TTL
- [x] **17i. Peer navigation** — DetailsTab shows peers from `/registry/:id/peers`, click to navigate
- [x] **17j. Inline workspace editing** — DetailsTab edit mode for name/role/tier with save to API
- [x] **17k. Workspace deletion** — DetailsTab danger zone with confirmation
- [x] **17l. Template palette** — Left sidebar with available workspace templates, click to deploy (from `GET /templates`)
- [x] **17m. Right-click context menu** — Export bundle, duplicate, restart, delete, open chat/terminal/details
- [ ] **17n. Skill drag-and-drop** — Drag skill from palette onto a node to add it
- [x] **17o. Canvas viewport persistence** — Save pan/zoom via `PUT /canvas/viewport` (debounced 1s), restore on page load
- [ ] **17p. Connection breakage visualization** — Visual indicator when A2A communication between workspaces fails (PRD F1.13)
- [ ] **17q. ClawHub skill installation** — `npx clawhub@latest install <skill-name>` integration for skill marketplace (PRD F4.4)

### Platform endpoints needed for canvas features

- [x] **17r. `GET /templates`** — Scans workspace-configs-templates/, returns name/description/tier/model/skills per template
- [x] **17s. `POST /workspaces/:id/a2a`** — Platform-side A2A proxy (resolves workspace URL, wraps in JSON-RPC 2.0 envelope, forwards to agent, returns response)

---

## Phase 12: Code Sandbox — TODO

> **Goal:** Tier 3 workspaces can execute arbitrary code safely (per `docs/development/code-sandbox.md`).

- [ ] **18a. `run_code` tool** — Agent tool that executes code in isolated sandbox
- [ ] **18b. Docker-in-Docker backend (MVP)** — Throwaway container per execution, network disabled, memory capped, read-only fs
- [ ] **18c. Firecracker backend (production)** — MicroVM isolation, faster cold starts
- [ ] **18d. E2B backend (cloud)** — Cloud-hosted via E2B API, no local Docker needed
- [ ] **18e. Sandbox config** — `sandbox` field in config.yaml (backend, memory_limit, timeout)

---

## Phase 13: Workspace Runtime Enhancements — TODO

> **Goal:** Runtime features documented in docs but not yet tracked.

- [ ] **19a. Hot-reload** — File watcher for skills/config changes → rebuild Agent Card → broadcast `AGENT_CARD_UPDATED` (per `docs/agent-runtime/config-format.md`)
- [ ] **19b. WebSocket subscription** — Workspace subscribes to platform WebSocket with `X-Workspace-ID` for peer events (per `docs/agent-runtime/workspace-runtime.md`)
- [ ] **19c. System prompt rebuild on peer events** — Rebuild prompt when peers go online/offline/expand/collapse (per `docs/agent-runtime/system-prompt-structure.md`)

---

## Phase 14: Production Hardening — TODO

- [ ] **20a. Full Docker Compose** — `docker compose up` boots everything (platform, canvas, postgres, redis, langfuse)
- [ ] **20b. Health checks** — All services have Docker healthchecks
- [ ] **20c. Secrets encryption** — AES-256 at-rest encryption for `workspace_secrets` (PRD F8.5)
- [ ] **20d. Rate limiting** — Protect platform API endpoints
- [ ] **20e. Graceful shutdown** — Platform drains WebSocket connections, stops liveness monitor cleanly
- [ ] **20f. Error recovery** — Workspace auto-reconnect after platform restart

---

## Phase 15: SaaS Preparation — TODO

> **Goal:** Prepare for hosted offering without changing open-source repo (per `docs/product/saas-upgrade.md`).

- [ ] **21a. Auth layer** — Clerk or Auth.js integration (agent-molecule-cloud wrapper)
- [ ] **21b. Multi-tenancy** — Add `org_id` to schema for org isolation
- [ ] **21c. Billing** — Stripe integration
- [ ] **21d. Managed infrastructure** — ECS + Neon + Upstash
- [ ] **21e. White-labeling** — Custom branding on canvas

---

## Recommended Build Sequence

```
Phase 2 (validate with real agent)
  └─→ Phase 4 (provisioner — auto-deploy containers)
       └─→ Phase 3 remainder (drag-to-nest, delegation e2e, forwarding)
            └─→ Phase 5 (agent management)
                 └─→ Phase 6 (bundle export/import)
                      └─→ Phase 7 (team expansion)
                           └─→ Phase 8 (human-in-the-loop)

Phase 9 (HMA memory) — can start after Phase 3
Phase 10 (observability) — can start after Phase 2
Phase 11 remainder (template palette, context menu) — after Phase 4
Phase 12 (code sandbox) — after Phase 4
Phase 13 (runtime enhancements) — after Phase 2
Phase 14 (hardening) — run last before SaaS
Phase 15 (SaaS) — after Phase 14
```

The critical path is: **real agent running (Phase 2) → provisioner (Phase 4) → agent management (Phase 5) → bundles (Phase 6) → team expansion (Phase 7)**. Everything else can be parallelized around this spine.

---

## CLAUDE.md Sync Notes

Endpoints added to CLAUDE.md API routes table on 2026-04-01:
- `GET/PATCH /workspaces/:id/config` — exists in router
- `GET/POST /workspaces/:id/memory` — exists in router
- `DELETE /workspaces/:id/memory/:key` — exists in router

All canvas-used endpoints are now implemented and documented.
