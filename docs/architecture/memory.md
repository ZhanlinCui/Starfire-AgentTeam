# Memory

Workspace agents maintain memory (conversation context, learned information) across tasks. The memory backend is configurable in `config.yaml`.

## Backends

### filesystem (default)

Memory lives in a Docker volume mounted from the host. The provisioner mounts a named volume per workspace:

```
docker volume: ws-{id}-memory -> mounted at /memory inside container
```

The volume is named after the workspace ID, not the container name. Survives container restarts and re-provisions as long as the volume isn't deleted.

```yaml
memory:
  backend: filesystem
  path: /memory
```

**Best for:** Local dev, single-machine deployments. Zero config, works out of the box.

### langgraph_store

Memory lives in Postgres via LangGraph's built-in `AsyncPostgresSaver` checkpointer. Reads `DATABASE_URL` from the environment — already present in every workspace container, no extra config needed.

```yaml
memory:
  backend: langgraph_store
  # uses DATABASE_URL env var automatically
  # LangGraph handles the schema
```

```python
# workspace-template/memory/backend.py

if config.memory.backend == "langgraph_store":
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    checkpointer = AsyncPostgresSaver.from_conn_string(
        os.getenv("DATABASE_URL")
    )
```

Memory lives in Postgres alongside everything else. Any workspace instance on any machine reads the same memory.

**Best for:** Production self-hosted, multi-machine deployments. Memory in same DB as everything else.

### s3

Memory synced to S3-compatible object storage.

```yaml
memory:
  backend: s3
  bucket: agent-molecule-memory   # or reads S3_BUCKET env var
  prefix: ws-{id}/
```

Requires additional env vars injected at provision time:

```
S3_BUCKET
S3_REGION
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

Most durable, most portable — memory survives even if Postgres is wiped.

**Best for:** Tier 4 EC2 workspaces that run in isolation from the main platform. Disaster recovery scenarios.

### When to Pick Each

```
filesystem      → MVP, single machine, simplest
                  memory dies if volume deleted
                  zero config

langgraph_store → multi-machine, DATABASE_URL already available
                  memory in same DB as everything else
                  best default for production self-hosted

s3              → Tier 4 isolated VMs, disaster recovery
                  memory survives total platform rebuild
                  requires AWS credentials
```

## When Is Memory Lost?

| Backend | Memory lost only when |
|---------|----------------------|
| `filesystem` | Volume explicitly deleted (`nuke.sh` or user delete) |
| `langgraph_store` | Postgres data deleted |
| `s3` | S3 bucket/prefix deleted |

Memory is **NOT** lost on: container restart, re-provision, image update, machine reboot, offline/online cycle, **or agent replacement**.

## Agent Handoff via Memory

Memory persistence is what makes agent replacement seamless. When an agent is replaced:

1. The outgoing agent finishes its current task
2. The outgoing agent writes a handoff document to memory — current work state, in-progress TODOs, decisions made, relevant context
3. The new agent starts and reads the handoff files from the same memory store
4. The new agent picks up where the old one left off

The workspace always persists its TODO list and current work state as files in memory. This serves double duty: it's the agent's working memory during normal operation, and it's the handoff mechanism when the agent is swapped.

See [Core Concepts — Agent Handoff](../product/core-concepts.md#agent-handoff) for the conceptual overview.

## Cleanup on Workspace Deletion

When a user deletes a workspace, the platform cleans up memory based on the backend:

| Backend | Cleanup action |
|---------|---------------|
| `filesystem` | Remove the named Docker volume |
| `langgraph_store` | Delete memory rows from Postgres |
| `s3` | Delete S3 prefix |

Structure events and agent card history are **never** deleted — only conversational memory is cleaned.

## Related Docs

- [Config Format](../agent-runtime/config-format.md) — Where memory backend is configured
- [Provisioner](./provisioner.md) — How volumes are mounted
- [Workspace Runtime](../agent-runtime/workspace-runtime.md) — Runtime that uses memory
