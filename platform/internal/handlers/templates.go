package handlers

import (
	"net/http"
	"os"
	"path/filepath"

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
