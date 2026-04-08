# Provisioner

The provisioner is the platform component that deploys workspace containers and VMs. It is triggered when a workspace is created, imported from a bundle, or expanded into a team.

## How It Works

1. Platform receives a workspace creation request (API call or bundle import)
2. Platform writes a `WORKSPACE_PROVISIONING` event and broadcasts it (canvas shows spinner)
3. Provisioner reads the workspace config (tier, model, env requirements)
4. Provisioner reads secrets from `workspace_secrets` table, decrypts them, prepares as env vars
5. Provisioner deploys based on tier:
   - **Tier 1-3:** Docker container on `agent-molecule-net`
   - **Tier 4:** EC2 VM with dedicated isolation
5. Provisioner waits for first heartbeat (workspace is live)
6. On first heartbeat: status transitions to `online`
7. On timeout (3 minutes) or immediate error: status transitions to `failed`

## Docker Networking (Tier 1-3)

All workspace containers join the `agent-molecule-net` Docker network. Containers are named `ws-{id[:12]}` (first 12 chars of workspace UUID). Two exported helpers in `provisioner` package provide the canonical naming:

- `provisioner.ContainerName(workspaceID)` → `ws-{id[:12]}`
- `provisioner.InternalURL(workspaceID)` → `http://ws-{id[:12]}:8000`

These are used by discovery, workspace provisioning, and terminal handlers — always use them instead of constructing names inline.

Containers are also given an ephemeral host port binding (`127.0.0.1:0→8000/tcp`) so the platform can reach them from the host.

After `ContainerStart`, the provisioner inspects the container to resolve the actual mapped port and stores the host-accessible URL:

```
http://127.0.0.1:{ephemeral_port}
```

This URL is pre-stored in both Postgres and Redis before the agent registers. When the agent calls `POST /registry/register`, the register endpoint preserves the provisioner URL (any URL starting with `http://127.0.0.1`) instead of overwriting it with the agent's Docker-internal hostname.

**Why not use Docker-internal URLs?** In local dev, the platform runs on the host (not in Docker), so it cannot resolve Docker container hostnames. The ephemeral port mapping lets the A2A proxy reach agents via localhost. In production (platform in Docker), the Docker-internal URL (`http://ws-{id}:8000`) would work directly.

**Workspace-to-workspace discovery:** When a workspace discovers another workspace (via `X-Workspace-ID` header on `GET /registry/discover/:id`), the platform returns the Docker-internal URL (`http://ws-{first12chars}:8000`) so containers can reach each other directly on `agent-molecule-net`. The internal URL is cached in Redis at provision time and also synthesized as a fallback if the cache misses (only for online/degraded workspaces).

For external HTTPS access (multi-host mode), Nginx on the host handles TLS termination and proxies to the container.

## EC2 Deployment (Tier 4)

Tier 4 workspaces run on dedicated EC2 VMs for kernel-level isolation.

**Environment variable delivery:**
- Non-secret config is passed via EC2 **user data**
- Secrets are fetched from the platform via a **one-time token** over HTTPS at startup
- In production: swap to **SSM Parameter Store** — same interface, different backend

## Workspace Lifecycle States

```
provisioning -> online <-----> degraded
     |              |              |
     v              v              v
   failed        offline        offline
     |              |              |
     v              v              v
   removed        removed        removed
     ^              ^
     |              |
  (retry)     (re-register)
```

- `provisioning -> online`: first heartbeat received
- `online -> degraded`: error_rate >= 50% (via heartbeat self-report)
- `degraded -> online`: error_rate < 10% (recovered)
- `online/degraded -> offline`: heartbeat TTL expired
- `provisioning -> failed`: 3min timeout or immediate Docker/EC2 error
- `failed -> provisioning`: user clicks Retry on canvas
- `offline -> online`: workspace re-registers
- `any -> removed`: user deletes workspace

| Status | Meaning | Canvas Display |
|--------|---------|----------------|
| `provisioning` | Container/VM is being spun up, waiting for first heartbeat | Spinner on node |
| `online` | Heartbeat received, reachable, accepting A2A messages | Green node |
| `degraded` | Online but error rate above 50%, self-reported via heartbeat | Yellow node with warning |
| `offline` | Heartbeat TTL expired, unreachable but not deleted | Gray node |
| `failed` | Provisioning timed out or immediate launch error | Red node + retry button |
| `removed` | User deleted it, kept in DB for event log + 410 responses | Node removed from canvas |

