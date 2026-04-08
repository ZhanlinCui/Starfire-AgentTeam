---
id: mem_20260408_115200_2dfa
type: decision
session_id: ses_1775615416973_v5lgkr
agent_role: builder_agent
tags: []
created_at: "2026-04-08T03:52:00.146Z"
updated_at: "2026-04-08T03:52:00.146Z"
source: codex
status: active
related: []
---

Implemented the first pass of workspace-scoped awareness integration across the platform, runtime, and docs. On the platform side, a new migration `platform/migrations/010_workspace_awareness.sql` adds `awareness_namespace` to the `workspaces` table. The workspace model now carries `AwarenessNamespace`. `POST /workspaces` in `platform/internal/handlers/workspace.go` generates a stable namespace using `workspace:<workspace_id>`, persists it in the row, and returns it in the create response. The handler also added helper functions to derive and reload the namespace for future restart/provisioning paths. The provisioner now accepts `AwarenessURL` and `AwarenessNamespace` and injects `AWARENESS_URL`/`AWARENESS_NAMESPACE` into the container environment only when both values are present. Tests were added to assert namespace creation and provisioning config wiring.

On the runtime side, I added `workspace-template/tools/awareness_client.py` as a thin HTTP wrapper around the awareness service. `workspace-template/tools/memory.py` preserves the existing `commit_memory(content, scope)` and `search_memory(query, scope)` signatures, but now routes to awareness when `AWARENESS_URL` and `AWARENESS_NAMESPACE` are configured. When those env vars are absent, it falls back to the existing platform memory API, so older workspaces still function. `workspace-template/main.py` now prints a small startup notice when awareness is enabled, which helps confirm container injection during debugging. A focused `workspace-template/tests/test_memory.py` was added to cover awareness routing, fallback behavior, and invalid scope rejection.

Documentation was updated to match the new contract: `docs/architecture/memory.md` now explains that awareness is the concrete runtime boundary behind the HMA scopes; `docs/agent-runtime/workspace-runtime.md` documents `AWARENESS_URL` and `AWARENESS_NAMESPACE` as runtime env vars; `docs/agent-runtime/cli-runtime.md` explains that CLI runtimes keep the same memory tool surface while routing into workspace-aware namespaces; `docs/api-protocol/platform-api.md` now mentions that new workspaces receive `awareness_namespace` and that awareness env vars are part of the common workspace secret/env set; `docs/agent-runtime/config-format.md` now lists awareness env vars in the optional section.

Verification performed after the edits: `python3 -m py_compile` succeeded for `workspace-template/tools/awareness_client.py`, `workspace-template/tools/memory.py`, `workspace-template/main.py`, `workspace-template/tests/test_memory.py`, and `workspace-template/tests/test_agent_base_urls.py`. Go formatting also succeeded on the modified Go files. Running `go test ./platform/internal/handlers -run TestWorkspaceCreate -v` failed before compilation because the repository's `go.mod` requires Go 1.25.0 and the local toolchain is Go 1.23.2. Running `python3 -m pytest ...` failed because `pytest` is not installed in the current Python environment.

Key assumptions kept explicit: awareness is a shared backend service, each workspace gets a namespace string derived from its workspace ID, and the runtime should continue to behave safely if awareness env vars are missing. The main unresolved dependency is the local Go toolchain version, which prevented a full Go test run in this session.
