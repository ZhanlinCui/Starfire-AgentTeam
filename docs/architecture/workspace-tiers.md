# Workspace Tiers

Three tiers control the security boundary for each workspace. Higher tiers get more system access but less isolation.

## Tier Overview

| Tier | Name | Container Flags | Use Case |
|------|------|----------------|----------|
| 1 | Sandboxed | No `/workspace` mount, config-only | SEO, marketing, analysis — text processing only |
| 2 | Standard | Normal Docker + `/workspace` mount | Most agents — can read/write the codebase |
| 3 | Full Access | Privileged + host network + host PID | Dev team, DevOps — full machine access |

## T1 — Sandboxed

Pure text/data processing. Docker container with no workspace mount — the agent can only see its own `/configs` directory. Used for agents that don't need codebase access (content writers, analysts, researchers).

## T2 — Standard (Default)

Normal Docker container with `/workspace` mounted (read-write). The agent can read and modify the codebase. Used for most development and coordination agents. Still containerized — no host access beyond the bind-mounted directories.

## T3 — Full Access

Privileged Docker container with:
- `--privileged` — full device access, can run Docker-in-Docker
- `--network=host` — shares host network stack (can bind ports, access localhost services)
- `--pid=host` — can see host processes

Used for DevOps agents, system administration, and agents that need to interact with the host machine directly. The container has near-VM-level access to the host.

## How Tiers Work

- The tier is stored in both the database (`workspaces.tier`) and `config.yaml`
- The provisioner reads the tier and sets Docker flags accordingly
- The canvas shows a tier badge on each node (T1/T2/T3)
- From A2A's perspective, **all tiers look identical** — same protocol, same Agent Card, same message format
- Tier changes take effect on next restart

## Related Docs

- [Provisioner](./provisioner.md) — How tiers affect deployment
- [Architecture](./architecture.md) — Where tiers fit in the system
