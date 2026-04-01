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
Must run from `platform/` directory (not repo root). Env vars: `DATABASE_URL`, `REDIS_URL`, `PORT` (defaults: postgres://dev:dev@localhost:5432/agentmolecule?sslmode=disable, redis://localhost:6379, 8080).

`molecli` reads `MOLECLI_URL` (default http://localhost:8080) to locate the platform. Logs are written to `molecli.log` in the working directory (already covered by `*.log` in `.gitignore`).

### Canvas (Next.js)
```bash
cd canvas
npm install
npm run dev                  # Dev server on :3000
npm run build && npm start   # Production
```
Env vars: `NEXT_PUBLIC_PLATFORM_URL` (default http://localhost:8080), `NEXT_PUBLIC_WS_URL` (default ws://localhost:8080/ws).

### Integration Tests
```bash
bash test_api.sh             # Runs 34 API tests against localhost:8080
```
Requires platform running. Tests full CRUD, registry, heartbeat, discovery, peers, access control, events, degraded/recovery lifecycle.

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

### Workspace Lifecycle
`provisioning` → `online` (on register) → `degraded` (error_rate > 0.5) → `online` (recovered) → `offline` (Redis TTL expired) → `removed` (deleted)

## Platform API Routes

| Method | Path | Handler |
|--------|------|---------|
| GET | /health | inline |
| POST/GET/PATCH/DELETE | /workspaces[/:id] | workspace.go |
| POST | /registry/register | registry.go |
| POST | /registry/heartbeat | registry.go |
| POST | /registry/update-card | registry.go |
| GET | /registry/discover/:id | discovery.go |
| GET | /registry/:id/peers | discovery.go |
| POST | /registry/check-access | discovery.go |
| GET | /events[/:workspaceId] | events.go |
| GET | /ws | socket.go |

## Database

5 migration files in `platform/migrations/`. Key tables: `workspaces` (core entity with status, agent_card JSONB, heartbeat columns), `canvas_layouts` (x/y position), `structure_events` (append-only event log), `agents`, `workspace_secrets`.

The platform auto-discovers and runs migrations on startup from several candidate paths.