## Restart & Runtime Detection

When a workspace is restarted (`POST /workspaces/:id/restart`):

1. **Read runtime** from the running container's `/configs/config.yaml` via `ExecRead` (docker exec) BEFORE stopping it
2. **Stop** the existing container
3. **Resolve template** — checks request body, name-based match, then runtime-default template (e.g. `claude-code-default/`)
4. **Select Docker image** — uses `RuntimeImages[runtime]` (e.g. `workspace-template:claude-code`)
5. **Re-provision** with the same config volume (configs persist across restarts)

**Runtime template fallback:** When a runtime has a default template directory (e.g. `workspace-configs-templates/claude-code-default/`), it's automatically applied on restart. This copies runtime-specific files like `CLAUDE.md`, `.claude/settings.json` into the container — important when switching runtimes via the Config tab.

**Image selection:** Each adapter has its own Docker image extending `workspace-template:base`:

| Runtime | Image |
|---------|-------|
| langgraph | `workspace-template:langgraph` |
| claude-code | `workspace-template:claude-code` |
| crewai | `workspace-template:crewai` |
| autogen | `workspace-template:autogen` |
| deepagents | `workspace-template:deepagents` |
| openclaw | `workspace-template:openclaw` |

## Failure Handling

When provisioning fails:
1. Status set to `failed`
2. `WORKSPACE_PROVISION_FAILED` event written with reason
3. Canvas shows a red node with the error message
4. User can click **Retry** — resets status to `provisioning` and re-runs the provisioner

## Docker Volume Mounts

By default, each workspace gets an isolated named Docker volume:

```
docker volume: ws-{id}-workspace
  -> mounted at /workspace inside the container
  -> persists across: container restart, re-provision, image update
  -> destroyed only when: user deletes workspace or runs nuke.sh
```

The volume is named after the workspace ID, not the container name. So even when a container is destroyed and re-provisioned, the new container mounts the same volume. Tier 1 workspaces skip the workspace volume for read-only isolation.

### Shared Workspace (WORKSPACE_DIR)

When the platform is started with `WORKSPACE_DIR=/path/to/repo`, all workspace containers bind-mount that host directory as `/workspace` instead of using isolated volumes. This gives all agents read/write access to the same codebase:

```bash
WORKSPACE_DIR=/Users/you/project go run ./cmd/server
```

All 15 agents then see the same files — the PM can read `CLAUDE.md`, the Backend Engineer can edit `platform/`, the Frontend Engineer can modify `canvas/`, etc. Changes made by one agent are immediately visible to all others.

See [Memory](./memory.md) for full memory backend details.

## Container Cleanup

When a workspace is deleted:
1. Docker container is stopped and removed
2. For EC2 (tier 4): VM is terminated
3. Memory cleaned up based on backend (volume removed, DB rows deleted, or S3 prefix deleted)
4. Workspace status set to `removed` in Postgres
5. `WORKSPACE_REMOVED` event written
6. Redis keys cleaned up

Structure events and agent card history are **never** deleted — only the conversational memory is cleaned.

## Docker Flags by Tier

| Tier | Flags |
|------|-------|
| 1 | `--network agent-molecule-net` no writable `/workspace` volume (config mount is read-only) |
| 2 | `--network agent-molecule-net` + Playwright pre-installed |
| 3 | `--network agent-molecule-net` + Xvfb + optional VNC |
| 4 | N/A — EC2 VM, not Docker |

## Related Docs

- [Memory](./memory.md) — Memory backends and persistence
- [Workspace Tiers](./workspace-tiers.md) — What each tier provides
- [Workspace Runtime](../agent-runtime/workspace-runtime.md) — What runs inside the container
- [Registry & Heartbeat](../api-protocol/registry-and-heartbeat.md) — How provisioning transitions to online
- [Team Expansion](../agent-runtime/team-expansion.md) — Provisioning triggered by team expansion
