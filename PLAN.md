# PLAN.md — Starfire Build Plan

> Completed phases (1–11, 13–14) are documented in `/docs` and removed from here.
> This file tracks only **in-progress and upcoming work**.

---

## Completed Phases (see /docs for details)

| Phase | Name | Docs |
|-------|------|------|
| 1 | Core Loop | `docs/architecture/architecture.md`, `CLAUDE.md` |
| 2 | E2E Validation | `CLAUDE.md` (build/test commands) |
| 3 | Hierarchy & Communication | `docs/api-protocol/communication-rules.md` |
| 4 | Provisioner | `docs/architecture/provisioner.md` |
| 5 | Agent Management | `CLAUDE.md` (API routes) |
| 6 | Bundle Export/Import | `docs/agent-runtime/bundle-system.md` |
| 7 | Team Expansion | `docs/agent-runtime/team-expansion.md` |
| 8 | Human-in-the-Loop Approvals | `docs/agent-runtime/system-prompt-structure.md` |
| 9 | Hierarchical Memory | `docs/architecture/memory.md` |
| 10 | Observability (Langfuse) | `docs/development/observability.md` |
| 11 | Canvas Polish & UX | `docs/frontend/canvas.md` |
| 13 | Runtime Enhancements | `docs/agent-runtime/workspace-runtime.md` |
| 14 | Production Hardening | `docs/architecture/provisioner.md`, `CLAUDE.md` |
| 15 | Per-Workspace Dir | PR #38 — `workspace_dir` per workspace |
| 16 | Plugin System | PR #39 — per-workspace plugins with registry |
| 17 | Agent GitHub Access | PR #40 — git/gh in images, GITHUB_TOKEN env |
| 18 | File Browser Lazy Loading | PR #37 — depth=1, path traversal protection |
| 19 | MCP Full Coverage | PR #40 — 52 tools (plugins, global secrets, pause/resume, org) |
| 21 | Claude Agent SDK Migration | `feat/claude-agent-sdk` — `ClaudeSDKExecutor` replaces CLI subprocess |

---

## Phase 21: Claude Agent SDK Migration — COMPLETE (pending merge)

> Branch: `feat/claude-agent-sdk`. Replaces CLI subprocess with `claude-agent-sdk` Python package for the `claude-code` runtime. Same Claude Code engine, no behavioral changes — just eliminates subprocess fragility.

- [x] `claude_sdk_executor.py` — SDK-based executor with asyncio.Lock, cancel, QueryResult
- [x] `executor_helpers.py` — shared helpers (memory, delegation, heartbeat, system prompt, error sanitization)
- [x] Adapter updated to return `ClaudeSDKExecutor`
- [x] SDK baked into Docker image (`pip install -r requirements.txt` in Dockerfile)
- [x] Dead `claude-code` branches removed from `cli_executor.py`
- [x] 100% test coverage (110 + 179 + 154 = 443 stmts, 0 misses)
- [x] Live cluster verified (12 workspaces, echo/session/tools/delegation/concurrent)
- [x] 5 iterative code review passes — all issues resolved

**Follow-ups** (see plan file at `.claude/plans/reflective-zooming-lark.md`):
- Live tool-call visibility on canvas (Phase 5A in plan)
- Cost/usage telemetry from ResultMessage (Phase 5B)
- Cancel UX — canvas Stop button (Phase 5C)
- Hooks for governance/audit (Phase 5D)

---

## Phase 12: Code Sandbox — PARTIAL

> MVP done (subprocess + Docker backends). Production backends not started.

- [x] `run_code` tool — `tools/sandbox.py`
- [x] Docker-in-Docker backend (MVP) — throwaway container with resource limits
- [ ] Firecracker backend (production) — MicroVM isolation, faster cold starts
- [ ] E2B backend (cloud) — cloud-hosted via E2B API
- [x] Sandbox config — `SandboxConfig` dataclass in config.py

---

## Phase 20: Canvas UX Sprint — IN PROGRESS

