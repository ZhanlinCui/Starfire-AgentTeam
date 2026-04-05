---
id: kc_mnlmi4j9_3336d8fc
category: decision
confidence: 0.95
tags: [ci, go, github-actions]
created_at: 2026-04-05T10:33:10.773Z
---

# CI uses Go 'stable' not version from go.mod

go.mod says 1.25.0 but GitHub Actions doesn't have Go 1.25 yet. CI uses 'stable' which grabs latest available Go. This may need updating when Go 1.25 ships.
