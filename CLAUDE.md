# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agent Molecule is a platform for orchestrating AI agent workspaces that form an organizational hierarchy. Workspaces register with a central platform, communicate via A2A protocol, and are visualized on a drag-and-drop canvas.

## Architecture

```
Canvas (Next.js :3000) ←WebSocket→ Platform (Go :8080) ←HTTP→ Postgres + Redis
                                                                  ↑
                                   Workspace A ←──A2A──→ Workspace B
                                   (Python agents)
                                        ↑ register/heartbeat ↑
                                        └───── Platform ─────┘
```

Four main components:
- **Platform** (`platform/`): Go/Gin control plane — workspace CRUD, registry, discovery, WebSocket hub, liveness monitoring
- **Canvas** (`canvas/`): Next.js 15 + React Flow (@xyflow/react v12) + Zustand + Tailwind — visual workspace graph
- **Workspace Runtime** (`workspace-template/`): Python template — LangGraph agent wrapped in A2A server, registers with platform, sends heartbeats
- **molecli** (`platform/cmd/cli/`): Go TUI dashboard (Bubbletea + Lipgloss) — real-time workspace monitoring, event log, health overview, delete/filter operations

## Build & Run Commands

### Infrastructure
```bash
./infra/scripts/setup.sh    # Start Postgres, Redis, Langfuse; run migrations
./infra/scripts/nuke.sh     # Tear down everything, remove volumes
```

### Platform (Go)
```bash
cd platform
go build ./cmd/server       # Build server
go run ./cmd/server          # Run server (requires Postgres + Redis running)
go build -o molecli ./cmd/cli  # Build TUI dashboard
./molecli                    # Run TUI dashboard (requires platform running)
```
Must run from `platform/` directory (not repo root). Env vars: `DATABASE_URL`, `REDIS_URL`, `PORT`, `PLATFORM_URL` (default `http://host.docker.internal:PORT` — passed to agent containers so they can reach the platform), `SECRETS_ENCRYPTION_KEY` (optional AES-256, 32 bytes), `CONFIGS_DIR` (auto-discovered), `PLUGINS_DIR` (default `/plugins`).

