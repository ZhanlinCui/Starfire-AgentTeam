---
id: kc_mngo5i2b_bb0c8764
category: problem_solution
confidence: 1
tags: [python, a2a, dependencies]
created_at: 2026-04-01T23:20:30.132Z
---

# a2a-sdk is the correct PyPI package for Google A2A protocol

requirements.txt had a2a-python>=0.2.0 which only has version 0.0.1 (stub package). The correct package is a2a-sdk>=0.3.0 which provides a2a.server.apps, a2a.types, etc. The bare 'a2a' package is an unrelated Scrapy wrapper.
