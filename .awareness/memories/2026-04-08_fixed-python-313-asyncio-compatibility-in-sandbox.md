---
id: mem_20260408_123401_305b
type: problem_solution
session_id: ses_1775615416973_v5lgkr
agent_role: builder_agent
tags: []
created_at: "2026-04-08T04:34:01.878Z"
updated_at: "2026-04-08T04:34:01.878Z"
source: codex
status: active
related: []
---

Investigated the Python 3.13 compatibility failures in `workspace-template/tests/test_sandbox.py`. The root cause was the helper `_run_sync`, which used `asyncio.get_event_loop().run_until_complete(coro)`. On Python 3.13, `asyncio.get_event_loop()` no longer auto-creates an event loop for the main thread, so the helper raised `RuntimeError: There is no current event loop in thread 'MainThread'` during test collection/execution. The minimal root-cause fix was to replace that helper with `asyncio.run(coro)`, which creates and manages a fresh event loop per call and is safe for the synchronous test cases in this file. No changes were made to the sandbox implementation itself because the failure was isolated to the test helper, not the production async code.
