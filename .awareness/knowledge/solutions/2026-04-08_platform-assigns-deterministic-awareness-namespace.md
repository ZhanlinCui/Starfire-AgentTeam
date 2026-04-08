---
id: kc_mnpica4u_c41384c3
category: problem_solution
confidence: 0.96
tags: [awareness, workspace, platform, provisioning]
created_at: 2026-04-08T03:47:44.334Z
---

# Platform assigns deterministic awareness namespaces at workspace creation

The platform-side implementation now stores `workspace:<workspace_id>` in `workspaces.awareness_namespace` and passes it into provisioning so each workspace can connect to an isolated awareness namespace without a separate awareness instance.
