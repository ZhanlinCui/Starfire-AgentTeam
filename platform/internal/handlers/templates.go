package handlers

import (
	"archive/tar"
	"bytes"
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/gin-gonic/gin"
	"gopkg.in/yaml.v3"
)

// allowedRoots are the container paths that the Files API can browse.
var allowedRoots = map[string]bool{
	"/configs":   true,
	"/workspace": true,
	"/home":      true,
	"/plugins":   true,
}

// maxExecOutput limits container exec output to 5MB to prevent OOM.
const maxExecOutput = 5 * 1024 * 1024

// maxUploadFiles limits the number of files in a single import/replace.
const maxUploadFiles = 200

type TemplatesHandler struct {
	configsDir string
	docker     *client.Client
}

func NewTemplatesHandler(configsDir string, dockerCli *client.Client) *TemplatesHandler {
	return &TemplatesHandler{configsDir: configsDir, docker: dockerCli}
}

// findContainer finds a running container for the workspace.
// Checks provisioner name, full ID, and DB workspace name (same candidates as terminal handler).
func (h *TemplatesHandler) findContainer(ctx context.Context, workspaceID string) string {
	if h.docker == nil {
		return ""
	}
	name := provisioner.ContainerName(workspaceID)
	candidates := []string{name}
	if name != "ws-"+workspaceID {
		candidates = append(candidates, "ws-"+workspaceID)
	}
	// Also check by workspace name from DB
	var wsName string
	db.DB.QueryRowContext(ctx, `SELECT LOWER(REPLACE(name, ' ', '-')) FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName)
	if wsName != "" {
		candidates = append(candidates, wsName)
	}
	for _, c := range candidates {
		info, err := h.docker.ContainerInspect(ctx, c)
		if err == nil && info.State.Running {
			return c
		}
	}
	return ""
}

// execInContainer runs a command in a container and returns stdout (capped at maxExecOutput).
func (h *TemplatesHandler) execInContainer(ctx context.Context, containerName string, cmd []string) (string, error) {
	execCfg := container.ExecOptions{
		Cmd:          cmd,
		AttachStdout: true,
		AttachStderr: true,
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
	// Use stdcopy to correctly demux Docker multiplexed stream (stdout/stderr)
	stdcopy.StdCopy(&stdout, io.Discard, io.LimitReader(resp.Reader, maxExecOutput))
	return strings.TrimSpace(stdout.String()), nil
}

type templateSummary struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Tier        int      `json:"tier"`
	Model       string   `json:"model"`
	Skills      []string `json:"skills"`
	SkillCount  int      `json:"skill_count"`
}

// normalizeName converts a display name to a directory-safe lowercase-hyphen string.
// Only allows alphanumeric, hyphens, and underscores. Strips everything else.
func normalizeName(name string) string {
	var b strings.Builder
	for _, r := range name {
		if r == ' ' || r == '-' {
			b.WriteRune('-')
		} else if r >= 'A' && r <= 'Z' {
			b.WriteRune(r + 32)
		} else if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '_' {
			b.WriteRune(r)
		}
		// Skip all other characters (dots, slashes, etc.)
	}
	result := b.String()
	// Prevent path traversal
	result = strings.ReplaceAll(result, "..", "")
	if result == "" {
		result = "unnamed"
	}
	return result
}

// resolveTemplateDir finds the template directory for a workspace on the host.
// Only resolves to actual templates (not ws-* dirs since those are now Docker volumes).
// Returns empty string if no matching template is found.
func (h *TemplatesHandler) resolveTemplateDir(wsName string) string {
	nameDir := filepath.Join(h.configsDir, normalizeName(wsName))
	if _, err := os.Stat(nameDir); err == nil {
		return nameDir
	}
	// Search templates by config.yaml name field (e.g., org-pm has name: "PM")
	if tmpl := findTemplateByName(h.configsDir, wsName); tmpl != "" {
		return filepath.Join(h.configsDir, tmpl)
	}
	return ""
}

// validateRelPath checks that a relative path doesn't escape the target directory.
func validateRelPath(relPath string) error {
	clean := filepath.Clean(relPath)
	if filepath.IsAbs(clean) || strings.HasPrefix(clean, "..") {
		return fmt.Errorf("path traversal blocked: %s", relPath)
	}
	return nil
}

// writeFiles writes a map of relative paths → content into destDir, validating each path.
func writeFiles(destDir string, files map[string]string) error {
	for relPath, content := range files {
		if err := validateRelPath(relPath); err != nil {
			return err
		}
		fullPath := filepath.Join(destDir, relPath)
		if err := os.MkdirAll(filepath.Dir(fullPath), 0755); err != nil {
			return fmt.Errorf("failed to create directory for %s: %w", relPath, err)
		}
		if err := os.WriteFile(fullPath, []byte(content), 0600); err != nil {
			return fmt.Errorf("failed to write %s: %w", relPath, err)
		}
	}
	return nil
}

// generateDefaultConfig creates a config.yaml from detected prompt files and skills.
func generateDefaultConfig(name string, files map[string]string) string {
	promptFiles := []string{}
	skillSet := map[string]bool{}

	for path := range files {
		// Root .md files are prompt files
		if filepath.Dir(path) == "." && filepath.Ext(path) == ".md" {
			promptFiles = append(promptFiles, path)
		}
		// Detect skills from skills/*/SKILL.md
		if filepath.Base(path) == "SKILL.md" {
			dir := filepath.Dir(path)
			if filepath.Dir(dir) == "skills" {
				skillSet[filepath.Base(dir)] = true
			}
		}
	}

	var cfg strings.Builder
	cfg.WriteString("name: " + name + "\n")
	cfg.WriteString("description: Imported agent\n")
	cfg.WriteString("version: 1.0.0\ntier: 1\n")
	cfg.WriteString("model: anthropic:claude-haiku-4-5-20251001\n")
	cfg.WriteString("\nprompt_files:\n")
	if len(promptFiles) > 0 {
		for _, f := range promptFiles {
			cfg.WriteString("  - " + f + "\n")
		}
	} else {
		cfg.WriteString("  - system-prompt.md\n")
	}
	cfg.WriteString("\nskills:\n")
	if len(skillSet) > 0 {
		for s := range skillSet {
			cfg.WriteString("  - " + s + "\n")
		}
	} else {
		cfg.WriteString("  []\n")
	}
	cfg.WriteString("\ntools: []\n")
	cfg.WriteString("\na2a:\n  port: 8000\n  streaming: true\n  push_notifications: true\n")
	cfg.WriteString("\nenv:\n  required:\n    - ANTHROPIC_API_KEY\n  optional: []\n")
	return cfg.String()
}

// Import handles POST /templates/import
func (h *TemplatesHandler) Import(c *gin.Context) {
	var body struct {
		Name  string            `json:"name" binding:"required"`
		Files map[string]string `json:"files" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if len(body.Files) > maxUploadFiles {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("too many files (%d), max %d", len(body.Files), maxUploadFiles)})
		return
	}

	dirName := normalizeName(body.Name)
	destDir := filepath.Join(h.configsDir, dirName)

	if _, err := os.Stat(destDir); err == nil {
		c.JSON(http.StatusConflict, gin.H{"error": "template already exists", "id": dirName})
		return
	}

	if err := writeFiles(destDir, body.Files); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Auto-generate config.yaml if not provided
	if _, exists := body.Files["config.yaml"]; !exists {
		cfg := generateDefaultConfig(body.Name, body.Files)
		if err := os.WriteFile(filepath.Join(destDir, "config.yaml"), []byte(cfg), 0600); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to write config.yaml"})
			return
		}
	}

	c.JSON(http.StatusCreated, gin.H{"status": "imported", "id": dirName, "name": body.Name})
}

