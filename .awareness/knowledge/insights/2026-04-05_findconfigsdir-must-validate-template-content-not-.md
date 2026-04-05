---
id: kc_mnlhwg7u_1609c434
category: pitfall
confidence: 0.95
tags: [platform, config, provisioner]
created_at: 2026-04-05T08:24:21.018Z
---

# findConfigsDir must validate template content, not just dir existence

os.Stat on an empty dir returns true. A stale platform/workspace-configs-templates/ with empty subdirs shadowed the real templates at ../workspace-configs-templates/. Fix: check for at least one config.yaml inside subdirs.
