# Tool Usage Guidelines

## Available Tools

### File Operations
- `read_file(path)` — Read a file from the workspace
- `write_file(path, content)` — Write/create a file (creates dirs)
- `list_files(path, pattern)` — List files with glob pattern
- `search_code(pattern, path, file_pattern)` — Grep-like search

### Shell Execution
- `run_shell(command, max_seconds)` — Execute shell command (60s default, 300s max)

### Delegation
- `delegate_to_workspace(workspace_id, task)` — Send task to a peer agent

## Tool Rules

1. **Read before write** — Always read a file before modifying it
2. **Search before create** — Check if similar code/files already exist
3. **Verify after change** — Run build/test/lint after modifications
4. **Small changes** — Make focused edits, not full file rewrites
5. **No secrets in files** — Never write API keys, passwords, or tokens to files
6. **Respect .gitignore** — Don't modify or create files in ignored directories

## Shell Safety
- Never run commands that require user input (use -y or --yes flags)
- Always specify paths explicitly (no `rm *` or `cd && rm`)
- Use timeouts for potentially long-running commands
- Prefer `git diff` over `git commit` — let the user decide when to commit
