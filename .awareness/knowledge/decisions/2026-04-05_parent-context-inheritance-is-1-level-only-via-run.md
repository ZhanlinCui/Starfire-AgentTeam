---
id: kc_mnln1kj0_bd41f3a3
category: decision
confidence: 0.95
tags: [architecture, context-sharing, team-memory]
created_at: 2026-04-05T10:48:17.964Z
---

# Parent context inheritance is 1-level only via runtime fetch

Children fetch parent's shared_context files via HTTP at startup, not via volume mounts. PARENT_ID env var injected during Expand. Grandchildren only see direct parent. Matches L2 TEAM memory scope from docs/architecture/memory.md.
