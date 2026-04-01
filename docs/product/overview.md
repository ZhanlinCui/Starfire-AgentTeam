# Overview

## What is Agent Molecule?

Agent Molecule is a visual AI agent orchestration platform. The best one-line description:

> "A visual org chart builder for AI agents — where any agent can become a team, and any team can become a company."

Users open a canvas (like n8n or Figma), drag workspace nodes onto it, nest them into teams, and configure them. Each node is a running AI agent. The platform handles provisioning, discovery, communication, and observability.

## The Chemistry Metaphor

The name comes from chemistry:

| Term | Meaning |
|---|---|
| **Agent Molecule** | The product name |
| **Atom** | An individual AI agent inside a workspace |
| **Molecule** | A workspace (the core unit) |
| **Bond** | An A2A relationship between workspaces (parent/child or sibling) |
| **Compound** | A team of workspaces bonded together |

Just like real chemistry, the structure can be as simple or as complex as needed, and you can always zoom in to see what a molecule is made of.

## Repository Names

| Repo | Purpose |
|---|---|
| `agent-molecule` | The open-source core (this repo) |
| `agent-molecule-cloud` | The future SaaS wrapper repo |

## What Makes This Different

The key insight: **the workspace abstraction**.

In every other platform (n8n, Flowise, Langflow), nodes represent **tasks or tools**. In Agent Molecule, nodes represent **roles**. The AI agent inside is swappable — you can replace one model with another, or replace a single agent with an entire team — without changing the role's position in the hierarchy or its configuration. The outside world always sees the same interface.

## What Agent Molecule Is Not

- **Not a workflow automation tool** (like n8n). Nodes are roles, not tasks.
- **Not a chat interface.** Workspaces communicate programmatically via A2A.
- **Not a model provider.** You bring your own API keys.
- **Not trying to replace LangGraph or Deep Agents.** They are the agent engine inside each workspace.
- **Not a managed service** (for MVP). This is a self-hosted open-source tool.

## Related Docs

- [Core Concepts](./core-concepts.md) — Workspace, Agent, Bundle, Agent Card
- [Architecture](../architecture/architecture.md) — System boundaries and folder structure
- [Technology Choices](../architecture/technology-choices.md) — Why each technology was chosen