// ReplaceFiles handles PUT /workspaces/:id/files
func (h *TemplatesHandler) ReplaceFiles(c *gin.Context) {
	workspaceID := c.Param("id")

	var body struct {
		Files map[string]string `json:"files" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if len(body.Files) > maxUploadFiles {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("too many files (%d), max %d", len(body.Files), maxUploadFiles)})
		return
	}

	ctx := c.Request.Context()
	var wsName string
	if err := db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}

	// Validate all paths first
	for relPath := range body.Files {
		if err := validateRelPath(relPath); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
	}

	// Write via Docker CopyToContainer when container is running
	if containerName := h.findContainer(ctx, workspaceID); containerName != "" {
		if err := h.copyFilesToContainer(ctx, containerName, "/configs", body.Files); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to write files: %v", err)})
			return
		}

		// Auto-generate config.yaml if not provided
		if _, exists := body.Files["config.yaml"]; !exists {
			// Check if config.yaml exists in container
			if _, err := h.execInContainer(ctx, containerName, []string{"test", "-f", "/configs/config.yaml"}); err != nil {
				cfg := generateDefaultConfig(wsName, body.Files)
				singleFile := map[string]string{"config.yaml": cfg}
				h.copyFilesToContainer(ctx, containerName, "/configs", singleFile)
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"status":    "replaced",
			"workspace": workspaceID,
			"files":     len(body.Files),
			"source":    "container",
		})
		return
	}

	// Container offline — try ephemeral container to write to volume
	volName := provisioner.ConfigVolumeName(workspaceID)
	if err := h.writeViaEphemeral(ctx, volName, body.Files); err != nil {
		// Last resort: write to host-side template dir
		destDir := h.resolveTemplateDir(wsName)
		if destDir == "" {
			c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to write files: %v", err)})
			return
		}
		os.MkdirAll(destDir, 0o755)
		if err := writeFiles(destDir, body.Files); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "replaced", "workspace": workspaceID, "files": len(body.Files), "source": "template"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "replaced", "workspace": workspaceID, "files": len(body.Files), "source": "volume"})
}

// ListFiles handles GET /workspaces/:id/files
// Lists files inside the running container's /configs directory (or /workspace, etc.).
// Falls back to host-side config templates directory when container isn't running.
func (h *TemplatesHandler) ListFiles(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	// Query param ?root= to explore different container paths (default: /configs)
	rootPath := c.DefaultQuery("root", "/configs")
	if !allowedRoots[rootPath] {
		c.JSON(http.StatusBadRequest, gin.H{"error": "root must be one of: /configs, /workspace, /home, /plugins"})
		return
	}

	var wsName string
	if err := db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}

	type fileEntry struct {
		Path string `json:"path"`
		Size int64  `json:"size"`
		Dir  bool   `json:"dir"`
	}

	// Try container filesystem first
	if containerName := h.findContainer(ctx, workspaceID); containerName != "" {
		// Portable file listing: works on both GNU and BusyBox/Alpine.
		// Uses find + sh -c stat to output TYPE|SIZE|PATH per line.
		output, err := h.execInContainer(ctx, containerName, []string{
			"sh", "-c",
			fmt.Sprintf(`find %s -maxdepth 5 -not -path '*/.git/*' -not -name .DS_Store | while IFS= read -r f; do
				rel="${f#%s/}"; [ "$rel" = "%s" ] && continue; [ -z "$rel" ] && continue
				if [ -d "$f" ]; then echo "d|0|$rel"; else s=$(stat -c %%s "$f" 2>/dev/null || stat -f %%z "$f" 2>/dev/null || echo 0); echo "f|$s|$rel"; fi
			done`, rootPath, rootPath, rootPath),
		})
		if err != nil {
			log.Printf("Container file list failed, falling back to host: %v", err)
		} else {
			var files []fileEntry
			for _, line := range strings.Split(output, "\n") {
				parts := strings.SplitN(line, "|", 3)
				if len(parts) != 3 || parts[2] == "" {
					continue
				}
				size, _ := strconv.ParseInt(parts[1], 10, 64)
				files = append(files, fileEntry{
					Path: parts[2],
					Size: size,
					Dir:  parts[0] == "d",
				})
			}
			if files == nil {
				files = []fileEntry{}
			}
			c.JSON(http.StatusOK, files)
			return
		}
	}

	// Fallback: host-side template dir (only for templates, not ws-* workspace volumes)
	configDir := h.resolveTemplateDir(wsName)
	if configDir == "" {
		c.JSON(http.StatusOK, []fileEntry{})
		return
	}

	if _, err := os.Stat(configDir); os.IsNotExist(err) {
		c.JSON(http.StatusOK, []fileEntry{})
		return
	}

	var files []fileEntry
	filepath.Walk(configDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || path == configDir {
			return nil
		}
		rel, _ := filepath.Rel(configDir, path)
		base := filepath.Base(rel)
		if base == ".git" || base == ".DS_Store" {
			if info.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		files = append(files, fileEntry{
			Path: rel,
			Size: info.Size(),
			Dir:  info.IsDir(),
		})
		return nil
	})

	if files == nil {
		files = []fileEntry{}
	}
	c.JSON(http.StatusOK, files)
}

// ReadFile handles GET /workspaces/:id/files/*path
func (h *TemplatesHandler) ReadFile(c *gin.Context) {
	workspaceID := c.Param("id")
	filePath := c.Param("path")
	if strings.HasPrefix(filePath, "/") {
		filePath = filePath[1:]
	}

	if err := validateRelPath(filePath); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()
	rootPath := c.DefaultQuery("root", "/configs")
	if !allowedRoots[rootPath] {
		c.JSON(http.StatusBadRequest, gin.H{"error": "root must be one of: /configs, /workspace, /home, /plugins"})
		return
	}

	var wsName string
	if err := db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}

	// Try container first
	if containerName := h.findContainer(ctx, workspaceID); containerName != "" {
		containerPath := rootPath + "/" + filePath
		content, err := h.execInContainer(ctx, containerName, []string{"cat", containerPath})
		if err == nil {
			c.JSON(http.StatusOK, gin.H{
				"path":    filePath,
				"content": content,
				"size":    len(content),
			})
			return
		}
	}

	// Fallback: host-side template dir
	templateDir := h.resolveTemplateDir(wsName)
	if templateDir == "" {
		c.JSON(http.StatusNotFound, gin.H{"error": "file not found (container offline, no template)"})
		return
	}
	fullPath := filepath.Join(templateDir, filePath)
	data, err := os.ReadFile(fullPath)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "file not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"path":    filePath,
		"content": string(data),
		"size":    len(data),
	})
}

// WriteFile handles PUT /workspaces/:id/files/*path
func (h *TemplatesHandler) WriteFile(c *gin.Context) {
	workspaceID := c.Param("id")
	filePath := c.Param("path")
	if strings.HasPrefix(filePath, "/") {
		filePath = filePath[1:]
	}

	if err := validateRelPath(filePath); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var body struct {
		Content string `json:"content"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()
	var wsName string
	if err := db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}

	// Write via Docker CopyToContainer when container is running
	if containerName := h.findContainer(ctx, workspaceID); containerName != "" {
		singleFile := map[string]string{filePath: body.Content}
		if err := h.copyFilesToContainer(ctx, containerName, "/configs", singleFile); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to write file: %v", err)})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "saved", "path": filePath})
		return
	}

	// Container offline — write via ephemeral container mounting the config volume
	volName := provisioner.ConfigVolumeName(workspaceID)
	singleFile := map[string]string{filePath: body.Content}
	if err := h.writeViaEphemeral(ctx, volName, singleFile); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to write file: %v", err)})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "saved", "path": filePath})
}

