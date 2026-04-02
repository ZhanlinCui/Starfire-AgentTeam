---
name: debug-assist
description: Debug issues by reading logs, stack traces, inspecting state, and tracing execution.
version: 1.0.0
tags:
  - debug
  - troubleshooting
  - logs
examples:
  - "This endpoint is returning 500, help me debug it"
  - "The tests are failing with this error, what's wrong?"
  - "Why is this function returning null?"
---

# Debug Assist

When asked to debug an issue:

## Process
1. **Reproduce** — Understand the error. Read the stack trace, logs, or error message.
2. **Locate** — Use `search_code` and `read_file` to find the relevant code.
3. **Trace** — Follow the execution path from entry point to failure.
4. **Diagnose** — Identify the root cause (not just the symptom).
5. **Fix** — Propose a targeted fix with explanation.
6. **Verify** — Use `run_shell` to run tests or reproduce the scenario.

## Reading Errors
- Stack traces: read bottom-up, the root cause is usually the first "Caused by"
- Build errors: read the first error, ignore cascading failures
- Test failures: read the assertion message and expected vs actual values
- Runtime errors: check for nil/null access, type mismatches, missing env vars

## Tools
- `read_file` to read source code and config files
- `search_code` to find related code, usages, and definitions
- `run_shell` to check logs, run tests, inspect state
