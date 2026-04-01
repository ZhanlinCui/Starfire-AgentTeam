# Technology Choices

This document explains why each technology was chosen for Agent Molecule.

## Next.js 15 (Canvas Frontend)

App router, React Server Components, and easy API proxying to the Go backend. React Flow is the industry standard for node-based canvas UIs and is what Sim.ai, Flowise, and most serious canvas tools use. Zustand is the state manager — lighter than Redux, works cleanly with React Flow's controlled flow pattern.

## Go + Gin (Platform Backend)

The platform API handles high-concurrency concerns: hundreds of workspace heartbeats every 30 seconds, WebSocket connections from multiple canvas clients, Redis pub/sub event broadcasting. Go's goroutines handle this with minimal resource usage. The `gin` framework is minimal and well-documented.

Go is **not** used for agent logic — just infrastructure coordination.

## Python (Workspace Runtime)

Deep Agents (`deepagents` package) and LangGraph are Python-native. There is no benefit to fighting this. Each workspace is a Python process. The Go platform communicates with it only via HTTP (A2A protocol) — Go never needs to understand Python internals.

## Deep Agents + LangGraph

Deep Agents is an "agent harness" built on LangGraph, inspired by Claude Code's architecture. It provides four things out of the box:

1. A planning tool (TODO list)
2. Sub-agent spawning
3. Filesystem-backed memory
4. A detailed system prompt structure

LangGraph is the underlying runtime — it manages the agent loop, state persistence, retries, streaming, and human-in-the-loop.

Neither Deep Agents nor LangGraph provide AI models — they call whatever provider you configure.

## deepagents-acp (A2A Wrapper)

`deepagents-acp` is the package that wraps a Deep Agent as an A2A server. It takes the agent created by `agent.py` and exposes it over HTTP with a standard A2A interface — handling JSON-RPC 2.0 message parsing, Agent Card serving at `/.well-known/agent-card.json`, SSE streaming, and task management. Without it, the agent would have no network-accessible endpoint.

## A2A Protocol

The Agent-to-Agent protocol (Google, Linux Foundation) is the standard for agent-to-agent communication. Key properties:

- Every workspace is an A2A server and can be an A2A client
- Workspaces communicate **directly** without routing through the platform
- Uses JSON-RPC 2.0 over HTTP — any language can implement it
- Any A2A-compliant agent from any framework can plug in

The platform only handles discovery (resolving workspace URLs) and registry (knowing what workspaces exist).

## Docker

Workspace instances are Docker containers. The generic `workspace-template` image is built once. Each instance gets different environment variables injecting the workspace ID, config path, model provider, and tier.

Docker gives: process isolation, easy cleanup, portability. Tier 4 (privileged) workspaces use EC2 VMs instead for stronger isolation.

## Postgres

Source of truth for workspace registry, workspace hierarchy, agent assignments, and the immutable structure event log. The event log is append-only — rows are never updated or deleted. The `workspaces` table is a projection of that log (current state).

Using `wal_level=logical` from the start enables future streaming of change events without a schema migration.

## Redis

Handles everything ephemeral:

- **Liveness detection** via TTL keys — if a workspace stops sending heartbeats, its key expires automatically
- **URL caching** for fast workspace resolution
- **Pub/sub** for broadcasting structure events to canvas WebSocket clients

Redis does not need to be durable — if it restarts, workspaces re-register on next heartbeat.

## Langfuse (Observability)

Self-hosted, fully open source, runs in Docker. LangGraph has native Langfuse integration — setting `LANGFUSE_HOST` is all that's needed. Captures every LLM call across all workspaces in one unified view.

LangSmith (the managed version) requires an enterprise license for self-hosting and was ruled out for this reason.

## Version Requirements

```
Go              1.22+
Python          3.11+
Node.js         20+
Next.js         15
React Flow      11+  (xyflow)
deepagents      0.4+
langfuse        3.x  (self-hosted Docker)
Postgres        16
Redis           7
Docker Compose  2.x
```
