<div align="center">

# Starfire 🌟

**The Organizational Operating System for AI Agents**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Go Version](https://img.shields.io/badge/go-1.25+-00ADD8?logo=go)](https://golang.org/)
[![Python Version](https://img.shields.io/badge/python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org/)

[Product Requirements Document (PRD)](./docs/product/PRD.md) • 
[Architecture](./docs/architecture/architecture.md) • 
[Communication Protocol](./docs/api-protocol/a2a-protocol.md) • 
[Agent Runtime](./docs/agent-runtime/workspace-runtime.md)

---

**Deploy in one click:**

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/yourusername/starfire)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/yourusername/starfire)

> Replace `yourusername/starfire` in the button URLs above with your actual GitHub repo path.

<!-- 
  DEMO GIF — INSERT HERE
  Recommended: 800×500px, max 5MB, recorded at the steps in docs/demo/fractal-expansion-script.md
  Format: ![Starfire fractal expansion demo](./docs/demo/fractal-expansion.gif)
-->

</div>

---

> *"Build your AI Org Chart where any agent can become a team, and any team can become a company."*

Starfire is a **visual AI Agent Team orchestration platform**. Unlike traditional workflow automation tools (like n8n) where nodes represent *tasks*, Starfire nodes represent **roles**. You drag and drop workspaces, nest them into teams, and let them collaborate securely using the industry-standard A2A (Agent-to-Agent) protocol. 

The organizational hierarchy *is* the network topology. No manual wiring needed.

---

## 🔥 Core Differentiators

### 👥 Role-Based Abstraction
In other platforms, nodes are API tasks. In Starfire, a node is a **Workspace** — an organizational role (e.g., "Developer PM" or "Marketing Lead"). The AI model inside can be hot-swapped effortlessly, but its position, hierarchy, and skills remain concrete.

### 🍱 Recursive Team Expansion (Fractal Architecture)
Any workspace node can recursively expand into an entire sub-team. From the outside, the node still exposes a single A2A interface. Inside, a Team Lead coordinates with sub-agents invisibly. Start with an individual contributor, scale them into a department — all without rewiring your main canvas.

### 🌐 The Org Chart IS the Topology
There are zero edge-drawing wires on the Starfire canvas. Edges are inferred purely from the `parent_id` hierarchy. 
- Siblings can talk to siblings.
- Parents can delegate to children.
- Children report up to parents.
**The organizational structure intrinsically enforces your access control policies.**

### 🧠 Hierarchical Memory Architecture (HMA)
Current agent memory frameworks (like Mem0 or MemU) use flat global vector databases, completely breaking organizational data silos. Starfire instead introduces **Topology-Aware Memory Isolation**:
- **L1 (Local Memory):** Scratchpads strictly isolated to the individual agent.
- **L2 (Team Shared Memory):** Retrievable only by a Team Lead and its direct children. Enforced by Row-Level Security.
- **L3 (Corporate Memory):** Top-down global knowledge bases (like employee handbooks) managed by the Root Workspace.

### 📈 Full Observability & Hierarchical Human-in-the-Loop
Every LLM call across your entire distributed team is traced automatically via a unified **Langfuse** instance. More importantly, when an agent detects a high-risk action, it pauses and escalates *up its org chart*. If the parent doesn't have authority, it goes up until the Root Workspace prompts a human on the UI for final approval.

### 🛡️ Tiered Security & Docker/EC2 Isolation
Different roles need different privileges. Starfire natively isolates workspaces:
- **Tier 1:** Text/Data Processing (Network Isolated, Read-only Docker)
- **Tier 2:** Browser Access (Packaged with Playwright)
- **Tier 3:** Desktop Operations (Xvfb Virtual Display + VNC)
- **Tier 4:** Full Privileges (Dedicated Kernel-Isolated EC2 VMs)

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
  - [Python Runtime](./docs/agent-runtime/workspace-runtime.md) | [Skills Ecosystem](./docs/agent-runtime/skills.md) | [Team Expansion Mechanics](./docs/agent-runtime/team-expansion.md)
- 🛠️ **[Development & Deployment](./docs/development/)**
  - [Build & Run Order](./docs/development/build-order.md) | [Observability](./docs/development/observability.md)
- 🎨 **[Frontend Canvas](./docs/frontend/)**
  - [Next.js Web Canvas Engine](./docs/frontend/canvas.md)

---

## ⚡ Quick Start

A full local deployment starts the entire multi-agent platform using Docker Compose.

```bash
# 1. Setup the Infrastructure (Postgres, Redis, Langfuse)
./infra/scripts/setup.sh

# 2. Run the Platform Control Plane (Go)
cd platform
go run ./cmd/server

# 3. Run the Canvas Frontend (Next.js 15)
cd ../canvas
npm install
npm run dev
```

Navigate to `http://localhost:3000` to open the Starfire Canvas and drag in your first Agent.

---

## 🏢 Architecture Overview

Starfire is a thoroughly distributed system:
1. **Canvas (Next.js 15):** The React Flow visual canvas. Communicates via HTTP + WebSockets.
2. **Platform (Go / Gin):** The Control Plane. Handles workspace CRUD, A2A discovery, registry liveness checks (Redis), and event streaming (Postgres pub/sub).
3. **Workspace Runtime (Python):** The execution engine for individual agents. Powered by Deep Agents + LangGraph, wrapped in a standardized A2A SDK.

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
