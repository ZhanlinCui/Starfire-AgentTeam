package handlers

import (
	"archive/tar"
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/agent-molecule/platform/internal/plugins"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/gin-gonic/gin"
	"gopkg.in/yaml.v3"
)

// Install-layer defaults. Overridable via env for deployments whose
// plugin sources are fast (or slow) enough to warrant different caps.
const (
	defaultInstallBodyMaxBytes = 64 * 1024       // 64 KiB JSON body cap
	defaultInstallFetchTimeout = 5 * time.Minute // per-fetch deadline
	defaultInstallMaxDirBytes  = 100 * 1024 * 1024 // 100 MiB staged tree
)

func envDuration(name string, def time.Duration) time.Duration {
	if v := os.Getenv(name); v != "" {
		if d, err := time.ParseDuration(v); err == nil && d > 0 {
			return d
		}
	}
	return def
}

func envInt64(name string, def int64) int64 {
	if v := os.Getenv(name); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil && n > 0 {
			return n
		}
	}
	return def
}

// dirSize returns the total bytes of files under dir. Short-circuits
// as soon as the cap is exceeded so pathological inputs don't run the
// full walk.
func dirSize(dir string, cap int64) (int64, error) {
	var total int64
	err := filepath.Walk(dir, func(path string, info os.FileInfo, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if !info.IsDir() {
			total += info.Size()
			if total > cap {
				return fmt.Errorf("staged plugin exceeds cap of %d bytes", cap)
			}
		}
		return nil
	})
	return total, err
}

// validatePluginName ensures the name is safe (no path traversal).
func validatePluginName(name string) error {
	if name == "" {
		return fmt.Errorf("plugin name is required")
	}
	if strings.Contains(name, "/") || strings.Contains(name, "\\") || strings.Contains(name, "..") {
		return fmt.Errorf("invalid plugin name: must not contain path separators or '..'")
	}
	if name != filepath.Base(name) {
		return fmt.Errorf("invalid plugin name")
	}
	return nil
}

// RuntimeLookup resolves a workspace's runtime identifier by ID. The
// handler uses this to filter the plugin registry to compatible plugins
// without needing a direct DB dependency. A nil lookup disables
// workspace-scoped filtering (handler falls back to unfiltered list).
type RuntimeLookup func(workspaceID string) (string, error)

// PluginsHandler manages the plugin registry and per-workspace plugin installation.
type PluginsHandler struct {
	pluginsDir    string             // host path to plugins/ registry
	docker        *client.Client     // Docker client for container operations
	restartFunc   func(string)       // auto-restart workspace after install/uninstall
	runtimeLookup RuntimeLookup      // workspace_id → runtime (optional)
	sources       *plugins.Registry  // pluggable install sources (local, github, clawhub, …)
}

func NewPluginsHandler(pluginsDir string, docker *client.Client, restartFunc func(string)) *PluginsHandler {
	// Default source registry ships with the local filesystem resolver
	// (legacy behaviour) and the github resolver (new). Deployments can
	// register additional schemes via WithSourceResolver before routes
	// are wired — e.g. a private enterprise registry or ClawHub.
	sources := plugins.NewRegistry()
	sources.Register(plugins.NewLocalResolver(pluginsDir))
	sources.Register(plugins.NewGithubResolver())
	return &PluginsHandler{
		pluginsDir:  pluginsDir,
		docker:      docker,
		restartFunc: restartFunc,
		sources:     sources,
	}
}

// WithSourceResolver registers a custom source resolver (e.g. a ClawHub
// client) alongside the defaults. Call during router wiring, before the
// first request. Chainable.
func (h *PluginsHandler) WithSourceResolver(resolver plugins.SourceResolver) *PluginsHandler {
	h.sources.Register(resolver)
	return h
}

// WithRuntimeLookup installs a workspace-runtime resolver. Used by the
// router during wiring so tests don't need a real DB.
func (h *PluginsHandler) WithRuntimeLookup(lookup RuntimeLookup) *PluginsHandler {
	h.runtimeLookup = lookup
	return h
}

