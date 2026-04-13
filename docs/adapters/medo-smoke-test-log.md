# MeDo Smoke Test Log — 2026-04-13

**Tester:** PM (direct execution, no sub-delegation)  
**Goal:** End-to-end: install Miaoda App Builder skill → build "Hello Starfire" landing page → publish → capture URL.  
**Budget allocated:** ≤50 credits (3-4 queries).  
**Credits spent:** 0 (workspace did not reach skill invocation — see §2).

---

## 1. Environment Verified

| Check | Result |
|-------|--------|
| Platform API (`http://platform:8080/health`) | ✅ `{"status":"ok"}` |
| MIAODA_API_KEY set as global secret | ✅ confirmed in secret store |
| Existing workspaces | 12 online (all `claude-code` runtime) |
| `workspace-template:openclaw` Docker image | ❌ **NOT BUILT** — root cause below |

---

## 2. Workspace Provisioning — BLOCKED

**Attempt:** `POST http://platform:8080/org/import` with inline template:

```json
{
  "name": "MeDo Smoke Test",
  "defaults": { "runtime": "openclaw" },
  "workspaces": [{ "name": "MeDo Builder", "role": "..." }]
}
```

**API response:** `{"count": 1, "org": "MeDo Smoke Test", "workspaces": [{"id": "404c4e1a-..."}]}`  
→ Record created successfully.

**Startup result:** `status: failed`, `uptime_seconds: 0`, `last_sample_error: ""`  
→ Workspace failed immediately on boot with no heartbeat.

**Root cause (inferred):** The provisioner (see `platform/internal/provisioner/provisioner.go`) maps
`runtime: openclaw` → Docker image `workspace-template:openclaw`. That image does not exist in the
local Docker daemon — it must be built first via:

```bash
bash workspace-template/build-all.sh openclaw
# or full rebuild:
bash workspace-template/build-all.sh
```

The Dockerfile exists at `workspace-template/adapters/openclaw/Dockerfile` and extends
`workspace-template:base`. Building takes ~5 min on first run (npm install -g openclaw).

**Action taken:** Deleted the failed workspace record (`DELETE /workspaces/404c4e1a-...` → `{"status":"removed"}`).

---

## 3. Skill Interaction — NOT REACHED

Because the workspace never came online, no A2A messages were sent. The following steps
from the original plan were not executed:

- ❌ Skill install prompt (`"Install the Miaoda App Builder skill..."`)
- ❌ Build request (`"Build me a simple landing page..."`)
- ❌ Publish request
- ❌ URL capture

---

## 4. Answers to Open Questions

### 5-C — Rate limits
**Status: UNKNOWN — not observed.**  
Workspace did not reach skill invocation. Rate limits cannot be inferred.  
*Recommendation:* Once the openclaw image is built, send two concurrent build requests and
observe whether one returns a 429 or queues. The Miaoda API docs mention no explicit rate
limit; test empirically.

### 5-D — Failure recovery
**Status: UNKNOWN — not observed.**  
Workspace container never started, so mid-generation crash recovery was not testable.  
*Recommendation:* During Week 2 testing, intentionally kill the container after
"Confirm & Generate" step (before Publish) and attempt `"Show me my apps"` to see if the
partial build is recoverable by app ID.

---

## 5. New Findings (not in PR #115 design doc)

| Finding | Impact | Action |
|---------|--------|--------|
| `workspace-template:openclaw` image must be pre-built | **Blocker** — no openclaw workspace can start without it | Operator: run `bash workspace-template/build-all.sh openclaw` before Week 2 |
| Platform inline-template org import works correctly | Positive — no file on platform FS needed; can provision via API from PM directly | Document in design doc §2.3 |
| Failed workspace leaves a `status: failed` record; DELETE endpoint exists at `/workspaces/:id` | Operational | Add cleanup step to smoke test runbook |
| `last_sample_error` is empty even on failure | Debugging gap | Provisioner should surface Docker image-not-found error; file platform issue (§6) |

---

## 6. Issues to File

### Issue: Provisioner swallows Docker image-not-found error

**Observed:** When `workspace-template:openclaw` image is missing, workspace transitions to
`status: failed` with `last_sample_error: ""` — no error message propagates. This makes
triage opaque (could be image missing, network issue, or misconfigured env).

**Expected:** `last_sample_error` should contain the Docker error (e.g.
`"Error response from daemon: No such image: workspace-template:openclaw"`).

**File as:** `fix(provisioner): surface Docker image-not-found error in last_sample_error`  
**Location:** `platform/internal/provisioner/provisioner.go` — in the container-start error path.

---

## 7. Next Steps (Week 2 prerequisite checklist)

- [ ] **Operator:** `bash workspace-template/build-all.sh openclaw` on host machine
- [ ] **Operator:** Verify: `docker images | grep workspace-template:openclaw`
- [ ] **PM:** Re-run smoke test — send install query, build "Hello Starfire", publish, capture URL
- [ ] **PM:** Test 5-C (concurrent builds) and 5-D (mid-gen crash recovery) during that run
- [ ] **Dev Lead:** Fix provisioner to surface Docker error in `last_sample_error` (§6)
- [ ] **Dev Lead:** Update `docs/adapters/medo-integration.md` §2 with image build prerequisite
