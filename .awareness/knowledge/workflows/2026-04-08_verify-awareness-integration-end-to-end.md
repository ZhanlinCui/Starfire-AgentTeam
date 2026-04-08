---
id: kc_mnpf80aq_34dcfed2
category: workflow
confidence: 0.95
tags: [workflow, verification, awareness]
created_at: 2026-04-08T02:20:26.114Z
---

# Verify awareness integration end to end

Use a three-step validation loop: check `codex mcp list`, probe the local daemon health and MCP endpoint, then call `awareness_init` and confirm `awareness_record`/`awareness_recall` are available. This distinguishes configuration issues from daemon/runtime issues.
