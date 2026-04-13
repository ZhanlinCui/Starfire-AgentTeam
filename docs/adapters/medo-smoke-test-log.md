# MeDo Smoke Test Log — 2026-04-13 (Run 3)

**Tester:** PM (direct execution)  
**Goal:** Install Miaoda App Builder skill → build "Hello Starfire" landing page → publish → capture URL.  
**Budget allocated:** ≤50 credits. **Credits spent:** 0 across all three runs.

---

## Run Summary

| Run | Blocker | Resolution |
|-----|---------|------------|
| 1 | `workspace-template:openclaw` image not built | ✅ Operator rebuilt image |
| 2 | Adapter key lookup ignores `AISTUDIO_API_KEY`/`QIANFAN_API_KEY` | ✅ Code fix committed (d779e16) — needs image rebuild |
| 3 | Executor creates fresh OpenClaw session per A2A message; responses are `payloads: []` | ❌ Architectural fix needed (see §4) |

---

## Run 3 — Detailed Findings

### Environment
| Check | Result |
|-------|--------|
| Platform health | ✅ `{"status":"ok"}` |
| `workspace-template:openclaw` image | ✅ built |
| `AISTUDIO_API_KEY` injected | ✅ confirmed — `provider: custom-generativelanguage-googleapis-com`, `model: gemini-2.0-flash` |
| Workspace boot time | ✅ 26 seconds to `online` |

### A2A Communication Confirmed Working
Three messages sent via `delegate_task`. All returned within 2 seconds with the same structure:
```json
{
  "status": "ok", "summary": "completed",
  "result": {"payloads": [], "meta": {"livenessState": "working",
    "agentMeta": {"provider": "custom-generativelanguage-googleapis-com",
                  "model": "gemini-2.0-flash"}}}
}
```

**AISTUDIO_API_KEY is working.** Gemini 2.0 Flash is the active model. Auth is resolved. ✅

### Install Outcome — Structurally Blocked

The natural-language install prompt reached the agent, but:
- `payloads: []` — agent produced no text response
- `livenessState: 'working'` — session still marked active (background work)
- Each call creates a fresh `sessionKey` (e.g. `agent:main:explicit:ec5e46d9-...`,
  `agent:main:explicit:f91197...`, `agent:main:explicit:a39dfe2...`)
- `miaoda-app-builder` never appeared in `skills.entries` across any session

**Diagnosis:** The OpenClaw executor (`OpenClawA2AExecutor.execute()`) calls
`openclaw agent --json --session-id <task_id> --timeout 120` for **every A2A message**.
Each A2A task has a unique `task_id`, so each call creates a completely new OpenClaw session.

The Miaoda App Builder skill is a **conversational, multi-turn workflow**:
1. Create → 2. Confirm requirements → 3. Generate (5–8 min, async) → 4. Publish

This workflow requires session continuity. With fresh sessions per message, the skill
loses all context between calls — it cannot progress through the workflow.

Additionally, the agent appears to use `sessions_spawn` or `sessions_yield` to hand off
the install to a background session, then immediately returns empty payloads. The background
session's output never surfaces to the A2A caller.

---

## 4. Root Cause — OpenClawA2AExecutor Architecture

**Problem:** `execute()` uses `context.task_id` as the OpenClaw session ID. Every A2A message
gets a fresh session; no conversational state is preserved.

**Required fix:** Use a stable, per-workspace session ID so all A2A messages from PM to
the MeDo Builder workspace flow into the same OpenClaw conversation thread.

**Proposed change** in `workspace-template/adapters/openclaw/adapter.py`:

```python
# Replace this in execute():
proc = await asyncio.create_subprocess_exec(
    "openclaw", "agent",
    "--session-id", context.task_id or "default",   # ← creates new session per message
    ...
)

# With:
_WORKSPACE_SESSION_ID = os.environ.get("WORKSPACE_ID", "starfire-default")

proc = await asyncio.create_subprocess_exec(
    "openclaw", "agent",
    "--session-id", _WORKSPACE_SESSION_ID,           # ← stable session for this workspace
    ...
)
```

This makes each workspace have one persistent OpenClaw conversation thread. A2A messages
chain together as a multi-turn dialogue, preserving Miaoda skill state across calls.

**Also needed:** Investigate why `payloads: []` when agent uses `sessions_yield`. OpenClaw
may need `--wait-for-yield` or a polling mechanism to collect the background session output
before the CLI exits.

---

## 5. Answers to Open Questions

### 5-C — Rate limits: **UNKNOWN** (never reached skill invocation)
### 5-D — Failure recovery: **UNKNOWN** (never reached app generation)

---

## 6. Issues to File

### Issue A (new — Run 3): OpenClawA2AExecutor creates fresh session per message
**Severity:** Blocker for any conversational skill (Miaoda App Builder, multi-turn workflows).  
**Fix:** Use stable per-workspace `--session-id` in `execute()` (see §4).  
**File as:** `fix(openclaw-adapter): use stable workspace session ID for multi-turn skill support`  
**Location:** `workspace-template/adapters/openclaw/adapter.py`, `OpenClawA2AExecutor.execute()`

### Issue B (from Run 2): openclaw adapter ignores AISTUDIO_API_KEY / QIANFAN_API_KEY
**Status:** Code fix committed in d779e16. **Needs openclaw image rebuild.**  
`bash workspace-template/build-all.sh openclaw`

### Issue C (from Run 1): Provisioner swallows Docker image-not-found in `last_sample_error`
**Status:** Open. Fix in `platform/internal/provisioner/provisioner.go`.

---

## 7. Next Steps (before Run 4)

- [ ] **Dev Lead:** Fix `OpenClawA2AExecutor.execute()` — stable session ID per workspace (Issue A)
- [ ] **Dev Lead:** Investigate `sessions_yield` / background session output capture
- [ ] **Operator:** Rebuild openclaw image after Issue A + B fixes:
  `bash workspace-template/build-all.sh openclaw`
- [ ] **PM (Run 4):** Re-run smoke test — expected to reach skill install confirmation and app build
