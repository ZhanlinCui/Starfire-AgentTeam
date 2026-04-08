---
id: kc_mnpj1c31_27069973
category: pitfall
confidence: 0.93
tags: [python, pytest, asyncio, compatibility]
created_at: 2026-04-08T04:07:13.261Z
---

# workspace-template sandbox tests are brittle on Python 3.13

The full Python test suite includes sandbox tests that still use `asyncio.get_event_loop()`, which fails on Python 3.13 with no current event loop in the main thread. This is separate from awareness integration but blocks full-suite green status.
