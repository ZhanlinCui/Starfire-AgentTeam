# Bootstrap

When starting a new session or receiving your first task:

1. **Orient** — Use `list_files` and `read_file` to understand the project structure
2. **Detect stack** — Identify the language, framework, package manager, and test runner
3. **Read config** — Check for tsconfig.json, package.json, go.mod, pyproject.toml, Makefile
4. **Check state** — Run `git status` to see if there are uncommitted changes
5. **Assess health** — Run the test suite or build command to establish a baseline

Do NOT start making changes until you understand the project context. If you can't determine the stack, ask.

## First Response Pattern
After orienting, summarize what you found:
- Project: [name/type]
- Stack: [language + framework]
- Status: [clean/dirty, tests passing/failing]
- Ready for: [what you can help with]
