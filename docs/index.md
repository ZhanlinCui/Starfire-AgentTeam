---
layout: home

hero:
  name: Starfire
  text: The Organizational OS for AI Agents
  tagline: Deploy, orchestrate, and scale AI agent teams on a visual canvas with built-in hierarchy, communication, and memory.
  image:
    src: /assets/branding/starfire-icon.png
    alt: Starfire
  actions:
    - theme: brand
      text: Quickstart
      link: /quickstart
    - theme: alt
      text: Architecture
      link: /architecture/architecture
    - theme: alt
      text: API Reference
      link: /api-protocol/platform-api

features:
  - title: Visual Agent Canvas
    details: Drag-and-drop org chart for AI agents. Nest workspaces to create teams with automatic hierarchy-based access control.
    icon: "🖼️"
  - title: A2A Protocol
    details: JSON-RPC 2.0 agent-to-agent communication. Agents discover peers, delegate tasks, and collaborate — platform stays out of the data path.
    icon: "🔗"
  - title: Runtime Agnostic
    details: 9 runtime adapters — LangGraph, Claude Code, CrewAI, AutoGen, Ollama, and more. Bring any agent framework.
    icon: "⚡"
  - title: Fractal Team Expansion
    details: One click to decompose any agent into a full team. The Team Lead + specialists self-organize via A2A.
    icon: "🌳"
  - title: Hierarchical Memory
    details: L1 local, L2 team-shared, L3 global memory scopes. Agents build institutional knowledge that persists across sessions.
    icon: "🧠"
  - title: Global Secrets & Config
    details: Platform-wide API keys inherited by all workspaces, with per-workspace overrides. AES-256-GCM encrypted at rest.
    icon: "🔐"
---

## Quick Reference

| Concept | Description |
|---------|-------------|
| **Workspace** | A containerized agent with a role, config, and position on the canvas |
| **Team** | A parent workspace with child workspaces (fractal expansion) |
| **A2A** | Agent-to-Agent protocol (JSON-RPC 2.0) for inter-workspace communication |
| **Canvas** | Visual React Flow interface for managing the agent org chart |
| **Platform** | Go control plane managing workspaces, routing, and provisioning |
| **Tier** | Security isolation level (T1=sandboxed, T2=browser, T3=desktop, T4=full VM) |
| **Skill** | A pluggable capability attached to an agent (search, code execution, etc.) |
| **Memory** | L1 (local), L2 (team shared), L3 (global) hierarchical knowledge store |
