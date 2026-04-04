---
name: shell-exec
description: Execute shell commands in the workspace container — build, test, git, package managers, and more.
version: 1.0.0
tags:
  - shell
  - terminal
  - devops
examples:
  - "Run the test suite"
  - "Install the dependencies"
  - "Check git status"
  - "Build the project"
---

# Shell Execution

Execute shell commands inside the workspace container.

## Safety Rules
- Never run destructive commands without confirming first (rm -rf, DROP TABLE, etc.)
- Never expose secrets in command arguments — use environment variables
- Set reasonable timeouts for long-running commands
- Prefer non-interactive commands (avoid editors, pagers)

## Common Workflows
- **Build**: `run_shell("npm run build")` or `run_shell("go build ./...")`
- **Test**: `run_shell("npm test")` or `run_shell("pytest")`
- **Git**: `run_shell("git status")`, `run_shell("git diff")`
- **Install**: `run_shell("npm install")` or `run_shell("pip install -r requirements.txt")`
- **Lint**: `run_shell("npx eslint .")` or `run_shell("golangci-lint run")`
