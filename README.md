<div align="center">

<p>
  <img src="./docs/assets/branding/starfire-icon.png" alt="Starfire Icon Logo" width="160" />
</p>

<p>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/branding/starfire-text-white.png">
    <img src="./docs/assets/branding/starfire-text-black.png" alt="Starfire Text Logo" width="420" />
  </picture>
</p>

<p>
  <a href="./README.md">English</a> | <a href="./README.zh-CN.md">中文</a>
</p>

**The Organizational Operating System for AI Agents**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Go Version](https://img.shields.io/badge/go-1.25+-00ADD8?logo=go)](https://golang.org/)
[![Python Version](https://img.shields.io/badge/python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org/)

[Product Requirements Document (PRD)](./docs/product/PRD.md) • 
[Architecture](./docs/architecture/architecture.md) • 
[Communication Protocol](./docs/api-protocol/a2a-protocol.md) • 
[Agent Runtime](./docs/agent-runtime/workspace-runtime.md)

[Quick Start](#-quick-start) •
[Compatible Agent Architectures](#compatible-agent-architectures) •
[Memory Architecture](#why-the-memory-architecture-is-ahead)

---

**Deploy in one click:**

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/ZhanlinCui/Starfire-AgentTeam)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ZhanlinCui/Starfire-AgentTeam)

<!-- 
  DEMO GIF — INSERT HERE
  Recommended: 800×500px, max 5MB, recorded at the steps in docs/demo/fractal-expansion-script.md
  Format: ![Starfire fractal expansion demo](./docs/demo/fractal-expansion.gif)
-->

</div>

---

> *Build an AI organization, not a brittle prompt chain.*

Starfire is a **commercial-grade orchestration and control plane for AI agent teams**. It helps teams move from isolated single-agent demos to real operating structures with roles, delegation boundaries, runtime compatibility, memory isolation, approval flows, and full observability.

Instead of treating each node as a task, Starfire treats each node as a **workspace role**. A workspace can be one agent today, a full sub-team tomorrow, and still keep the same interface, permissions, memory boundary, and position in the org chart.

---

## Why Starfire Exists

Most agent products work well in a demo and break down in an organization. The failure modes are predictable:

| Production problem | What breaks in conventional agent setups | How Starfire solves it |
|---|---|---|
| One giant general-purpose agent becomes the bottleneck | Context mixes planning, execution, approvals, and domain knowledge into one fragile thread | Split work into persistent workspace roles with explicit hierarchy and delegation paths |
| Multi-agent graphs become hard to evolve | Teams hard-code topology, edges, and routing logic into the workflow itself | The org chart is the topology, so structure changes do not require rewiring the entire system |
| Different teams prefer different agent frameworks | LangGraph, Claude Code, CrewAI, AutoGen, and CLI agents rarely share one operating model | Starfire standardizes them behind one workspace lifecycle, A2A contract, memory surface, and canvas |
| Shared memory leaks across teams | Flat global memory stores ignore org boundaries and create governance risk | HMA aligns memory access to reporting lines, team boundaries, and explicit scopes |
| No operational control plane | Demos lack approvals, liveness, retries, tracing, and restart behavior | Starfire adds platform registry, health detection, restart flows, HITL escalation, and event streaming |

## What Makes It Commercially Useful

- **Role-native orchestration:** model choice is swappable, but the role, permissions, memory, and topology stay stable.
- **Progressive scale-up:** turn one workspace into a managed sub-team without changing how the rest of the system talks to it.
- **Operational guardrails:** workspace lifecycle, health sweeps, approval escalation, and runtime tiering are part of the platform, not ad hoc scripts.
- **Enterprise-friendly isolation:** access control, memory segmentation, and workspace-level config/secrets are enforced at the platform layer.
- **Heterogeneous runtime support:** teams can standardize governance without standardizing on one agent framework.

## Compatible Agent Architectures

Starfire is designed to unify heterogeneous agent stacks under one operating model rather than forcing every team into one framework.

| Runtime | Architecture style | Native strength | What Starfire adds |
|---|---|---|---|
| **LangGraph** | Graph-based Python agent runtime | Structured tool use, controllable execution graph, skills/plugins | Canvas orchestration, A2A delegation, org-aware memory, runtime tiers, platform lifecycle |
| **DeepAgents** | Planning-heavy LangGraph variant | Deeper task decomposition and coordination patterns | Same workspace contract, hierarchy routing, observability, and restart behavior |
| **Claude Code** | Agentic CLI runtime | Real coding workflows, native session continuity, CLAUDE.md and tool hooks | Secure workspace containerization, MCP/A2A delegation, org topology, shared control plane |
| **CrewAI** | Role-based multi-agent framework | Lightweight crew composition and task-oriented collaboration | Persistent workspace identity, access control, shared canvas, standardized agent card and registry |
| **AutoGen** | Assistant-agent + tool orchestration | Tool-rich conversational agents and Microsoft ecosystem fit | Same deployment model, runtime governance, memory surface, and inter-agent communication layer |
| **OpenClaw** | CLI-native agent runtime | Alternative agent CLI workflows with native session handling | Workspace lifecycle, platform routing, monitoring, and hierarchical collaboration model |

All of these runtimes plug into the same workspace abstraction, the same A2A communication rules, and the same control plane.

## Why The Memory Architecture Is Ahead

Starfire's **HMA (Hierarchical Memory Architecture)** is built for organizations, not just agents.

| Conventional agent memory | Starfire HMA |
|---|---|
| Flat global memory store or loosely separated app-level namespaces | Memory scopes mirror the org chart: **L1 Local**, **L2 Team**, **L3 Global** |
| Memory sharing is usually implicit and easy to overexpose | Sharing is deliberate and topology-aware, aligned to reporting lines and team structure |
| Isolation is often a convention in application code | Isolation is backed by workspace awareness namespaces, platform rules, and RLS-backed access boundaries |
| Good for recall, weak for governance | Built for recall **and** governance, so teams can segment sensitive knowledge by organizational boundary |
| Memory and operating procedures stay disconnected | Durable patterns can be promoted from memory into reusable skills, then hot-loaded back into the runtime |

This matters commercially because real teams do not want one agent accidentally reading every other team's working memory. Starfire treats memory like organizational infrastructure, not a global scratchpad.

## Core Differentiators

### 👥 Role-Based Abstraction
In other platforms, nodes are API tasks. In Starfire, a node is a **Workspace**: an organizational role such as Developer PM, Marketing Lead, or QA. The underlying model and runtime can change without breaking the team's structure.

### 🍱 Recursive Team Expansion (Fractal Architecture)
Any workspace can expand into an internal sub-team while continuing to expose a single A2A interface externally. Start with one specialist, then scale that specialist into a department without changing upstream integrations.

### 🌐 The Org Chart IS the Topology
There are zero edge-drawing wires on the Starfire canvas. Communication paths are inferred from `parent_id` hierarchy, which means topology and access policy stay aligned by default.
- Siblings can talk to siblings.
- Parents can delegate to children.
- Children report up to parents.
**The organizational structure intrinsically enforces your access control policies.**

### 🧠 Hierarchical Memory Architecture (HMA)
Starfire introduces **topology-aware memory isolation**:
- **L1 (Local Memory):** Scratchpads strictly isolated to the individual agent.
- **L2 (Team Shared Memory):** Retrievable only by a Team Lead and its direct children. Enforced by Row-Level Security.
- **L3 (Corporate Memory):** Top-down global knowledge bases (like employee handbooks) managed by the Root Workspace.

### 📈 Full Observability & Hierarchical Human-in-the-Loop
Every LLM call across your distributed team can be traced through **Langfuse**. When a workspace detects a high-risk action, it can pause and escalate up the org chart until an authorized parent or human approves the action.

### 🛡️ Tiered Security & Runtime Isolation
Different roles need different privileges. Starfire natively isolates workspaces:
- **Tier 1:** Text/Data Processing (Network Isolated, Read-only Docker)
- **Tier 2:** Standard Workspace (resource-limited Docker + shared `/workspace` mount)
- **Tier 3:** Privileged Operations (`--privileged` + host PID, Docker network)
- **Tier 4:** Full Host Access (privileged + host PID + host network + Docker socket)

---

## 📚 Documentation 

Starfire has extensive, production-ready documentation organized by layer:

- 📖 **[Product & Concepts](./docs/product/)**
  - [Comprehensive PRD](./docs/product/PRD.md) | [Core Concepts](./docs/product/core-concepts.md)
- 🏗️ **[Architecture & Infrastructure](./docs/architecture/)**
  - [System Architecture](./docs/architecture/architecture.md) | [Database Schema](./docs/architecture/database-schema.md) | [Provisioner](./docs/architecture/provisioner.md)
- 🔌 **[Protocols & APIs](./docs/api-protocol/)**
  - [A2A Communication Protocol](./docs/api-protocol/a2a-protocol.md) | [Hierarchy Routing Rules](./docs/api-protocol/communication-rules.md)
- 🤖 **[Workspace Agent Runtime](./docs/agent-runtime/)**
  - [Runtime Overview](./docs/agent-runtime/workspace-runtime.md) | [Skills Ecosystem](./docs/agent-runtime/skills.md) | [Team Expansion Mechanics](./docs/agent-runtime/team-expansion.md)
- 🛠️ **[Development & Deployment](./docs/development/)**
  - [Build & Run Order](./docs/development/build-order.md) | [Observability](./docs/development/observability.md)
- 🎨 **[Frontend Canvas](./docs/frontend/)**
  - [Next.js Web Canvas Engine](./docs/frontend/canvas.md)

---

## ⚡ Quick Start

A full local deployment starts the entire multi-agent platform using Docker Compose.

Recommended local path:
1. Start the shared infrastructure with `./infra/scripts/setup.sh`
2. Run `molecli doctor` from the repo root to verify local prerequisites
3. Start the platform control plane
4. Start the Canvas frontend
5. Open the Canvas and deploy your first template

```bash
# 1. Setup the Infrastructure (Postgres, Redis, Langfuse)
./infra/scripts/setup.sh

# 2. Verify your local environment
molecli doctor

# 3. Run the Platform Control Plane (Go)
cd platform
go run ./cmd/server

# 4. Run the Canvas Frontend (Next.js 15)
cd ../canvas
npm install
npm run dev
```

Navigate to `http://localhost:3000`, open the template palette, and deploy your first Agent workspace.

---

## 🏢 Architecture Overview

Starfire is a thoroughly distributed system:
1. **Canvas (Next.js 15):** The React Flow visual canvas. Communicates via HTTP + WebSockets.
2. **Platform (Go / Gin):** The Control Plane. Handles workspace CRUD, A2A discovery, registry liveness checks (Redis), and event streaming (Postgres pub/sub).
3. **Workspace Runtime (pluggable adapters):** A unified runtime layer for LangGraph, DeepAgents, Claude Code, CrewAI, AutoGen, and OpenClaw, all exposed as standardized A2A workspaces.

> *Workspaces talk directly to one another via JSON-RPC 2.0. The platform is never in the data path of an agent conversation.*

---

## ☁️ One-Click Cloud Deployment

Starfire ships `railway.toml` and `render.yaml` for zero-config cloud deployment. Both platforms provision managed Postgres and Redis automatically.

### Railway
```bash
# Option A: Click the deploy button in the README
# Option B: CLI deploy
railway login
railway init
railway up
```

### Render
```bash
# Option A: Click the deploy button in the README
# Option B: Blueprint deploy from the Render dashboard
#   New → Blueprint → point at your GitHub repo
```

### Required Environment Variables

| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | ✅ | Postgres connection string | auto-injected by Railway/Render |
| `REDIS_URL` | ✅ | Redis connection string | auto-injected by Railway/Render |
| `SECRETS_ENCRYPTION_KEY` | ✅ | AES-256 key for workspace secrets | `openssl rand -base64 32` |
| `PLATFORM_URL` | ✅ | Public URL of the platform service | `https://starfire-platform.up.railway.app` |
| `CORS_ORIGINS` | ✅ | Comma-separated allowed origins | `https://starfire-canvas.up.railway.app` |
| `PORT` | — | API server port (default `8080`) | auto-set by Railway/Render |
| `RATE_LIMIT` | — | Requests/min per IP (default `100`) | `500` |
| `ACTIVITY_RETENTION_DAYS` | — | Activity log retention (default `7`) | `30` |

> **Note:** Workspace agent containers are provisioned by the platform via the Docker socket. Cloud deployments that don't support Docker-in-Docker (Railway, Render free tier) will run without the provisioner; workspaces must be started externally and registered via the API. For full provisioner support, self-host on a VM with Docker access.

---

## 🔀 Multi-Provider Routing with LiteLLM

Starfire ships with an optional [LiteLLM](https://docs.litellm.ai/) proxy service that gives every workspace agent a single unified OpenAI-compatible endpoint — regardless of which underlying model provider you're using.

**Start the stack with LiteLLM:**
```bash
docker compose --profile multi-provider up
```

**Configure a workspace** — in `config.yaml` or via the canvas Secrets panel:
```yaml
# config.yaml
model: claude-opus-4-5        # or gpt-4o, openrouter/deepseek-r1, ollama/llama3.2
```
Add these secrets to the workspace via the canvas or API:
```
OPENAI_BASE_URL  = http://litellm:4000
OPENAI_API_KEY   = sk-starfire          # matches LITELLM_MASTER_KEY
```

**Configure providers** by editing `infra/litellm_config.yml`. Set the relevant API key env vars in your shell or `.env` file:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENROUTER_API_KEY=sk-or-...
```

The LiteLLM UI is available at `http://localhost:4000/ui` for monitoring, model testing, and spend tracking.

> **Combine with Ollama:** Run `docker compose --profile multi-provider --profile local-models up` to have both available simultaneously. The `ollama/llama3.2` model entry in `litellm_config.yml` routes through LiteLLM → Ollama automatically.

---

## 🦙 Using Local Models with Ollama

Starfire ships with an optional Ollama service so workspace agents can run entirely on local models — no API keys required.

**Start the stack with Ollama:**
```bash
docker compose --profile local-models up
```

**Pull a model** (first run only):
```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

**Point a workspace at Ollama** — in your workspace `config.yaml`:
```yaml
model: ollama:llama3.2       # or ollama:qwen2.5-coder:7b
```

Workspace agents inside the Docker network reach Ollama at `http://ollama:11434`. The Ollama data volume (`ollamadata`) persists downloaded models across restarts so you only pull once.

> **GPU support:** Add `deploy.resources.reservations.devices` to the `ollama` service in `docker-compose.yml` to pass through a CUDA/ROCm device. See the [Ollama Docker docs](https://hub.docker.com/r/ollama/ollama) for details.

---

## 📄 License & Community

Starfire is open-source software licensed under the **[MIT License](LICENSE)**.

*Starfire — Igniting the future of Agent Organizations.*
