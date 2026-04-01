<div align="center">

# Starfire 🌟

**The Organizational Operating System for AI Agents**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Go Version](https://img.shields.io/badge/go-1.22+-00ADD8?logo=go)](https://golang.org/)
[![Python Version](https://img.shields.io/badge/python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org/)

[Product Requirements Document (PRD)](./docs/product/PRD.md) • 
[Architecture](./docs/architecture/architecture.md) • 
[Communication Protocol](./docs/api-protocol/a2a-protocol.md) • 
[Agent Runtime](./docs/agent-runtime/workspace-runtime.md)

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

## 📄 License & Community

Starfire is open-source software licensed under the **[MIT License](LICENSE)**.

*Starfire — Igniting the future of Agent Organizations.*
