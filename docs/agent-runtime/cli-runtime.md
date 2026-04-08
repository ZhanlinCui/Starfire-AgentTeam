# Agent Runtime Adapters

## Overview

The workspace runtime uses a **pluggable adapter architecture** — each agent infrastructure (Claude Code, OpenClaw, LangGraph, CrewAI, AutoGen, etc.) has its own adapter that bridges the A2A protocol to the infra's native interface.

Adapters live in `workspace-template/adapters/<runtime>/` and are auto-discovered at startup. Each adapter implements `BaseAdapter` (from `adapters/base.py`) with `setup()` and `create_executor()` methods.

The runtime is selected via `config.yaml`:

```yaml
runtime: claude-code    # or: langgraph, openclaw, deepagents, crewai, autogen
runtime_config:
  model: sonnet
  auth_token_file: .auth-token
  timeout: 0
```

## How It Works

The unified `workspace-template` Docker image includes both Python (LangGraph) and Node.js (CLI runtimes). At startup, `main.py` checks the `runtime` field in `config.yaml`:

- **`langgraph`** (default): Creates a LangGraph ReAct agent with skills, tools, plugins, and peer discovery. Full Python agent runtime.
- **Any CLI runtime**: Creates a `CLIAgentExecutor` that invokes the CLI tool via subprocess on each A2A request. Skips LangGraph-specific setup (plugins, skills, tools, coordinator) for faster startup.

```
A2A request arrives
      |
      v
CLIAgentExecutor._build_command(message)
      |  - selects preset (claude-code, codex, ollama)
      |  - adds model flag, system prompt flag
      |  - adds auth (env var: CLAUDE_CODE_OAUTH_TOKEN or OPENAI_API_KEY)
      |  - adds prompt
      v
asyncio.create_subprocess_exec(cmd, args)
      |
      v
stdout → A2A response
```

## Built-in Runtime Presets

### Claude Code (`runtime: claude-code`)

```yaml
runtime: claude-code
runtime_config:
  model: sonnet          # or opus, haiku
  auth_token_file: .auth-token   # OAuth token file in /configs/
  timeout: 0           # seconds
```

Invokes: `claude --print --dangerously-skip-permissions --allowed-tools Bash --model sonnet --system-prompt <prompt> -p "<message>"`

**Auth:** Uses the `CLAUDE_CODE_OAUTH_TOKEN` env var — the OAuth token is read from `/configs/.auth-token` and injected into the subprocess environment. The `--bare` flag is **not** used because it disables OAuth and reduces the agent to a simple LLM provider. Without `--bare`, each workspace is a full agentic Claude Code instance with hooks, CLAUDE.md discovery, auto-memory, and plugin support.

**Important:** Claude Code refuses to run as root with `--dangerously-skip-permissions`. The Dockerfile creates a non-root `agent` user.

### OpenAI Codex (`runtime: codex`)

```yaml
runtime: codex
runtime_config:
  model: gpt-5.4
  auth_token_env: OPENAI_API_KEY
```

Invokes: `codex --print --dangerously-skip-permissions --model gpt-5.4 -p "<message>"`

**Auth:** Uses `OPENAI_API_KEY` env var (set via workspace secrets).

### Ollama (`runtime: ollama`)

```yaml
runtime: ollama
runtime_config:
  model: llama3
```

Invokes: `ollama run llama3 "<message>"`

**Auth:** None needed (local model).

### Custom (`runtime: custom`)

```yaml
runtime: custom
runtime_config:
  command: my-agent
  args: ["--flag1", "--flag2"]
  timeout: 600
```

Invokes: `my-agent --flag1 --flag2 -p "<message>"`

## Session Continuity (Claude Code)

Claude Code workspaces maintain conversation state across messages using the `--resume` flag:

1. **First message**: runs with `--output-format json` to capture the `session_id` from the response
2. **Subsequent messages**: runs with `--resume <session_id>` to continue the same conversation
3. **System prompt**: only injected on the first message — resumed sessions already have it

Session state is stored inside the container at `~/.claude/` and persists across messages but resets on container restart. This means the PM remembers what you discussed earlier in the conversation.

## System Prompt

CLI runtimes load `system-prompt.md` from the workspace's config directory (`/configs/system-prompt.md`). The prompt is injected on the **first message only** (subsequent messages resume the session). Hot-reload still works — restart the container to pick up prompt changes.

For LangGraph runtimes, the system prompt is built from multiple sources (config, skills, plugins, peer capabilities) at startup.

## Auth Token Resolution

The CLI executor resolves auth tokens in this order:

1. **Environment variable** — `CLAUDE_AUTH_TOKEN`, `OPENAI_API_KEY`, etc.
2. **Token file** — `/configs/.auth-token` (relative to config dir)

For Claude Code specifically:
- Extract your OAuth access token from the macOS keychain: `security find-generic-password -s "Claude Code-credentials" -a "<username>" -w`
- Write it to `workspace-configs-templates/claude-code-default/.auth-token`
- The provisioner copies this file to each new workspace's config dir

## Auto-Provisioning Without Templates

Workspaces can be created without specifying a `template`. The platform automatically:

