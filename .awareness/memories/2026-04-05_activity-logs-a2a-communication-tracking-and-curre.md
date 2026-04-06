---
id: mem_20260405_201444_dcae
type: turn_summary
session_id: ses_1775442815659_ue73kv
agent_role: builder_agent
tags: []
created_at: "2026-04-06T03:14:44.195Z"
updated_at: "2026-04-06T03:14:44.195Z"
source: "claude-code"
status: active
related: []
---

## What was done

Added comprehensive activity logging, inter-agent communication visibility, and current task tracking across the full stack.

### Backend (Platform - Go)

1. **Migration 009** (`platform/migrations/009_activity_logs.sql`):
   - New `activity_logs` table: id, workspace_id, activity_type, source_id, target_id, method, summary, request_body JSONB, response_body JSONB, duration_ms, status, error_detail, created_at
   - activity_type values: 'a2a_send', 'a2a_receive', 'task_update', 'agent_log', 'error'
   - Added `current_task TEXT` column to workspaces table

2. **Activity handler** (`platform/internal/handlers/activity.go`):
   - `GET /workspaces/:id/activity?type=&limit=` — list activity logs with optional type filter
   - `POST /workspaces/:id/activity` — agents self-report activity logs
   - `LogActivity()` helper function used by ProxyA2A and available to other handlers

3. **A2A proxy logging** (`platform/internal/handlers/workspace.go`):
   - ProxyA2A now logs every A2A request/response to activity_logs with method, duration, status
   - Failed A2A attempts are also logged with error details

4. **Heartbeat current_task** (`platform/internal/handlers/registry.go`):
   - HeartbeatPayload now includes `current_task` field
   - Saved to workspaces table on each heartbeat
   - Broadcasts `TASK_UPDATED` WebSocket event when current_task is non-empty

5. **BroadcastOnly** (`platform/internal/events/broadcaster.go`):
   - New method for WebSocket-only events (no structure_events insert)
   - Used for high-frequency events like ACTIVITY_LOGGED and TASK_UPDATED

6. **Workspace queries** updated to include current_task in List/Get responses

### Frontend (Canvas - Next.js)

1. **Store updates** (`canvas/src/store/canvas.ts`, `canvas/src/store/socket.ts`):
   - Added `currentTask: string` to WorkspaceNodeData and WorkspaceData
   - Added `"activity"` to PanelTab union type
   - New `TASK_UPDATED` event handler in applyEvent()

2. **ActivityTab** (`canvas/src/components/tabs/ActivityTab.tsx`):
   - Comprehensive activity log viewer with type filters (All, A2A In, A2A Out, Tasks, Logs, Errors)
   - Color-coded activity types, status icons (ok/error/timeout)
   - A2A flow indicator showing source → target workspace IDs
   - Expandable details with request/response JSON
   - Auto-refresh (5s) with live/paused toggle
   - Duration display in milliseconds

3. **SidePanel** (`canvas/src/components/SidePanel.tsx`):
   - Added Activity tab (positioned after Details, before Chat)
   - Current task banner appears below tabs when agent has an active task (amber pulsing dot)

4. **WorkspaceNode** (`canvas/src/components/WorkspaceNode.tsx`):
   - Current task displayed as amber banner inside workspace card

### MCP Server
- Added `list_activity` tool with type/limit filters

### Tests
- Updated Go test mocks (heartbeat: added 6th arg for current_task, workspace list: added current_task column)
- All 9 Go tests pass, all 47 canvas Vitest tests pass

### Files changed
- platform/migrations/009_activity_logs.sql (new)
- platform/internal/models/activity.go (new)
- platform/internal/models/workspace.go
- platform/internal/handlers/activity.go (new)
- platform/internal/handlers/workspace.go
- platform/internal/handlers/registry.go
- platform/internal/handlers/events.go (unchanged)
- platform/internal/handlers/handlers_test.go
- platform/internal/events/broadcaster.go
- platform/internal/router/router.go
- canvas/src/store/canvas.ts
- canvas/src/store/socket.ts
- canvas/src/components/SidePanel.tsx
- canvas/src/components/WorkspaceNode.tsx
- canvas/src/components/tabs/ActivityTab.tsx (new)
- mcp-server/src/index.ts
- CLAUDE.md
