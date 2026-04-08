---
id: kc_mnph6oxv_69f2fac9
category: decision
confidence: 0.94
tags: [awareness, workspace, architecture, isolation]
created_at: 2026-04-08T03:15:23.971Z
---

# Awareness should be workspace-scoped by default

For this repo, awareness fits best as a workspace-scoped capability inside the workspace runtime, with isolation handled by workspace_id or namespace rather than by duplicating the entire awareness stack per workspace.