// DeleteFile handles DELETE /workspaces/:id/files/*path
func (h *TemplatesHandler) DeleteFile(c *gin.Context) {
	workspaceID := c.Param("id")
	filePath := c.Param("path")
	if strings.HasPrefix(filePath, "/") {
		filePath = filePath[1:]
	}

	if err := validateRelPath(filePath); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()
	var wsName string
	if err := db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}

	// Delete via docker exec when container is running
	if containerName := h.findContainer(ctx, workspaceID); containerName != "" {
		containerPath := "/configs/" + filePath
		_, err := h.execInContainer(ctx, containerName, []string{"rm", "-rf", containerPath})
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to delete: %v", err)})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "deleted", "path": filePath})
		return
	}

	// Container offline — delete via ephemeral container
	volName := provisioner.ConfigVolumeName(workspaceID)
	if err := h.deleteViaEphemeral(ctx, volName, filePath); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to delete: %v", err)})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "deleted", "path": filePath})
}

// SharedContext handles GET /workspaces/:id/shared-context
// Returns the files listed in the workspace's config.yaml shared_context field.
func (h *TemplatesHandler) SharedContext(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	var wsName string
	if err := db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}

	type contextFile struct {
		Path    string `json:"path"`
		Content string `json:"content"`
	}

	// Try reading from running container first
	if containerName := h.findContainer(ctx, workspaceID); containerName != "" {
		configData, err := h.execInContainer(ctx, containerName, []string{"cat", "/configs/config.yaml"})
		if err != nil {
			c.JSON(http.StatusOK, []interface{}{})
			return
		}

		var cfg struct {
			SharedContext []string `yaml:"shared_context"`
		}
		if err := yaml.Unmarshal([]byte(configData), &cfg); err != nil || len(cfg.SharedContext) == 0 {
			c.JSON(http.StatusOK, []interface{}{})
			return
		}

		files := make([]contextFile, 0, len(cfg.SharedContext))
		for _, relPath := range cfg.SharedContext {
			if err := validateRelPath(relPath); err != nil {
				continue
			}
			content, err := h.execInContainer(ctx, containerName, []string{"cat", "/configs/" + relPath})
			if err != nil {
				continue
			}
			files = append(files, contextFile{Path: relPath, Content: content})
		}
		c.JSON(http.StatusOK, files)
		return
	}

	// Fallback to host-side template dir
	configDir := h.resolveTemplateDir(wsName)
	if configDir == "" {
		c.JSON(http.StatusOK, []interface{}{})
		return
	}

	configData, err := os.ReadFile(filepath.Join(configDir, "config.yaml"))
	if err != nil {
		c.JSON(http.StatusOK, []interface{}{})
		return
	}

	var cfg struct {
		SharedContext []string `yaml:"shared_context"`
	}
	if err := yaml.Unmarshal(configData, &cfg); err != nil || len(cfg.SharedContext) == 0 {
		c.JSON(http.StatusOK, []interface{}{})
		return
	}

	files := make([]contextFile, 0, len(cfg.SharedContext))
	for _, relPath := range cfg.SharedContext {
		if err := validateRelPath(relPath); err != nil {
			continue
		}
		data, err := os.ReadFile(filepath.Join(configDir, relPath))
		if err != nil {
			continue
		}
		files = append(files, contextFile{Path: relPath, Content: string(data)})
	}

	c.JSON(http.StatusOK, files)
}

