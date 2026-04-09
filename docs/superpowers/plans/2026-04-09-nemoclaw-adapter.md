# NemoClaw Adapter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `runtime: nemoclaw` adapter that provisions as its own runtime, reuses the current OpenClaw execution path for task handling in the first release, and fits the existing workspace/template/provisioner flow.

**Architecture:** NemoClaw is treated as an independent runtime entry in the platform and template registry. The adapter will install/configure NemoClaw on top of the existing OpenClaw-compatible workspace image so we can reuse the proven `openclaw agent --json` execution path first, then swap internals later if NemoClaw exposes a better native execution surface.

**Tech Stack:** Go provisioner mapping, Python adapter layer, Docker image layering, YAML workspace templates, pytest for adapter/provisioner smoke tests.

---

### Task 1: Add the NemoClaw adapter package

**Files:**
- Create: `workspace-template/adapters/nemoclaw/__init__.py`
- Create: `workspace-template/adapters/nemoclaw/adapter.py`
- Create: `workspace-template/adapters/nemoclaw/Dockerfile`

- [ ] **Step 1: Write the failing test**

```python
def test_nemoclaw_adapter_is_discoverable():
    from adapters import get_adapter
    assert get_adapter("nemoclaw").name() == "nemoclaw"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest workspace-template/tests/test_adapters.py -v`
Expected: FAIL because `nemoclaw` adapter does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement a `NemoClawAdapter` that:
- advertises `name() == "nemoclaw"`
- exposes its own config schema
- installs `nemoclaw` non-interactively
- reuses OpenClaw-style execution for `create_executor()`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest workspace-template/tests/test_adapters.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add workspace-template/adapters/nemoclaw
git commit -m "feat: add nemoclaw runtime adapter"
```

### Task 2: Add the NemoClaw workspace template

**Files:**
- Create: `workspace-configs-templates/nemoclaw/config.yaml`
- Create: `workspace-configs-templates/nemoclaw/SOUL.md`
- Create: `workspace-configs-templates/nemoclaw/BOOTSTRAP.md`
- Create: `workspace-configs-templates/nemoclaw/AGENTS.md`
- Create: `workspace-configs-templates/nemoclaw/HEARTBEAT.md`
- Create: `workspace-configs-templates/nemoclaw/TOOLS.md`

- [ ] **Step 1: Write the failing test**

```python
def test_nemoclaw_template_exists():
    assert Path("workspace-configs-templates/nemoclaw/config.yaml").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest workspace-template/tests/test_template_files.py -v`
Expected: FAIL because the template directory does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Copy the OpenClaw prompt-file layout and adjust `config.yaml` to declare `runtime: nemoclaw`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest workspace-template/tests/test_template_files.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add workspace-configs-templates/nemoclaw
git commit -m "feat: add nemoclaw workspace template"
```

### Task 3: Wire NemoClaw into provisioning and image builds

**Files:**
- Modify: `platform/internal/provisioner/provisioner.go`
- Modify: `scripts/build-images.sh`
- Modify: `docs/agent-runtime/cli-runtime.md`
- Modify: `docs/agent-runtime/config-format.md`

- [ ] **Step 1: Write the failing test**

```go
func TestRuntimeImagesIncludesNemoClaw(t *testing.T) {
    if got := RuntimeImages["nemoclaw"]; got != "workspace-template:nemoclaw" {
        t.Fatalf("unexpected image: %s", got)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./platform/internal/provisioner -run TestRuntimeImagesIncludesNemoClaw -v`
Expected: FAIL because the map entry is missing.

- [ ] **Step 3: Write minimal implementation**

Add the `nemoclaw` runtime image mapping and include it in the build script.

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./platform/internal/provisioner -run TestRuntimeImagesIncludesNemoClaw -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add platform/internal/provisioner/provisioner.go scripts/build-images.sh docs/agent-runtime/cli-runtime.md docs/agent-runtime/config-format.md
git commit -m "feat: wire nemoclaw runtime through provisioning"
```

### Task 4: Add lightweight verification coverage

**Files:**
- Create: `workspace-template/tests/test_adapters.py`
- Create: `platform/internal/provisioner/provisioner_test.go`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

```bash
git add workspace-template/tests/test_adapters.py platform/internal/provisioner/provisioner_test.go
git commit -m "test: cover nemoclaw adapter registration"
```

