---
id: kc_mnph6oxv_c76026a3
category: insight
confidence: 0.95
tags: [awareness, multi-tenancy, ops, tradeoff]
created_at: 2026-04-08T03:15:23.971Z
---

# Separate instance vs shared namespace is an isolation-cost tradeoff

A per-workspace awareness instance gives the cleanest fault and data boundary, but the operational overhead scales linearly with workspace count. A shared backend with namespacing is much cheaper and usually sufficient unless the product requires strong tenant isolation.
