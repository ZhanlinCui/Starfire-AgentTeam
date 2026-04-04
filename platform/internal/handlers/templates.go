package handlers

import (
	"net/http"
	"os"
	"path/filepath"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/gin-gonic/gin"
	"gopkg.in/yaml.v3"
)

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

// Import handles POST /templates/import
// Accepts a JSON body with the template name and files content.
func (h *TemplatesHandler) Import(c *gin.Context) {
	var body struct {
		Name  string            `json:"name" binding:"required"`
		Files map[string]string `json:"files" binding:"required"` // path → content
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Normalize name for directory
	dirName := ""
	for _, r := range body.Name {
		if r == ' ' {
			dirName += "-"
		} else if r >= 'A' && r <= 'Z' {
			dirName += string(r + 32)
		} else {
			dirName += string(r)
		}
	}

	destDir := filepath.Join(h.configsDir, dirName)
	if _, err := os.Stat(destDir); err == nil {
		c.JSON(http.StatusConflict, gin.H{"error": "template already exists", "id": dirName})
		return
	}

	// Write files
	for relPath, content := range body.Files {
		fullPath := filepath.Join(destDir, relPath)
		if err := os.MkdirAll(filepath.Dir(fullPath), 0755); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create directory"})
			return
		}
		if err := os.WriteFile(fullPath, []byte(content), 0644); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to write file"})
			return
		}
	}

	// Auto-generate config.yaml if not provided
	if _, exists := body.Files["config.yaml"]; !exists {
		promptFiles := []string{}
		skills := []string{}
		for path := range body.Files {
			// Root .md files are prompt files
			if filepath.Dir(path) == "." && filepath.Ext(path) == ".md" {
				promptFiles = append(promptFiles, path)
			}
			// skills/*/SKILL.md
			parts := filepath.SplitList(path)
			if len(parts) == 0 {
				dir := filepath.Dir(path)
				parent := filepath.Dir(dir)
				if filepath.Base(parent) == "skills" || parent == "skills" {
					skillName := filepath.Base(dir)
					found := false
					for _, s := range skills {
						if s == skillName {
							found = true
							break
						}
					}
					if !found {
						skills = append(skills, skillName)
					}
				}
			}
		}

		// Detect skills from directory structure
		for path := range body.Files {
			if filepath.Base(path) == "SKILL.md" {
				dir := filepath.Dir(path)
				if filepath.Dir(dir) == "skills" {
					skillName := filepath.Base(dir)
					found := false
					for _, s := range skills {
						if s == skillName {
							found = true
							break
						}
					}
					if !found {
						skills = append(skills, skillName)
					}
				}
			}
		}

		configYaml := "name: " + body.Name + "\n"
		configYaml += "description: Imported agent\n"
		configYaml += "version: 1.0.0\n"
		configYaml += "tier: 1\n"
		configYaml += "model: anthropic:claude-haiku-4-5-20251001\n"
		configYaml += "\nprompt_files:\n"
		if len(promptFiles) > 0 {
			for _, f := range promptFiles {
				configYaml += "  - " + f + "\n"
			}
		} else {
			configYaml += "  - system-prompt.md\n"
		}
		configYaml += "\nskills:\n"
		if len(skills) > 0 {
			for _, s := range skills {
				configYaml += "  - " + s + "\n"
			}
		} else {
			configYaml += "  []\n"
		}
		configYaml += "\ntools: []\n"
		configYaml += "\na2a:\n  port: 8000\n  streaming: true\n  push_notifications: true\n"
		configYaml += "\nenv:\n  required:\n    - ANTHROPIC_API_KEY\n  optional: []\n"

		os.WriteFile(filepath.Join(destDir, "config.yaml"), []byte(configYaml), 0644)
	}

	c.JSON(http.StatusCreated, gin.H{
		"status": "imported",
		"id":     dirName,
		"name":   body.Name,
	})
}

// ReplaceFiles handles PUT /workspaces/:id/files
// Replaces the workspace's config files with uploaded content, then restarts.
func (h *TemplatesHandler) ReplaceFiles(c *gin.Context) {
	workspaceID := c.Param("id")

	var body struct {
		Files map[string]string `json:"files" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Find or create config directory for this workspace
	// Use workspace name from DB to find matching template dir
	ctx := c.Request.Context()
	var wsName string
	err := db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}

	// Normalize name for directory
	dirName := ""
	for _, r := range wsName {
		if r == ' ' {
			dirName += "-"
		} else if r >= 'A' && r <= 'Z' {
			dirName += string(r + 32)
		} else {
			dirName += string(r)
		}
	}

	destDir := filepath.Join(h.configsDir, dirName)

	// Clear existing files (except keeping the directory)
	if info, err := os.Stat(destDir); err == nil && info.IsDir() {
		os.RemoveAll(destDir)
	}

	// Write new files
	for relPath, content := range body.Files {
		fullPath := filepath.Join(destDir, relPath)
		os.MkdirAll(filepath.Dir(fullPath), 0755)
		if err := os.WriteFile(fullPath, []byte(content), 0644); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to write file: " + relPath})
			return
		}
	}

	// Auto-generate config.yaml if not provided
	if _, exists := body.Files["config.yaml"]; !exists {
		promptFiles := []string{}
		skills := []string{}
		for path := range body.Files {
			if filepath.Dir(path) == "." && filepath.Ext(path) == ".md" {
				promptFiles = append(promptFiles, path)
			}
			if filepath.Base(path) == "SKILL.md" && filepath.Dir(filepath.Dir(path)) == "skills" {
				skills = append(skills, filepath.Base(filepath.Dir(path)))
			}
		}

		cfg := "name: " + wsName + "\ndescription: Replaced agent files\nversion: 1.0.0\ntier: 1\nmodel: anthropic:claude-haiku-4-5-20251001\n\nprompt_files:\n"
		if len(promptFiles) > 0 {
			for _, f := range promptFiles {
				cfg += "  - " + f + "\n"
			}
		} else {
			cfg += "  - system-prompt.md\n"
		}
		cfg += "\nskills:\n"
		if len(skills) > 0 {
			for _, s := range skills {
				cfg += "  - " + s + "\n"
			}
		} else {
			cfg += "  []\n"
		}
		cfg += "\ntools: []\n\na2a:\n  port: 8000\n  streaming: true\n  push_notifications: true\n"
		cfg += "\nenv:\n  required:\n    - ANTHROPIC_API_KEY\n  optional: []\n"
		os.WriteFile(filepath.Join(destDir, "config.yaml"), []byte(cfg), 0644)
	}

	c.JSON(http.StatusOK, gin.H{
		"status":    "replaced",
		"workspace": workspaceID,
		"files":     len(body.Files),
		"config_dir": dirName,
	})
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
