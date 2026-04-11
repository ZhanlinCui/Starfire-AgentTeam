package handlers

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/agent-molecule/platform/internal/crypto"
	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/models"
	"github.com/agent-molecule/platform/internal/provisioner"
)

// provisionWorkspace handles async container deployment with timeout.
func (h *WorkspaceHandler) provisionWorkspace(workspaceID, templatePath string, configFiles map[string][]byte, payload models.CreateWorkspacePayload) {
	ctx, cancel := context.WithTimeout(context.Background(), provisioner.ProvisionTimeout)
	defer cancel()

	// Load global secrets first, then workspace-specific secrets (which override globals).
	envVars := map[string]string{}

	// 1. Global secrets (platform-wide defaults)
	globalRows, globalErr := db.DB.QueryContext(ctx,
		`SELECT key, encrypted_value FROM global_secrets`)
	if globalErr == nil {
		defer globalRows.Close()
		for globalRows.Next() {
			var k string
			var v []byte
			if globalRows.Scan(&k, &v) == nil {
				decrypted, decErr := crypto.Decrypt(v)
				if decErr != nil {
					log.Printf("Provisioner: failed to decrypt global secret %s: %v", k, decErr)
					continue
				}
				envVars[k] = string(decrypted)
			}
		}
	}

	// 2. Workspace-specific secrets (override globals with same key)
	rows, err := db.DB.QueryContext(ctx,
		`SELECT key, encrypted_value FROM workspace_secrets WHERE workspace_id = $1`, workspaceID)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var k string
			var v []byte
			if rows.Scan(&k, &v) == nil {
				decrypted, decErr := crypto.Decrypt(v)
				if decErr != nil {
					log.Printf("Provisioner: failed to decrypt secret %s: %v", k, decErr)
					continue
				}
				envVars[k] = string(decrypted)
			}
		}
	}

	pluginsPath, _ := filepath.Abs(filepath.Join(h.configsDir, "..", "plugins"))
	awarenessNamespace := h.loadAwarenessNamespace(ctx, workspaceID)
	cfg := h.buildProvisionerConfig(workspaceID, templatePath, configFiles, payload, envVars, pluginsPath, awarenessNamespace)

	url, err := h.provisioner.Start(ctx, cfg)
	if err != nil {
		log.Printf("Provisioner: failed to start workspace %s: %v", workspaceID, err)
		if _, dbErr := db.DB.ExecContext(ctx,
			`UPDATE workspaces SET status = 'failed', updated_at = now() WHERE id = $1`, workspaceID); dbErr != nil {
			log.Printf("Provisioner: failed to mark workspace %s as failed: %v", workspaceID, dbErr)
		}
		h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_PROVISION_FAILED", workspaceID, map[string]interface{}{
			"error": err.Error(),
		})
	} else if url != "" {
		// Pre-store the host-accessible URL (http://127.0.0.1:<port>) so the A2A proxy can reach the container.
		// The registry's ON CONFLICT preserves URLs starting with http://127.0.0.1 when the agent self-registers.
		if _, dbErr := db.DB.ExecContext(ctx, `UPDATE workspaces SET url = $1 WHERE id = $2`, url, workspaceID); dbErr != nil {
			log.Printf("Provisioner: failed to store URL for %s: %v", workspaceID, dbErr)
		}
		if cacheErr := db.CacheURL(ctx, workspaceID, url); cacheErr != nil {
			log.Printf("Provisioner: failed to cache URL for %s: %v", workspaceID, cacheErr)
		}
		// Also cache the Docker-internal URL for workspace-to-workspace discovery.
		// Containers on agent-molecule-net can reach each other by container name.
		internalURL := provisioner.InternalURL(workspaceID)
		if cacheErr := db.CacheInternalURL(ctx, workspaceID, internalURL); cacheErr != nil {
			log.Printf("Provisioner: failed to cache internal URL for %s: %v", workspaceID, cacheErr)
		}
	}
	// On success, the workspace will register via POST /registry/register
	// which transitions status to 'online' and broadcasts WORKSPACE_ONLINE
}

func workspaceAwarenessNamespace(workspaceID string) string {
	return fmt.Sprintf("workspace:%s", workspaceID)
}

func (h *WorkspaceHandler) loadAwarenessNamespace(ctx context.Context, workspaceID string) string {
	var awarenessNamespace string
	err := db.DB.QueryRowContext(ctx, `SELECT COALESCE(awareness_namespace, '') FROM workspaces WHERE id = $1`, workspaceID).Scan(&awarenessNamespace)
	if err != nil || awarenessNamespace == "" {
		return workspaceAwarenessNamespace(workspaceID)
	}
	return awarenessNamespace
}

