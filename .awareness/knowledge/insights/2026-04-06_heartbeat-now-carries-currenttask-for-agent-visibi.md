---
id: kc_mnmma537_c3070f96
category: key_point
confidence: 0.95
tags: [platform, canvas, agent-visibility]
created_at: 2026-04-06T03:14:44.419Z
---

# Heartbeat now carries current_task for agent visibility

HeartbeatPayload extended with CurrentTask string field. Platform saves it to workspaces.current_task column and broadcasts TASK_UPDATED WebSocket event. Canvas displays it as amber banner in WorkspaceNode cards and SidePanel header.
