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
| 19 | MCP Full Coverage | PR #40 — 52→54 tools (plugins, global secrets, pause/resume, org, delegation) |
| 20 | Canvas UX Sprint | PRs #4, #21, #39 — Settings Panel, Onboarding, Plugins UI, Pause/Resume |
| 21 | Claude Agent SDK Migration | PR #48 — `ClaudeSDKExecutor` replaces CLI subprocess |
| 22 | Cron Scheduling | PR #49 — recurring tasks via cron expressions, Canvas Schedule tab |
| 23 | Code Quality & Multi-Provider | PR #50 — model fallback, DeepAgents full SDK, 7 LLM providers, 100% test coverage |
| 24 | Async Delegation | PR #41 — non-blocking delegation with status polling, `check_delegation_status` tool |

---

## Phase 12: Code Sandbox — PARTIAL

> MVP done (subprocess + Docker backends). Production backends not started.

- [x] `run_code` tool — `tools/sandbox.py`
- [x] Docker-in-Docker backend (MVP) — throwaway container with resource limits
- [ ] Firecracker backend (production) — MicroVM isolation, faster cold starts
- [ ] E2B backend (cloud) — cloud-hosted via E2B API
- [x] Sandbox config — `SandboxConfig` dataclass in config.py

---

## Phase 20: Canvas UX Sprint — MOSTLY COMPLETE

> UX specs created by UIUX Designer agent. See `docs/ux-specs/` for full specs.

### 20.1 Settings Panel (Global Secrets UI) — DONE
**Spec**: `docs/ux-specs/ux-spec-settings-panel.md`

- [x] Gear icon in canvas top bar (Cmd+, shortcut)
- [x] Slide-over drawer (480px, right-anchored)
- [x] Service groups (GitHub, Anthropic, OpenRouter, Custom)
- [x] CRUD: add, view (masked), edit, delete secrets
- [x] Empty state with guided setup
- [x] Unsaved changes guard on close

### 20.2 Onboarding / Deploy Interception — DONE
**Spec**: `docs/ux-specs/ux-spec-onboarding-interception.md`

- [x] Pre-deploy secret check — detect missing API keys per runtime
- [x] Missing Keys Modal — inline form, only asks for what's needed
- [x] Provisioning timeout → named error state with recovery actions
- [x] No dead ends — every error has a fix action

### 20.3 Canvas UI Improvements — PARTIAL
**Spec**: `docs/ux-specs/ux-spec-canvas-improvements.md`

- [x] Plugins install/uninstall in Skills tab (PR #39)
- [x] Pause/resume from context menu
- [ ] Org template import from canvas
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

1. **Canvas: Org template import** — Phase 20.3 (deploy org from canvas UI)
2. **Canvas: Workspace search (Cmd+K)** — Phase 20.3 (quick find)
3. **Canvas: Batch operations** — Phase 20.3 (multi-select delete/restart)
4. **Sandbox: Firecracker/E2B backends** — Phase 12 (production isolation)
5. **NemoClaw adapter** — stub exists at `adapters/nemoclaw/`, no implementation yet
6. **Remote plugin registry** — install plugins from npm/git (currently local only)
7. **Agent git worktrees** — per-agent branches without full clone
8. **SDK follow-ups** — live tool-call visibility, cost telemetry, cancel UX, governance hooks

---

## Test Coverage

| Stack | Tests | Framework |
|-------|-------|-----------|
| Go (platform) | 406 | `go test -race` |
| Python (workspace) | 973 | pytest |
| Canvas (frontend) | 345 | Vitest |
| **Total** | **1,724** | |

E2E: 68/68 comprehensive checks passing, 62 API tests.

---

## Team Assignments

| Agent | Current Focus |
|-------|--------------|
| PM | Sprint coordination, backlog prioritization |
| Dev Lead | Engineering planning, PR review |
| UIUX Designer | UX specs for Phase 20 (DONE — 5 specs delivered) |
| Frontend Engineer | Phase 20.3 remaining items (org import, search, batch) |
| Backend Engineer | Sandbox production backends, API completeness |
| QA Engineer | **Review every PR for docs + plan compliance** |
| DevOps Engineer | CI/CD, Docker image optimization |
| Security Auditor | API key handling, path traversal, auth review |

---

## Next Steps

1. Frontend Engineer implements remaining Phase 20.3 items (org import from canvas, Cmd+K search)
2. Backend Engineer scopes Firecracker/E2B sandbox backends (Phase 12)
3. QA Engineer reviews PR #52 for docs compliance before merge
4. All agents use `GITHUB_TOKEN` env var to clone repo, branch, and create PRs