> UX specs created by UIUX Designer agent. See `docs/ux-specs/` for full specs.

### 20.1 Settings Panel (Global Secrets UI)
**Spec**: `docs/ux-specs/ux-spec-settings-panel.md`
**Owner**: Frontend Engineer
**Status**: Spec complete, implementation pending

- [ ] Gear icon in canvas top bar (Cmd+, shortcut)
- [ ] Slide-over drawer (480px, right-anchored)
- [ ] Service groups (GitHub, Anthropic, OpenRouter, Custom)
- [ ] CRUD: add, view (masked), edit, delete secrets
- [ ] Empty state with guided setup
- [ ] Format validation + test connection button
- [ ] Unsaved changes guard on close

### 20.2 Onboarding / Deploy Interception
**Spec**: `docs/ux-specs/ux-spec-onboarding-interception.md`
**Owner**: Frontend Engineer
**Status**: Spec complete, implementation pending

- [ ] Pre-deploy secret check — detect missing API keys per runtime
- [ ] Missing Keys Modal — inline form, only asks for what's needed
- [ ] Provisioning timeout (30s) → named error state with recovery actions
- [ ] No dead ends — every error has a fix action

### 20.3 Canvas UI Improvements
**Spec**: `docs/ux-specs/ux-spec-canvas-improvements.md`
**Owner**: Frontend Engineer
**Status**: Spec complete, implementation pending

- [ ] Plugins install/uninstall in Skills tab (DONE — PR #39)
- [ ] Org template import from canvas
- [ ] Pause/resume from context menu
- [ ] Workspace search (Cmd+K)
- [ ] Batch operations

---

## PR Workflow Rules

All PRs must follow this checklist:

1. **Branch**: Never push to main. Always create a feature/fix branch.
2. **Code Review**: Run `/code-review` skill and fix all issues before requesting merge.
3. **Tests**: All existing tests must pass. New features require new tests.
4. **Documentation**: Run `/update-docs` skill. Every PR must update:
   - `docs/edit-history/` session log
   - Relevant docs in `docs/` (API, architecture, frontend, etc.)
   - `CLAUDE.md` if routes, env vars, or commands changed
   - `PLAN.md` if the work completes a phase or adds new items
5. **E2E Test**: Rebuild, restart service, and manually verify before reporting done.
6. **QA Review**: QA Engineer reviews for edge cases, plan compliance, and documentation completeness before CEO merge approval.
7. **CEO Approval**: Only the CEO approves merges. Never merge without explicit approval.

---

## Backlog (prioritized)

1. **Settings Panel implementation** — Phase 20.1 (spec ready)
2. **Onboarding interception** — Phase 20.2 (spec ready)
3. **Canvas UI improvements** — Phase 20.3 (spec ready)
4. **Test coverage gaps** — many handlers still lack unit tests
5. **NemoClaw adapter** — PR #5 open (NVIDIA runtime support)
6. **Remote plugin registry** — future: install plugins from npm/git (currently local only)
7. **Agent git worktrees** — per-agent branches without full clone

---

## Team Assignments

| Agent | Current Focus |
|-------|--------------|
| PM | Sprint coordination, backlog prioritization |
| Dev Lead | Engineering planning, PR review |
| UIUX Designer | UX specs for Phase 20 (DONE — 5 specs delivered) |
| Frontend Engineer | Phase 20.1 Settings Panel implementation |
| Backend Engineer | API completeness verification |
| QA Engineer | **Review every PR for docs + plan compliance** |
| DevOps Engineer | CI/CD, Docker image optimization |
| Security Auditor | API key handling, path traversal, auth review |

---

## Next Steps

- Frontend Engineer implements Settings Panel (Phase 20.1) based on UX spec
- QA Engineer reviews PR for docs compliance before merge
- PM tracks sprint progress and reports to CEO
- All agents use `GITHUB_TOKEN` env var to clone repo, branch, and create PRs
