---
name: code-review
description: Review code for bugs, security issues, performance problems, and style violations.
version: 1.0.0
tags:
  - code
  - review
  - quality
examples:
  - "Review this pull request for issues"
  - "Check this function for security vulnerabilities"
  - "Is this code following best practices?"
---

# Code Review

When asked to review code:

## Checklist
1. **Correctness** — Does it do what it's supposed to? Edge cases handled?
2. **Security** — Input validation, injection risks, secret exposure, auth checks
3. **Performance** — N+1 queries, unbounded loops, memory leaks, missing indexes
4. **Readability** — Clear naming, reasonable function sizes, no dead code
5. **Error handling** — Are errors caught? Surfaced to users? Logged?
6. **Type safety** — Any `any` types, missing null checks, unsafe casts?

## Output Format
For each issue found:
- **Severity**: critical / warning / suggestion
- **Location**: file:line
- **Description**: what's wrong
- **Fix**: specific recommendation or code snippet

## Process
1. Use `read_file` to read the code under review
2. Use `search_code` to check for patterns across the codebase
3. Provide structured feedback grouped by severity
4. For critical issues, provide the fixed code inline
