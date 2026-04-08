# 🧠 Memory Architecture (HMA)

Starfire uses a completely novel approach to agent memory called **HMA (Hierarchical Memory Architecture)**. 

Unlike traditional multi-agent systems (like Mem0 or MemU) that utilize primitive global "Shared Memory" (where all agents query a massive, flat vector database), Starfire treats memory like **corporate data silos**. 

If a company's HR department shouldn't expose employee salaries to the Engineering department, why should their respective AI Agents store facts in the same vector database? 

## Core Philosophy: Org-Chart Driven Isolation

HMA enforces that **memory isolation perfectly mirrors the org chart topology**. We define three distinct tiers of memory scopes, strictly controlled by Postgres Row-Level Security (RLS) and the platform's `CanCommunicate` rules.

In the current implementation, each workspace also receives its own awareness namespace. That namespace is the concrete runtime boundary behind these logical scopes: the agent still uses the same memory tools, but the backend routes requests into the workspace's isolated awareness space.

---

### 1. L1: Local Memory (Personal Scratchpad)
- **Scope**: Entirely isolated to the current independent Workspace node.
- **Analogy**: A worker's personal notepad or clipboard.
- **Usage**: Automatically managed by the agent's internal LangGraph `StateGraph`. Used for storing intermediate execution state, short-term task tracking, and specialized prompt iterations.
- **Access Control**: **Invisible** to any other agent on the canvas, including direct parents or children.

### 2. L2: Team Shared Memory (Department Drive)
- **Scope**: Accessible exclusively by a "Team" (defined as a parent node and its direct children).
- **Analogy**: A departmental Google Drive folder or a team Slack channel.
- **Usage**: When a child agent synthesizes valuable information (e.g., Frontend Agent learns a new API schema), it purposefully calls the `commit_memory(fact, scope='TEAM')` A2A tool. This fact is written to L2 memory.
- **Access Control**: Any sibling agent (e.g., Backend Agent) or the Team Lead (parent) can use the `search_memory(scope='TEAM')` tool to retrieve it. Requests originating from outside this immediate team structure are hard-rejected with a HTTP 403 Forbidden.

### 3. L3: Global Corporate Memory (Company Wiki)
- **Scope**: Available to the entire organizational tree.
- **Analogy**: The company Wiki, All-Hands announcements, or Employee Handbooks.
- **Usage**: Top-down knowledge distribution. For instance, the company's brand voice guidelines, specific coding standards, or global APIs.
- **Access Control**: Usually mounted physically at the Root Workspace. Readable by all nodes globally down the tree. Writable **only** by explicitly authorized Admin nodes or human users.

---

## Technical Implementation

### 1. PostgreSQL + pgvector
We leverage the platform's existing PostgreSQL instance equipped with the `pgvector` extension. 
By persisting memory centrally rather than locally in each container, we drastically reduce memory fragmentation while letting the Platform gracefully enforce access control.

**Schema Concept:**
```sql
CREATE TABLE agent_memories (
    id UUID PRIMARY KEY,
    workspace_id UUID REFERENCES workspaces(id),
    content TEXT NOT NULL,
    embedding vector(1536),
    scope VARCHAR(10) CHECK (scope IN ('LOCAL', 'TEAM', 'GLOBAL')),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2. A2A Memory Operations
Memory interactions happen via standardized tool definitions exposed to the language model:
- `search_memory("what is the database password", scope="TEAM")`
- `commit_memory("the staging API URL is api.stage.com", scope="TEAM")`

### 3. Parent Context Inheritance (L2 complement)

L2 Team Memory stores facts explicitly committed at runtime. **Shared context** complements this by giving children access to the parent's static project knowledge (architecture docs, conventions, API schemas) without requiring the parent to commit each document as a memory entry.

The parent declares `shared_context: [architecture.md, conventions.md]` in its `config.yaml`. Children fetch these files at startup via `GET /workspaces/{parent_id}/shared-context` and inject them into their system prompt as a `## Parent Context` section. This is 1-level only — grandchildren see their direct parent's shared context, not the grandparent's.

See [Config Format — shared_context](../agent-runtime/config-format.md) and [System Prompt Structure — Parent Context](../agent-runtime/system-prompt-structure.md).

### 4. Asynchronous Cognitive Consolidation
Since Local Memory degrades as the context window fills, agents feature an independent Consolidation Loop. Similar to human sleep, when an agent reaches a configurable TTL of heartbeat-idleness, it can wake up a background goroutine/LangGraph thread to summarize noisy local scratchpad entries into dense, high-value knowledge facts, committing them back to L1 or L2 memory.
