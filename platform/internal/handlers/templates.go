package handlers

import (
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/gin-gonic/gin"
	"gopkg.in/yaml.v3"
)

// maxUploadFiles limits the number of files in a single import/replace.
const maxUploadFiles = 200

type TemplatesHandler struct {
	configsDir string
}

func NewTemplatesHandler(configsDir string) *TemplatesHandler {
	return &TemplatesHandler{configsDir: configsDir}
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
func normalizeName(name string) string {
	var b strings.Builder
	for _, r := range name {
		if r == ' ' {
			b.WriteRune('-')
		} else if r >= 'A' && r <= 'Z' {
			b.WriteRune(r + 32)
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
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
		if err := os.WriteFile(fullPath, []byte(content), 0644); err != nil {
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
		if err := os.WriteFile(filepath.Join(destDir, "config.yaml"), []byte(cfg), 0644); err != nil {
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

	dirName := normalizeName(wsName)
	destDir := filepath.Join(h.configsDir, dirName)

	// Clear existing files
	if info, err := os.Stat(destDir); err == nil && info.IsDir() {
		os.RemoveAll(destDir)
	}

	if err := writeFiles(destDir, body.Files); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Auto-generate config.yaml if not provided
	if _, exists := body.Files["config.yaml"]; !exists {
		cfg := generateDefaultConfig(wsName, body.Files)
		if err := os.WriteFile(filepath.Join(destDir, "config.yaml"), []byte(cfg), 0644); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to write config.yaml"})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"status":     "replaced",
		"workspace":  workspaceID,
		"files":      len(body.Files),
		"config_dir": dirName,
	})
}

// ListFiles handles GET /workspaces/:id/files
// Returns the file tree of a workspace's config directory.
func (h *TemplatesHandler) ListFiles(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	var wsName string
	if err := db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}

	dirName := normalizeName(wsName)
	configDir := filepath.Join(h.configsDir, dirName)

	if _, err := os.Stat(configDir); os.IsNotExist(err) {
		c.JSON(http.StatusOK, []interface{}{})
		return
	}

	type fileEntry struct {
		Path string `json:"path"`
		Size int64  `json:"size"`
		Dir  bool   `json:"dir"`
	}

	var files []fileEntry
	filepath.Walk(configDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || path == configDir {
			return nil
		}
		rel, _ := filepath.Rel(configDir, path)
		if strings.HasPrefix(rel, ".") {
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
	var wsName string
	if err := db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}

	fullPath := filepath.Join(h.configsDir, normalizeName(wsName), filePath)
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

	fullPath := filepath.Join(h.configsDir, normalizeName(wsName), filePath)
	os.MkdirAll(filepath.Dir(fullPath), 0755)
	if err := os.WriteFile(fullPath, []byte(body.Content), 0644); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to write file"})
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

	fullPath := filepath.Join(h.configsDir, normalizeName(wsName), filePath)

	info, err := os.Stat(fullPath)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "not found"})
		return
	}

	if info.IsDir() {
		if err := os.RemoveAll(fullPath); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete folder"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "deleted", "path": filePath, "type": "directory"})
		return
	}

	if err := os.Remove(fullPath); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete file"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "deleted", "path": filePath, "type": "file"})
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
