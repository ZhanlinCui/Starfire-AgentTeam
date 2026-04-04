package bundle

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/google/uuid"
)

// ImportResult tracks the outcome of importing a bundle tree.
type ImportResult struct {
	WorkspaceID string         `json:"workspace_id"`
	Name        string         `json:"name"`
	Status      string         `json:"status"` // "provisioning" or "failed"
	Error       string         `json:"error,omitempty"`
	Children    []ImportResult `json:"children,omitempty"`
}

// Import provisions a workspace tree from a Bundle.
// It creates workspace records, writes config files to a temp dir, and triggers the provisioner.
func Import(
	ctx context.Context,
	b *Bundle,
	parentID *string,
	broadcaster *events.Broadcaster,
	prov *provisioner.Provisioner,
	platformURL string,
) ImportResult {
	// Generate fresh workspace ID
	wsID := uuid.New().String()

	result := ImportResult{
		WorkspaceID: wsID,
		Name:        b.Name,
		Status:      "provisioning",
	}

	// Create workspace record
	_, err := db.DB.ExecContext(ctx, `
		INSERT INTO workspaces (id, name, role, tier, status, parent_id, source_bundle_id)
		VALUES ($1, $2, $3, $4, 'provisioning', $5, $6)
	`, wsID, b.Name, nilIfEmpty(b.Description), b.Tier, parentID, b.ID)
	if err != nil {
		result.Status = "failed"
		result.Error = fmt.Sprintf("failed to create workspace record: %v", err)
		return result
	}

	broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_PROVISIONING", wsID, map[string]interface{}{
		"name":             b.Name,
		"tier":             b.Tier,
		"source_bundle_id": b.ID,
	})

	// Write config files to a temp directory for the provisioner
	configDir, err := writeBundleConfig(b)
	if err != nil {
		log.Printf("Import: failed to write config for %s: %v", wsID, err)
		result.Status = "failed"
		result.Error = err.Error()
		markFailed(ctx, wsID, broadcaster, err)
		return result
	}

	// Provision the container if provisioner is available
	if prov != nil {
		cfg := provisioner.WorkspaceConfig{
			WorkspaceID: wsID,
			ConfigPath:  configDir,
			Tier:        b.Tier,
			EnvVars:     map[string]string{},
			PlatformURL: platformURL,
			// PluginsPath set by caller if available
		}
		go func() {
			provCtx, cancel := context.WithTimeout(context.Background(), provisioner.ProvisionTimeout)
			defer cancel()
			if _, err := prov.Start(provCtx, cfg); err != nil {
				markFailed(provCtx, wsID, broadcaster, err)
			}
		}()
	}

	// Recursively import sub-workspaces
	for _, sub := range b.SubWorkspaces {
		childResult := Import(ctx, &sub, &wsID, broadcaster, prov, platformURL)
		result.Children = append(result.Children, childResult)
	}

	return result
}

// writeBundleConfig writes a bundle's config, prompt, and skill files to a temp directory.
func writeBundleConfig(b *Bundle) (string, error) {
	idPrefix := b.ID
	if len(idPrefix) > 8 {
		idPrefix = idPrefix[:8]
	}
	dir, err := os.MkdirTemp("", fmt.Sprintf("ws-bundle-%s-*", idPrefix))
	if err != nil {
		return "", fmt.Errorf("failed to create temp dir: %w", err)
	}

	// Write system-prompt.md
	if b.SystemPrompt != "" {
		if err := os.WriteFile(filepath.Join(dir, "system-prompt.md"), []byte(b.SystemPrompt), 0644); err != nil {
			return "", fmt.Errorf("failed to write system-prompt.md: %w", err)
		}
	}

	// Write config.yaml from prompts if present
	if configYaml, ok := b.Prompts["config.yaml"]; ok {
		if err := os.WriteFile(filepath.Join(dir, "config.yaml"), []byte(configYaml), 0644); err != nil {
			return "", fmt.Errorf("failed to write config.yaml: %w", err)
		}
	}

	// Write skills
	skillsDir := filepath.Join(dir, "skills")
	os.MkdirAll(skillsDir, 0755)
	for _, skill := range b.Skills {
		skillDir := filepath.Join(skillsDir, skill.ID)
		for relPath, content := range skill.Files {
			fullPath := filepath.Join(skillDir, relPath)
			os.MkdirAll(filepath.Dir(fullPath), 0755)
			os.WriteFile(fullPath, []byte(content), 0644)
		}
	}

	return dir, nil
}

func markFailed(ctx context.Context, wsID string, broadcaster *events.Broadcaster, err error) {
	db.DB.ExecContext(ctx,
		`UPDATE workspaces SET status = 'failed', updated_at = now() WHERE id = $1`, wsID)
	broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_PROVISION_FAILED", wsID, map[string]interface{}{
		"error": err.Error(),
	})
}

func nilIfEmpty(s string) interface{} {
	if s == "" {
		return nil
	}
	return s
}
