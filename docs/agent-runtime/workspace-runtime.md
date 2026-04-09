# Workspace Runtime

> Starfire supports both LangGraph-based and adapter-based runtimes. For the runtime matrix and non-LangGraph adapters, see [CLI Runtime](./cli-runtime.md).

## workspace-template/

The generic workspace runtime image. Every deployed workspace is a container instance of this image, injected with a config at startup via environment variables.

The template contains **no business logic**. All business logic lives in `workspace-configs-templates/`. The template reads config files at startup — it does not know what kind of workspace it is until it loads config.

The default runtime path is LangGraph/DeepAgents, but the same image also supports pluggable adapters such as Claude Code, CrewAI, AutoGen, and OpenClaw via the adapter registry in `workspace-template/adapters/`.

### Environment Variables

```
WORKSPACE_ID=ws-reno-stars-seo-001
WORKSPACE_CONFIG_PATH=/configs/seo-agent
MODEL_PROVIDER=anthropic:claude-sonnet-4-6
TIER=1
PLATFORM_URL=http://platform:8080
PARENT_ID=                   # set by platform during team expansion (empty for top-level)
ANTHROPIC_API_KEY=sk-...
LANGFUSE_HOST=http://langfuse-web:3000
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
AWARENESS_URL=http://awareness:37800
AWARENESS_NAMESPACE=workspace:ws-reno-stars-seo-001
```

When awareness is configured, the workspace keeps using the same `commit_memory` / `search_memory` tools, but the backend routes those calls into the workspace's own awareness namespace. If the two awareness env vars are absent, the runtime falls back to the platform memory API for compatibility.

`awareness` is the workspace's durable memory backend. It stores facts that should survive across turns, while `session-search` provides the thin recall surface over recent activity and memory rows. The division of labor stays narrow:

- `memory-curation` decides what is durable and compresses it into a packet
- `awareness` persists that packet inside the workspace's isolated namespace
- `session-search` recovers recent decisions, notes, and activity traces
- `skill-authoring` only runs when a repeated workflow is stable enough to become a reusable skill
- `skills runtime` loads the resulting skill package and hot-reloads it into the agent

This keeps the runtime source-faithful to Hermes-style behavior: memory is for persistence and recall, skills are for repeatable procedure, and promotion is only a signal until the normal skill lifecycle creates the actual package.

## workspace-configs-templates/

One folder per workspace type. Contains the "personality" of the workspace — the specific skills, prompts, and config for that role.

```
workspace-configs-templates/
+-- seo-agent/
    +-- config.yaml              # skills list, tools, tier, model
    +-- system-prompt.md         # the agent's core instructions
    +-- skills/
    |   +-- generate-seo-page/
    |   |   +-- SKILL.md         # instructions for the agent
    |   |   +-- tools/
    |   |       +-- write_page.py
    |   |       +-- check_gsc.py
    |   +-- audit-seo-page/
    |   |   +-- SKILL.md
    |   +-- keyword-research/
    |       +-- SKILL.md
    |       +-- links.yaml
    |       +-- examples/
    +-- workspace.bundle.json    # compiled bundle (auto-generated)
```

## Startup Sequence

```
Container starts
      |
      v
config.py loads WORKSPACE_CONFIG_PATH
      |
      v
plugins.py scans /plugins/ for shared skills, rules, prompt fragments
      |
      v
skills/loader.py loads workspace skills + plugin skills (deduplicated by ID)
      |
      v
coordinator.py fetches parent's shared context (if PARENT_ID set)
      |
      v
runtime adapter initializes executor (LangGraph by default)
      |
      v
main.py wraps agent in A2A server (a2a-sdk)
      |
      v
A2AStarletteApplication auto-registers all A2A routes:
  /.well-known/agent-card.json, message/send,
  message/sendSubscribe, tasks/cancel
      |
      v
POST /registry/register sends id, url, and agent_card to platform
      |
      v
heartbeat.py starts 30s POST loop to platform /registry/heartbeat
      |
      v
WebSocket subscribes to platform /ws with X-Workspace-ID header
      |
      v
Workspace is live, discoverable, and receiving peer events
```