func (h *WorkspaceHandler) buildProvisionerConfig(
	workspaceID, templatePath string,
	configFiles map[string][]byte,
	payload models.CreateWorkspacePayload,
	envVars map[string]string,
	pluginsPath, awarenessNamespace string,
) provisioner.WorkspaceConfig {
	// Per-workspace workspace_dir takes priority over global WORKSPACE_DIR env var.
	// If neither is set, the provisioner creates an isolated Docker volume.
	workspacePath := payload.WorkspaceDir
	if workspacePath == "" {
		// Check DB — needed for restarts where payload.WorkspaceDir isn't populated
		var dbDir string
		if err := db.DB.QueryRow(`SELECT COALESCE(workspace_dir, '') FROM workspaces WHERE id = $1`, workspaceID).Scan(&dbDir); err == nil && dbDir != "" {
			workspacePath = dbDir
		}
	}
	if workspacePath == "" {
		workspacePath = os.Getenv("WORKSPACE_DIR")
	}

	return provisioner.WorkspaceConfig{
		WorkspaceID:        workspaceID,
		TemplatePath:       templatePath,
		ConfigFiles:        configFiles,
		PluginsPath:        pluginsPath,
		WorkspacePath:      workspacePath,
		Tier:               payload.Tier,
		Runtime:            payload.Runtime,
		EnvVars:            envVars,
		PlatformURL:        h.platformURL,
		AwarenessURL:       os.Getenv("AWARENESS_URL"),
		AwarenessNamespace: awarenessNamespace,
	}
}

// findTemplateByName looks for a workspace-configs-templates directory matching a name.
func findTemplateByName(configsDir, name string) string {
	entries, err := os.ReadDir(configsDir)
	if err != nil {
		return ""
	}
	// Normalize name: "SEO Agent" → look for "seo-agent"
	normalized := strings.ToLower(strings.ReplaceAll(name, " ", "-"))
	for _, e := range entries {
		if e.IsDir() && e.Name() == normalized {
			return e.Name()
		}
	}
	// Also search by config.yaml name field (for templates like org-pm where dir name != workspace name)
	for _, e := range entries {
		if !e.IsDir() || strings.HasPrefix(e.Name(), "ws-") {
			continue
		}
		cfgPath := filepath.Join(configsDir, e.Name(), "config.yaml")
		data, err := os.ReadFile(cfgPath)
		if err != nil {
			continue
		}
		// Quick YAML name extraction (avoids importing yaml parser)
		for _, line := range strings.Split(string(data), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "name:") {
				cfgName := strings.TrimSpace(strings.TrimPrefix(line, "name:"))
				if strings.EqualFold(cfgName, name) {
					return e.Name()
				}
				break
			}
		}
	}
	return ""
}

// configDirName returns the standard config directory name for a workspace ID.
// Used by resolveConfigDir in templates.go for host-side template resolution.
func configDirName(workspaceID string) string {
	id := workspaceID
	if len(id) > 12 {
		id = id[:12]
	}
	return "ws-" + id
}

// ensureDefaultConfig generates minimal config files in memory for workspaces without a template.
// Returns a map of filename → content to be written into the container's /configs volume.
func (h *WorkspaceHandler) ensureDefaultConfig(workspaceID string, payload models.CreateWorkspacePayload) map[string][]byte {
	files := make(map[string][]byte)

	// Determine runtime
	runtime := payload.Runtime
	if runtime == "" {
		runtime = "langgraph"
	}

	// Generate a minimal config.yaml
	model := payload.Model
	if model == "" {
		if runtime == "claude-code" {
			model = "sonnet"
		} else {
			model = "anthropic:claude-sonnet-4-6"
		}
	}

	// Sanitize name/role for YAML safety — quote values that contain special chars
	safeName := strings.ReplaceAll(strings.ReplaceAll(payload.Name, "\n", " "), "\r", "")
	safeRole := strings.ReplaceAll(strings.ReplaceAll(payload.Role, "\n", " "), "\r", "")
	// Quote if contains YAML-breaking chars
	quoteName := safeName
	quoteRole := safeRole
	for _, special := range []string{":", "#", "'", "\"", "{", "}", "[", "]"} {
		if strings.Contains(safeName, special) {
			quoteName = fmt.Sprintf("%q", safeName)
			break
		}
	}
	for _, special := range []string{":", "#", "'", "\"", "{", "}", "[", "]"} {
		if strings.Contains(safeRole, special) {
			quoteRole = fmt.Sprintf("%q", safeRole)
			break
		}
	}
	configYAML := fmt.Sprintf("name: %s\ndescription: %s\nversion: 1.0.0\ntier: %d\nruntime: %s\n",
		quoteName, quoteRole, payload.Tier, runtime)

	// Model always at top level — config.py reads raw["model"] for all runtimes.
	configYAML += fmt.Sprintf("model: %s\n", model)

	// CLI runtimes need auth_token_file and timeout in runtime_config.
	// The model is NOT duplicated here — adapters read config.model (top-level).
	if runtime != "langgraph" && runtime != "deepagents" {
		configYAML += "runtime_config:\n  auth_token_file: .auth-token\n  timeout: 0\n"
	}

	files["config.yaml"] = []byte(configYAML)

	// Copy auth token from the default template if it exists (for CLI runtimes)
	if runtime != "langgraph" {
		defaultTokenPath := filepath.Join(h.configsDir, "claude-code-default", ".auth-token")
		if tokenData, err := os.ReadFile(defaultTokenPath); err == nil {
			files[".auth-token"] = tokenData
		}
	}

	log.Printf("Provisioner: generated %d config files for workspace %s (runtime: %s)", len(files), workspaceID, runtime)
	return files
}
