# Ecosystem Watch

Projects adjacent to Starfire-AgentTeam that are worth tracking — for design
ideas to borrow, terminology collisions to be aware of, and to stay honest
about where our differentiation actually is.

## How to use this doc

- **Skim quarterly.** The agent-infra space moves fast; expect entries to be
  stale within ~3 months. When a project on this list ships something we
  should react to, add a line under "Signals to react to" for that entry
  and a short plan.
- **Add entries liberally.** Easier to prune than to miss.
- **One entry per project.** Keep each under ~200 words — link out, don't duplicate.

## Template

````markdown
### <Project> — `org/repo`

**Pitch:** one sentence in their words.

**Shape:** what it actually is (language, deployment target, one-vs-many-agents, etc.)

**Overlap with us:** where our designs touch.

**Differentiation:** why we're not the same product.

**Worth borrowing:** specific ideas we should study.

**Terminology collisions:** shared words that mean different things.

**Signals to react to:** what they might ship that would change our roadmap.

**Last reviewed:** YYYY-MM-DD · **Stars / activity:** <quick stat>
````

---

## Entries

### Holaboss — `holaboss-ai/holaboss-ai`

**Pitch:** "AI workspace desktop for business — build, run, and package AI
workspaces and workspace templates with a desktop app and portable runtime."

**Shape:** Electron desktop app + TypeScript runtime. **Single active agent
per workspace.** MIT-licensed OSS core with a hosted Holaboss backend for
some features (proposal ideation). macOS supported; Windows/Linux in progress.

**Overlap with us:** both call the unit of packaging a "workspace";
both ship a `skills/<id>/SKILL.md` convention; both have a plugin/app
marketplace; both treat long-lived context as important.

**Differentiation:** Holaboss is the **"AI employee"** shape — one agent
holding one role for months, with heroic effort spent on token-cost
discipline (compaction boundaries, `prompt_cache_profile`, stable vs
volatile prompt sections). We're the **"AI company"** shape — many agents
collaborating via A2A, visual org chart, multiple runtimes. No A2A, no
multi-agent coordination on their side.

**Worth borrowing:**
- Filesystem-as-memory: `memory/workspace/<id>/knowledge/{facts,procedures,blockers,reference}/` + scoped `preference/` and `identity/` namespaces. Clean model for durable memory that beats our current DB-only approach for inspectability.
- Compaction boundary artifact (summary + restoration order + preserved turn ids + request snapshot fingerprint) — if we ever add long-horizon single-agent mode, this is the reference design.
- Section-based prompt assembly with per-section cache fingerprints. Could reduce our Claude Code prompt cost.
- `workspace.yaml` rejects inline prompt bodies — forces prompts into `AGENTS.md`. We should do the same in `config.yaml` to keep runtime plans machine-readable.

**Terminology collisions:**
- "workspace" — theirs is a directory + agent state; ours is a Docker container running one agent in a team.
- "MEMORY.md" — theirs is the structured memory-service root; ours is the native file Claude Code / DeepAgents read.
- "skills/SKILL.md" — same filesystem convention, both inject into system prompt. Fully compatible in spirit.

**Signals to react to:**
- If they add A2A between workspaces → direct competitor; revisit differentiation.
- If they publish the compaction-boundary format as a spec → adopt.

**Last reviewed:** 2026-04-12 · **Stars / activity:** ~1.7k ⭐, pushed today

---

### Hermes Agent — `NousResearch/hermes-agent`

**Pitch:** "The self-improving AI agent built by Nous Research — creates
skills from experience, improves them during use, searches its own past
conversations, and builds a model of who you are across sessions."

**Shape:** Python-first agent framework with a TUI + multi-messenger
gateway (Telegram / Discord / Slack / WhatsApp / Signal / Email). Single
user, single continuous agent with a closed **learning loop**. Six
execution backends (local, Docker, SSH, Daytona, Singularity, Modal —
last two are serverless w/ hibernation). MIT, ~61k⭐ and climbing fast.

