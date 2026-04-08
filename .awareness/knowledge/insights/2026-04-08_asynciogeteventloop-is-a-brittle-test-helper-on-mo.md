---
id: kc_mnpjztaw_ffa00ca2
category: pitfall
confidence: 0.98
tags: [python-3.13, asyncio, testing]
created_at: 2026-04-08T04:34:01.880Z
---

# asyncio.get_event_loop is a brittle test helper on modern Python

`asyncio.get_event_loop()` in synchronous tests can fail on Python 3.13 because no loop exists by default in the main thread; the failure surfaces as a runtime error unrelated to the feature under test.