// pluginInfo is the API response for a plugin.
type pluginInfo struct {
	Name        string   `json:"name"`
	Version     string   `json:"version"`
	Description string   `json:"description"`
	Author      string   `json:"author"`
	Tags        []string `json:"tags"`
	Skills      []string `json:"skills"`
	// Runtimes declares which workspace runtimes this plugin ships an adaptor
	// for. Empty means "unknown / legacy plugin" — the canvas should still
	// allow install (the raw-drop fallback will surface a warning at install
	// time). Runtime names use underscore form (e.g. "claude_code").
	Runtimes []string `json:"runtimes"`
	// SupportedOnRuntime is populated by ListInstalled/compatibility only.
	// When a workspace changes runtime, plugins whose manifest doesn't
	// declare the new runtime become inert (files present, tools unwired).
	// The canvas reads this to grey out rows.
	// Pointer so the field is omitted on endpoints that don't compute it.
	SupportedOnRuntime *bool `json:"supported_on_runtime,omitempty"`
}

// supportsRuntime returns true if the plugin declares support for the given
// runtime OR if it declares no runtimes at all (legacy). Comparison is
// normalized — "claude-code" and "claude_code" are treated as equal.
func (p pluginInfo) supportsRuntime(runtime string) bool {
	if len(p.Runtimes) == 0 {
		return true
	}
	want := strings.ReplaceAll(runtime, "-", "_")
	for _, r := range p.Runtimes {
		if strings.ReplaceAll(r, "-", "_") == want {
			return true
		}
	}
	return false
}

// ListRegistry handles GET /plugins — lists all available plugins from the registry.
// Supports optional ?runtime=<name> query param to filter to plugins that
// declare support for the given runtime (plus legacy plugins with no
// `runtimes` field, which are assumed compatible).
func (h *PluginsHandler) ListRegistry(c *gin.Context) {
	runtime := c.Query("runtime")
	c.JSON(http.StatusOK, h.listRegistryFiltered(runtime))
}

// listRegistryFiltered is the shared read-plus-filter path used by both
// /plugins and /workspaces/:id/plugins/available.
func (h *PluginsHandler) listRegistryFiltered(runtime string) []pluginInfo {
	plugins := []pluginInfo{}
	entries, err := os.ReadDir(h.pluginsDir)
	if err != nil {
		return plugins
	}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		info := h.readPluginManifest(filepath.Join(h.pluginsDir, e.Name()), e.Name())
		if runtime != "" && !info.supportsRuntime(runtime) {
			continue
		}
		plugins = append(plugins, info)
	}
	return plugins
}

// ListSources handles GET /plugins/sources — returns the list of
// registered install-source schemes so clients can show users which
// kinds of plugin sources they can install from.
func (h *PluginsHandler) ListSources(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"schemes": h.sources.Schemes()})
}

// ListAvailableForWorkspace handles GET /workspaces/:id/plugins/available —
// returns plugins from the registry filtered to those supported by the
// workspace's runtime. If no runtime lookup is wired, falls back to the
// full registry.
func (h *PluginsHandler) ListAvailableForWorkspace(c *gin.Context) {
	workspaceID := c.Param("id")
	runtime := ""
	if h.runtimeLookup != nil {
		if r, err := h.runtimeLookup(workspaceID); err == nil {
			runtime = r
		}
	}
	c.JSON(http.StatusOK, h.listRegistryFiltered(runtime))
}

// ListInstalled handles GET /workspaces/:id/plugins — lists plugins installed in the workspace.
func (h *PluginsHandler) ListInstalled(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()
	plugins := []pluginInfo{}

	containerName := h.findRunningContainer(ctx, workspaceID)
	if containerName == "" {
		c.JSON(http.StatusOK, plugins)
		return
	}

	// List directories in /configs/plugins/
	output, err := h.execInContainer(ctx, containerName, []string{
		"sh", "-c", "ls -1 /configs/plugins/ 2>/dev/null || true",
	})
	if err != nil {
		c.JSON(http.StatusOK, plugins)
		return
	}

	for _, name := range strings.Split(output, "\n") {
		name = strings.TrimSpace(name)
		if name == "" || validatePluginName(name) != nil {
			continue
		}
		// Try to read manifest from container (safe: name is validated)
		manifestOutput, err := h.execInContainer(ctx, containerName, []string{
			"cat", fmt.Sprintf("/configs/plugins/%s/plugin.yaml", name),
		})
		if err != nil || manifestOutput == "" {
			plugins = append(plugins, pluginInfo{Name: name})
			continue
		}
		info := parseManifestYAML(name, []byte(manifestOutput))
		plugins = append(plugins, info)
	}

	// Annotate each installed plugin with whether it still supports the
	// workspace's current runtime. Lets the canvas grey out plugins that
	// went inert after a runtime change.
	if h.runtimeLookup != nil {
		if runtime, err := h.runtimeLookup(workspaceID); err == nil && runtime != "" {
			for i := range plugins {
				ok := plugins[i].supportsRuntime(runtime)
				plugins[i].SupportedOnRuntime = &ok
			}
		}
	}

	c.JSON(http.StatusOK, plugins)
}