// copyFilesToContainer creates a tar archive from a map of files and copies it into a container.
func (h *TemplatesHandler) copyFilesToContainer(ctx context.Context, containerName, destPath string, files map[string]string) error {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)

	createdDirs := map[string]bool{}
	for name, content := range files {
		// Create parent directories in tar (deduplicated)
		dir := filepath.Dir(name)
		if dir != "." && !createdDirs[dir] {
			tw.WriteHeader(&tar.Header{
				Typeflag: tar.TypeDir,
				Name:     dir + "/",
				Mode:     0755,
			})
			createdDirs[dir] = true
		}

		data := []byte(content)
		header := &tar.Header{
			Name: name,
			Mode: 0644,
			Size: int64(len(data)),
		}
		if err := tw.WriteHeader(header); err != nil {
			return fmt.Errorf("failed to write tar header for %s: %w", name, err)
		}
		if _, err := tw.Write(data); err != nil {
			return fmt.Errorf("failed to write tar data for %s: %w", name, err)
		}
	}
	if err := tw.Close(); err != nil {
		return fmt.Errorf("failed to close tar writer: %w", err)
	}

	return h.docker.CopyToContainer(ctx, containerName, destPath, &buf, container.CopyToContainerOptions{})
}

// writeViaEphemeral writes files to a named volume using an ephemeral Alpine container.
// Used when the workspace container is offline (e.g., during provisioning).
func (h *TemplatesHandler) writeViaEphemeral(ctx context.Context, volumeName string, files map[string]string) error {
	if h.docker == nil {
		return fmt.Errorf("docker not available")
	}

	// Create ephemeral container mounting the volume
	resp, err := h.docker.ContainerCreate(ctx, &container.Config{
		Image: "alpine:latest",
		Cmd:   []string{"sleep", "10"},
	}, &container.HostConfig{
		Binds: []string{volumeName + ":/configs"},
	}, nil, nil, "")
	if err != nil {
		return fmt.Errorf("failed to create ephemeral container: %w", err)
	}
	defer h.docker.ContainerRemove(ctx, resp.ID, container.RemoveOptions{Force: true})

	if err := h.docker.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
		return fmt.Errorf("failed to start ephemeral container: %w", err)
	}

	// Copy files via tar
	return h.copyFilesToContainer(ctx, resp.ID, "/configs", files)
}

