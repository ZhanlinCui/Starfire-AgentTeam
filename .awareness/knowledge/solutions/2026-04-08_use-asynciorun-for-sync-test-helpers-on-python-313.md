---
id: kc_mnpjztaw_3ea32b50
category: problem_solution
confidence: 0.99
tags: [python, asyncio, pytest, compatibility]
created_at: 2026-04-08T04:34:01.880Z
---

# Use asyncio.run for sync test helpers on Python 3.13

Synchronous test wrappers that previously relied on `asyncio.get_event_loop().run_until_complete(...)` should switch to `asyncio.run(...)` to remain compatible with Python 3.13's stricter event loop behavior.
