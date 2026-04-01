# Observability (Langfuse)

## Overview

Self-hosted Langfuse runs in Docker alongside the rest of the stack. Every workspace agent sends traces automatically via LangGraph's built-in Langfuse integration.

## What Gets Traced Automatically

LangGraph detects Langfuse env vars at import time and patches the tracer automatically. No callback handlers, no explicit instrumentation — just env vars:

```
LANGFUSE_HOST=http://langfuse-web:3000
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGSMITH_TRACING=true    # LangGraph reads this to enable tracing
```

Automatic traces include:

| Traced | What's captured |
|--------|----------------|
| LLM calls | Input prompt, output, tokens, latency, cost |
| Tool calls | Function name, arguments, return value |
| Agent steps | Planning steps, TODO list updates |
| Sub-agent spawns | Nested trace under parent task |
| Errors | Full stack traces |

## What Requires Manual Instrumentation

A2A delegations are HTTP calls — LangGraph doesn't know about them. The delegation tool creates a manual span:

```python
# workspace-template/tools/delegation.py

from langfuse import Langfuse
langfuse = Langfuse()

@tool
async def delegate_to_workspace(workspace_id: str, task: str) -> dict:
    span = langfuse.span(
        name="a2a_delegation",
        metadata={"from": WORKSPACE_ID, "to": workspace_id},
    )
    result = await send_a2a_task(workspace_id, task)
    span.end(output=result)
    return result
```

The `parent_task_id` in the A2A message metadata links the child workspace's trace back to the parent — Langfuse renders the full call tree across workspaces.

All workspaces report to a single unified Langfuse instance, giving you a cross-workspace view of all agent activity.

## Why This Matters

Debugging distributed agents is hard. Without centralized observability, you cannot see what happened across multiple machines. Langfuse provides the unified trace view that makes this possible.

## Local Stack

Langfuse runs as part of the Docker Compose stack:

- **Langfuse web** on `:3001` (host-mapped; internal container port is `:3000`)
- **Langfuse worker** (background processing)
- **ClickHouse** (Langfuse dependency for analytics)

## Why Not LangSmith?

LangSmith (the managed version from LangChain) requires an enterprise license for self-hosting. Langfuse is fully open source and self-hostable.

## Related Docs

- [Architecture](../architecture/architecture.md) — Where Langfuse fits in the system
- [Local Development](./local-development.md) — Running the full stack
- [Workspace Runtime](../agent-runtime/workspace-runtime.md) — Where `LANGFUSE_HOST` is configured
- [Technology Choices](../architecture/technology-choices.md) — Why Langfuse was chosen over LangSmith