// deleteViaEphemeral deletes a file from a named volume using an ephemeral container.
func (h *TemplatesHandler) deleteViaEphemeral(ctx context.Context, volumeName, filePath string) error {
	if h.docker == nil {
		return fmt.Errorf("docker not available")
	}

	resp, err := h.docker.ContainerCreate(ctx, &container.Config{
		Image: "alpine:latest",
		Cmd:   []string{"rm", "-rf", "/configs/" + filePath},
	}, &container.HostConfig{
		Binds: []string{volumeName + ":/configs"},
	}, nil, nil, "")
	if err != nil {
		return fmt.Errorf("failed to create ephemeral container: %w", err)
	}
	defer h.docker.ContainerRemove(ctx, resp.ID, container.RemoveOptions{Force: true})

	if err := h.docker.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
		return err
	}
	// Wait for the rm command to finish before removing the container
	statusCh, errCh := h.docker.ContainerWait(ctx, resp.ID, container.WaitConditionNotRunning)
	select {
	case <-statusCh:
		return nil
	case err := <-errCh:
		return err
	}
}

// List handles GET /templates
func (h *TemplatesHandler) List(c *gin.Context) {
	entries, err := os.ReadDir(h.configsDir)
	if err != nil {
		c.JSON(http.StatusOK, []templateSummary{})
		return
	}

	templates := make([]templateSummary, 0)
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}

		configPath := filepath.Join(h.configsDir, entry.Name(), "config.yaml")
		data, err := os.ReadFile(configPath)
		if err != nil {
			continue
		}

		var raw struct {
			Name        string   `yaml:"name"`
			Description string   `yaml:"description"`
			Tier        int      `yaml:"tier"`
			Model       string   `yaml:"model"`
			Skills      []string `yaml:"skills"`
		}
		if err := yaml.Unmarshal(data, &raw); err != nil {
			continue
		}

		templates = append(templates, templateSummary{
			ID:          entry.Name(),
			Name:        raw.Name,
			Description: raw.Description,
			Tier:        raw.Tier,
			Model:       raw.Model,
			Skills:      raw.Skills,
			SkillCount:  len(raw.Skills),
		})
	}

	c.JSON(http.StatusOK, templates)
}