**Overlap with us:**
- "Skills" with filesystem convention — compatible with the
  [agentskills.io](https://agentskills.io) open standard they back.
- Subagent spawning for parallel work.
- Scheduled automations (natural-language cron).
- Model-agnostic (Nous Portal, OpenRouter, GLM, Kimi, MiniMax, OpenAI, …).

**Differentiation:** Hermes is the **"personal AI across every messenger"**
shape — one agent that knows *you* deeply and runs anywhere. We're the
**"team of agents behind a canvas"** shape — many roles collaborating on
shared work. Hermes has no visual canvas, no org hierarchy, no A2A between
workspaces.

**Worth borrowing:**
- **Closed learning loop**: autonomous skill creation after complex tasks,
  skills self-improve during use, agent-curated memory with periodic nudges
  to persist knowledge. This is a much stronger memory discipline than
  ours; the "nudge to persist" pattern in particular is cheap to implement.
- **FTS5 + LLM-summarization** for cross-session recall — cheap, no
  vector-store overhead, works great for the "did I tell you about X" case.
- **Honcho dialectic user modeling** (`plastic-labs/honcho`) for building
  a model of the user across sessions. Worth evaluating as a memory backend
  for Starfire's PM workspace specifically (the one role where knowing
  the CEO well matters most).
- **Daytona / Modal serverless backends** with hibernation — a great fit
  for our DevOps workspaces that only wake for scheduled audits. Could
  drop our idle compute cost meaningfully.
- **`hermes claw migrate`** command — gracefully import users from
  OpenClaw (the predecessor). Good pattern if we ever deprecate a runtime
  adapter.

