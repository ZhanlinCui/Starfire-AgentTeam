# Local Development

## Starting the Stack

```bash
docker compose up
```

This starts:

| Service | Port | Description |
|---------|------|-------------|
| Postgres | `:5432` | Primary database |
| Redis | `:6379` | Ephemeral state |
| Platform (Go) | `:8080` | Control plane API |
| Canvas (Next.js) | `:3000` | Visual frontend |
| Langfuse web | `:3001` (host) / `:3000` (internal) | Observability UI |
| Langfuse worker | — | Background processing |
| ClickHouse | — | Langfuse dependency |

Each workspace container is provisioned **on demand** by the platform when a user creates or imports one.

### Infrastructure Only

To start just Postgres, Redis, and Langfuse (no application code):

```bash
docker compose -f docker-compose.infra.yml up
```

## Environment Variables

### Platform (Go)

```
DATABASE_URL=postgres://dev:dev@postgres:5432/agentmolecule
REDIS_URL=redis://redis:6379
PORT=8080
SECRETS_ENCRYPTION_KEY=dev-key-change-in-production
```

### Canvas (Next.js)

```
NEXT_PUBLIC_PLATFORM_URL=http://localhost:8080
NEXT_PUBLIC_WS_URL=ws://localhost:8080/ws
```

### Workspace (Python)

```
WORKSPACE_ID=           # assigned by platform on provision
WORKSPACE_CONFIG_PATH=  # path to config folder inside container
MODEL_PROVIDER=         # e.g. anthropic:claude-sonnet-4-6
TIER=                   # 1, 2, 3, or 4
PLATFORM_URL=           # http://platform:8080
ANTHROPIC_API_KEY=      # or OPENAI_API_KEY, etc.
LANGFUSE_HOST=          # http://langfuse-web:3000 (internal container port; host-mapped to :3001)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGSMITH_TRACING=true  # LangGraph reads this to enable tracing
```

## Technology Versions

```
Go              1.22+
Python          3.11+
Node.js         20+
Next.js         15
React Flow      11+  (xyflow)
deepagents      0.4+
a2a-python      latest   (A2A server SDK)
langfuse        3.x  (self-hosted Docker)
Postgres        16
Redis           7
Docker Compose  2.x
```

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `infra/scripts/setup.sh` | Initialize the local environment |
| `infra/scripts/nuke.sh` | Tear down and clean up everything |
| `bundle-compile.sh` | Compile workspace config folders into `.bundle.json` files |

## Related Docs

- [Architecture](../architecture/architecture.md) — System overview
- [Observability](./observability.md) — Langfuse details
