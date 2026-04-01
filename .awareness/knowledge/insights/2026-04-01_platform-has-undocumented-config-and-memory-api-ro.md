---
id: kc_mnfppg0e_b9fb0d4b
category: key_point
confidence: 0.95
tags: [platform, api, routes, claude-md]
created_at: 2026-04-01T07:16:14.030Z
---

# Platform has undocumented config and memory API routes

The Go platform router has GET/PATCH /workspaces/:id/config, GET/POST /workspaces/:id/memory, and DELETE /workspaces/:id/memory/:key endpoints that were missing from CLAUDE.md's API routes table. These were added by migration 006_workspace_config_memory.sql. POST /workspaces/:id/a2a is needed by ChatTab but does NOT exist yet.
