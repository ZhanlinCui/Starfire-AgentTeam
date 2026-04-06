---
id: mem_20260405_203115_8242
type: turn_summary
session_id: ses_1775442815659_ue73kv
agent_role: builder_agent
tags: []
created_at: "2026-04-06T03:31:15.179Z"
updated_at: "2026-04-06T03:31:15.179Z"
source: "claude-code"
status: active
related: []
---

## Tests added for activity logging, A2A tracking, and current task visibility

### Go unit tests (platform/internal/handlers/handlers_test.go) — 25 total (was 14)
New tests:
- TestHeartbeatHandler_TaskChanged — prevTask SELECT returns old task, verifies broadcast fires
- TestHeartbeatHandler_TaskUnchanged — same task, no broadcast
- TestHeartbeatHandler_TaskCleared — task goes from "old" to "", broadcast fires
- TestActivityHandler_List — 2 rows with full column scan
- TestActivityHandler_ListByType — filter by error type
- TestActivityHandler_ListEmpty — empty result set
- TestActivityHandler_ListCustomLimit — limit=10
- TestActivityHandler_ListMaxLimit — 9999 capped to 500
- TestActivityHandler_Report — POST agent_log
- TestActivityHandler_Report_InvalidType — 400 on bad type
- TestActivityHandler_ReportAllValidTypes — subtests for all 5 types
- TestActivityHandler_ReportMissingBody — 400 on empty body
- TestWorkspaceGet_CurrentTask — verifies current_task in GET response
- TestProxyA2A_JSONRPCWrapping — updated to expect async INSERT INTO activity_logs

### Canvas Vitest (canvas/src/store/__tests__/canvas.test.ts) — 58 total (was 52)
New tests:
- TASK_UPDATED sets currentTask and activeTasks
- TASK_UPDATED clears currentTask when empty
- TASK_UPDATED is no-op for unknown workspace
- hydrate maps current_task into currentTask
- hydrate defaults currentTask to empty string
- ACTIVITY_LOGGED event does not crash store (no-op)
- TASK_UPDATED handles missing current_task in payload
- TASK_UPDATED handles missing active_tasks in payload
- TASK_UPDATED preserves other node data
- TASK_UPDATED does not affect other nodes
- setPanelTab to "activity"

### Integration tests (test_api.sh) — ~62 checks (was ~43)
Added 19 new checks:
- POST /workspaces/:id/activity — report agent_log, a2a_send, error, task_update
- Invalid activity_type → 400
- GET /workspaces/:id/activity — list all (count=4)
- GET activity?type=error — filter + verify error_detail
- GET activity?type=a2a_send — filter + verify target_id
- GET activity?limit=2 — limit cap
- GET activity for workspace with no logs → []
- Heartbeat with current_task → visible in GET workspace
- Clear current_task via heartbeat → verify empty
- current_task present in list response

### E2E tests (test_activity_e2e.sh) — 25 tests (NEW)
Requires platform + 1 online agent:
- A2A message → activity_log created with method, duration_ms, request/response bodies
- Agent self-report: task_update, error, agent_log with metadata
- Activity filtering by type (error, task_update, agent_log)
- Current task: set via heartbeat, visible in detail + list, update, clear
- Cross-workspace isolation: activity doesn't leak between workspaces
- Edge cases: missing workspace returns [], missing activity_type → 400

### Files changed
- platform/internal/handlers/handlers_test.go (11 new test functions)
- canvas/src/store/__tests__/canvas.test.ts (6 new test blocks)
- test_api.sh (19 new checks)
- test_activity_e2e.sh (new file, 25 tests)
- CLAUDE.md (updated test counts)