### Key Files

| File | Role |
|------|------|
| `main.py` | Entry point — wraps agent in A2A server via `a2a-sdk` |
| `config.py` | Loads workspace config from `WORKSPACE_CONFIG_PATH` |
| `agent.py` | Creates the default LangGraph ReAct agent with model + skills + tools |
| `coordinator.py` | Team coordination (get_children, get_parent_context, route_task) |
| `a2a_executor.py` | Bridges deepagent (LangGraph) to A2A request/response |
| `adapters/` | Pluggable runtime adapters for Claude Code, CrewAI, AutoGen, DeepAgents, OpenClaw, etc. |
| `skills/loader.py` | Loads skill packages (SKILL.md + tools) from config |
| `heartbeat.py` | Sends 30s heartbeat to platform registry |
| `events.py` | Subscribes to platform WebSocket, handles peer events |

## A2A Server Wrapping

The workspace uses the `a2a-sdk` package (PyPI: `a2a-sdk[http-server]`). `A2AStarletteApplication` auto-registers all A2A routes at the root URL.

```python
# workspace-template/main.py (simplified)

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
import uvicorn

async def main():
    # 1. create LangGraph ReAct agent with provider-specific LLM
    #    agent.py parses "provider:model" and loads ChatAnthropic/ChatOpenAI/etc.
    agent = create_agent(config.model, all_tools, system_prompt)

    # 2. build Agent Card from loaded skill metadata
    agent_card = AgentCard(
        name=config.name,
        url=f"http://{MACHINE_IP}:{PORT}",
        capabilities=AgentCapabilities(streaming=True, pushNotifications=True),
        skills=[AgentSkill(id=s.metadata.id, name=s.metadata.name, ...)
                for s in loaded_skills],
        ...
    )

    # 3. wrap in A2A executor + handler
    executor = LangGraphA2AExecutor(agent)
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    # 4. create A2A app — routes auto-registered at root URL:
    #    /.well-known/agent-card.json, message/send, message/sendSubscribe
    app = A2AStarletteApplication(agent_card=agent_card, http_handler=handler)

    # 5. register with platform, start heartbeat, run server
    await register_with_platform(workspace_id, workspace_url, agent_card_dict)
    heartbeat.start()
    await uvicorn.Server(uvicorn.Config(app.build(), host="0.0.0.0", port=port)).serve()
```

The executor bridges LangGraph's streaming to A2A's event model:

```python
# workspace-template/a2a_executor.py

class LangGraphA2AExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        # Extract text from A2A message parts
        text_parts = [p.text for p in context.message.parts if hasattr(p, "text") and p.text]
        user_input = " ".join(text_parts).strip()
        if not user_input:
            await event_queue.enqueue_event(
                new_agent_text_message("Error: message contained no text content.")
            )
            return

        # Stream through LangGraph, collect final response
        final_content = ""
        async for chunk in self.agent.astream(
            {"messages": [("user", user_input)]},
            config={"configurable": {"thread_id": context.context_id}},
        ):
            if "messages" in chunk:
                content = getattr(chunk["messages"][-1], "content", "")
                if isinstance(content, str) and content.strip():
                    final_content = content

        await event_queue.enqueue_event(new_agent_text_message(final_content or "(no response)"))
```

**Key distinction:** ACP (Agent Client Protocol) connects agents to editors/IDEs (Zed, Claude Code). A2A (Agent-to-Agent) connects workspaces to each other. Starfire uses A2A for inter-workspace communication.

## Delegation Failure Handling

When a workspace delegates to a peer and the peer fails, the behavior depends on the failure type:

| Scenario | Detection | Response |
|----------|-----------|----------|
| Peer offline before task starts | Discovery returns offline status | A never sends the message — reports to LLM immediately |
| Peer crashes mid-task | SSE stream drops / connection reset | Retry with backoff |
| Peer returns `failed` status | SSE terminal event | No retry — report to LLM |
| Peer stuck in `input-required` | Timeout | Retry with backoff, then report to LLM |

