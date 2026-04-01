# Workspace Tiers

The tier system solves the security boundary problem. Different workspace types need different levels of system access, and you cannot run a sudo-capable agent the same way as a text processor.

## Tier Overview

| Tier | Runtime | Capabilities | Use Case |
|------|---------|-------------|----------|
| 1 | Docker (no privileges) | Text/data processing only | SEO, marketing, analysis |
| 2 | Docker + Playwright | Browser access | Web scraping, UI testing |
| 3 | Docker + Xvfb | Full desktop/screen | Computer use agents |
| 4 | EC2 VM | Sudo, filesystem, system | DevOps, Claude Code style |

## Tier 1 — Headless (Most Workspaces)

Pure text/data processing. Docker container with no privileged flags, read-only filesystem, network-isolated. Used for SEO agents, marketing agents, analysis agents. Cheapest to run.

## Tier 2 — Browser

Needs web browser access. Docker container with Playwright installed. Used for web scraping, form filling, UI testing, research agents. Still containerized — no host access.

## Tier 3 — Computer Use

Full desktop access. Docker container with Xvfb (virtual display) and optional VNC. Used for Claude Computer Use-style agents that control GUI applications. Still containerized — the "desktop" is virtual, not the host machine.

## Tier 4 — Privileged / Sudo

Full system access — can install packages, run arbitrary code, manage files, deploy infrastructure. Uses a real **EC2 VM** (not a container) for strong kernel-level isolation. Equivalent to running Claude Code. Never shared — dedicated instance per workspace.

## Code Sandbox by Tier

| Tier | Sandbox |
|------|---------|
| 1, 2 | No sandbox — tools are just API calls |
| 3 | Docker-in-Docker (MVP), Firecracker or E2B (production) |
| 4 | Already a dedicated VM — no extra sandbox needed |

Tier 3 agents can run arbitrary code. Each execution spawns a throwaway container — network disabled, memory capped, read-only filesystem, destroyed after run. See [Code Sandbox](../development/code-sandbox.md) for details.

## How Tiers Work

- The tier is stored in the workspace config (`config.yaml`)
- The tier determines how the **provisioner** deploys the workspace (Docker flags, VM vs container, resource allocation)
- The tier determines the **sandbox backend** for code execution
- The workspace code is the **same** regardless of tier
- The canvas shows a tier badge on each node
- From A2A's perspective, **all tiers look identical** — same protocol, same Agent Card, same message format

## Related Docs

- [Code Sandbox](../development/code-sandbox.md) — Sandbox backends and configuration
- [Workspace Runtime](../agent-runtime/workspace-runtime.md) — The generic runtime that runs at all tiers
- [Provisioner](./provisioner.md) — How tiers affect deployment
- [Architecture](./architecture.md) — Where tiers fit in the system
