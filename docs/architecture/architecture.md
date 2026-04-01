# System Architecture

## Overview

The platform is fully distributed — workspaces can run on different machines and communicate via the A2A (Agent-to-Agent) protocol.

## System Boundaries

The platform consists of four distinct systems:

```
+-----------------------------------------------------------+
|  canvas/              Next.js 15 frontend                  |
|  React Flow visual canvas, Zustand state, WebSocket        |
+-----------------------------+-----------------------------+
                              | HTTP + WebSocket
+-----------------------------v-----------------------------+
|  platform/            Go (gin) backend                     |
|  Registry, hierarchy, event log, provisioner, bundles       |
+------+---------------------------------------+------------+
       | Postgres                               | Redis
+------v------+                       +---------v---------+
|  Postgres   |                       |     Redis         |
|  (Docker)   |                       |    (Docker)       |
+-------------+                       +-------------------+

       A2A HTTP (JSON-RPC 2.0) — direct workspace-to-workspace
+-----------------------------------------------------------+
|  workspace-template/  Python agent runtime                 |
|  Deep Agents + LangGraph + deepagents-acp (A2A wrapper)    |
|  One container instance per running workspace              |
+-----------------------------------------------------------+
       |
+------v----------------------------------------------------+
|  Langfuse             Observability (Docker)               |
|  Traces every LLM call across all workspaces               |
+-----------------------------------------------------------+
```

### Data Flow Summary

- **Canvas <-> Platform:** HTTP REST + WebSocket for real-time events
- **Platform <-> Postgres:** Source of truth for registry, hierarchy, events
- **Platform <-> Redis:** Ephemeral state — liveness, caching, pub/sub
- **Platform -> Workspace:** Provisioning (Docker/EC2), discovery
- **Workspace <-> Workspace:** Direct A2A (JSON-RPC 2.0) — platform not in path
- **Workspace -> Langfuse:** Automatic LLM tracing

## Folder Structure

```
agent-molecule/
|
+-- docker-compose.yml               # full local dev stack
+-- docker-compose.infra.yml         # postgres, redis, langfuse only
+-- .env.example
+-- README.md
|
+-- canvas/                          # Next.js 15 frontend
+-- platform/                        # Go backend
+-- workspace-template/              # Python agent runtime (generic image)
+-- workspace-configs-templates/     # workspace personality definitions
+-- infra/                           # scripts + langfuse compose
+-- docs/                            # documentation
```

## Related Docs

- [Platform API](../api-protocol/platform-api.md) — Go backend details
- [Workspace Runtime](../agent-runtime/workspace-runtime.md) — Python runtime details
- [Canvas UI](../frontend/canvas.md) — Next.js frontend details
- [Technology Choices](./technology-choices.md) — Why each piece was chosen
