---
id: kc_mnmma536_aa7b793a
category: decision
confidence: 0.95
tags: [platform, database, architecture]
created_at: 2026-04-06T03:14:44.419Z
---

# Activity logs use separate table from structure_events

activity_logs table is separate from structure_events. structure_events tracks lifecycle/structural changes (WORKSPACE_ONLINE, AGENT_ASSIGNED etc). activity_logs tracks operational activity (A2A communications, task updates, agent logs, errors). Activity events use BroadcastOnly (WebSocket-only, no DB insert to structure_events) to avoid polluting the structural event log.