// CheckRuntimeCompatibility handles GET /workspaces/:id/plugins/compatibility?runtime=<name>
// — preflight for runtime changes. Reports which installed plugins would
// become inert if the workspace switched to <runtime>. Canvas uses this
// to show a confirm dialog before applying the change.
func (h *PluginsHandler) CheckRuntimeCompatibility(c *gin.Context) {
	workspaceID := c.Param("id")
	targetRuntime := c.Query("runtime")
	ctx := c.Request.Context()

	if targetRuntime == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "runtime query parameter is required"})
		return
	}

	containerName := h.findRunningContainer(ctx, workspaceID)
	if containerName == "" {
		// Workspace not running — nothing installed yet, trivially compatible.
		c.JSON(http.StatusOK, gin.H{
			"target_runtime":   targetRuntime,
			"compatible":       []pluginInfo{},
			"incompatible":     []pluginInfo{},
			"all_compatible":   true,
		})
		return
	}

	output, err := h.execInContainer(ctx, containerName, []string{
		"sh", "-c", "ls -1 /configs/plugins/ 2>/dev/null || true",
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list installed plugins"})
		return
	}

	compatible := []pluginInfo{}
	incompatible := []pluginInfo{}
	for _, name := range strings.Split(output, "\n") {
		name = strings.TrimSpace(name)
		if name == "" || validatePluginName(name) != nil {
			continue
		}
		manifestOutput, err := h.execInContainer(ctx, containerName, []string{
			"cat", fmt.Sprintf("/configs/plugins/%s/plugin.yaml", name),
		})
		var info pluginInfo
		if err != nil || manifestOutput == "" {
			info = pluginInfo{Name: name}
		} else {
			info = parseManifestYAML(name, []byte(manifestOutput))
		}
		if info.supportsRuntime(targetRuntime) {
			compatible = append(compatible, info)
		} else {
			incompatible = append(incompatible, info)
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"target_runtime": targetRuntime,
		"compatible":     compatible,
		"incompatible":   incompatible,
		"all_compatible": len(incompatible) == 0,
	})
}