**Terminology collisions:**
- "skills" — same direction as ours post-refactor (file-based, installable,
  runtime-agnostic). Their
  [agentskills.io](https://agentskills.io) spec is worth reading before we
  finalize our plugin manifest schema.
- Topic tags on the repo include `openclaw`, `clawdbot`, `moltbot`,
  `claude-code`, `codex` — Nous Research has a whole agent family. Our
  `workspace-template/adapters/openclaw/` adapter predates Hermes's
  rebrand; check whether it still points to a live project.

**Signals to react to:**
- If `agentskills.io` spec picks up mass adoption → align our plugin
  manifest so the same skill repo installs on Hermes AND Starfire.
- If Hermes ships multi-agent / A2A → direct overlap with our core thesis.
- If Atropos RL trajectory generation becomes the standard for training
  tool-calling models → our workspace activity logs should adopt the
  trajectory schema so users can export training data.

**Last reviewed:** 2026-04-12 · **Stars / activity:** ~61k ⭐, pushed today

---

### gstack — `garrytan/gstack`

**Pitch:** "Use Garry Tan's exact Claude Code setup: 23 opinionated tools
that serve as CEO, Designer, Eng Manager, Release Manager, Doc Engineer,
and QA." Claude Code skills bundle, MIT, ~70k⭐ and going viral on X.

**Shape:** A single directory of Markdown slash-command definitions
installed at `~/.claude/skills/gstack/`, invoked inside one Claude Code
session: `/office-hours`, `/plan-ceo-review`, `/review`, `/qa`, `/ship`,
`/land-and-deploy`, `/cso` (security), `/retro`, etc. No services, no
containers, no DB — just prompts and scripts that the Claude Code CLI
executes in whatever repo the user has open.

**Overlap with us:**
- **Same role metaphor as starfire-dev.** Both cast AI work as a cast of
  roles (CEO, Eng Manager, Designer, Security, QA). The naming overlap is
  nearly 1:1 with our org template.
- **Claude Code-native**, Markdown-driven config, "skills" as the unit.
- Team-mode auto-updates shared repos — same instinct as our org templates.

**Differentiation:** gstack is **sequential, single-session, single-repo.**
One Claude Code session runs each slash command in turn; the "team" is a
persona switch, not separate processes. We're **parallel, multi-session,
hierarchical**: real containers, A2A between siblings, a visual canvas,
real-time WebSocket updates, schedules, org bundles. gstack has no
multi-agent coordination, no A2A, no canvas, no workspace persistence
beyond git — it's a brilliant prompt library, not an orchestration platform.

**Worth borrowing:**
- **`/retro` command**: generates a weekly retrospective from git history
  ("140,751 lines added, 362 commits, ~115k net LOC in one week"). Would
  be a natural addition to our PM agent's toolbox — `commit_memory` +
  git log synthesis. Cheap win.
- **`/autoplan` and `/freeze` / `/guard` / `/unfreeze`** for architectural
  guardrails during a risky change. Maps cleanly onto our approval flow —
  could turn into a `/freeze` hook that sets a workspace-level policy flag
  preventing certain tool calls during a migration.
- **Role-prompt library.** gstack has spent a lot of effort on the CEO /
  Designer / Eng Manager personas. Even without adopting their runtime,
  we could lift the prompt text into our starfire-dev system-prompt.md
  files with attribution. Their CSO (OWASP + STRIDE audit) and Designer
  (AI-slop detection) personas are both stronger than ours today.
- **Team-mode auto-update** (throttled once/hour, network-failure-safe,
  silent) — good pattern for keeping plugins in sync across an org
  without requiring manual `/plugins/install` calls.

**Terminology collisions:**
- "Skills" — gstack ships everything as Claude Code skills (filesystem
  convention `~/.claude/skills/<name>/`). Same filesystem shape as
  ours AND Hermes AND Holaboss. Four projects, one spec shape — should
  formalize with [agentskills.io](https://agentskills.io).
- "Ship / Release" — their `/ship` is a local PR-and-merge flow;
  nothing to do with our A2A lifecycle.
- Mentions "OpenClaw" (247k ⭐ claim) as inspiration — tracks with the
  Hermes entry's note that the OpenClaw name is alive in multiple
  ecosystems.

**Signals to react to:**
- If gstack adds multi-session / parallel execution (spawning multiple
  Claude Code workers and routing between them) → direct competitor
  with a 70k⭐ head start. Revisit our differentiation messaging.
- If their `/plan-ceo-review` prompt or `/qa` browser flow becomes an
  informal standard → copy it into starfire-dev's system prompts.
- If Garry Tan posts a video deploying gstack on a new use case →
  high-signal about what "everyone" will ask us to support next week.

**Last reviewed:** 2026-04-12 · **Stars / activity:** ~70k ⭐, pushed yesterday

---

### Composio — `composio-dev/composio`

**Pitch:** "The integration layer for AI agents — 250+ tools across Slack,
GitHub, Telegram, Linear, Discord, and more, with managed auth."

**Shape:** Python + TypeScript SDK. Pure integration library — no agent
runtime, no visual canvas. Plugs into any LLM framework (LangChain,
LangGraph, AutoGen, CrewAI, Claude, OpenAI Agents). Managed auth so agents
can act on user-connected accounts. MIT-adjacent, ~18k ⭐.

**Overlap with us:** Both provide agent-accessible Slack, Telegram, and
Discord channels. Both handle OAuth / credential management for workspace
integrations. Channels feature in `platform/internal/handlers/channels.go`
does a subset of what Composio does for the messaging platforms.

**Differentiation:** Composio is a tool library, not a runtime or org
hierarchy. No canvas, no A2A between agents, no org structure. They're
"the 250 tools agents can call"; we're "the company that runs the agents."
Composio could be a dependency inside a Starfire workspace skill — not a
competitor for the platform layer.

**Worth borrowing:**
- **Trigger model:** inbound webhook → fire agent → respond in same channel.
  Our channels feature handles outbound well but inbound triggers are still
  manually configured. Composio's trigger schema is worth adopting.
- **"Connected accounts" pattern:** per-workspace OAuth token stored per
  integration, reused across runs. Our `workspace_channels` JSONB config is
  close; formalize as a named model.
- **Auth sandbox:** test mode that mocks API calls — useful for our
  `POST /workspaces/:id/channels/:id/test` endpoint.

**Terminology collisions:**
- "actions" = their tool calls; we use "skills."
- "triggers" = their inbound webhooks; we use channels + schedules.

**Signals to react to:**
- If they add persistent agent identity across trigger runs → direct overlap
  with our workspace model.
- If they add A2A between agent sessions or multi-agent orchestration → threat
  to our integration story.
- If `agentskills.io` adopts Composio trigger schema → we should too.

**Last reviewed:** 2026-04-13 · **Stars / activity:** ~18k ⭐, active

---

### n8n — `n8n-io/n8n`

**Pitch:** "Fair-code workflow automation with 400+ integrations — build AI
pipelines visually, self-host or cloud."

**Shape:** Node.js, self-hosted or n8n cloud. Visual workflow builder (nodes
+ edges, not unlike React Flow). 400+ connectors: Slack, Telegram, Discord,
WhatsApp, Email, GitHub, Linear, Notion, … plus dedicated AI nodes
(LLM chains, agent nodes, vector stores, tool use). Fair-code license
(source-available, free for internal use). ~50k ⭐, pushed daily.

**Overlap with us:**
- Visual graph metaphor for orchestrating work (their nodes ≈ our canvas
  workspaces).
- Connects AI agents to Slack / Telegram / Discord / WhatsApp — identical
  surface to our `workspace_channels` feature.
- Scheduled automations (cron triggers) → same as `workspace_schedules`.
- Self-hostable, Docker Compose first-class.

**Differentiation:** n8n is trigger→step→step→output (stateless sequential
workflow per run). No persistent agent identity, no shared memory across
runs, no org hierarchy, no A2A between agents. Each execution is isolated.
We're "agents that remember, collaborate, and hold roles"; they're "workflows
that transform data." The UX audiences barely overlap: n8n users are ops/no-code
builders; Starfire users are developers building agent companies.

**Worth borrowing:**
- **Channel trigger UX:** select platform → OAuth → pick chat → done in
  three clicks. Our channel setup requires more manual config; this flow is
  the right target for `POST /workspaces/:id/channels`.
- **"Test workflow" dry-run:** one-click test execution with live output.
  Maps well onto our `POST /workspaces/:id/channels/:id/test` — we should
  fire a real test message and show the round-trip result inline.
- **Sticky notes on canvas:** freeform annotation nodes for documentation.
  Cheap win for our canvas — could be a "comment node" workspace type.
- **Execution log with step-level timing:** n8n shows each node's in/out
  data and ms. Our `activity_logs` captures A2A traffic but not intra-agent
  step timing. Worth adding to the trace view.

**Terminology collisions:**
- "workflow" — their atomic unit; for us "workflow" is informal. No hard
  collision but our marketing copy should avoid it to stay distinct.
- "nodes" — their workflow steps; our canvas nodes are workspaces. Different
  enough to not cause user confusion, but worth noting in docs.

**Signals to react to:**
- If n8n ships persistent agent nodes (memory between runs) → direct
  substitute for simple Starfire use cases. They've been adding AI nodes
  fast (AI Agent node shipped 2024-Q3).
- If they add multi-agent coordination with shared state → revisit our
  differentiation messaging.
- If a major Slack/Discord bot tutorial uses n8n instead of a custom agent
  → indicates channel-first UX is the market expectation we need to match.

**Last reviewed:** 2026-04-13 · **Stars / activity:** ~50k ⭐, pushed daily

---

### Pydantic AI — `pydantic/pydantic-ai`

**Pitch:** "AI Agent Framework, the Pydantic way."

**Shape:** Python SDK (MIT), ~16.3k ⭐, last release v1.8.0 on April 10, 2026 — actively maintained at high velocity. Single and multi-agent, with typed dependency injection (`RunContext[DepsType]`), structured/validated outputs (`Agent[Deps, OutputType]`), composable capability bundles (tools + hooks + instructions + model settings), built-in streaming, and human-in-the-loop tool approvals. Supports A2A and MCP natively as first-class integrations. Model-agnostic: OpenAI, Anthropic, Gemini, Mistral, Cohere, DeepSeek, Bedrock, Vertex, Ollama, OpenRouter, and more. Observability via Pydantic Logfire.

**Overlap with us:** A2A support means Pydantic AI agents can speak directly to Starfire workspaces over our native protocol — they're potential consumers of Starfire's registry, not just a parallel ecosystem. MCP integration mirrors our workspace tool model. The composable capability bundles are the same instinct as our plugin/skills system. Logfire's agent tracing is a polished alternative to our `GET /workspaces/:id/traces` + Langfuse stack.

**Differentiation:** Pydantic AI is a library for building agents in Python — no visual canvas, no Docker workspace isolation, no registry/discovery, no scheduling, no WebSocket org chart, no channels. It's the in-process layer; we're the operational platform layer. The two are naturally complementary: a Starfire workspace *running* Pydantic AI agents is a valid architecture, not a contradiction.

**Worth borrowing:**
- **Typed dependency injection via `RunContext`** — passing strongly-typed deps (DB connection, API client, user object) into every tool and instruction without global state. Our `config.yaml` passes env vars; this pattern is safer and more testable.
- **`Agent[Deps, OutputType]` generic typing** — structured, schema-validated agent outputs. Our A2A responses are freeform text; adopting structured output schemas at the A2A layer would enable typed inter-workspace contracts.
- **Composable capability bundles** — reusable packages of tools + hooks + instructions. Our plugins install files; this is the right next evolution (code bundles, not just Markdown).

**Terminology collisions:**
- "capabilities" — their term for composable tool+instruction bundles; we use "plugins" or "skills."
- "RunContext" — their typed dependency carrier; not a shared term, but will appear in codebases mixing Pydantic AI + Starfire adapters.
- "tools" — same word, same meaning. No collision, but documentation should be explicit about Pydantic AI tools vs. MCP tools vs. Starfire skills.

**Signals to react to:**
- If Pydantic AI ships a workspace/session persistence layer → fills the one gap between it and Starfire's value; revisit our Python-SDK adapter story.
- If `pydantic-deepagents` (`vstorm-co/pydantic-deepagents`) gains traction — "Claude Code–style deep agents on Pydantic AI" — it would become a direct competitor to our Claude Code runtime adapter.
- If Logfire's agent tracing becomes the de facto standard → align our trace schema so Logfire can ingest Starfire workspace traces natively.

**Last reviewed:** 2026-04-13 · **Stars / activity:** ~16.3k ⭐, v1.8.0 released April 10, 2026

---

### Rivet — `Ironclad/rivet`

**Pitch:** "The open-source visual AI programming environment and TypeScript library."

**Shape:** Electron desktop app + TypeScript library (MIT), ~4.5k ⭐. Visual node-based editor where AI workflows are built by connecting nodes in a graph: LLM call nodes, tool nodes, subgraph nodes, conditional branches. Runs locally; exports workflows as `.rivet-project` files that can be embedded in applications via the `@ironclad/rivet-node` npm package. Built and open-sourced by Ironclad (a Series D contract intelligence company). Model-agnostic. Plugin marketplace for custom node types.

**Overlap with us:** The canvas is the obvious overlap — both products present AI agent work as a visual graph. Rivet's subgraph nesting (complex workflows broken into reusable components) maps to our parent/child workspace hierarchy. The plugin marketplace for custom nodes mirrors our `plugins/` registry. Rivet workflows can call external APIs, making them potential consumers of Starfire's `/workspaces/:id/a2a` endpoint — a Rivet node that delegates to a Starfire agent is a plausible integration.

**Differentiation:** Rivet is a **workflow authoring tool**, not an agent runtime. A `.rivet-project` file describes a static graph; there's no persistent agent identity, no memory across runs, no org hierarchy, no real-time WebSocket canvas, no scheduling, no Docker container management. The Rivet editor is for building workflows; Starfire is for running a live org of agents. The `/channels` angle is absent from Rivet — it has no concept of an agent receiving or sending messages via Telegram, Slack, or other social platforms. Rivet's audience is developers prototyping single pipelines; ours is teams deploying multi-agent organizations.

**Worth borrowing:**
- **Nested subgraph UX** — Rivet's handling of "graph within graph" as a first-class reusable node is the cleanest visual pattern for our parent/child workspace hierarchy. Our current Canvas flattens deeply nested teams into chips; Rivet's subgraph expand/collapse is the reference UX to study.
- **Node-level debug inspector** — clicking any node in a completed run shows its exact inputs, outputs, and latency. Our Canvas chat shows A2A messages but not intra-workspace step-level data. This is the natural evolution of our trace view.
- **`.rivet-project` portability** — workflow-as-file, embeddable in any TypeScript app via npm. Suggests we should support a "workspace bundle export" that can run outside Starfire, not just be imported back into it.

**Terminology collisions:**
- "graph" — their graph is a workflow definition (static); ours is the live org chart (dynamic, stateful). Different semantics, same word.
- "node" — their nodes are workflow steps; our canvas nodes are workspaces. No runtime collision but documentation must be unambiguous.
- "plugin" — both have plugin systems; theirs extends the node palette, ours extends the workspace runtime.

**Signals to react to:**
- If Rivet adds persistent agent state between runs → closes the gap with Starfire for simple use cases; revisit our "quick start" story for non-enterprise users.
- If Rivet adds a "deploy workflow as agent endpoint" feature → their visual builder becomes a Starfire workspace creator; consider a Rivet → Starfire import adapter.
- If `.rivet-project` format becomes a de facto workflow interchange standard → support importing Rivet projects as Starfire workspace configs.

**Last reviewed:** 2026-04-13 · **Stars / activity:** ~4.5k ⭐, actively maintained

---

### Letta — `letta-ai/letta`

**Pitch:** "The platform for building stateful agents: AI with advanced memory that can learn and self-improve over time."

**Shape:** Python + TypeScript SDK (Apache-2.0), ~22k ⭐, v0.16.7 released March 31, 2026. Formerly MemGPT (the research project that pioneered OS-inspired virtual context management for LLMs). Letta's defining feature is a **multi-block memory architecture**: each agent holds named, editable in-context memory segments ("core memory") such as `human`, `persona`, and `archival` blocks, which the agent can read and write via tool calls. Memories persist across sessions in a Letta Server (self-hosted or Letta Cloud). Agents are accessed via a REST API. The **ADE (Agent Development Environment)** is a graphical interface for creating, testing, and monitoring agents in real-time. Multi-agent support via subagents and shared memory. Model-agnostic (OpenAI, Anthropic, local LLMs via Ollama).

**Overlap with us:** Letta's named memory blocks (`human`, `persona`, `archival`) are a structured evolution of the same problem our `agent_memories` table and `MEMORY.md` file solve — persistent, durable knowledge for a long-lived agent. The ADE's graphical agent-monitoring interface overlaps with our Canvas; both offer a UI to inspect and interact with running agents. Letta Server exposes a REST API that accepts messages at agent endpoints — structurally similar to our A2A proxy (`POST /workspaces/:id/a2a`). Multi-agent subagent support maps to our parent/child workspace hierarchy. Letta's `initial_prompt` equivalent (agent system prompt + memory bootstrap) mirrors our `initial_prompt` in `config.yaml`.

**Differentiation:** Letta is focused on **the single-agent memory problem**, not the multi-agent org problem. No Docker container isolation per agent, no workspace registry, no real-time WebSocket org chart, no scheduling, no channels to Slack/Telegram/Discord. The ADE shows individual agents; it does not visualize an org hierarchy or inter-agent A2A traffic. Letta's multi-agent support is hierarchical subagent spawning within a single Letta Server context — not independently deployable, independently schedulable workspaces. We're "a company of agents"; Letta is "an agent with a very good memory."

**Worth borrowing:**
- **Named, agent-editable memory blocks** — the `human` / `persona` / `archival` distinction is the clearest taxonomy we've seen for agent memory. Our `agent_memories` namespace is flat; adopting explicit named blocks (at minimum: `self`, `user`, `task-context`, `long-term-knowledge`) would make memory more inspectable and auditable in the Canvas.
- **Memory self-editing as a tool call** — Letta agents call `core_memory_replace(label, old, new)` and `archival_memory_insert(content)` as first-class tool actions, making memory updates part of the visible tool-call trace. Our `commit_memory` MCP tool is close; making it show up in `activity_logs` as a named tool call (not a silent background action) would match this pattern.
- **ADE real-time message inspector** — the ADE shows each tool call, memory read/write, and reasoning step inline in a timeline. This is more granular than our Canvas chat tab; it's the reference design for a "step-through debug mode" in our trace view.

**Terminology collisions:**
- "archival memory" — Letta: a searchable long-term store the agent queries via tool calls. Ours: not a defined term. Our `agent_memories` table is functionally similar but not surfaced to agents as a named primitive.
- "persona" — Letta: a named memory block containing the agent's self-description. Ours: the `role:` field in `config.yaml` plus the system prompt. Same intent, different packaging.
- "agent" — Letta: a long-lived server-side object with persistent memory, accessed via REST. Ours: a Docker container running one of six runtimes. Same word, substantially different operational model.

**Signals to react to:**
- If Letta ships a multi-agent canvas that visualizes org hierarchies (not just individual agent inspection) → direct overlap with our Canvas; they have strong memory credibility that could attract our target buyer.
- If Letta formalizes a memory-block schema as an open spec (building on their MemGPT research lineage) → evaluate adopting it as Starfire's `agent_memories` schema to gain interoperability with the Letta ecosystem.
- If Letta Cloud adds Slack/Telegram/Discord inbound triggers → they gain channels capability; currently absent, but a REST API means it's one webhook away.
- Watch v0.x → v1.0 trajectory: v0.16.7 suggests pre-1.0 API stability; a 1.0 GA announcement would signal enterprise readiness and an accelerated sales motion.

**Last reviewed:** 2026-04-13 · **Stars / activity:** ~22k ⭐, v0.16.7 March 31, 2026

---

### Trigger.dev — `triggerdotdev/trigger.dev`

**Pitch:** "Build and deploy fully-managed AI agents and workflows."

**Shape:** TypeScript (Apache-2.0), ~14.5k ⭐, v4.4.3 released March 10, 2026. Started as a developer-friendly alternative to cron + background jobs; v4 repositions it squarely as **durable execution infrastructure for AI agents**. Tasks are TypeScript functions decorated with `task()` — they run in a managed cloud with: automatic retry with exponential backoff, checkpoint/resume (task state saved to storage, resumed after crash or timeout), queue and concurrency control, and cron scheduling up to one-year duration. Human-in-the-loop via `waitForApproval()`. MCP server available (`trigger-dev` MCP) so AI assistants (Claude Code, Cursor, etc.) can trigger tasks, check run status, and deploy from chat. Warm starts execute in 100–300ms. Fully self-hostable.

**Overlap with us:** Trigger.dev's `schedules.task()` cron system overlaps directly with our `workspace_schedules` table and `POST /workspaces/:id/schedules` API — both schedule recurring prompts/tasks on a cron expression. The checkpoint/resume model (`waitForApproval`, `wait.for()`) is a precise parallel to our workspace `pause` / `resume` lifecycle. Human-in-the-loop approval gates match our `POST /workspaces/:id/approvals`. The MCP server enabling AI agents to trigger tasks maps to the same use case as our MCP server's `delegate_task` tool. Both platforms treat long-running, fault-tolerant execution as a core design constraint.

**Differentiation:** Trigger.dev has **no agent identity** — tasks are stateless TypeScript functions, not persistent agents with memory, roles, or system prompts. No visual canvas, no org hierarchy, no A2A protocol, no workspace registry. It is execution infrastructure, not an agent platform. The right mental model: Trigger.dev is to Starfire what Temporal is to Starfire — a lower-level durable execution substrate that Starfire's workspaces could use as a backend for their scheduled tasks, rather than a replacement for Starfire itself. Their `/channels` story is inbound-only (HTTP triggers, webhooks, cron) with no native Slack/Telegram messaging surface.

**Worth borrowing:**
- **Idempotency keys on task invocation** — `trigger("send-report", payload, { idempotencyKey: runId })` ensures a task is only ever executed once for a given key, even if triggered multiple times. Our delegation system has no equivalent guard; duplicate delegations from container-restart races are a known issue (see `delegationRetryDelay` in `delegation.go`). Adding idempotency keys to `POST /workspaces/:id/delegate` would fix the duplicate-execution class of bugs.
- **`waitForApproval()` inline in task code** — instead of a separate approvals table and polling loop, the task itself calls `await wait.for({ event: "approval" })` and suspends. Our approval flow requires a separate API round-trip and the agent to re-check; Trigger.dev's inline suspension is the right long-term model.
- **Warm-start pool for sub-300ms agent starts** — Trigger.dev pre-warms TypeScript runtimes to achieve 100–300ms cold start. Our Docker workspace startup is measured in seconds. Worth evaluating their warm-pool approach for our claude-code and langgraph adapters.

**Terminology collisions:**
- "task" — Trigger.dev: a decorated TypeScript function, the atomic unit of execution. Ours: informal (used in delegation context and `current_task` heartbeat field). Their definition is more precise; consider whether our heartbeat `current_task` field should be renamed to avoid collision with Trigger.dev vocabulary in integrations.
- "schedule" — same word, same meaning. Trigger.dev's cron schedule API and ours (`workspace_schedules`) are functionally identical at the surface. Our docs should distinguish "Starfire schedules" from "Trigger.dev schedules" clearly when positioning integrations.
- "run" — Trigger.dev: a single execution of a task with full lifecycle tracking. Ours: informal. No hard collision.

**Signals to react to:**
- If Trigger.dev ships native agent identity (persistent state, memory across runs, named agents) → crosses from infrastructure into platform territory; reevaluate positioning.
- If the `trigger-dev` MCP becomes a de facto standard for AI-tool-triggered background work → add a Trigger.dev adapter to our workspace runtime so Starfire agents can fire Trigger.dev tasks as a tool call (complementary, not competitive).
- If Trigger.dev ships a Slack/Discord trigger adapter → they gain a channels surface; currently absent. Watch their integration roadmap.
- Their TypeScript-first stack and MCP server target the same developer audience as our Canvas + mcp-server. Co-marketing opportunity: "run your Starfire agent on a schedule via Trigger.dev" is a cleaner story than our current in-house cron for some user segments.

**Last reviewed:** 2026-04-13 · **Stars / activity:** ~14.5k ⭐, v4.4.3 March 10, 2026

---

### MeDo — `moda.baidu.com` *(commercial, no public repo)*

**Pitch:** Baidu's no-code AI application builder — scaffold and publish AI-powered apps through a visual editor with pre-built LLM integrations.

**Shape:** SaaS platform (Baidu Cloud, Chinese-market primary). Users compose apps from prompt nodes, data connectors, and UI blocks via a drag-and-drop canvas. Published apps get a hosted endpoint. REST API for programmatic create/update/publish. No OSS repo; requires Baidu Cloud account. Hackathon track: MeDo SEEAI May 2026.

**Overlap with us:** Both expose a canvas (theirs visual, ours org-chart + agent config). Both have an app-publish lifecycle. Our Canvas + workspace provisioner covers roughly the same surface for technical teams; MeDo targets non-developers. Starfire is integrating MeDo via the new `medo.py` builtin tool to enter the May 2026 hackathon.

**Differentiation:** MeDo is a no-code builder for end-user AI apps; Starfire is a developer platform for multi-agent engineering workflows. MeDo has no A2A, no workspace Docker runtime, no persistent agent memory. Starfire has no no-code UI builder. The integration is complementary: Starfire agents can create and publish MeDo apps programmatically as a delivery step.

**Worth borrowing:**
- **Visual prompt-node composition** — their drag-and-drop prompt pipeline could inspire a simpler Canvas view for non-technical stakeholders who want to inspect an agent's workflow without reading system-prompt.md.

**Terminology collisions:**
- "app" — a published MeDo application vs a Starfire workspace; different lifecycles.
- "canvas" — their visual editor surface vs our org-chart canvas.

**Signals to react to:**
- If MeDo opens a REST API to third-party agent platforms → expand `medo.py` from stub to full integration; file a Hermes-style adapter PR.
- If the MeDo hackathon win generates user interest → prioritise MeDo as a first-class delivery target alongside GitHub and Slack.

**Last reviewed:** 2026-04-13 · **Stars / activity:** commercial SaaS (Baidu Cloud), active hackathon track May 2026

---

### Inngest — `inngest/inngest`

**Pitch:** "The durable execution engine for AI agents and background functions — write reliable step functions that survive failures, retries, and deploys."

**Shape:** Go + TypeScript SDK (Apache 2.0), ~5.2k ⭐. Cloud-hosted or self-hosted. Developers define "functions" as async step graphs; Inngest handles scheduling, retries, concurrency limits, rate limits, and failure recovery. HTTP-native — functions live in your existing web server and Inngest calls them. Comparable to Temporal but lighter: no gRPC, no workflow history replay, just durable HTTP step execution.

**Overlap with us:** Starfire ships an in-house cron scheduler and a Temporal adapter for durable background work. Inngest is a third option in the same space: schedule-driven agent tasks, retry-on-failure, fan-out. Any Starfire feature that today uses `CronCreate` or temporal_workflow could instead use Inngest's step functions.

**Differentiation:** Inngest is infrastructure-as-a-service for function scheduling; Starfire is an agent platform. Inngest has no concept of persistent agent identity, workspace lifecycle, org hierarchy, or A2A. Our Temporal adapter is the direct equivalent for complex multi-step workflows; Inngest targets simpler event-triggered functions with less operational overhead than Temporal.

**Worth borrowing:**
- **HTTP-native step graph model** — Inngest steps live in a plain web route. Adopting this pattern for Starfire's skill execution would remove the need for the workspace's internal runner process for short tasks.
- **Built-in rate limiting per function** — our current delegation tool has no per-workspace rate limit; Inngest's concurrency + rate-limit primitives are the reference design.

**Terminology collisions:**
- "function" — Inngest functions are durable async step graphs; ours are Python tool functions decorated with `@tool`.
- "event" — Inngest events trigger functions; our `event_queue` in A2A is different.

**Signals to react to:**
- If Inngest ships native agent-state primitives (memory, long-running sessions) → direct overlap with our workspace model; re-evaluate our Temporal dependency.
- If Inngest becomes the dominant alternative to Temporal in AI stacks → add an `inngest` adapter alongside `temporal_workflow.py`.

**Last reviewed:** 2026-04-13 · **Stars / activity:** ~5.2k ⭐, v0.x actively developed

---

## Candidates to add (backlog)

Short-list of projects to write up next time someone has an hour:

- **LangGraph** (`langchain-ai/langgraph`) — we already support it as a
  runtime; worth a full entry for how their graph model compares to our
  workspace hierarchy.
- **AutoGen** (`microsoft/autogen`) — ditto, we adapt it.
- **CrewAI** (`crewaiinc/crewai`) — ditto.
- **DeepAgents** (`langchain-ai/deepagents`) — ditto; particularly their
  sub-agent feature that collides with our "skills" word.
- **OpenClaw** — check if this is still live post-Hermes rebrand; our
  adapter may need renaming.
- **Moltiverse / Moltbook** (`molti-verse.com`) — "social network for AI
  agents." Not a competitor; orthogonal ecosystem but worth tracking in
  case we want agent-to-agent discovery beyond a single org.
- **Temporal** (`temporalio/temporal`) — we already integrate; entry
  should cover when to lean on Temporal vs our in-house scheduling.