1. Creates a config directory (`ws-<id>`) under `workspace-configs-templates/`
2. Generates a minimal `config.yaml` with the workspace's name, role, runtime, and model
3. Copies `.auth-token` from the `claude-code-default` template (if it exists)
4. Merges any files previously uploaded via the Files API
5. Starts the container

This means you can create a workspace with just:
```bash
curl -X POST http://localhost:8080/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "My Agent", "role": "Does things", "runtime": "claude-code"}'
```

And it provisions, registers, and comes online automatically.

## Dockerfile

The unified `workspace-template/Dockerfile` includes both Python and Node.js:

```dockerfile
FROM python:3.11-slim

# Node.js for CLI runtimes (claude-code, codex)
RUN apt-get update && apt-get install -y nodejs
RUN npm install -g @anthropic-ai/claude-code

# Non-root user (claude --dangerously-skip-permissions refuses root)
RUN useradd -m -s /bin/bash agent

# Python deps for LangGraph runtime
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
USER agent
CMD ["python", "main.py"]
```

## Inter-Agent Communication (A2A Delegation)

CLI-based workspaces can communicate with other workspaces via two mechanisms:

### MCP Tools (Claude Code, Codex)

For MCP-compatible runtimes, an A2A MCP server (`a2a_mcp_server.py`) is automatically injected via `--mcp-config`. This gives the agent three MCP tools:

| Tool | Description |
|------|-------------|
| `list_peers` | Discover sibling/parent/child workspaces (name, ID, status, role) |
| `delegate_task` | Send a task to a peer and get their response via A2A |
| `get_workspace_info` | Get this workspace's own metadata |

The agent uses these tools naturally — no special instructions needed. Access control is enforced by the platform registry.

Example flow: Marketing uses `delegate_task(seo_id, "What is your status?")` → A2A message to SEO → SEO responds → result returned to Marketing.

### CLI Commands (Ollama, Custom)

For non-MCP runtimes, A2A instructions are injected into the system prompt. The agent uses bash commands:

```bash
a2a peers                          # List available peers
a2a delegate <workspace_id> <task>  # Send task to a peer
a2a info                           # Show workspace info
```

Both approaches use the same backend: platform registry for discovery, A2A protocol for messaging, and access control enforcement (parent↔child, siblings only).

## Task Status Reporting

Any process inside a workspace container (cron jobs, scripts, background tasks) can update the canvas card display:

```bash
agent-molecule-status "Running weekly SEO audit..."  # show on canvas
agent-molecule-status ""                              # clear when done
```

From Python:
```python
from agent_molecule_status import set_status
set_status("Analyzing competitor data...")
```

This pushes an immediate heartbeat with `current_task` to the platform, which broadcasts via WebSocket to the canvas. The task banner appears instantly on the workspace card.

## Key Files

| File | Role |
|------|------|
| `cli_executor.py` | Generic CLI agent executor with runtime presets |
| `agent_molecule_status.py` | CLI tool + module for updating canvas task display from any process |
| `a2a_mcp_server.py` | MCP server exposing A2A delegation tools (list_peers, delegate_task, delegate_task_async, check_task_status) |
| `a2a_cli.py` | CLI tool for A2A delegation (all runtimes) |
| `config.py` | `RuntimeConfig` dataclass, `runtime` field in `WorkspaceConfig` |
| `main.py` | Runtime selector — creates `CLIAgentExecutor` or `LangGraphA2AExecutor` |

## Rate Limit Handling

The CLI executor includes built-in retry logic with exponential backoff:
- Empty responses (common rate limit signal) → retry up to 3 times (5s, 10s, 20s)
- Rate limit errors (429, "overloaded") → retry with same backoff
- Timeouts → kill subprocess and report (no retry)

The A2A CLI (`a2a_cli.py`) also retries delegation calls on rate limits.

For production with many concurrent agents, consider:
- Using different auth tokens per workspace (separate subscriptions)
- Staggering agent invocations
- Using `delegate_task_async` for long-running tasks

## Known Limitations

- **Tier 1 (sandboxed)**: Read-only root filesystem is disabled for CLI runtimes because Claude Code needs writable directories (`.claude/`, `.npm/`, `/tmp`). Tier 1 still restricts the `/workspace` volume.
- **Rate limits**: All workspaces share the same Claude subscription. Retry logic handles transient rate limits, but sustained high volume needs separate tokens.
- **Auth token lifecycle**: OAuth tokens expire and need refreshing. Use `claude setup-token` for long-lived tokens in production.

## Extending with New Runtimes

To add a new CLI runtime:

1. Add a preset to `RUNTIME_PRESETS` in `cli_executor.py`:
```python
"my-runtime": {
    "command": "my-agent-cli",
    "base_args": ["--output-text"],
    "prompt_flag": "-p",
    "model_flag": "--model",
    "system_prompt_flag": "--system",
    "auth_pattern": "env",      # or "apiKeyHelper" or None
    "default_auth_env": "MY_API_KEY",
    "default_auth_file": "",
},
```

2. Install the CLI tool in the Dockerfile
3. Use it in config.yaml: `runtime: my-runtime`