// Install handles POST /workspaces/:id/plugins — installs a plugin.
//
// Accepts EITHER:
//
//   - {"name": "my-plugin"}                         → local registry (back-compat)
//   - {"source": "local://my-plugin"}               → explicit local
//   - {"source": "github://owner/repo"}             → install from GitHub
//   - {"source": "github://owner/repo#v1.2.0"}      → pinned ref
//   - {"source": "clawhub://sonoscli@1.2.0"}        → when a ClawHub resolver is registered
//
// The shape of the plugin (agentskills.io format, MCP server, DeepAgents
// sub-agent, …) is orthogonal and handled by the per-runtime adapter
// inside the workspace at startup.
func (h *PluginsHandler) Install(c *gin.Context) {
	workspaceID := c.Param("id")
	// Cap the JSON body so a pathological POST can't exhaust parser memory.
	bodyMax := envInt64("PLUGIN_INSTALL_BODY_MAX_BYTES", defaultInstallBodyMaxBytes)
	c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, bodyMax)

	// Bound the whole install (fetch + copy) so a slow/malicious source
	// can't tie up an HTTP handler goroutine indefinitely. Overridable
	// via PLUGIN_INSTALL_FETCH_TIMEOUT (duration string, e.g. "10m").
	timeout := envDuration("PLUGIN_INSTALL_FETCH_TIMEOUT", defaultInstallFetchTimeout)
	ctx, cancel := context.WithTimeout(c.Request.Context(), timeout)
	defer cancel()

	var body struct {
		Name   string `json:"name"`
		Source string `json:"source"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	// Reject ambiguous calls that set BOTH `name` and `source`. Forces
	// the caller to pick one explicitly so we don't silently shadow.
	if body.Name != "" && body.Source != "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "specify either 'name' (local shortcut) or 'source' (full scheme://spec), not both",
		})
		return
	}
	// Back-compat: bare `name` promotes to local:// source.
	rawSource := body.Source
	if rawSource == "" {
		rawSource = body.Name
	}
	if rawSource == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "either 'name' or 'source' is required"})
		return
	}

	source, err := plugins.ParseSource(rawSource)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	resolver, err := h.sources.Resolve(source)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":             err.Error(),
			"available_schemes": h.sources.Schemes(),
		})
		return
	}
	// Front-run obvious input validation for local sources so path-
	// traversal attempts yield 400 rather than a resolver-level 502.
	// Other schemes do their own spec validation inside Fetch.
	if source.Scheme == "local" {
		if err := validatePluginName(source.Spec); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
	}

	// Fetch first so a missing plugin yields 404 regardless of whether a
	// container is up. For remote resolvers (github, clawhub, …) this
	// means we do the network round-trip before the container check, but
	// the cost is bounded by the fetch resolver's own timeouts and we
	// don't want to confuse "plugin doesn't exist" with "workspace down."
	fetchDst, err := os.MkdirTemp("", "starfire-plugin-fetch-*")
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create staging dir"})
		return
	}
	defer os.RemoveAll(fetchDst)

	pluginName, err := resolver.Fetch(ctx, source.Spec, fetchDst)
	if err != nil {
		log.Printf("Plugin install: resolver %s failed for %s: %v", source.Scheme, source.Spec, err)
		status := http.StatusBadGateway
		// Typed sentinel — any resolver can signal "not found" and we
		// map it to a 404 without string-matching the message.
		if errors.Is(err, plugins.ErrPluginNotFound) {
			status = http.StatusNotFound
		} else if errors.Is(err, context.DeadlineExceeded) {
			status = http.StatusGatewayTimeout
		}
		c.JSON(status, gin.H{
			"error":  fmt.Sprintf("failed to fetch plugin from %s: %v", source.Scheme, err),
			"source": source.Raw(),
		})
		return
	}
	// Re-validate the plugin name BEFORE the container check: a hostile
	// resolver that returns "../../etc/passwd" should be a 400, not a
	// 503 waiting for a container.
	if err := validatePluginName(pluginName); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":  fmt.Sprintf("resolver returned invalid plugin name %q: %v", pluginName, err),
			"source": source.Raw(),
		})
		return
	}
	// Enforce a staged-tree size cap before we copy into the container.
	// Protects both the platform host filesystem and the workspace
	// container from a huge accidental-or-malicious plugin.
	maxBytes := envInt64("PLUGIN_INSTALL_MAX_DIR_BYTES", defaultInstallMaxDirBytes)
	if _, err := dirSize(fetchDst, maxBytes); err != nil {
		c.JSON(http.StatusRequestEntityTooLarge, gin.H{
			"error":  err.Error(),
			"source": source.Raw(),
		})
		return
	}

	containerName := h.findRunningContainer(ctx, workspaceID)
	if containerName == "" {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "workspace container not running"})
		return
	}
	if err := h.copyPluginToContainer(ctx, containerName, fetchDst, pluginName); err != nil {
		log.Printf("Plugin install: failed to copy %s to %s: %v", pluginName, workspaceID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to copy plugin to container"})
		return
	}
	h.execAsRoot(ctx, containerName, []string{
		"chown", "-R", "1000:1000", "/configs/plugins/" + pluginName,
	})

	if h.restartFunc != nil {
		go h.restartFunc(workspaceID)
	}

	log.Printf("Plugin install: %s via %s → workspace %s (restarting)", pluginName, source.Scheme, workspaceID)
	c.JSON(http.StatusOK, gin.H{
		"status": "installed",
		"plugin": pluginName,
		"source": source.Raw(),
	})
}

// Uninstall handles DELETE /workspaces/:id/plugins/:name — removes a plugin.
func (h *PluginsHandler) Uninstall(c *gin.Context) {
	workspaceID := c.Param("id")
	pluginName := c.Param("name")
	ctx := c.Request.Context()

	if err := validatePluginName(pluginName); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	containerName := h.findRunningContainer(ctx, workspaceID)
	if containerName == "" {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "workspace container not running"})
		return
	}

	// Delete plugin directory from container (as root to handle file ownership)
	_, err := h.execAsRoot(ctx, containerName, []string{
		"rm", "-rf", "/configs/plugins/" + pluginName,
	})
	if err != nil {
		log.Printf("Plugin uninstall: failed to remove %s from %s: %v", pluginName, workspaceID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to remove plugin"})
		return
	}

	// Verify deletion before restart
	h.execInContainer(ctx, containerName, []string{"sync"})

	// Auto-restart (small delay to ensure fs writes are flushed)
	if h.restartFunc != nil {
		go func() {
			time.Sleep(2 * time.Second)
			h.restartFunc(workspaceID)
		}()
	}

	log.Printf("Plugin uninstall: %s from workspace %s (restarting)", pluginName, workspaceID)
	c.JSON(http.StatusOK, gin.H{
		"status": "uninstalled",
		"plugin": pluginName,
	})
}

// --- helpers ---

func (h *PluginsHandler) readPluginManifest(pluginPath, fallbackName string) pluginInfo {
	data, err := os.ReadFile(filepath.Join(pluginPath, "plugin.yaml"))
	if err != nil {
		return pluginInfo{Name: fallbackName}
	}
	return parseManifestYAML(fallbackName, data)
}

// parseManifestYAML parses plugin.yaml bytes into pluginInfo.
func parseManifestYAML(fallbackName string, data []byte) pluginInfo {
	info := pluginInfo{Name: fallbackName}
	var raw map[string]interface{}
	if yaml.Unmarshal(data, &raw) != nil {
		return info
	}
	info.Version = strDefault(raw, "version", "")
	info.Description = strDefault(raw, "description", "")
	info.Author = strDefault(raw, "author", "")
	if tags, ok := raw["tags"].([]interface{}); ok {
		for _, t := range tags {
			if s, ok := t.(string); ok {
				info.Tags = append(info.Tags, s)
			}
		}
	}
	if skills, ok := raw["skills"].([]interface{}); ok {
		for _, s := range skills {
			if str, ok := s.(string); ok {
				info.Skills = append(info.Skills, str)
			}
		}
	}
	if runtimes, ok := raw["runtimes"].([]interface{}); ok {
		for _, r := range runtimes {
			if str, ok := r.(string); ok {
				info.Runtimes = append(info.Runtimes, str)
			}
		}
	}
	return info
}

func strDefault(m map[string]interface{}, key, fallback string) string {
	if v, ok := m[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return fallback
}

func (h *PluginsHandler) findRunningContainer(ctx context.Context, workspaceID string) string {
	if h.docker == nil {
		return ""
	}
	name := provisioner.ContainerName(workspaceID)
	info, err := h.docker.ContainerInspect(ctx, name)
	if err == nil && info.State.Running {
		return name
	}
	return ""
}

func (h *PluginsHandler) execAsRoot(ctx context.Context, containerName string, cmd []string) (string, error) {
	return h.execInContainerAs(ctx, containerName, "root", cmd)
}

func (h *PluginsHandler) execInContainer(ctx context.Context, containerName string, cmd []string) (string, error) {
	return h.execInContainerAs(ctx, containerName, "", cmd)
}

func (h *PluginsHandler) execInContainerAs(ctx context.Context, containerName, user string, cmd []string) (string, error) {
	execCfg := container.ExecOptions{
		Cmd:          cmd,
		AttachStdout: true,
		AttachStderr: true,
		User:         user,
	}
	execID, err := h.docker.ContainerExecCreate(ctx, containerName, execCfg)
	if err != nil {
		return "", err
	}
	resp, err := h.docker.ContainerExecAttach(ctx, execID.ID, container.ExecAttachOptions{})
	if err != nil {
		return "", err
	}
	defer resp.Close()
	var stdout bytes.Buffer
	stdcopy.StdCopy(&stdout, io.Discard, resp.Reader)
	return strings.TrimSpace(stdout.String()), nil
}

// copyPluginToContainer creates a tar from a host directory and copies it into /configs/plugins/<name>/.
// The tar entries are prefixed with plugins/<name>/ so Docker creates the directory structure.
func (h *PluginsHandler) copyPluginToContainer(ctx context.Context, containerName, hostDir, pluginName string) error {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)

	err := filepath.Walk(hostDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(hostDir, path)
		if err != nil {
			return err
		}

		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		// Prefix: plugins/<pluginName>/<rel> → extracts under /configs/
		header.Name = filepath.Join("plugins", pluginName, rel)

		if err := tw.WriteHeader(header); err != nil {
			return err
		}
		if !info.IsDir() {
			data, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			if _, err := tw.Write(data); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return fmt.Errorf("failed to create tar from %s: %w", hostDir, err)
	}
	if err := tw.Close(); err != nil {
		return fmt.Errorf("failed to close tar: %w", err)
	}

	// Copy to /configs — the tar's plugins/<name>/ prefix creates the directory
	return h.docker.CopyToContainer(ctx, containerName, "/configs", &buf, container.CopyToContainerOptions{})
}
