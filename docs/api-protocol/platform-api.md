# Platform API (Go Backend)

The Go backend is the **control plane**. It does not run agent logic — it manages the infrastructure around agents.

## Responsibilities

- Workspace CRUD (create, read, update, delete)
- Agent Card registry (store and serve cards)
- Heartbeat management (Redis TTL liveness detection)
- Hierarchy-based peer discovery and access control
- Structure event log (append-only change history)
- WebSocket broadcaster (push events to canvas in real time)
- Workspace provisioner (spin up Docker containers or EC2 VMs)
- Bundle import/export

## Caller Identification

All scoped endpoints use the `X-Workspace-ID` header to identify the calling workspace. The platform uses this to enforce access control via `CanCommunicate()`. Canvas clients do not send this header — they are not workspaces and have unrestricted read access (auth is handled in the SaaS layer).

## API Endpoints

### Workspaces

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/workspaces` | Create workspace from template (body: `{ template, name, model, tier, parent_id, canvas }`) |
| `GET` | `/workspaces` | List all workspaces (JOINs `canvas_layouts` — returns x, y, collapsed inline) |
| `GET` | `/workspaces/:id` | Get workspace + agent card |
| `PATCH` | `/workspaces/:id` | Update workspace fields (name, role, tier, model, parent_id) |
| `DELETE` | `/workspaces/:id` | Remove workspace |
| `POST` | `/workspaces/:id/expand` | Expand workspace into a team (provisions sub-workspaces from config) |
| `POST` | `/workspaces/:id/collapse` | Collapse team back to single workspace (stops sub-workspaces) |
| `POST` | `/workspaces/:id/restart` | Restart offline/failed workspace (stops old container, re-provisions) |
| `POST` | `/workspaces/:id/a2a` | Proxy A2A JSON-RPC to workspace agent (injects `messageId`, wraps envelope) |

### Config & Memory

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/workspaces/:id/config` | Get workspace config as JSON |
| `PATCH` | `/workspaces/:id/config` | Update workspace config |
| `GET` | `/workspaces/:id/memory` | List all memory entries |
| `GET` | `/workspaces/:id/memory/:key` | Get a specific memory entry |
| `POST` | `/workspaces/:id/memory` | Set a memory entry (body: `{ key, value, ttl_seconds? }`) |
| `DELETE` | `/workspaces/:id/memory/:key` | Delete a memory entry |

### Secrets (API Keys & Env Vars)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/workspaces/:id/secrets` | List secret keys only (values never exposed to browser) |
| `POST` | `/workspaces/:id/secrets` | Set a secret (body: `{ key, value }`) — upsert |
| `DELETE` | `/workspaces/:id/secrets/:key` | Delete a secret |
| `GET` | `/workspaces/:id/model` | Get current model override from secrets |

Secrets are stored in `workspace_secrets` table as plaintext bytes for MVP (AES-256 encryption planned for Phase 14). The provisioner reads secrets at container deploy time and injects them as environment variables. Common keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `MODEL_PROVIDER`.

### Terminal

| Protocol | Path | Description |
|----------|------|-------------|
| `WS` | `/workspaces/:id/terminal` | WebSocket shell session into workspace container |

Upgrades to WebSocket, creates a Docker exec `/bin/sh` session, bridges stdin/stdout. Sessions auto-close after 30 minutes of inactivity. WebSocket origins restricted to localhost.

### Approvals (Human-in-the-Loop)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/approvals/pending` | List all pending approvals across workspaces (single query) |
| `POST` | `/workspaces/:id/approvals` | Create approval request (body: `{ action, reason }`) |
| `GET` | `/workspaces/:id/approvals` | List approvals for a workspace |
| `POST` | `/workspaces/:id/approvals/:approvalId/decide` | Approve or deny (body: `{ decision, decided_by }`) |

Pending approvals auto-expire after 10 minutes. Events: `APPROVAL_REQUESTED`, `APPROVAL_ESCALATED`, `APPROVAL_APPROVED`, `APPROVAL_DENIED`.

### Agent Memories (HMA)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/workspaces/:id/memories` | Commit a memory fact (body: `{ content, scope }`) |
| `GET` | `/workspaces/:id/memories` | Search memories (params: `q`, `scope`) |
| `DELETE` | `/workspaces/:id/memories/:memoryId` | Delete a memory |

Scopes: `LOCAL` (workspace only), `TEAM` (parent + siblings), `GLOBAL` (all read, root write only). Access enforced via `CanCommunicate()`.

