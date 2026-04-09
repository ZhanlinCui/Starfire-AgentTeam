# Platform API (Go Backend)

The Go backend is Starfire's control plane. It does not execute agent reasoning itself. It manages the infrastructure and coordination around workspaces.

## Responsibilities

- workspace lifecycle
- registry and heartbeats
- hierarchy-aware discovery
- A2A proxying for browser-initiated calls
- approvals and activity logs
- memory APIs
- secrets and global secrets
- files, templates, bundles, terminal, and viewport state
- WebSocket fanout to canvas clients and workspaces

## Caller Identification

Workspace-scoped calls use the `X-Workspace-ID` header when the caller is another workspace. Browser/canvas calls do not send that header.

The platform uses the caller identity to enforce hierarchy-based access rules.

## Core Endpoints

### Health and metrics

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |

### Workspaces

| Method | Path | Description |
|---|---|---|
| `POST` | `/workspaces` | Create and provision a workspace |
| `GET` | `/workspaces` | List workspaces with inline canvas layout data |
| `GET` | `/workspaces/:id` | Get one workspace |
| `PATCH` | `/workspaces/:id` | Update name, role, tier, runtime, workspace_dir, parent, etc. |
| `DELETE` | `/workspaces/:id` | Remove workspace |
| `POST` | `/workspaces/:id/restart` | Restart workspace |
| `POST` | `/workspaces/:id/pause` | Pause workspace |
| `POST` | `/workspaces/:id/resume` | Resume workspace |
| `POST` | `/workspaces/:id/a2a` | Proxy A2A request to the target workspace |

Workspace creation also assigns an `awareness_namespace` on the workspace row. That namespace is later injected into the provisioned runtime.

### Registry

| Method | Path | Description |
|---|---|---|
| `POST` | `/registry/register` | Workspace registration on startup |
| `POST` | `/registry/heartbeat` | Liveness and task updates |
| `POST` | `/registry/update-card` | Push Agent Card updates after runtime/skill changes |
| `GET` | `/registry/discover/:id` | Resolve workspace URL for A2A calls |
| `GET` | `/registry/:id/peers` | List reachable peers |
| `POST` | `/registry/check-access` | Validate reachability/access |

### Activity and recall

| Method | Path | Description |
|---|---|---|
| `GET` | `/workspaces/:id/activity` | List activity rows |
| `POST` | `/workspaces/:id/activity` | Report activity from a workspace |
| `POST` | `/workspaces/:id/notify` | Emit user-facing notifications/activity |
| `GET` | `/workspaces/:id/session-search` | Search recent activity + memory for recall |

### Memory

There are two distinct memory surfaces:

#### Scoped agent memory

| Method | Path | Description |
|---|---|---|
| `POST` | `/workspaces/:id/memories` | Commit a `LOCAL` / `TEAM` / `GLOBAL` memory |
| `GET` | `/workspaces/:id/memories` | Search scoped memories |
| `DELETE` | `/workspaces/:id/memories/:memoryId` | Delete an owned memory |

#### Key/value workspace memory

| Method | Path | Description |
|---|---|---|
| `GET` | `/workspaces/:id/memory` | List key/value memory entries |
| `GET` | `/workspaces/:id/memory/:key` | Get one key/value entry |
| `POST` | `/workspaces/:id/memory` | Upsert a key/value entry with optional TTL |
| `DELETE` | `/workspaces/:id/memory/:key` | Delete a key/value entry |

### Secrets

#### Workspace secrets

| Method | Path | Description |
|---|---|---|
| `GET` | `/workspaces/:id/secrets` | Return merged workspace + inherited global secret metadata |
| `POST` | `/workspaces/:id/secrets` | Upsert workspace secret |
| `PUT` | `/workspaces/:id/secrets` | Upsert workspace secret |
| `DELETE` | `/workspaces/:id/secrets/:key` | Delete workspace secret |
| `GET` | `/workspaces/:id/model` | Get workspace model override |

Important detail: `GET /workspaces/:id/secrets` does **not** return values. It returns key metadata plus a `scope` field so the frontend can distinguish inherited globals from workspace overrides.

#### Global secrets

| Method | Path | Description |
|---|---|---|
| `GET` | `/settings/secrets` | List global secret metadata |
| `POST` | `/settings/secrets` | Upsert global secret |
| `PUT` | `/settings/secrets` | Upsert global secret |
| `DELETE` | `/settings/secrets/:key` | Delete global secret |

Backward-compatible admin aliases also exist under `/admin/secrets`.

