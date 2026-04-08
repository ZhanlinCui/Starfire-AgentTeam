---
id: kc_mnpizz3e_cdcaeefc
category: problem_solution
confidence: 0.99
tags: [go, tests, platform, awareness]
created_at: 2026-04-08T04:06:09.770Z
---

# Missing models import in handlers tests

The new awareness provisioning test in `platform/internal/handlers/handlers_test.go` needed `github.com/agent-molecule/platform/internal/models`; without it the platform tests failed to compile under Go 1.25.