### Agents

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/workspaces/:id/agent` | Assign an agent to a workspace |
| `PATCH` | `/workspaces/:id/agent` | Replace agent model (triggers `AGENT_REPLACED`) |
| `DELETE` | `/workspaces/:id/agent` | Remove agent from workspace |
| `POST` | `/workspaces/:id/agent/move` | Move agent to a different workspace (body: `{ target_workspace_id }`) |

### Registry

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/registry/register` | Workspace announces itself on startup |
| `POST` | `/registry/heartbeat` | Workspace sends liveness ping + health stats every 30s |
| `POST` | `/registry/update-card` | Workspace pushes updated Agent Card after skill reload |
| `GET` | `/registry/discover/:id` | Resolve workspace URL by ID (scoped — 403 for private sub-workspaces) |

See [Registry & Heartbeat](./registry-and-heartbeat.md) for the full flow.

### Hierarchy & Peers

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/registry/:id/peers` | Get reachable workspaces (siblings + children + parent) |
| `POST` | `/registry/check-access` | Validate if caller can communicate with target |

Communication topology is derived from the `parent_id` hierarchy — there is no manual connection wiring. See [Communication Rules](./communication-rules.md).

### Activity Logs

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/workspaces/:id/activity` | List activity logs (params: `type`, `limit`) |
| `POST` | `/workspaces/:id/activity` | Agent self-reports activity (body: `{ activity_type, method?, summary?, target_id?, status?, error_detail?, duration_ms?, metadata? }`) |

Activity types: `a2a_send`, `a2a_receive`, `task_update`, `agent_log`, `error`. Invalid types return 400. Limit defaults to 100, max 500. A2A proxy calls are logged automatically.

### Traces (Langfuse)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/workspaces/:id/traces` | List recent LLM traces from Langfuse (proxied) |

### Events

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/events` | Get structure change log |
| `GET` | `/events/:workspaceId` | Get events for one workspace |

See [Event Log](../architecture/event-log.md) for details.

### Templates & Files

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/templates` | List available workspace templates (from `workspace-configs-templates/`) |
| `POST` | `/templates/import` | Import agent folder as a new template (body: `{ name, files }`) |
| `GET` | `/workspaces/:id/files` | List workspace config file tree |
| `GET` | `/workspaces/:id/files/*path` | Read a workspace config file |
| `PUT` | `/workspaces/:id/files/*path` | Write/create a workspace config file |
| `PUT` | `/workspaces/:id/files` | Replace all workspace config files (body: `{ files }`) |
| `DELETE` | `/workspaces/:id/files/*path` | Delete a workspace config file |

All file paths are validated against path traversal (`../` and absolute paths blocked).

### Canvas Viewport

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/canvas/viewport` | Get saved canvas pan/zoom state |
| `PUT` | `/canvas/viewport` | Save canvas pan/zoom state (body: `{ x, y, zoom }`) |

### Team Expansion

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/workspaces/:id/expand` | Expand workspace into team (creates sub-workspaces from config) |
| `POST` | `/workspaces/:id/collapse` | Collapse team (stops and removes sub-workspaces) |

### Bundles

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/bundles/import` | Provision workspace tree from bundle |
| `GET` | `/bundles/export/:id` | Export running workspace as bundle |

See [Bundle System](../agent-runtime/bundle-system.md) for the format specification.

### WebSocket

| Protocol | Path | Description |
|----------|------|-------------|
| `WS` | `/ws` | Real-time structure events — canvas clients and workspace agents both subscribe |

Both canvas clients and workspace agents connect to the same WebSocket endpoint. Workspaces send `X-Workspace-ID` header on connect — the platform filters events server-side so each workspace only receives events about workspaces it can communicate with (via `CanCommunicate()`). Canvas clients connect without the header and receive all events.

## Environment Variables

```
DATABASE_URL=postgres://dev:dev@postgres:5432/agentmolecule
REDIS_URL=redis://redis:6379
PORT=8080
SECRETS_ENCRYPTION_KEY=...                # AES-256 key for workspace_secrets table
ACTIVITY_RETENTION_DAYS=7                 # How long to keep activity logs (default: 7)
ACTIVITY_CLEANUP_INTERVAL_HOURS=6         # How often to purge old logs (default: 6)
```

## Related Docs

- [Registry & Heartbeat](./registry-and-heartbeat.md)
- [Communication Rules](./communication-rules.md)
- [Event Log](../architecture/event-log.md)
- [Database Schema](../architecture/database-schema.md)
- [Bundle System](../agent-runtime/bundle-system.md)
