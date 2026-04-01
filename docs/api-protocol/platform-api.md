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
| `POST` | `/workspaces/:id/retry` | Retry failed provisioning |

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

### Events

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/events` | Get structure change log |
| `GET` | `/events/:workspaceId` | Get events for one workspace |

See [Event Log](../architecture/event-log.md) for details.

### Templates

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/templates` | List available workspace templates (from `workspace-configs-templates/`) |

Returns summary only — enough to render the template palette card:

```json
[
  {
    "id": "seo-agent",
    "name": "Vancouver SEO Agent",
    "description": "Bilingual EN/ZH SEO page builder",
    "tier": 1,
    "model": "anthropic:claude-sonnet-4-6",
    "skills": ["generate-seo-page", "audit-seo-page", "keyword-research"],
    "skill_count": 3
  }
]
```

Full `config.yaml` is only read from disk at provisioning time (`POST /workspaces`). The template list is scanned at startup and cached in memory — a file watcher on `workspace-configs-templates/` invalidates the cache when templates are added, removed, or modified.

See [Canvas UI — Creating Workspaces](../frontend/canvas.md#creating-workspaces) for the template palette UX.

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
SECRETS_ENCRYPTION_KEY=...   # AES-256 key for workspace_secrets table
```

## Related Docs

- [Registry & Heartbeat](./registry-and-heartbeat.md)
- [Communication Rules](./communication-rules.md)
- [Event Log](../architecture/event-log.md)
- [Database Schema](../architecture/database-schema.md)
- [Bundle System](../agent-runtime/bundle-system.md)
