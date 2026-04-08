---
id: kc_mnpihris_d1aae031
category: decision
confidence: 0.92
tags: [awareness, environment, provisioner]
created_at: 2026-04-08T03:52:00.148Z
---

# Inject awareness only when both URL and namespace are present

The provisioner now adds AWARENESS_URL and AWARENESS_NAMESPACE only as a pair so partially configured workspaces do not receive misleading empty awareness settings.
