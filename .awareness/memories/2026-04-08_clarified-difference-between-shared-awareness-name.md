---
id: mem_20260408_111523_c7f4
type: decision
session_id: ses_1775615416973_v5lgkr
agent_role: builder_agent
tags: []
created_at: "2026-04-08T03:15:23.969Z"
updated_at: "2026-04-08T03:15:23.969Z"
source: codex
status: active
related: []
---

Discussed the user's question about whether each new workspace should get its own awareness project. The core distinction is between (1) a shared awareness backend with per-workspace namespace/isolation, and (2) a fully separate awareness instance or project per workspace. The first option keeps one daemon/service and separates data by workspace_id or equivalent namespace. The second option duplicates the whole awareness stack per workspace, giving stronger isolation but much higher operational cost. Framed the decision around four axes: resource cost, failure isolation, data sharing/portability, and operational complexity. Recommended treating awareness as workspace-scoped by default inside the runtime and only promoting to separate instances if the workspace boundary truly needs hard isolation or separate ownership.