`molecli` reads `MOLECLI_URL` (default http://localhost:8080) to locate the platform. Logs are written to `molecli.log` in the working directory (already covered by `*.log` in `.gitignore`).

### Canvas (Next.js)
```bash
cd canvas
npm install
npm run dev                  # Dev server on :3000
npm run build && npm start   # Production
```
Env vars: `NEXT_PUBLIC_PLATFORM_URL` (default http://localhost:8080), `NEXT_PUBLIC_WS_URL` (default ws://localhost:8080/ws).

### Unit Tests
```bash
cd platform && go test ./...                    # 9 Go handler tests (sqlmock + miniredis)
cd canvas && npm test                            # 47 Vitest store tests
cd workspace-template && python -m pytest -v     # 45 pytest tests (config, heartbeat, prompt, skills, a2a)
```

### Integration Tests
```bash
bash test_api.sh             # Runs 43 API tests against localhost:8080
bash test_a2a_e2e.sh         # Runs 22 A2A end-to-end tests (requires 2 online agents)
```
`test_api.sh` requires platform running. Tests full CRUD, registry, heartbeat, discovery, peers, access control, events, degraded/recovery lifecycle, bundle round-trip (export → delete → import → verify).

`test_a2a_e2e.sh` requires platform + two provisioned agents (Echo Agent, SEO Agent) running with a valid `OPENROUTER_API_KEY`. Tests message/send, JSON-RPC wrapping, error handling, peer discovery, agent cards, heartbeat. Timeout configurable via `A2A_TIMEOUT` env var (default 120s).

### MCP Server
```bash
cd mcp-server
npm install && npm run build   # Build MCP server
node dist/index.js             # Run (stdio transport)
```
Exposes 20 tools for managing Starfire from Claude Code, Cursor, Codex, or any MCP client. Configured in `.mcp.json`. Env: `STARFIRE_URL` (default http://localhost:8080).

### CI Pipeline
GitHub Actions (`.github/workflows/ci.yml`) runs on push to main and PRs:
- **platform-build**: Go build, vet, test
- **canvas-build**: npm build, vitest
- **mcp-server-build**: npm build
- **python-lint**: pytest

### Docker Compose
```bash
docker compose -f docker-compose.infra.yml up -d    # Infra only
docker compose up                                     # Full stack
```

## Key Architectural Patterns

### Import Cycle Prevention
The platform uses function injection to avoid Go import cycles between ws, registry, and events packages:
- `ws.NewHub(canCommunicate AccessChecker)` — Hub accepts `registry.CanCommunicate` as a function
- `registry.StartLivenessMonitor(ctx, onOffline OfflineHandler)` — Liveness accepts broadcaster callback
- Wiring happens in `platform/cmd/server/main.go`

### Communication Rules (`registry/access.go`)
`CanCommunicate(callerID, targetID)` determines if two workspaces can talk:
- Same workspace → allowed
- Siblings (same parent_id) → allowed
- Root-level siblings (both parent_id IS NULL) → allowed
- Parent ↔ child → allowed
- Everything else → denied

### JSONB Gotcha
When inserting Go `[]byte` (from `json.Marshal`) into Postgres JSONB columns, you must:
1. Convert to `string()` first
2. Use `::jsonb` cast in SQL

lib/pq treats `[]byte` as `bytea`, not JSONB.

### WebSocket Events Flow
1. Action occurs (register, heartbeat, etc.)
2. `broadcaster.RecordAndBroadcast()` inserts into `structure_events` table + publishes to Redis pub/sub
3. Redis subscriber relays to WebSocket hub
4. Hub broadcasts to canvas clients (all events) and workspace clients (filtered by CanCommunicate)

### Canvas State Management
- Initial load: HTTP fetch from `GET /workspaces` → Zustand hydrate
- Real-time updates: WebSocket events → `applyEvent()` in Zustand store
- Position persistence: `onNodeDragStop` → `PATCH /workspaces/:id` with `{x, y}`
- Embedded sub-workspaces: `nestNode` sets `hidden: !!targetId` on child nodes; children render as recursive `TeamMemberChip` components inside parent (up to 3 levels), not as separate canvas nodes. Use `n.data.parentId` (not React Flow's `n.parentId`) for hierarchy lookups.

### Workspace Lifecycle
`provisioning` → `online` (on register) → `degraded` (error_rate > 0.5) → `online` (recovered) → `offline` (Redis TTL expired) → `removed` (deleted)

## Platform API Routes

| Method | Path | Handler |
|--------|------|---------|
| GET | /health | inline |
| POST/GET/PATCH/DELETE | /workspaces[/:id] | workspace.go |
| GET/PATCH | /workspaces/:id/config | workspace.go |
| GET/POST | /workspaces/:id/memory | workspace.go |
| DELETE | /workspaces/:id/memory/:key | workspace.go |
| POST/PATCH/DELETE | /workspaces/:id/agent | agent.go |
| POST | /workspaces/:id/agent/move | agent.go |
| GET/POST | /workspaces/:id/secrets | secrets.go |
| DELETE | /workspaces/:id/secrets/:key | secrets.go |
| GET | /workspaces/:id/model | secrets.go |
| WS | /workspaces/:id/terminal | terminal.go |
| POST | /workspaces/:id/expand | team.go |
| POST | /workspaces/:id/collapse | team.go |
| POST/GET | /workspaces/:id/approvals | approvals.go |
| POST | /workspaces/:id/approvals/:id/decide | approvals.go |
| GET | /approvals/pending | approvals.go |
| POST/GET | /workspaces/:id/memories | memories.go |
| DELETE | /workspaces/:id/memories/:id | memories.go |
| GET | /workspaces/:id/traces | traces.go |
| POST | /workspaces/:id/restart | workspace.go |
| POST | /workspaces/:id/a2a | workspace.go |
| GET | /workspaces/:id/shared-context | templates.go |
| GET/PUT/DELETE | /workspaces/:id/files[/*path] | templates.go |
| GET/PUT | /canvas/viewport | viewport.go |
| GET | /templates | templates.go |
| POST | /templates/import | templates.go |
| POST | /registry/register | registry.go |
| POST | /registry/heartbeat | registry.go |
| POST | /registry/update-card | registry.go |
| GET | /registry/discover/:id | discovery.go |
| GET | /registry/:id/peers | discovery.go |
| POST | /registry/check-access | discovery.go |
| GET | /bundles/export/:id | bundle.go |
| POST | /bundles/import | bundle.go |
| GET | /events[/:workspaceId] | events.go |
| GET | /ws | socket.go |

## Database

6 migration files in `platform/migrations/`. Key tables: `workspaces` (core entity with status, agent_card JSONB, heartbeat columns), `canvas_layouts` (x/y position), `structure_events` (append-only event log), `agents`, `workspace_secrets`.

The platform auto-discovers and runs migrations on startup from several candidate paths.

<!-- AWARENESS_RULES_START -->
# Project Memory (Awareness MCP)

> IMPORTANT: These instructions override default behavior. You must follow them exactly.

## Awareness Memory Integration (MANDATORY)

awareness_* = cross-session persistent memory (past decisions, knowledge, tasks).
Other tools = current codebase navigation (file search, code index).
Use BOTH - they serve different purposes.

STEP 1 - SESSION START:
  Call awareness_init(source="claude-code") -> get session_id, review context.
  If active_skills[] is returned: skill = reusable procedure done 2+ times;
  summary = injectable instruction, methods = steps. Apply matching skills to tasks.

STEP 2 - RECALL BEFORE WORK (progressive disclosure):
  1. awareness_recall(semantic_query=..., keyword_query=..., detail='summary') → lightweight index.
  2. Review summaries/scores, pick relevant IDs.
  3. awareness_recall(detail='full', ids=[...]) → expand only what you need.

STEP 3 - RECORD EVERY CHANGE:
  After EVERY code edit, decision, or bug fix:
  awareness_record(content=<detailed natural language description>,
    insights={knowledge_cards:[...], action_items:[...], risks:[...]})
  Content should be RICH and DETAILED — include reasoning, key code snippets,
  user quotes, alternatives considered, and files changed. Do NOT compress into
  a single-line summary. The content IS the memory — more detail = better recall.
  Include insights to create searchable knowledge in ONE step (recommended).
  Skipping = permanent data loss.

STEP 4 - CATEGORY GUIDE (for insights.knowledge_cards):
  - decision = choice made between alternatives.
  - problem_solution = bug/problem plus the fix that resolved it.
  - workflow = process, setup, or configuration steps only.
  - pitfall = blocker, warning, or limitation without a fix yet.
  - insight = reusable pattern or general learning.
  - skill = reusable procedure done 2+ times; summary = injectable instruction, methods = steps.
  - key_point = important technical fact when nothing else fits.
  Never default everything to workflow.

STEP 5 - SESSION END:
  awareness_record(content=[step1, step2, ...], insights={...}) with final summary.

BACKFILL (if applicable):
  If MCP connected late: awareness_record(content=<transcript>)

RULES VERSION: Pass rules_version="2" to awareness_init so the server knows you have these rules.
If the server returns _setup_action, the rules have been updated — follow the instruction to re-sync.

NOTE: memory_id from X-Awareness-Memory-Id header. source/actor/event_type auto-inferred.

## Compliance Check

Before responding to ANY user request:

1. Have you called awareness_init yet this session? If not, call it NOW.

2. Did you just edit a file? Call awareness_record(content=<detailed description>, insights={...}) IMMEDIATELY.

3. Is the user asking about past work? Call awareness_recall FIRST.
<!-- AWARENESS_RULES_END -->
