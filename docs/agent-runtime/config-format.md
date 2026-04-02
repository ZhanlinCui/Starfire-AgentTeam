# Config Format (config.yaml)

Each workspace type has a `config.yaml` that defines its personality — the model, skills, tools, and settings.

## Full Example

```yaml
# workspace-configs-templates/seo-agent/config.yaml

name: Vancouver SEO Agent
description: Bilingual EN/ZH SEO page builder for Vancouver renovation companies
version: 1.0.0
tier: 1

# AI model -- any LangChain-compatible provider string
model: anthropic:claude-sonnet-4-6

# Prompt files loaded in order into the system prompt.
# Supports any agent framework's file structure.
# Default (if omitted): system-prompt.md
prompt_files:
  - system-prompt.md
# OpenClaw example:
#   prompt_files: [SOUL.md, BOOTSTRAP.md, AGENTS.md, HEARTBEAT.md, TOOLS.md, USER.md, MEMORY.md]
# Claude Code example:
#   prompt_files: [CLAUDE.md]
# OpenAI Codex example:
#   prompt_files: [AGENTS.md]

# Skills to load -- folder names under skills/
skills:
  - generate-seo-page
  - audit-seo-page
  - keyword-research
  - monitor-rankings

# Built-in tools from workspace-template (not skill-specific)
tools:
  - web_search
  - filesystem
  - browser       # only valid for tier 2+
  - computer      # only valid for tier 3+

# Memory backend
memory:
  backend: filesystem   # filesystem | langgraph_store | s3
  path: /memory         # where to store (relative inside container)

# A2A server config
a2a:
  port: 8000
  streaming: true
  push_notifications: true

# Delegation defaults (override per-call in the tool)
delegation:
  retry_attempts: 3
  retry_delay: 5       # seconds, multiplied per attempt (backoff)
  timeout: 120         # seconds before treating as crashed
  escalate: true       # return failure to LLM on exhaustion

# Code sandbox config (tier 3+ only)
# sandbox:
#   backend: docker       # docker | firecracker | e2b
#   memory_limit: 256m
#   network: false
#   timeout: 30s

# Sub-workspaces -- empty = single agent, populated = team
# Each entry references another config in workspace-configs-templates/
sub_workspaces: []
# sub_workspaces:
#   - config: developer-frontend
#   - config: developer-backend
#   - config: qa-pm

# Environment variables this workspace needs
# Values are never stored here -- injected at provision time
# This just declares what keys are required
env:
  required:
    - ANTHROPIC_API_KEY
  optional:
    - GSC_CLIENT_ID
    - GSC_CLIENT_SECRET
    - NEON_DATABASE_URL
```

## Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name for the workspace |
| `description` | Yes | What this workspace does |
| `version` | Yes | Semantic version |
| `tier` | Yes | 1-4, determines deployment method |
| `model` | Yes | LangChain-compatible provider string (e.g. `anthropic:claude-sonnet-4-6`). Overridden by `MODEL_PROVIDER` env var if set. |
| `prompt_files` | No | Ordered list of markdown files to load as system prompt. Defaults to `["system-prompt.md"]` if omitted. Supports any agent framework's file structure (OpenClaw, Claude Code, etc.) |
| `skills` | Yes | List of skill folder names to load from `skills/` |
| `tools` | No | Built-in tools from workspace-template |
| `memory` | No | Memory backend config (defaults to filesystem) |
| `a2a` | No | A2A server settings (defaults to port 8000, streaming on) |
| `sub_workspaces` | No | Sub-workspace configs for team expansion |
| `delegation` | No | Delegation retry/timeout/escalation defaults (see [Delegation Failure Handling](./workspace-runtime.md#delegation-failure-handling)) |
| `sandbox` | No | Code sandbox config for tier 3+ (see [Code Sandbox](../development/code-sandbox.md)) |
| `env.required` | No | Environment variable keys that must be present at startup |
| `env.optional` | No | Environment variable keys that are used if present |

## Hot-Reload Behavior

The file watcher monitors the entire config directory. When `config.yaml` changes at runtime, different fields have different reload behaviors:

| Field | Hot-reloadable? | What happens |
|-------|----------------|--------------|
| `model` | Yes | Recreate deepagent with new model, no restart needed |
| `skills` | Yes | Load/unload skill files, rebuild Agent Card |
| `tools` | Yes | Reload tool registrations |
| `memory.backend` | Yes (with caveat) | Switch backend going forward; existing memory in old backend stays and is not migrated automatically |
| `tier` | **No** | Tier affects how the container was provisioned (Docker flags, VM vs container). Requires re-provision. Change is logged as a warning and ignored at runtime. |
| `name`, `description`, `version` | Yes | Rebuild Agent Card with new metadata |
| `a2a` | **No** | Port and protocol changes require container restart |
| `delegation` | Yes | Retry/timeout defaults take effect on next delegation call |
| `sub_workspaces` | **No** | Team structure changes go through `POST /workspaces/:id/expand` |

See [Skills — Live Reload](./skills.md#live-reload) for the full file watcher flow.

## Tools vs Skills

- **Tools** are built-in capabilities from `workspace-template` (web search, filesystem, browser, computer)
- **Skills** are loaded from the workspace config folder and contain domain-specific instructions and MCP tools
- Some tools are tier-gated: `browser` requires tier 2+, `computer` requires tier 3+

## Sub-Workspace Config

When `sub_workspaces` is populated, the workspace becomes a team. Each entry references another config folder in `workspace-configs-templates/`:

```yaml
sub_workspaces:
  - config: developer-frontend
  - config: developer-backend
  - config: qa-pm
```

The provisioner reads these and spins up sub-workspace containers using the referenced configs. See [Team Expansion](./team-expansion.md).

## Related Docs

- [Skills](./skills.md) — Skill package structure and interface
- [Workspace Runtime](./workspace-runtime.md) — How config is loaded at startup
- [Workspace Tiers](../architecture/workspace-tiers.md) — What each tier enables
- [Team Expansion](./team-expansion.md) — How sub_workspaces creates teams