### Approvals

| Method | Path | Description |
|---|---|---|
| `GET` | `/approvals/pending` | List pending approvals |
| `POST` | `/workspaces/:id/approvals` | Create approval request |
| `GET` | `/workspaces/:id/approvals` | List approvals for a workspace |
| `POST` | `/workspaces/:id/approvals/:approvalId/decide` | Approve or deny |

### Team operations

| Method | Path | Description |
|---|---|---|
| `POST` | `/workspaces/:id/expand` | Expand workspace into a team |
| `POST` | `/workspaces/:id/collapse` | Collapse team back down |

### Plugins

| Method | Path | Description |
|---|---|---|
| `GET` | `/plugins` | List available plugins from registry |
| `GET` | `/workspaces/:id/plugins` | List installed plugins in workspace |
| `POST` | `/workspaces/:id/plugins` | Install plugin `{"name":"ecc"}` — copies to container, auto-restarts |
| `DELETE` | `/workspaces/:id/plugins/:name` | Uninstall plugin — removes from container, auto-restarts |

Plugins are installed per-workspace into `/configs/plugins/<name>/`. The registry is the `plugins/` directory at the repo root, each containing a `plugin.yaml` manifest. Plugin names are validated (no path traversal).

### Files and templates

| Method | Path | Description |
|---|---|---|
| `GET` | `/templates` | List available templates |
| `POST` | `/templates/import` | Import an agent folder as a new template |
| `GET` | `/workspaces/:id/shared-context` | Read parent shared-context files |
| `GET` | `/workspaces/:id/files` | List files under an allowed root |
| `GET` | `/workspaces/:id/files/*path` | Read a file |
| `PUT` | `/workspaces/:id/files/*path` | Write a file |
| `PUT` | `/workspaces/:id/files` | Replace workspace file set |
| `DELETE` | `/workspaces/:id/files/*path` | Delete a file |

Query parameters for `GET /workspaces/:id/files`:

| Param | Default | Description |
|-------|---------|-------------|
| `root` | `/configs` | Base path — one of `/configs`, `/workspace`, `/home`, `/plugins` |
| `path` | `""` | Subdirectory relative to root (validated against path traversal) |
| `depth` | `1` | Max recursion depth (1–5). Use with `path` for lazy-loading subdirectories |

Invalid `depth` or traversal paths return 400.

### Terminal

| Protocol | Path | Description |
|---|---|---|
| `WS` | `/workspaces/:id/terminal` | Terminal session into the running container |

### Bundles

| Method | Path | Description |
|---|---|---|
| `GET` | `/bundles/export/:id` | Export workspace tree as a bundle |
| `POST` | `/bundles/import` | Import a bundle |

### Canvas viewport and events

| Method | Path | Description |
|---|---|---|
| `GET` | `/canvas/viewport` | Get saved canvas pan/zoom |
| `PUT` | `/canvas/viewport` | Save canvas pan/zoom |
| `GET` | `/events` | List structure events |
| `GET` | `/events/:workspaceId` | List workspace-scoped events |

### WebSocket

| Protocol | Path | Description |
|---|---|---|
| `WS` | `/ws` | Live events for canvas clients and workspaces |

Canvas clients receive the global event stream. Workspaces connect with `X-Workspace-ID` and receive filtered events based on communication rules.

## A2A Proxy Behavior

`POST /workspaces/:id/a2a` is more than a naive forwarder.

It currently:

- normalizes incoming JSON into JSON-RPC 2.0
- injects `messageId` when missing
- applies different timeout rules for browser-initiated vs workspace-initiated calls
- logs the resulting A2A activity
- broadcasts successful browser-initiated responses back to the canvas as `A2A_RESPONSE`
- triggers restart flow when the target container is confirmed dead

That is why the chat UX no longer depends on polling as the primary response path.

## Environment Variables

```bash
DATABASE_URL=postgres://dev:dev@postgres:5432/agentmolecule?sslmode=prefer
REDIS_URL=redis://redis:6379
PORT=8080
SECRETS_ENCRYPTION_KEY=...
ACTIVITY_RETENTION_DAYS=7
ACTIVITY_CLEANUP_INTERVAL_HOURS=6
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
RATE_LIMIT=600
```

## Related Docs

- [Registry & Heartbeat](./registry-and-heartbeat.md)
- [Communication Rules](./communication-rules.md)
- [Workspace Runtime](../agent-runtime/workspace-runtime.md)
- [Canvas UI](../frontend/canvas.md)
