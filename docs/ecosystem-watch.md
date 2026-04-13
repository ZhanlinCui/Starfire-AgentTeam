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
