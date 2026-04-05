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
- [x] **9f. Delegation tool testing** — E2E tested with SEO + Echo agents via OpenRouter, peer discovery + access control verified
- [x] **9g. Delegation failure handling** — `delegation.py` has configurable retry (env vars), exponential backoff, error reporting to LLM
- [x] **9h. Workspace forwarding** — Discovery follows `forwarded_to` chain (max 5 hops), transparent redirect to new workspace

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
- [x] **12e. Canvas BundleDropZone** — Drag `.bundle.json` onto canvas to import (visual overlay, toast feedback)
- [x] **12f. Canvas right-click export** — Right-click node → "Export as bundle" → downloads file (via context menu)
- [x] **12g. Canvas duplicate node** — Right-click → "Duplicate" (export + re-import via context menu)
- [x] **12h. Recursive sub-workspaces** — `importer.go` already recursively imports `sub_workspaces[]` tree
- [x] **12i. Partial failure handling** — `importer.go` continues on child failure, returns ImportResult per workspace with error details
- [x] **12j. Round-trip test** — Export → delete → import → workspace reappears with same config

---

## Phase 7: Team Expansion (PRD F2) — TODO

> **Goal:** Any workspace node can "expand" into a sub-team while keeping its single A2A interface (per `docs/agent-runtime/team-expansion.md`).

- [x] **13a. Expand API** — `POST /workspaces/:id/expand` reads `sub_workspaces` from config, creates+provisions child workspaces (emits `WORKSPACE_EXPANDED`)
- [x] **13b. Collapse API** — `POST /workspaces/:id/collapse` — stops containers, removes children (emits `WORKSPACE_COLLAPSED`)
- [x] **13c. Coordinator pattern** — `coordinator.py` auto-detects children, injects team description into prompt, adds `route_task_to_team` tool. Agent analyzes task + children's skills to route.
- [x] **13d. Scoped registry** — Already enforced via `CanCommunicate()` in access.go (siblings, parent-child only)
- [x] **13e. Canvas expand UX** — Right-click node → "Expand to Team" / "Collapse Team" in context menu
- [x] **13f. Canvas collapse view** — Collapse Team in right-click context menu (calls POST /collapse)
- [x] **13g. Canvas zoom-in** — Double-click team node to zoom/fit to parent + children with smooth animation (500ms)
- [x] **13h. Delete team** — Cascade delete with confirmation (returns children list if not ?confirm=true, stops containers)

---

## Phase 8: Human-in-the-Loop Approval Chain (PRD F6) — TODO

> **Goal:** Agents can pause for human approval; requests escalate up the hierarchy (per `docs/agent-runtime/system-prompt-structure.md`).

- [x] **14a. LangGraph interrupt integration** — `request_approval` tool pauses agent, polls platform for decision
- [x] **14b. Approval request propagation** — `POST /workspaces/:id/approvals` creates request, broadcasts APPROVAL_REQUESTED
- [x] **14c. Escalation chain** — Platform auto-escalates to parent workspace via APPROVAL_ESCALATED event
- [x] **14d. Root node → Canvas UI** — `ApprovalBanner` polls pending approvals, shows approve/deny cards with workspace name
- [x] **14e. Result propagation** — `POST /workspaces/:id/approvals/:id/decide` broadcasts APPROVAL_APPROVED/DENIED, agent resumes
- [x] **14f. Configurable approval rules** — Agent decides when to call `request_approval` based on system prompt guidelines

---

## Phase 9: Hierarchical Memory Architecture — TODO

> **Goal:** Org-chart-driven memory isolation with three scopes (per `docs/architecture/memory.md`).

- [x] **15a. `agent_memories` table + pgvector** — Migration 008 with workspace_id, content, embedding vector(1536), scope CHECK
- [x] **15b. L1: Local Memory** — `scope='LOCAL'`, filtered to `workspace_id` only
- [x] **15c. L2: Team Shared Memory** — `scope='TEAM'`, queries join parent_id for team members
- [x] **15d. L3: Global Corporate Memory** — `scope='GLOBAL'`, readable by all, write restricted to root (no parent_id)
- [x] **15e. Access control enforcement** — `CanCommunicate()` check on TEAM results, parent_id check on GLOBAL writes
- [x] **15f. A2A memory tools** — `commit_memory(content, scope)` and `search_memory(query, scope)` in tools/memory.py
- [x] **15g. Consolidation loop** — `consolidation.py` runs every 5min, summarizes LOCAL memories into TEAM knowledge when threshold reached

