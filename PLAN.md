# PLAN.md — Starfire Build Plan

> Based on `docs/development/build-order.md`, PRD, and current codebase state.
> Updated: 2026-03-31

## Status Legend

- [x] Done — code exists and works
- [~] Partial — skeleton exists, needs completion
- [ ] Not started

---

## Phase 1: Core Loop (Steps 1–7) — DONE

The foundational loop is complete: workspace registers → canvas shows it → heartbeat keeps it alive → goes offline → canvas grays it out.

- [x] **Step 1: Infrastructure** — `docker-compose.infra.yml`, `setup.sh`, `nuke.sh`
- [x] **Step 2: Database Migrations** — 6 migration files in `platform/migrations/`
- [x] **Step 3: Platform API Skeleton** — Go/Gin server, router, CORS, Postgres + Redis connections
- [x] **Step 4: Registry Endpoints** — register, heartbeat, update-card, Redis TTL, keyspace notifications
- [x] **Step 5: Workspace Runtime (Python)** — `main.py`, config loader, LangGraph agent, A2A server, heartbeat loop, skill loader
- [x] **Step 6: Canvas Skeleton** — Next.js 15, React Flow, Zustand, WorkspaceNode, initial hydration, edge rendering from hierarchy
- [x] **Step 7: WebSocket Live Updates** — `socket.go`, Redis pub/sub broadcaster, `useSocket.ts`

---

## Phase 2: End-to-End Validation (Step 8) — TODO

> **Goal:** Prove the full loop works with a real agent, not just test scripts.

- [ ] **Step 8: First Real Workspace Config**
  - [ ] 8a. Write `workspace-configs-templates/seo-agent/` with real `config.yaml`, `system-prompt.md`, and at least one skill
  - [ ] 8b. Build workspace-template Docker image
  - [ ] 8c. Deploy SEO agent container on `agent-molecule-net`
  - [ ] 8d. **Verify end-to-end:** container starts → registers → appears on canvas → heartbeat → stays green
  - [ ] 8e. Send an A2A `message/send` to the running agent and get a real LLM response

> **Note:** Echo and Summarizer templates exist in `workspace-configs-templates/` but have not been deployed and tested as running containers. This step validates the full container lifecycle.

---

## Phase 3: Hierarchy & Communication (Step 9) — PARTIAL

> **Goal:** Workspaces can discover peers, communicate via A2A, and respect hierarchy access rules.

- [x] **9a. `CanCommunicate()` access check** — `registry/access.go` implemented
- [x] **9b. `GET /registry/:id/peers`** — discovery endpoint exists
- [x] **9c. `POST /registry/check-access`** — endpoint exists
- [ ] **9d. Canvas drag-to-nest** — drag a node into another to set `parent_id`
- [ ] **9e. Delegation tool testing** — `workspace-template/tools/delegation.py` exists but needs end-to-end test: Agent A delegates to Agent B via A2A, platform enforces access
- [ ] **9f. Delegation failure handling** — 3x retry + exponential backoff + optional fallback workspace (PRD F3.7)

---

## Phase 4: Provisioner (NEW — not in build-order.md but required by PRD)

> **Goal:** Platform can deploy workspace containers on demand (not just accept registrations from pre-started containers).

- [ ] **10a. `platform/internal/provisioner/` package** — Docker SDK integration to start/stop workspace containers
- [ ] **10b. Container networking** — Join `agent-molecule-net`, address as `http://ws-{id}:8000`
- [ ] **10c. Secret injection** — Read from `workspace_secrets` table, decrypt, pass as env vars
- [ ] **10d. Volume mounts** — Named volume `ws-{id}-memory` mounted at `/memory`
- [ ] **10e. Tier-based Docker flags** — Tier 1 (read-only), Tier 2 (+Playwright), Tier 3 (+Xvfb), Tier 4 (EC2, future)
- [ ] **10f. Lifecycle transitions** — `provisioning` → wait for heartbeat → `online`; timeout 3min → `failed`
- [ ] **10g. Canvas "Create Workspace" flow** — Click template → configure → POST /workspaces → provisioner deploys → node appears with spinner → turns green
- [ ] **10h. Retry on failure** — Canvas shows red node with retry button, re-triggers provisioner

---

## Phase 5: Bundle Export/Import (Step 10)

> **Goal:** Workspaces are portable — export a running workspace as `.bundle.json`, import it anywhere.

