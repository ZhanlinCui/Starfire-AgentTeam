# Workspace Runtime (Python)

## workspace-template/

The generic Python runtime. Every deployed workspace is a container instance of this image, injected with a config at startup via environment variables.

The template contains **no business logic**. All business logic lives in `workspace-configs-templates/`. The template reads config files at startup — it does not know what kind of workspace it is until it loads config.

### Environment Variables

```
WORKSPACE_ID=ws-reno-stars-seo-001
WORKSPACE_CONFIG_PATH=/configs/seo-agent
MODEL_PROVIDER=anthropic:claude-sonnet-4-6
TIER=1
PLATFORM_URL=http://platform:8080
ANTHROPIC_API_KEY=sk-...
LANGFUSE_HOST=http://langfuse-web:3000
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
```

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
skills/loader.py dynamically loads skill files from config
      |
      v
agent.py creates deepagent with loaded model + skills + tools
      |
      v
main.py wraps agent in A2A server (a2a-python SDK)
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
| `main.py` | Entry point — wraps agent in A2A server via `a2a-python` |
| `config.py` | Loads workspace config from `WORKSPACE_CONFIG_PATH` |
| `agent.py` | Creates the Deep Agent with model + skills + tools |
| `a2a_executor.py` | Bridges deepagent (LangGraph) to A2A request/response |
| `skills/loader.py` | Loads skill packages (SKILL.md + tools) from config |
| `heartbeat.py` | Sends 30s heartbeat to platform registry |
| `events.py` | Subscribes to platform WebSocket, handles peer events |

## A2A Server Wrapping

The workspace uses the `a2a-python` SDK (not `deepagents-acp` — that's for ACP/editor integration, a different protocol). `A2AStarletteApplication` auto-registers all routes:

```python
# workspace-template/main.py

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
from deepagents import create_deep_agent
import uvicorn

async def main():
    # 1. create deepagent with loaded skills + tools
    agent = create_deep_agent(
        model=init_chat_model(config.model),
        tools=load_all_tools(CONFIG_PATH, config.skills),
        system_prompt=await build_system_prompt(CONFIG_PATH),
    )

    # 2. build Agent Card explicitly from loaded skill metadata
    #    a2a-python does NOT auto-generate from tool list
    agent_card = AgentCard(
        name=config.name,
        description=config.description,
        version=config.version,
        url=f"http://{MACHINE_IP}:{PORT}",
        capabilities=AgentCapabilities(
            streaming=True,
            pushNotifications=True,
        ),
        skills=[
            AgentSkill(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                tags=skill.tags,
                examples=skill.examples,
            )
            for skill in loaded_skills
        ],
        defaultInputModes=["text/plain", "application/json"],
        defaultOutputModes=["text/plain", "application/json"],
    )

    # 3. wrap in A2A executor + handler
    executor = LangGraphA2AExecutor(agent)
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    # 4. create A2A app — all routes auto-registered:
    #    /.well-known/agent-card.json
    #    /a2a (message/send, message/sendSubscribe, tasks/cancel)
    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=handler,
    )

    uvicorn.run(app.build(), host="0.0.0.0", port=PORT)
```

The executor bridges LangGraph's streaming to A2A's event model:

```python
# workspace-template/a2a_executor.py

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

class LangGraphA2AExecutor(AgentExecutor):
    def __init__(self, agent):
        self.agent = agent  # compiled LangGraph graph

    async def execute(self, context: RequestContext, queue: EventQueue):
        user_input = " ".join(
            part.text for part in context.message.parts
            if hasattr(part, "text")
        )
        async for chunk in self.agent.astream(
            {"messages": [{"role": "user", "content": user_input}]},
            config={"thread_id": context.context_id}
        ):
            if "messages" in chunk:
                msg = chunk["messages"][-1]
                await queue.enqueue_event(
                    new_agent_text_message(msg.content)
                )

    async def cancel(self, context: RequestContext, queue: EventQueue):
        await self.agent.ainterrupt(context.context_id)
```

**Key distinction:** ACP (Agent Client Protocol) connects agents to editors/IDEs (Zed, Claude Code). A2A (Agent-to-Agent) connects workspaces to each other. Agent Molecule uses A2A for inter-workspace communication.

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

@tool
async def delegate_to_workspace(
    workspace_id: str,
    task: str,
    retry_attempts: int = 3,
    retry_delay: float = 5.0,
    fallback: str = None,        # fallback workspace_id
    escalate_on_failure: bool = True,
) -> dict:
    """Delegate a task to a peer workspace."""
    last_error = None
    for attempt in range(retry_attempts):
        try:
            peers = await get_reachable_workspaces()
            target = next((p for p in peers if p["id"] == workspace_id), None)

            if not target:
                raise WorkspaceNotFoundError(workspace_id)
            if target["status"] == "offline":
                raise WorkspaceOfflineError(workspace_id)

            result = await send_a2a_task(target["url"], task)
            if result["status"] == "completed":
                return result["artifacts"]
            if result["status"] == "failed":
                last_error = result.get("error")
                break  # don't retry explicit failures

        except (ConnectionError, TimeoutError) as e:
            last_error = str(e)
            if attempt < retry_attempts - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
            continue

    # try fallback workspace if configured
    if fallback:
        return await delegate_to_workspace(
            fallback, task,
            retry_attempts=1,
            escalate_on_failure=escalate_on_failure,
        )

    # return failure to LLM for decision
    if escalate_on_failure:
        return {
            "success": False,
            "error": last_error,
            "workspace_id": workspace_id,
            "message": f"Delegation to {workspace_id} failed after "
                      f"{retry_attempts} attempts."
        }
    raise DelegationFailedError(workspace_id, last_error)
```

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
