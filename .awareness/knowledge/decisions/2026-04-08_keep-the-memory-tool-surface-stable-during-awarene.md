---
id: kc_mnpi8am4_4a171369
category: decision
confidence: 0.94
tags: [memory, migration, stability, awareness]
created_at: 2026-04-08T03:44:38.332Z
---

# Keep the memory tool surface stable during awareness migration

The implementation plan intentionally preserves `commit_memory` and `search_memory` so the agent-facing contract does not churn while the backend is swapped to awareness.
