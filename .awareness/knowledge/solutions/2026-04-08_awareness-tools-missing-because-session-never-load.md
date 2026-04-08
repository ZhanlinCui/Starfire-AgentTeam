---
id: kc_mnpf80aq_4eca7775
category: problem_solution
confidence: 0.97
tags: [awareness, mcp, debugging, codex]
created_at: 2026-04-08T02:20:26.114Z
---

# Awareness tools missing because session never loaded project MCP

The awareness daemon was healthy and the repo had a local `.mcp.json`, but the Codex session did not expose awareness tools until the server was added to the Codex global MCP registry. After adding the server, `codex mcp list` showed it enabled and `awareness_init` succeeded.
