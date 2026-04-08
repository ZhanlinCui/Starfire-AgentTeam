---
id: kc_mnpk3ffn_9cebbb6e
category: decision
confidence: 0.98
tags: [git, state, awareness, repo-hygiene]
created_at: 2026-04-08T04:36:50.531Z
---

# Leave runtime state directories uncommitted

`.awareness/` and `.agents/` are local runtime/state artifacts and should stay out of source control; only source and docs were committed.
