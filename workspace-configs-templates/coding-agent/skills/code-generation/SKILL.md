---
name: code-generation
description: Generate code from specifications — new files, functions, components, APIs, tests, and more.
version: 1.0.0
tags:
  - code
  - generation
  - development
examples:
  - "Create a REST API endpoint for user authentication"
  - "Write a React component for a data table with sorting"
  - "Generate unit tests for the payment service"
  - "Add a new database migration for the orders table"
---

# Code Generation

When asked to generate code:

## Process
1. **Understand the context** — read existing code in the project to match style, patterns, and conventions
2. **Plan the structure** — decide what files to create or modify before writing
3. **Generate code** — write clean, idiomatic code following the project's conventions
4. **Verify** — use `run_shell` to run linters, type checks, or tests if available

## Output Standards
- Follow the existing code style (indentation, naming, imports)
- Include proper error handling
- Add types/interfaces for TypeScript/Go/Python typed codebases
- No placeholder comments like "// TODO: implement this" — write the actual implementation
- Keep functions focused and under 50 lines when possible

## File Operations
Use the `read_file` and `write_file` tools to interact with the filesystem.
Use `search_code` to find existing patterns before generating new code.
Use `run_shell` to verify generated code compiles/passes lint.
