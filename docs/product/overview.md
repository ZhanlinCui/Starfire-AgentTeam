# Overview

## What is Starfire?

Starfire is a visual AI agent orchestration platform. The best one-line description:

> "A visual org chart builder for AI agents — where any agent can become a team, and any team can become a company."

Users open a canvas (like n8n or Figma), drag workspace nodes onto it, nest them into teams, and configure them. Each node is a running AI agent. The platform handles provisioning, discovery, communication, and observability.

## Repository Names

| Repo | Purpose |
|---|---|
| `Starfire-AgentTeam` | The open-source core (this repo) |
| `starfire-cloud` | The future SaaS wrapper repo |

## What Makes This Different

The key insight: **the workspace abstraction**.

In every other platform (n8n, Flowise, Langflow), nodes represent **tasks or tools**. In Starfire, nodes represent **roles**. The AI agent inside is swappable — you can replace one model with another, or replace a single agent with an entire team — without changing the role's position in the hierarchy or its configuration. The outside world always sees the same interface.

## What Starfire Is Not

- **Not a workflow automation tool** (like n8n). Nodes are roles, not tasks.
- **Not a chat interface.** Workspaces communicate programmatically via A2A.
- **Not a model provider.** You bring your own API keys.
- **Not trying to replace LangGraph, CrewAI, AutoGen, Claude Code, or other agent runtimes.** They are optional execution backends inside each workspace.
- **Not a managed service** (for MVP). This is a self-hosted open-source tool.

## Related Docs

- [Core Concepts](./core-concepts.md) — Workspace, Agent, Bundle, Agent Card
- [Architecture](../architecture/architecture.md) — System boundaries and folder structure
- [Technology Choices](../architecture/technology-choices.md) — Why each technology was chosen