### Default: Three Attempts Then Escalate

The built-in `delegate_to_workspace` tool implements configurable retry with backoff:

```python
# workspace-template/tools/delegation.py

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")
DELEGATION_RETRY_ATTEMPTS = int(os.environ.get("DELEGATION_RETRY_ATTEMPTS", "3"))
DELEGATION_RETRY_DELAY = float(os.environ.get("DELEGATION_RETRY_DELAY", "5.0"))
DELEGATION_TIMEOUT = float(os.environ.get("DELEGATION_TIMEOUT", "120.0"))

@tool
async def delegate_to_workspace(workspace_id: str, task: str) -> dict:
    """Delegate a task to a peer workspace via A2A protocol."""
    # 1. Discover target URL via platform (enforces CanCommunicate)
    discover_resp = await client.get(
        f"{PLATFORM_URL}/registry/discover/{workspace_id}",
        headers={"X-Workspace-ID": WORKSPACE_ID},
    )
    target_url = discover_resp.json()["url"]

    # 2. Send A2A message/send with retry
    for attempt in range(DELEGATION_RETRY_ATTEMPTS):
        a2a_resp = await client.post(target_url, json={...})  # JSON-RPC 2.0
        if a2a_resp.status_code == 200:
            return {"success": True, "response": extract_text(a2a_resp)}
        await asyncio.sleep(DELEGATION_RETRY_DELAY * (attempt + 1))

    return {"success": False, "error": last_error, "workspace_id": workspace_id}
```

Note: The delegation tool sends A2A requests to the **root URL** of the target workspace (not `/a2a`), as the `a2a-sdk` serves all routes at root.

### Why the LLM Decides

The agent receives the failure return value in its context and decides the next step. Hardcoding "always retry" or "always fail up" is wrong for all cases. The LLM can reason contextually:

- "QA Agent failed — I'll note it in my report and ask if they want to proceed without QA"
- "Backend Agent crashed — likely transient, I'll retry in 60 seconds"
- "Frontend Agent is offline — I'll attempt the task myself using my own skills"

The system prompt tells the agent how to handle failures:

```markdown
## Handling delegation failures
If a delegation fails:
1. Check if the task is blocking — if not, continue other work
2. Retry transient failures (connection errors) after 30 seconds
3. For persistent failures, report to the caller with context
4. Never silently drop a failed task
```

### Configuration

Delegation defaults are configurable in `config.yaml`:

```yaml
delegation:
  retry_attempts: 3
  retry_delay: 5       # seconds, multiplied per attempt (backoff)
  timeout: 120         # seconds before treating as crashed
  escalate: true       # return failure to LLM on exhaustion
```

### Canvas Visibility

When a delegation fails, the platform receives failure stats from the workspace heartbeat. The canvas shows a warning indicator on the edge between the two workspaces — a signal that delegation is struggling, not a blocking error.

## Task Concurrency

When a workspace has sub-workspaces, the agent delegates tasks to them and can run multiple delegated tasks concurrently.

When a workspace has **no** sub-workspaces (a leaf agent), it handles concurrency as follows:

- **Major features:** One at a time, sequentially. The agent completes one before starting the next.
- **Side questions and small updates:** Can be handled in parallel alongside the current major feature.

This means a leaf agent won't try to build two big features simultaneously, but it can answer a quick question or make a small fix while working on a larger task.

## Related Docs

- [Skills](./skills.md) — Skill package structure and interface
- [Config Format](./config-format.md) — Full `config.yaml` reference
- [Provisioner](../architecture/provisioner.md) — How containers are deployed
- [Workspace Tiers](../architecture/workspace-tiers.md) — How tier affects deployment
- [Agent Card](./agent-card.md) — The identity document published at startup
- [Bundle System](./bundle-system.md) — How configs compile to portable bundles
- [A2A Protocol](../api-protocol/a2a-protocol.md) — How A2A wrapping works
- [Registry & Heartbeat](../api-protocol/registry-and-heartbeat.md) — The heartbeat loop
