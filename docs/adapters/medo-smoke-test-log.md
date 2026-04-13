# MeDo Smoke Test Log — 2026-04-13 (Run 2)

**Tester:** PM (direct execution, no sub-delegation)  
**Goal:** End-to-end: install Miaoda App Builder skill → build "Hello Starfire" landing page → publish → capture URL.  
**Budget allocated:** ≤50 credits (3-4 queries). **Credits spent:** 0.

---

## 1. Environment

| Check | Result |
|-------|--------|
| Platform API (`http://platform:8080/health`) | ✅ `{"status":"ok"}` |
| MIAODA_API_KEY global secret | ✅ set |
| AISTUDIO_API_KEY global secret | ✅ set |
| QIANFAN_API_KEY global secret | ✅ set |
| `workspace-template:openclaw` Docker image | ✅ **BUILT** (operator resolved between runs) |
| OPENAI_API_KEY / OPENROUTER_API_KEY | ❌ not set — **root cause of Run 2 failure** |

---

## 2. Workspace Provisioning — ✅ SUCCEEDED (Run 2)

**Attempt:** `POST http://platform:8080/org/import` with inline template (same as Run 1).

**API response:** `{"count": 1, "org": "MeDo Smoke Test", "workspaces": [{"id": "e56f56d7-..."}]}`

**Startup:** workspace reached `status: online`, `uptime: 61s`. Agent card URL: `http://ee069684c4e2:8000`. Reachable as A2A peer. Image blocker from Run 1 is resolved. ✅

---

## 3. Skill Install — ❌ AUTH FAILURE (stop per budget rule)

**Message sent via A2A `delegate_task`:**
```
Install the Miaoda App Builder skill from ClawHub: seiriosPlus/miaoda-app-builder
```

**Response received (verbatim):**
```
OpenClaw error: Gateway agent failed; falling back to embedded:
GatewayClientRequestError: FailoverError: No API key found for provider
"custom-api-openai-com". Auth store:
/home/agent/.openclaw/agents/main/agent/auth-profiles.json
(agentDir: /home/agent/.openclaw/agents/main/agent).
Configure auth for this agent.
```

**Root cause — confirmed by reading `workspace-template/adapters/openclaw/adapter.py`:**

The adapter's key lookup (line ~65) is:
```python
api_key = os.environ.get("OPENAI_API_KEY",
            os.environ.get("GROQ_API_KEY",
              os.environ.get("OPENROUTER_API_KEY", "")))
```

Available hackathon secrets (`MIAODA_API_KEY`, `AISTUDIO_API_KEY`, `QIANFAN_API_KEY`) are **not checked**. `api_key` is therefore empty → `auth-profiles.json` is never written → OpenClaw gateway boots with no credential → every request fails with `FailoverError`.

**Action taken:** Deleted workspace (`DELETE /workspaces/e56f56d7-...` → `{"status":"removed"}`).  
**Credits burned:** 0. Stopped per budget rule ("if skill install fails outright, stop and report").

---

## 4. Fix Required — openclaw adapter key lookup

**File:** `workspace-template/adapters/openclaw/adapter.py` (lines ~65 and ~107)

The adapter must check `AISTUDIO_API_KEY` (Google AI Studio, OpenAI-compat) and `QIANFAN_API_KEY` (Baidu Qianfan) in addition to the existing three. The provider URL must be inferred from which key was found.

**Proposed change (lines ~63–75):**

```python
# Priority order: OPENAI → GROQ → OPENROUTER → AISTUDIO → QIANFAN
_KEY_PROVIDERS = [
    ("OPENAI_API_KEY",     "https://api.openai.com/v1"),
    ("GROQ_API_KEY",       "https://api.groq.com/openai/v1"),
    ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
    ("AISTUDIO_API_KEY",   "https://generativelanguage.googleapis.com/v1beta/openai"),
    ("QIANFAN_API_KEY",    "https://qianfan.baidubce.com/v2"),
]
api_key, auto_provider_url = "", ""
for env_var, url in _KEY_PROVIDERS:
    val = os.environ.get(env_var, "")
    if val:
        api_key, auto_provider_url = val, url
        break
provider_url = config.runtime_config.get("provider_url", auto_provider_url)
```

**Also update org-templates/medo-smoke/org.yaml** to specify a model compatible with AISTUDIO_API_KEY:
```yaml
config:
  model: "gemini-2.0-flash"   # works with AISTUDIO_API_KEY via Google AI Studio
```

**After code fix:** rebuild openclaw image with `bash workspace-template/build-all.sh openclaw`.

---

## 5. Skill Interaction — NOT REACHED (both runs)

- ❌ Skill install (auth failure — stop per budget rule)
- ❌ App build (not attempted)
- ❌ Publish / URL (not attempted)

---

## 6. Open Questions Status

### 5-C — Rate limits
**UNKNOWN.** Workspace came online but auth blocked skill invocation.

### 5-D — Failure recovery
**UNKNOWN.** No app generation attempted.

---

## 7. New Findings (additions vs. Run 1 log)

| Finding | Impact | Action |
|---------|--------|--------|
| openclaw image now built ✅ | Run 1 blocker resolved | None |
| Workspace provisions + boots successfully in ~60s | Positive | Document in PR #115 |
| Inline-template org import works without platform FS access | Positive | Design doc update |
| Adapter key lookup misses AISTUDIO_API_KEY / QIANFAN_API_KEY | **Blocker** | Fix adapter + rebuild image (§4) |
| `auth-profiles.json` only written if api_key non-empty | Debugging note | Covered by §4 fix |
| Failed workspace DELETE endpoint `/workspaces/:id` works | Operational | — |

---

## 8. Issues to File

### Issue A: openclaw adapter ignores AISTUDIO_API_KEY and QIANFAN_API_KEY
**Fix location:** `workspace-template/adapters/openclaw/adapter.py` lines ~65, ~107  
**Fix:** Extend key lookup to check all five env vars with correct provider URLs (see §4).  
**Required after fix:** `bash workspace-template/build-all.sh openclaw`

### Issue B: Provisioner swallows container-start errors in `last_sample_error`
*(carried from Run 1)* When openclaw image was missing, workspace transitioned to `status: failed`
with empty `last_sample_error`. Docker daemon error should propagate.  
**Fix location:** `platform/internal/provisioner/provisioner.go` — container-start error path.

---

## 9. Next Steps

- [ ] **Dev Lead:** Fix openclaw adapter key lookup (§4) + rebuild image
- [ ] **Operator:** Set either `OPENROUTER_API_KEY` **or** confirm AISTUDIO_API_KEY fix is in image
- [ ] **PM:** Run smoke test again — expected to reach skill install and app build
- [ ] **Dev Lead:** Fix provisioner `last_sample_error` propagation (Issue B)
- [ ] **PM (post-fix):** Test 5-C (rate limits) and 5-D (failure recovery) during next run
