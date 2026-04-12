package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

// ---------- ListRegistry: empty dir → 200 [] ----------

func TestPluginListRegistry_EmptyDir(t *testing.T) {
	dir := t.TempDir()
	h := NewPluginsHandler(dir, nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/plugins", nil)

	h.ListRegistry(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var plugins []pluginInfo
	if err := json.Unmarshal(w.Body.Bytes(), &plugins); err != nil {
		t.Fatalf("failed to unmarshal: %v", err)
	}
	if len(plugins) != 0 {
		t.Errorf("expected 0 plugins, got %d", len(plugins))
	}
}

// ---------- ListRegistry: non-existent dir → 200 [] ----------

func TestPluginListRegistry_NonExistentDir(t *testing.T) {
	h := NewPluginsHandler("/tmp/does-not-exist-plugins-xyz", nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/plugins", nil)

	h.ListRegistry(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var plugins []pluginInfo
	if err := json.Unmarshal(w.Body.Bytes(), &plugins); err != nil {
		t.Fatalf("failed to unmarshal: %v", err)
	}
	if len(plugins) != 0 {
		t.Errorf("expected 0 plugins, got %d", len(plugins))
	}
}

// ---------- ListRegistry: with plugins → returns manifest data ----------

func TestPluginListRegistry_WithPlugins(t *testing.T) {
	dir := t.TempDir()

	// Create a plugin with manifest
	pluginDir := filepath.Join(dir, "my-plugin")
	if err := os.Mkdir(pluginDir, 0755); err != nil {
		t.Fatal(err)
	}
	manifest := `name: my-plugin
version: "1.0.0"
description: A test plugin
author: tester
tags:
  - test
  - example
skills:
  - greet
`
	if err := os.WriteFile(filepath.Join(pluginDir, "plugin.yaml"), []byte(manifest), 0644); err != nil {
		t.Fatal(err)
	}

	// Create a plugin without manifest (just a directory)
	bareDir := filepath.Join(dir, "bare-plugin")
	if err := os.Mkdir(bareDir, 0755); err != nil {
		t.Fatal(err)
	}

	// Create a regular file (should be skipped — not a directory)
	if err := os.WriteFile(filepath.Join(dir, "not-a-dir.txt"), []byte("hi"), 0644); err != nil {
		t.Fatal(err)
	}

	h := NewPluginsHandler(dir, nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/plugins", nil)

	h.ListRegistry(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var plugins []pluginInfo
	if err := json.Unmarshal(w.Body.Bytes(), &plugins); err != nil {
		t.Fatalf("failed to unmarshal: %v", err)
	}
	if len(plugins) != 2 {
		t.Fatalf("expected 2 plugins, got %d", len(plugins))
	}

	// Find the manifest plugin (order depends on readdir)
	var found bool
	for _, p := range plugins {
		if p.Name == "my-plugin" {
			found = true
			if p.Version != "1.0.0" {
				t.Errorf("expected version 1.0.0, got %s", p.Version)
			}
			if p.Description != "A test plugin" {
				t.Errorf("expected description 'A test plugin', got %s", p.Description)
			}
			if p.Author != "tester" {
				t.Errorf("expected author 'tester', got %s", p.Author)
			}
			if len(p.Tags) != 2 || p.Tags[0] != "test" || p.Tags[1] != "example" {
				t.Errorf("unexpected tags: %v", p.Tags)
			}
			if len(p.Skills) != 1 || p.Skills[0] != "greet" {
				t.Errorf("unexpected skills: %v", p.Skills)
			}
		}
		if p.Name == "bare-plugin" {
			if p.Version != "" {
				t.Errorf("bare plugin should have empty version, got %s", p.Version)
			}
		}
	}
	if !found {
		t.Error("my-plugin not found in results")
	}
}

// ---------- Install: missing name → 400 ----------

func TestPluginInstall_MissingName(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-123"}}
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-123/plugins", bytes.NewBufferString(`{}`))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Install(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// ---------- Install: invalid name (path traversal) → 400 ----------

func TestPluginInstall_InvalidName_PathTraversal(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-123"}}
	body := `{"name":"../../../etc/passwd"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-123/plugins", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Install(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// ---------- Install: plugin not found → 404 ----------

func TestPluginInstall_NotFound(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-123"}}
	body := `{"name":"nonexistent-plugin"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-123/plugins", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Install(c)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
}

// ---------- Uninstall: invalid name → 400 ----------

func TestPluginUninstall_InvalidName(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{
		{Key: "id", Value: "ws-123"},
		{Key: "name", Value: "../escape"},
	}
	c.Request = httptest.NewRequest("DELETE", "/workspaces/ws-123/plugins/../escape", nil)

	h.Uninstall(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// ---------- Uninstall: empty name → 400 ----------

func TestPluginUninstall_EmptyName(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{
		{Key: "id", Value: "ws-123"},
		{Key: "name", Value: ""},
	}
	c.Request = httptest.NewRequest("DELETE", "/workspaces/ws-123/plugins/", nil)

	h.Uninstall(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// ---------- validatePluginName: valid names pass ----------

func TestValidatePluginName_ValidNames(t *testing.T) {
	valid := []string{
		"my-plugin",
		"plugin_v2",
		"AwesomePlugin",
		"plugin123",
		"a",
	}
	for _, name := range valid {
		if err := validatePluginName(name); err != nil {
			t.Errorf("validatePluginName(%q) should pass, got: %v", name, err)
		}
	}
}

// ---------- validatePluginName: "/" rejected ----------

func TestValidatePluginName_SlashRejected(t *testing.T) {
	names := []string{
		"foo/bar",
		"/leading",
		"trailing/",
		"a/b/c",
	}
	for _, name := range names {
		if err := validatePluginName(name); err == nil {
			t.Errorf("validatePluginName(%q) should fail for slash", name)
		}
	}
}

// ---------- validatePluginName: ".." rejected ----------

func TestValidatePluginName_DotDotRejected(t *testing.T) {
	names := []string{
		"..",
		"..foo",
		"foo..",
		"a..b",
	}
	for _, name := range names {
		if err := validatePluginName(name); err == nil {
			t.Errorf("validatePluginName(%q) should fail for '..'", name)
		}
	}
}

// ---------- validatePluginName: backslash rejected ----------

func TestValidatePluginName_BackslashRejected(t *testing.T) {
	if err := validatePluginName(`foo\bar`); err == nil {
		t.Error(`validatePluginName("foo\\bar") should fail`)
	}
}

// ---------- validatePluginName: empty rejected ----------

func TestValidatePluginName_EmptyRejected(t *testing.T) {
	if err := validatePluginName(""); err == nil {
		t.Error("validatePluginName(\"\") should fail")
	}
}

// ---------- parseManifestYAML: valid yaml → correct pluginInfo ----------

func TestParseManifestYAML_ValidYAML(t *testing.T) {
	yaml := []byte(`
name: test-plugin
version: "2.0.0"
description: "Does things"
author: "dev"
tags:
  - utility
  - automation
skills:
  - summarize
  - translate
`)
	info := parseManifestYAML("fallback-name", yaml)

	// Name should use fallbackName, not the yaml name field
	if info.Name != "fallback-name" {
		t.Errorf("expected name 'fallback-name', got %s", info.Name)
	}
	if info.Version != "2.0.0" {
		t.Errorf("expected version 2.0.0, got %s", info.Version)
	}
	if info.Description != "Does things" {
		t.Errorf("expected description 'Does things', got %s", info.Description)
	}
	if info.Author != "dev" {
		t.Errorf("expected author 'dev', got %s", info.Author)
	}
	if len(info.Tags) != 2 || info.Tags[0] != "utility" || info.Tags[1] != "automation" {
		t.Errorf("unexpected tags: %v", info.Tags)
	}
	if len(info.Skills) != 2 || info.Skills[0] != "summarize" || info.Skills[1] != "translate" {
		t.Errorf("unexpected skills: %v", info.Skills)
	}
}

// ---------- parseManifestYAML: invalid yaml → fallback ----------

func TestParseManifestYAML_InvalidYAML(t *testing.T) {
	info := parseManifestYAML("safe-name", []byte(`{{{not valid yaml`))
	if info.Name != "safe-name" {
		t.Errorf("expected fallback name 'safe-name', got %s", info.Name)
	}
	if info.Version != "" {
		t.Errorf("expected empty version on invalid yaml, got %s", info.Version)
	}
}

// ---------- parseManifestYAML: minimal yaml (no tags/skills) ----------

func TestParseManifestYAML_MinimalYAML(t *testing.T) {
	yaml := []byte(`version: "0.1"`)
	info := parseManifestYAML("minimal", yaml)

	if info.Name != "minimal" {
		t.Errorf("expected name 'minimal', got %s", info.Name)
	}
	if info.Version != "0.1" {
		t.Errorf("expected version '0.1', got %s", info.Version)
	}
	if info.Tags != nil {
		t.Errorf("expected nil tags, got %v", info.Tags)
	}
	if info.Skills != nil {
		t.Errorf("expected nil skills, got %v", info.Skills)
	}
}

// ---------- Runtime filter on ListRegistry ----------

// writePlugin is a small helper for the runtime-filter tests.
func writePlugin(t *testing.T, dir, name, manifest string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Join(dir, name), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, name, "plugin.yaml"), []byte(manifest), 0644); err != nil {
		t.Fatal(err)
	}
}

func TestPluginListRegistry_FiltersByRuntime(t *testing.T) {
	dir := t.TempDir()
	writePlugin(t, dir, "p-cc", "name: p-cc\nruntimes: [claude_code]\n")
	writePlugin(t, dir, "p-da", "name: p-da\nruntimes: [deepagents]\n")
	writePlugin(t, dir, "p-both", "name: p-both\nruntimes: [claude_code, deepagents]\n")
	writePlugin(t, dir, "p-legacy", "name: p-legacy\n") // no runtimes — always allowed

	h := NewPluginsHandler(dir, nil, nil)

	cases := []struct {
		name     string
		runtime  string
		expected map[string]bool
	}{
		{"no filter returns all", "", map[string]bool{"p-cc": true, "p-da": true, "p-both": true, "p-legacy": true}},
		{"claude_code filter", "claude_code", map[string]bool{"p-cc": true, "p-both": true, "p-legacy": true}},
		{"deepagents filter", "deepagents", map[string]bool{"p-da": true, "p-both": true, "p-legacy": true}},
		{"hyphen form normalized", "claude-code", map[string]bool{"p-cc": true, "p-both": true, "p-legacy": true}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			c, _ := gin.CreateTestContext(w)
			url := "/plugins"
			if tc.runtime != "" {
				url += "?runtime=" + tc.runtime
			}
			c.Request = httptest.NewRequest("GET", url, nil)
			h.ListRegistry(c)

			var plugins []pluginInfo
			if err := json.Unmarshal(w.Body.Bytes(), &plugins); err != nil {
				t.Fatalf("unmarshal: %v", err)
			}
			got := map[string]bool{}
			for _, p := range plugins {
				got[p.Name] = true
			}
			if len(got) != len(tc.expected) {
				t.Errorf("runtime=%q: got %v, want %v", tc.runtime, got, tc.expected)
			}
			for name := range tc.expected {
				if !got[name] {
					t.Errorf("runtime=%q: missing %q", tc.runtime, name)
				}
			}
		})
	}
}

// ---------- ListAvailableForWorkspace ----------

func TestPluginListAvailableForWorkspace_UsesRuntimeLookup(t *testing.T) {
	dir := t.TempDir()
	writePlugin(t, dir, "only-deepagents", "name: only-deepagents\nruntimes: [deepagents]\n")
	writePlugin(t, dir, "only-claude", "name: only-claude\nruntimes: [claude_code]\n")

	// Workspace resolves to deepagents.
	h := NewPluginsHandler(dir, nil, nil).WithRuntimeLookup(func(id string) (string, error) {
		if id == "ws-da" {
			return "deepagents", nil
		}
		return "claude_code", nil
	})

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-da"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/ws-da/plugins/available", nil)
	h.ListAvailableForWorkspace(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var plugins []pluginInfo
	if err := json.Unmarshal(w.Body.Bytes(), &plugins); err != nil {
		t.Fatal(err)
	}
	if len(plugins) != 1 || plugins[0].Name != "only-deepagents" {
		t.Errorf("expected only-deepagents, got %+v", plugins)
	}
}

func TestPluginListAvailableForWorkspace_NoLookupReturnsAll(t *testing.T) {
	dir := t.TempDir()
	writePlugin(t, dir, "only-deepagents", "name: only-deepagents\nruntimes: [deepagents]\n")
	writePlugin(t, dir, "only-claude", "name: only-claude\nruntimes: [claude_code]\n")

	// No runtime lookup wired → falls back to full registry.
	h := NewPluginsHandler(dir, nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "anything"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/anything/plugins/available", nil)
	h.ListAvailableForWorkspace(c)

	var plugins []pluginInfo
	if err := json.Unmarshal(w.Body.Bytes(), &plugins); err != nil {
		t.Fatal(err)
	}
	if len(plugins) != 2 {
		t.Errorf("expected 2 plugins, got %d", len(plugins))
	}
}

// ---------- Manifest parsing: runtimes field ----------

func TestParseManifestYAML_PicksUpRuntimes(t *testing.T) {
	info := parseManifestYAML("demo", []byte("name: demo\nruntimes:\n  - claude_code\n  - deepagents\n"))
	if len(info.Runtimes) != 2 || info.Runtimes[0] != "claude_code" || info.Runtimes[1] != "deepagents" {
		t.Errorf("expected [claude_code, deepagents], got %v", info.Runtimes)
	}
	if !info.supportsRuntime("claude-code") {
		t.Error("hyphen/underscore normalization broken")
	}
	if info.supportsRuntime("langgraph") {
		t.Error("should not support langgraph")
	}
}

func TestSupportsRuntime_EmptyMeansLegacy(t *testing.T) {
	info := pluginInfo{Name: "legacy"}
	if !info.supportsRuntime("anything") {
		t.Error("legacy plugins (no runtimes field) must be treated as compatible")
	}
}

// ---------- CheckRuntimeCompatibility ----------

func TestCheckRuntimeCompatibility_RejectsMissingRuntimeParam(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/ws/plugins/compatibility", nil)
	h.CheckRuntimeCompatibility(c)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestCheckRuntimeCompatibility_TriviallyCompatibleWhenContainerMissing(t *testing.T) {
	// No docker client + no container → treated as "nothing installed, all compatible".
	h := NewPluginsHandler(t.TempDir(), nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/ws/plugins/compatibility?runtime=deepagents", nil)
	h.CheckRuntimeCompatibility(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["all_compatible"] != true {
		t.Errorf("expected all_compatible=true, got %v", body["all_compatible"])
	}
	if body["target_runtime"] != "deepagents" {
		t.Errorf("target_runtime mismatch: %v", body["target_runtime"])
	}
}


// ---------- ListSources ----------

func TestPluginListSources_ReturnsRegisteredSchemes(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/plugins/sources", nil)
	h.ListSources(c)

	if w.Code != http.StatusOK {
		t.Fatalf("status=%d", w.Code)
	}
	var body map[string][]string
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	hasLocal, hasGithub := false, false
	for _, s := range body["schemes"] {
		if s == "local" {
			hasLocal = true
		}
		if s == "github" {
			hasGithub = true
		}
	}
	if !hasLocal || !hasGithub {
		t.Errorf("expected local+github by default, got %v", body["schemes"])
	}
}

// ---------- Install — source routing ----------

func TestPluginInstall_RejectsEmptyBody(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x", bytes.NewBufferString(`{}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusBadRequest {
		t.Errorf("want 400, got %d: %s", w.Code, w.Body.String())
	}
}

func TestPluginInstall_RejectsUnknownScheme(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"source":"mystery://thing"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusBadRequest {
		t.Errorf("want 400, got %d: %s", w.Code, w.Body.String())
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("available_schemes")) {
		t.Errorf("response should list available_schemes: %s", w.Body.String())
	}
}

func TestPluginInstall_BareNameBackCompatRoutesToLocal(t *testing.T) {
	base := t.TempDir()
	pluginDir := filepath.Join(base, "demo")
	if err := os.MkdirAll(pluginDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(pluginDir, "plugin.yaml"), []byte("name: demo\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	h := NewPluginsHandler(base, nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"name":"demo"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	// No docker client configured → resolves source, then 503 on container
	// lookup. That's enough to prove the source dispatch works.
	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("want 503 (no container), got %d: %s", w.Code, w.Body.String())
	}
}

func TestPluginInstall_LocalSchemeAlias(t *testing.T) {
	base := t.TempDir()
	pluginDir := filepath.Join(base, "demo")
	_ = os.MkdirAll(pluginDir, 0o755)
	_ = os.WriteFile(filepath.Join(pluginDir, "plugin.yaml"), []byte("name: demo\n"), 0o644)
	h := NewPluginsHandler(base, nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"source":"local://demo"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("local:// should reach container lookup: got %d: %s", w.Code, w.Body.String())
	}
}

func TestPluginInstall_InvalidSourceString(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"source":"   "}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusBadRequest {
		t.Errorf("whitespace-only source should be rejected: got %d", w.Code)
	}
}


func TestPluginInstall_RejectsBothNameAndSource(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"name":"x","source":"local://y"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("not both")) {
		t.Errorf("response should explain the conflict: %s", w.Body.String())
	}
}

func TestPluginInstall_RejectsOversizedBody(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)
	// Build a JSON body larger than the cap (default 64 KiB).
	big := `{"source":"local://` + strings.Repeat("a", 70*1024) + `"}`
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x", bytes.NewBufferString(big))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for oversized body, got %d", w.Code)
	}
}

// Install 404 via the local sentinel (replaces the old string-match test).
func TestPluginInstall_NotFoundUsesTypedSentinel(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-123"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"name":"nonexistent"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404 via ErrPluginNotFound, got %d: %s", w.Code, w.Body.String())
	}
}

// Install 502 for non-sentinel resolver errors (e.g. network / auth).
func TestPluginInstall_NonSentinelResolverErrorIs502(t *testing.T) {
	// Register a stub resolver whose Fetch returns a plain (non-ErrPluginNotFound) error.
	h := NewPluginsHandler(t.TempDir(), nil, nil).
		WithSourceResolver(&erroringResolver{scheme: "broken", err: errors.New("connection refused")})
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"source":"broken://whatever"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusBadGateway {
		t.Errorf("non-sentinel resolver error should be 502, got %d: %s", w.Code, w.Body.String())
	}
}

// Install returns 504 when fetch honours ctx.DeadlineExceeded.
func TestPluginInstall_DeadlineExceededIs504(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil).
		WithSourceResolver(&erroringResolver{scheme: "slow", err: context.DeadlineExceeded})
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"source":"slow://x"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusGatewayTimeout {
		t.Errorf("deadline exceeded should be 504, got %d", w.Code)
	}
}

// Install 413 when the fetched tree exceeds the configured cap.
func TestPluginInstall_OversizedStagedTreeIs413(t *testing.T) {
	t.Setenv("PLUGIN_INSTALL_MAX_DIR_BYTES", "1024") // 1 KiB cap
	h := NewPluginsHandler(t.TempDir(), nil, nil).
		WithSourceResolver(&bigBlobResolver{bytes: 2048}) // 2 KiB blob
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"source":"big://whatever"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("oversized staged tree should be 413, got %d: %s", w.Code, w.Body.String())
	}
}

// envDuration / envInt64 moved to platform/internal/envx; see
// envx/envx_test.go for their tests.

func TestDirSize_ShortCircuitsOnCap(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "a"), bytes.Repeat([]byte("x"), 2048), 0o644); err != nil {
		t.Fatal(err)
	}
	_, err := dirSize(dir, 1024)
	if err == nil {
		t.Error("expected cap-exceeded error")
	}
	// Under the cap: no error.
	if _, err := dirSize(dir, 1<<20); err != nil {
		t.Errorf("1 MiB cap should accept 2 KiB: %v", err)
	}
}

// ---- test-only resolver stubs ----

type erroringResolver struct {
	scheme string
	err    error
}

func (e *erroringResolver) Scheme() string { return e.scheme }
func (e *erroringResolver) Fetch(ctx context.Context, spec, dst string) (string, error) {
	return "", e.err
}

type bigBlobResolver struct {
	bytes int
}

func (b *bigBlobResolver) Scheme() string { return "big" }
func (b *bigBlobResolver) Fetch(ctx context.Context, spec, dst string) (string, error) {
	if err := os.WriteFile(filepath.Join(dst, "blob"), bytes.Repeat([]byte("a"), b.bytes), 0o644); err != nil {
		return "", err
	}
	return "big", nil
}


func TestPluginInstall_RejectsHostileResolverPluginName(t *testing.T) {
	// Prove the post-fetch validatePluginName call catches a resolver
	// that tries to smuggle a traversal name into /configs/plugins/.
	h := NewPluginsHandler(t.TempDir(), nil, nil).
		WithSourceResolver(&hostileResolver{})
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"source":"hostile://anything"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusBadRequest {
		t.Errorf("hostile plugin name must be 400, got %d: %s", w.Code, w.Body.String())
	}
}

type hostileResolver struct{}

func (h *hostileResolver) Scheme() string { return "hostile" }
func (h *hostileResolver) Fetch(ctx context.Context, spec, dst string) (string, error) {
	// Emit files into dst (so dirSize passes) but return a traversal name.
	_ = os.WriteFile(filepath.Join(dst, "plugin.yaml"), []byte("name: x\n"), 0o644)
	return "../../../etc/passwd", nil
}


func TestPluginInstall_EmptySpecAfterSchemeRejected(t *testing.T) {
	h := NewPluginsHandler(t.TempDir(), nil, nil)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws"}}
	c.Request = httptest.NewRequest("POST", "/x",
		bytes.NewBufferString(`{"source":"github://"}`))
	c.Request.Header.Set("Content-Type", "application/json")
	h.Install(c)
	if w.Code != http.StatusBadRequest {
		t.Errorf("want 400, got %d: %s", w.Code, w.Body.String())
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("empty spec")) {
		t.Errorf("error should mention 'empty spec': %s", w.Body.String())
	}
}