---

## Phase 10: Observability (PRD F7) — TODO

> **Goal:** Unified Langfuse tracing across all workspaces (per `docs/development/observability.md`).

- [x] **16a. Langfuse auto-injection** — `_setup_langfuse()` in agent.py detects env vars, creates CallbackHandler, sets LANGSMITH_TRACING
- [x] **16b. Cross-workspace trace linking** — Delegation tool passes `parent_task_id` and `source_workspace_id` in A2A metadata
- [x] **16c. Canvas trace preview** — TracesTab in SidePanel shows recent LLM calls from Langfuse (input/output/latency/cost/tokens), proxy via `GET /workspaces/:id/traces`

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
- [x] **17n. Skill drag-and-drop** — SkillInstaller in DetailsTab: type skill name to add, creates SKILL.md in workspace files
- [x] **17o. Canvas viewport persistence** — Save pan/zoom via `PUT /canvas/viewport` (debounced 1s), restore on page load
- [x] **17p. Connection breakage visualization** — Edges styled by status: animated green (online), amber/thick (degraded), dashed gray (offline/failed)
- [x] **17q. ClawHub skill installation** — "Install from ClawHub" button in DetailsTab, sends install command to agent via A2A

### Platform endpoints needed for canvas features

- [x] **17r. `GET /templates`** — Scans workspace-configs-templates/, returns name/description/tier/model/skills per template
- [x] **17s. `POST /workspaces/:id/a2a`** — Platform-side A2A proxy (resolves workspace URL, wraps in JSON-RPC 2.0 envelope, forwards to agent, returns response)

---

## Phase 12: Code Sandbox — TODO

> **Goal:** Tier 3 workspaces can execute arbitrary code safely (per `docs/development/code-sandbox.md`).

- [x] **18a. `run_code` tool** — `tools/sandbox.py` executes code in isolated sandbox (subprocess or Docker)
- [x] **18b. Docker-in-Docker backend (MVP)** — `--network none --memory 256m --read-only --cpus 0.5` throwaway container
- [ ] **18c. Firecracker backend (production)** — MicroVM isolation, faster cold starts
- [ ] **18d. E2B backend (cloud)** — Cloud-hosted via E2B API, no local Docker needed
- [x] **18e. Sandbox config** — `SandboxConfig` dataclass in config.py (backend, memory_limit, timeout)

---

## Phase 13: Workspace Runtime Enhancements — TODO

> **Goal:** Runtime features documented in docs but not yet tracked.

- [x] **19a. Hot-reload** — `watcher.py` polls config directory for file hash changes (3s interval, 2s debounce), triggers reload callback + Agent Card update
- [x] **19b. WebSocket subscription** — `events.py` connects to platform `/ws` with `X-Workspace-ID` header, exponential backoff reconnect
- [x] **19c. System prompt rebuild on peer events** — `PlatformEventSubscriber` triggers on WORKSPACE_ONLINE/OFFLINE/EXPANDED/COLLAPSED/REMOVED and AGENT_CARD_UPDATED

---

## Phase 14: Production Hardening — TODO

- [x] **20a. Full Docker Compose** — `docker compose up` boots postgres, redis, langfuse+clickhouse, platform, canvas on shared network
- [x] **20b. Health checks** — All 6 services have Docker healthchecks (pg_isready, redis-cli ping, wget /health)
- [x] **20c. Secrets encryption** — AES-256-GCM via `crypto/aes.go`, encrypt on write, decrypt on read + provisioner inject. Enabled via `SECRETS_ENCRYPTION_KEY` env var.
- [x] **20d. Rate limiting** — Token bucket rate limiter (100 req/min/IP) via `middleware/ratelimit.go`
- [x] **20e. Graceful shutdown** — Signal handler (SIGINT/SIGTERM), context cancellation, HTTP drain (30s), WebSocket hub Close()
- [x] **20f. Error recovery** — `events.py` reconnects with exponential backoff, `socket.ts` re-hydrates on reconnect

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
