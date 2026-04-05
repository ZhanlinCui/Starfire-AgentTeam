---
id: mem_20260405_012420_ec23
type: turn_summary
session_id: null
agent_role: builder_agent
tags: []
created_at: "2026-04-05T08:24:20.997Z"
updated_at: "2026-04-05T08:24:20.997Z"
source: "claude-code"
status: active
related: []
---

## A2A End-to-End Pipeline — Fully Working (8e)

Successfully tested the full A2A pipeline: Canvas → Platform proxy (POST /workspaces/:id/a2a) → Docker agent container → OpenRouter API.

### Infrastructure fixes required to make it work:

1. **findConfigsDir validation** (platform/cmd/server/main.go): The auto-discovery was finding a stale empty `platform/workspace-configs-templates/` dir before the real one at `../workspace-configs-templates/`. Fixed by requiring at least one template with `config.yaml` inside the dir.

2. **PLATFORM_URL for Docker containers** (main.go): Was hardcoded to `http://localhost:PORT`. Containers can't reach host's localhost. Changed to `http://host.docker.internal:PORT` (macOS Docker). Now reads from `PLATFORM_URL` env var with this as default.

3. **Host port mapping for A2A proxy** (provisioner.go): Platform runs on the host but agents run in Docker containers. The proxy couldn't reach Docker-internal URLs. Added ephemeral host port binding (`127.0.0.1:0->8000/tcp`) and resolved the actual port via ContainerInspect after start.

4. **Provisioner URL preservation** (workspace.go + registry.go): The provisioner returns a `http://127.0.0.1:PORT` URL, but the agent's self-registration overwrites it with its Docker-internal hostname. Fixed by: (a) pre-storing the provisioner URL in DB+Redis, (b) register endpoint preserves URLs starting with `http://127.0.0.1` instead of overwriting.

### Result:
- Agent status: online at http://127.0.0.1:59902
- A2A response received: JSON-RPC 2.0 with agent error (401 from OpenRouter = expired API key, NOT a pipeline issue)
- Pipeline: proxy → agent container → LLM API — all working

### 12j Bundle Round-Trip Test also added:
- Export → delete → import → verify name/tier match, new ID assigned
- All 9 new test assertions pass
