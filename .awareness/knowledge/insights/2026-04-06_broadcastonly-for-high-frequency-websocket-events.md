---
id: kc_mnmma537_86fa0832
category: insight
confidence: 0.95
tags: [platform, websocket, events]
created_at: 2026-04-06T03:14:44.419Z
---

# BroadcastOnly for high-frequency WebSocket events

Added Broadcaster.BroadcastOnly() method that sends WebSocket events without inserting into structure_events table. Used for ACTIVITY_LOGGED and TASK_UPDATED events which are high-frequency and have their own storage (activity_logs table and workspaces.current_task column respectively).
