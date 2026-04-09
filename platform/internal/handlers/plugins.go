package handlers

import (
	"archive/tar"
	"bytes"
	"context"
	"fmt"
	"io"
	"log"
	"time"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/gin-gonic/gin"
	"gopkg.in/yaml.v3"
)

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

// PluginsHandler manages the plugin registry and per-workspace plugin installation.
type PluginsHandler struct {
	pluginsDir  string         // host path to plugins/ registry
	docker      *client.Client // Docker client for container operations
	restartFunc func(string)   // auto-restart workspace after install/uninstall
}

func NewPluginsHandler(pluginsDir string, docker *client.Client, restartFunc func(string)) *PluginsHandler {
	return &PluginsHandler{pluginsDir: pluginsDir, docker: docker, restartFunc: restartFunc}
}

// pluginInfo is the API response for a plugin.
type pluginInfo struct {
	Name        string   `json:"name"`
	Version     string   `json:"version"`
	Description string   `json:"description"`
	Author      string   `json:"author"`
	Tags        []string `json:"tags"`
	Skills      []string `json:"skills"`
}

// ListRegistry handles GET /plugins — lists all available plugins from the registry.
func (h *PluginsHandler) ListRegistry(c *gin.Context) {
	plugins := []pluginInfo{}

	entries, err := os.ReadDir(h.pluginsDir)
	if err != nil {
		c.JSON(http.StatusOK, plugins)
		return
	}

	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		info := h.readPluginManifest(filepath.Join(h.pluginsDir, e.Name()), e.Name())
		plugins = append(plugins, info)
	}

	c.JSON(http.StatusOK, plugins)
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

	c.JSON(http.StatusOK, plugins)
}

// Install handles POST /workspaces/:id/plugins — installs a plugin from the registry.
func (h *PluginsHandler) Install(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	var body struct {
		Name string `json:"name" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := validatePluginName(body.Name); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate plugin exists in registry
	pluginSrc := filepath.Join(h.pluginsDir, body.Name)
	info, err := os.Stat(pluginSrc)
	if err != nil || !info.IsDir() {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("plugin '%s' not found in registry", body.Name)})
		return
	}

	// Find container
	containerName := h.findRunningContainer(ctx, workspaceID)
	if containerName == "" {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "workspace container not running"})
		return
	}

	// Copy plugin into /configs/plugins/<name>/ — tar is prefixed with plugins/<name>/ so
	// Docker creates the directory structure automatically under /configs
	if err := h.copyPluginToContainer(ctx, containerName, pluginSrc, body.Name); err != nil {
		log.Printf("Plugin install: failed to copy %s to %s: %v", body.Name, workspaceID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to copy plugin to container"})
		return
	}

	// Fix ownership so the agent user (UID 1000) can read/write plugin files
	h.execAsRoot(ctx, containerName, []string{
		"chown", "-R", "1000:1000", "/configs/plugins/" + body.Name,
	})

	// Auto-restart workspace to pick up the plugin
	if h.restartFunc != nil {
		go h.restartFunc(workspaceID)
	}

	log.Printf("Plugin install: %s → workspace %s (restarting)", body.Name, workspaceID)
	c.JSON(http.StatusOK, gin.H{
		"status": "installed",
		"plugin": body.Name,
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
