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

All workspace containers join the `agent-molecule-net` Docker network. Containers are addressed by container name:

```
http://ws-{id}:8000
```

This is the internal URL. The platform, Redis, and Postgres are all on the same network.

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

## Failure Handling

When provisioning fails:
1. Status set to `failed`
2. `WORKSPACE_PROVISION_FAILED` event written with reason
3. Canvas shows a red node with the error message
4. User can click **Retry** — resets status to `provisioning` and re-runs the provisioner

## Docker Volume Mounts

Each workspace gets a named Docker volume for memory persistence:

```
docker volume: ws-{id}-memory
  -> mounted at /memory inside the container
  -> persists across: container restart, re-provision, image update
  -> destroyed only when: user deletes workspace or runs nuke.sh
```

The volume is named after the workspace ID, not the container name. So even when a container is destroyed and re-provisioned, the new container mounts the same volume.

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
| 1 | `--read-only --network agent-molecule-net` (named volumes like `/memory` remain writable) |
| 2 | `--network agent-molecule-net` + Playwright pre-installed |
| 3 | `--network agent-molecule-net` + Xvfb + optional VNC |
| 4 | N/A — EC2 VM, not Docker |

## Related Docs

- [Memory](./memory.md) — Memory backends and persistence
- [Workspace Tiers](./workspace-tiers.md) — What each tier provides
- [Workspace Runtime](../agent-runtime/workspace-runtime.md) — What runs inside the container
- [Registry & Heartbeat](../api-protocol/registry-and-heartbeat.md) — How provisioning transitions to online
- [Team Expansion](../agent-runtime/team-expansion.md) — Provisioning triggered by team expansion
