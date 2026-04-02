package bundle

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/agent-molecule/platform/internal/db"
)

// Export serializes a running workspace into a Bundle.
func Export(ctx context.Context, workspaceID, configsDir string) (*Bundle, error) {
	// Fetch workspace record
	var name, role, status string
	var tier int
	var agentCard []byte
	var parentID *string

	err := db.DB.QueryRowContext(ctx, `
		SELECT name, COALESCE(role, ''), tier, status,
		       COALESCE(agent_card, 'null'::jsonb), parent_id
		FROM workspaces WHERE id = $1
	`, workspaceID).Scan(&name, &role, &tier, &status, &agentCard, &parentID)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("workspace %s not found", workspaceID)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to fetch workspace: %w", err)
	}

	// Parse agent card
	var card interface{}
	if err := json.Unmarshal(agentCard, &card); err != nil {
		card = nil
	}

	b := &Bundle{
		Schema:      "1.0",
		ID:          workspaceID,
		Name:        name,
		Description: role,
		Tier:        tier,
		AgentCard:   card,
		Version:     "1.0.0",
	}

	// Try to find and read the config directory
	// Look for a config that matches the workspace name
	configPath := findConfigDir(configsDir, name)
	if configPath != "" {
		b.loadFromConfigDir(configPath)
	}

	// Recursively export sub-workspaces
	rows, err := db.DB.QueryContext(ctx,
		`SELECT id FROM workspaces WHERE parent_id = $1 AND status != 'removed'`, workspaceID)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var childID string
			if rows.Scan(&childID) == nil {
				childBundle, err := Export(ctx, childID, configsDir)
				if err == nil {
					b.SubWorkspaces = append(b.SubWorkspaces, *childBundle)
				}
			}
		}
	}

	if b.SubWorkspaces == nil {
		b.SubWorkspaces = []Bundle{}
	}
	if b.Skills == nil {
		b.Skills = []BundleSkill{}
	}
	if b.Tools == nil {
		b.Tools = []BundleTool{}
	}
	if b.Prompts == nil {
		b.Prompts = map[string]string{}
	}

	return b, nil
}

// loadFromConfigDir reads config files and skills from a workspace config directory.
func (b *Bundle) loadFromConfigDir(dir string) {
	// Read system-prompt.md
	if data, err := os.ReadFile(filepath.Join(dir, "system-prompt.md")); err == nil {
		b.SystemPrompt = string(data)
	}

	// Read config.yaml for model/tools
	if data, err := os.ReadFile(filepath.Join(dir, "config.yaml")); err == nil {
		b.Prompts["config.yaml"] = string(data)
	}

	// Read skills
	skillsDir := filepath.Join(dir, "skills")
	entries, err := os.ReadDir(skillsDir)
	if err != nil {
		return
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		skill := BundleSkill{
			ID:    entry.Name(),
			Name:  entry.Name(),
			Files: map[string]string{},
		}

		// Walk all files in the skill directory
		skillPath := filepath.Join(skillsDir, entry.Name())
		filepath.Walk(skillPath, func(path string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() {
				return nil
			}
			relPath, _ := filepath.Rel(skillPath, path)
			data, err := os.ReadFile(path)
			if err == nil {
				skill.Files[relPath] = string(data)
			}
			return nil
		})

		// Extract description from SKILL.md if present
		if content, ok := skill.Files["SKILL.md"]; ok {
			skill.Description = extractDescription(content)
		}

		b.Skills = append(b.Skills, skill)
	}
}

// findConfigDir tries to match a workspace name to a config directory.
// It checks for a directory whose config.yaml "name" field matches the workspace name,
// falling back to the first directory with a config.yaml if no name match is found.
func findConfigDir(configsDir, name string) string {
	entries, err := os.ReadDir(configsDir)
	if err != nil {
		return ""
	}

	var fallback string
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		configPath := filepath.Join(configsDir, e.Name(), "config.yaml")
		data, err := os.ReadFile(configPath)
		if err != nil {
			continue
		}
		// Check if the config name matches the workspace name
		if strings.Contains(string(data), "name: "+name) {
			return filepath.Join(configsDir, e.Name())
		}
		if fallback == "" {
			fallback = filepath.Join(configsDir, e.Name())
		}
	}
	return fallback
}

// extractDescription pulls the first non-empty line after YAML frontmatter.
func extractDescription(content string) string {
	inFrontmatter := false
	for _, line := range splitLines(content) {
		if line == "---" {
			inFrontmatter = !inFrontmatter
			continue
		}
		if !inFrontmatter && len(line) > 0 && line[0] != '#' {
			return line
		}
	}
	return ""
}

func splitLines(s string) []string {
	var lines []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			lines = append(lines, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		lines = append(lines, s[start:])
	}
	return lines
}
