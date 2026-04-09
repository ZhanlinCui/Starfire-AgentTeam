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

---

## Phase 12: Code Sandbox — PARTIAL

> MVP done (subprocess + Docker backends). Production backends not started.

- [x] `run_code` tool — `tools/sandbox.py`
- [x] Docker-in-Docker backend (MVP) — throwaway container with resource limits
- [ ] Firecracker backend (production) — MicroVM isolation, faster cold starts
- [ ] E2B backend (cloud) — cloud-hosted via E2B API
- [x] Sandbox config — `SandboxConfig` dataclass in config.py

---

## Operational Features — DONE (recent)

- [x] **Container health detection** — 3-layer: passive (Redis TTL 60s), proactive (Docker health sweep 15s), reactive (A2A proxy check)
- [x] **Auto-restart on offline** — liveness monitor + health sweep trigger `RestartByID`
- [x] **Workspace pause/resume** — `POST /pause` / `POST /resume` with cascade to children, parent-paused guard
- [x] **Agent push messaging** — `send_message_to_user` MCP tool → `POST /notify` → WebSocket AGENT_MESSAGE
- [x] **Tier system** — T1 (sandboxed), T2 (standard), T3 (privileged), T4 (full host) via `ApplyTierConfig()`
- [x] **Config persistence** — restart preserves config volume; `apply_template` flag for runtime changes
- [x] **Skills system** — agents create persistent skills in `/configs/skills/` that auto-inject into prompts
- [x] **Build script** — `workspace-template/build-all.sh` builds base + all 6 runtime images
- [x] **Graceful delegation errors** — `[A2A_ERROR]` sentinel, coordinator rules, retry with backoff

---

## Backlog (prioritized by PM)

1. **Test coverage gaps** — 18 of 26 Go handler files have zero unit tests (a2a_proxy, workspace, templates, registry, discovery, secrets, etc.)
2. **Silent ExecContext failures** — 6+ locations where DB writes are fire-and-forget
3. **Python tool JSON decode** — tools call `resp.json()` without catching decode errors
4. **NemoClaw adapter** — PR #5 open (new runtime, NVIDIA support)
5. **Canvas improvements** — search, batch operations, keyboard shortcuts
6. **Documentation gaps** — some docs reference T4/EC2 (removed), inconsistent API docs

---

## Next Steps

- PM agent owns the backlog and assigns sprint work to Dev team
- All work on branches (never push to main)
- Dev team runs code-review + update-docs skills after implementation
- QA reviews for edge cases + plan compliance before merge