- [ ] **11a. `platform/internal/bundle/exporter.go`** — Serialize running workspace → bundle JSON (config, prompts, skills, sub-workspaces recursively)
- [ ] **11b. `platform/internal/bundle/importer.go`** — Parse bundle JSON → create workspace records → trigger provisioner for each
- [ ] **11c. API endpoints** — `GET /bundles/export/:id`, `POST /bundles/import`
- [ ] **11d. Canvas BundleDropZone** — Drag `.bundle.json` onto canvas to import
- [ ] **11e. Canvas right-click export** — Right-click node → "Export as bundle" → downloads file
- [ ] **11f. Recursive sub-workspaces** — Import walks `sub_workspaces[]` tree, provisions each
- [ ] **11g. Partial failure handling** — Failed sub-workspace doesn't block parent; red node + retry
- [ ] **11h. Round-trip test** — Export → delete → import → workspace reappears with same config

---

## Phase 6: Team Expansion (PRD F2)

> **Goal:** Any workspace node can "expand" into a sub-team while keeping its single A2A interface.

- [ ] **12a. Expand API** — `POST /workspaces/:id/expand` reads team definition from config, creates child workspaces
- [ ] **12b. Canvas expand UX** — Right-click node → "Expand to team" → children appear inside a group box
- [ ] **12c. Coordinator pattern** — Parent workspace becomes the team coordinator, routes incoming A2A to appropriate children
- [ ] **12d. Collapse view** — Canvas can toggle between expanded (see children) and collapsed (single node) view

---

## Phase 7: Human-in-the-Loop Approval Chain (PRD F6)

> **Goal:** Agents can pause for human approval; requests escalate up the hierarchy.

- [ ] **13a. LangGraph interrupt integration** — Workspace runtime uses LangGraph `interrupt` to pause execution
- [ ] **13b. Approval request propagation** — Child sends approval request to parent via A2A `input-required` status
- [ ] **13c. Root node → Canvas UI** — When root receives approval request, canvas shows approval card (approve/deny/escalate)
- [ ] **13d. Result propagation** — Approval/denial flows back down the hierarchy, triggers resume/abort

---

## Phase 8: Observability (PRD F7)

> **Goal:** Unified Langfuse tracing across all workspaces.

- [ ] **14a. Langfuse auto-injection** — Workspace runtime detects `LANGFUSE_*` env vars and auto-instruments LangGraph
- [ ] **14b. Cross-workspace trace linking** — A2A delegation passes `parent_task_id` to link child traces to parent span
- [ ] **14c. Canvas trace preview (future)** — Click node → see recent LLM calls inline

---

## Phase 9: Canvas Polish & UX

> **Goal:** Canvas becomes the full control plane, not just a viewer.

- [ ] **15a. Template palette** — Left sidebar with available workspace templates (from `workspace-configs-templates/`)
- [x] **15b. Node detail panel** — Click node → right panel shows config, skills, status, logs (SidePanel with 5 tabs: Details, Chat, Config, Memory, Events)
- [ ] **15c. Skill drag-and-drop** — Drag skill from palette onto a node to add it
- [x] **15d. Config editor** — Edit workspace config (model, prompt, skills) directly in canvas (ConfigTab in SidePanel)
- [x] **15e. Status indicators** — Spinner (provisioning), green (online), yellow (degraded), gray (offline), red (failed) (implemented with pulse animation for provisioning)
- [x] **15f. Event log panel** — Workspace-scoped event log in SidePanel Events tab (per-node, not global bottom panel)

---

## Phase 10: Production Hardening

- [ ] **16a. Full Docker Compose** — `docker compose up` boots everything (platform, canvas, postgres, redis, langfuse)
- [ ] **16b. Health checks** — All services have Docker healthchecks
- [ ] **16c. Secrets encryption** — AES-256 at-rest encryption for `workspace_secrets` (PRD F8.5)
- [ ] **16d. Rate limiting** — Protect platform API endpoints
- [ ] **16e. Graceful shutdown** — Platform drains WebSocket connections, stops liveness monitor cleanly
- [ ] **16f. Error recovery** — Workspace auto-reconnect after platform restart

---

## Recommended Build Sequence

```
Phase 2 (validate with real agent)
  └─→ Phase 4 (provisioner — auto-deploy containers)
       └─→ Phase 3 remainder (drag-to-nest, delegation e2e)
            └─→ Phase 5 (bundle export/import)
                 └─→ Phase 6 (team expansion)
                      └─→ Phase 7 (human-in-the-loop)

Phase 8 (observability) — can run in parallel after Phase 2
Phase 9 (canvas polish) — can run in parallel after Phase 4
Phase 10 (hardening) — run last
```

The critical path is: **real agent running (Phase 2) → provisioner (Phase 4) → bundles (Phase 5) → team expansion (Phase 6)**. Everything else can be parallelized around this spine.
