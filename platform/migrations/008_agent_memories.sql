CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS agent_memories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID REFERENCES workspaces(id),
    content         TEXT NOT NULL,
    embedding       vector(1536),
    scope           VARCHAR(10) NOT NULL CHECK (scope IN ('LOCAL', 'TEAM', 'GLOBAL')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memories_workspace ON agent_memories(workspace_id);
CREATE INDEX IF NOT EXISTS idx_memories_scope ON agent_memories(scope);
