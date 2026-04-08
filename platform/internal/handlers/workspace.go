package handlers

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/agent-molecule/platform/internal/crypto"
	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/models"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// maxProxyRequestBody is the maximum size of an A2A proxy request body (1MB).
const maxProxyRequestBody = 1 << 20

// maxProxyResponseBody is the maximum size of an A2A proxy response body (10MB).
const maxProxyResponseBody = 10 << 20

// a2aClient is a shared HTTP client for proxying A2A requests to workspace agents.
var a2aClient = &http.Client{Timeout: 30 * time.Minute}

// restartMu prevents concurrent RestartByID calls for the same workspace
var restartMu sync.Map // map[workspaceID]*sync.Mutex

type WorkspaceHandler struct {
	broadcaster *events.Broadcaster
	provisioner *provisioner.Provisioner
	platformURL string
	configsDir  string // path to workspace-configs-templates/ (for reading templates)
}

func NewWorkspaceHandler(b *events.Broadcaster, p *provisioner.Provisioner, platformURL, configsDir string) *WorkspaceHandler {
	return &WorkspaceHandler{
		broadcaster: b,
		provisioner: p,
		platformURL: platformURL,
		configsDir:  configsDir,
	}
}

// Create handles POST /workspaces
func (h *WorkspaceHandler) Create(c *gin.Context) {
	var payload models.CreateWorkspacePayload
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	id := uuid.New().String()
	awarenessNamespace := workspaceAwarenessNamespace(id)
	if payload.Tier == 0 {
		payload.Tier = 1
	}

	ctx := c.Request.Context()

	// Convert empty role to NULL
	var role interface{}
	if payload.Role != "" {
		role = payload.Role
	}

	// Insert workspace
	_, err := db.DB.ExecContext(ctx, `
		INSERT INTO workspaces (id, name, role, tier, awareness_namespace, status, parent_id)
		VALUES ($1, $2, $3, $4, $5, 'provisioning', $6)
	`, id, payload.Name, role, payload.Tier, awarenessNamespace, payload.ParentID)
	if err != nil {
		log.Printf("Create workspace error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create workspace"})
		return
	}

	// Insert canvas layout
	_, err = db.DB.ExecContext(ctx, `
		INSERT INTO canvas_layouts (workspace_id, x, y) VALUES ($1, $2, $3)
	`, id, payload.Canvas.X, payload.Canvas.Y)
	if err != nil {
		log.Printf("Create canvas layout error: %v", err)
	}

	// Broadcast provisioning event
	h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_PROVISIONING", id, map[string]interface{}{
		"name": payload.Name,
		"tier": payload.Tier,
	})

	// Auto-provision — always start a container
	if h.provisioner != nil {
		var templatePath string
		var configFiles map[string][]byte
		if payload.Template != "" {
			templatePath = filepath.Join(h.configsDir, payload.Template)
			// Read runtime from template config.yaml if not specified in request
			if payload.Runtime == "" {
				cfgData, _ := os.ReadFile(filepath.Join(templatePath, "config.yaml"))
				for _, line := range strings.Split(string(cfgData), "\n") {
					line = strings.TrimSpace(line)
					if strings.HasPrefix(line, "runtime:") {
						payload.Runtime = strings.TrimSpace(strings.TrimPrefix(line, "runtime:"))
						break
					}
				}
			}
		} else {
			// No template — generate config files in memory
			configFiles = h.ensureDefaultConfig(id, payload)
		}
		go h.provisionWorkspace(id, templatePath, configFiles, payload)
	}

	c.JSON(http.StatusCreated, gin.H{
		"id":                  id,
		"status":              "provisioning",
		"awareness_namespace": awarenessNamespace,
	})
}

// scanWorkspaceRow is a helper to scan workspace+layout rows into a clean JSON map.
func scanWorkspaceRow(rows interface {
	Scan(dest ...interface{}) error
}) (map[string]interface{}, error) {
	var id, name, role, status, url, sampleError, currentTask string
	var tier, activeTasks, uptimeSeconds int
	var errorRate, x, y float64
	var collapsed bool
	var parentID *string
	var agentCard []byte

	err := rows.Scan(&id, &name, &role, &tier, &status, &agentCard, &url,
		&parentID, &activeTasks, &errorRate, &sampleError, &uptimeSeconds,
		&currentTask, &x, &y, &collapsed)
	if err != nil {
		return nil, err
	}

	ws := map[string]interface{}{
		"id":                id,
		"name":              name,
		"tier":              tier,
		"status":            status,
		"url":               url,
		"parent_id":         parentID,
		"active_tasks":      activeTasks,
		"last_error_rate":   errorRate,
		"last_sample_error": sampleError,
		"uptime_seconds":    uptimeSeconds,
		"current_task":      currentTask,
		"x":                 x,
		"y":                 y,
		"collapsed":         collapsed,
	}

	// Only include non-empty values
	if role != "" {
		ws["role"] = role
	} else {
		ws["role"] = nil
	}

	// Parse agent_card as raw JSON
	if len(agentCard) > 0 && string(agentCard) != "null" {
		ws["agent_card"] = json.RawMessage(agentCard)
	} else {
		ws["agent_card"] = nil
	}

	return ws, nil
}

const workspaceListQuery = `
	SELECT w.id, w.name, COALESCE(w.role, ''), w.tier, w.status,
		   COALESCE(w.agent_card, 'null'::jsonb), COALESCE(w.url, ''),
		   w.parent_id, w.active_tasks, w.last_error_rate,
		   COALESCE(w.last_sample_error, ''), w.uptime_seconds,
		   COALESCE(w.current_task, ''),
		   COALESCE(cl.x, 0), COALESCE(cl.y, 0), COALESCE(cl.collapsed, false)
	FROM workspaces w
	LEFT JOIN canvas_layouts cl ON cl.workspace_id = w.id
	WHERE w.status != 'removed'
	ORDER BY w.created_at`

// List handles GET /workspaces
func (h *WorkspaceHandler) List(c *gin.Context) {
	rows, err := db.DB.QueryContext(c.Request.Context(), workspaceListQuery)
	if err != nil {
		log.Printf("List workspaces error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query failed"})
		return
	}
	defer rows.Close()

	workspaces := make([]map[string]interface{}, 0)
	for rows.Next() {
		ws, err := scanWorkspaceRow(rows)
		if err != nil {
			log.Printf("List scan error: %v", err)
			continue
		}
		workspaces = append(workspaces, ws)
	}

	c.JSON(http.StatusOK, workspaces)
}

// Get handles GET /workspaces/:id
func (h *WorkspaceHandler) Get(c *gin.Context) {
	id := c.Param("id")

	row := db.DB.QueryRowContext(c.Request.Context(), `
		SELECT w.id, w.name, COALESCE(w.role, ''), w.tier, w.status,
			   COALESCE(w.agent_card, 'null'::jsonb), COALESCE(w.url, ''),
			   w.parent_id, w.active_tasks, w.last_error_rate,
			   COALESCE(w.last_sample_error, ''), w.uptime_seconds,
			   COALESCE(w.current_task, ''),
			   COALESCE(cl.x, 0), COALESCE(cl.y, 0), COALESCE(cl.collapsed, false)
		FROM workspaces w
		LEFT JOIN canvas_layouts cl ON cl.workspace_id = w.id
		WHERE w.id = $1
	`, id)

	ws, err := scanWorkspaceRow(row)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}
	if err != nil {
		log.Printf("Get workspace error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query failed"})
		return
	}

	c.JSON(http.StatusOK, ws)
}

// Update handles PATCH /workspaces/:id
func (h *WorkspaceHandler) Update(c *gin.Context) {
	id := c.Param("id")

	var body map[string]interface{}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()

	if name, ok := body["name"]; ok {
		if _, err := db.DB.ExecContext(ctx, `UPDATE workspaces SET name = $2, updated_at = now() WHERE id = $1`, id, name); err != nil {
			log.Printf("Update name error for %s: %v", id, err)
		}
	}
	if role, ok := body["role"]; ok {
		if _, err := db.DB.ExecContext(ctx, `UPDATE workspaces SET role = $2, updated_at = now() WHERE id = $1`, id, role); err != nil {
			log.Printf("Update role error for %s: %v", id, err)
		}
	}
	if tier, ok := body["tier"]; ok {
		if _, err := db.DB.ExecContext(ctx, `UPDATE workspaces SET tier = $2, updated_at = now() WHERE id = $1`, id, tier); err != nil {
			log.Printf("Update tier error for %s: %v", id, err)
		}
	}
	if parentID, ok := body["parent_id"]; ok {
		if _, err := db.DB.ExecContext(ctx, `UPDATE workspaces SET parent_id = $2, updated_at = now() WHERE id = $1`, id, parentID); err != nil {
			log.Printf("Update parent_id error for %s: %v", id, err)
		}
	}

	// Update canvas position if both x and y provided
	if x, xOk := body["x"]; xOk {
		if y, yOk := body["y"]; yOk {
			if _, err := db.DB.ExecContext(ctx, `
				INSERT INTO canvas_layouts (workspace_id, x, y)
				VALUES ($1, $2, $3)
				ON CONFLICT (workspace_id) DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y
			`, id, x, y); err != nil {
				log.Printf("Update position error for %s: %v", id, err)
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{"status": "updated"})
}

// Delete handles DELETE /workspaces/:id
// If the workspace has children (is a team), cascade deletes all sub-workspaces.
// Use ?confirm=true to actually delete (otherwise returns children list for confirmation).
func (h *WorkspaceHandler) Delete(c *gin.Context) {
	id := c.Param("id")
	ctx := c.Request.Context()
	confirm := c.Query("confirm") == "true"

	// Check for children
	rows, err := db.DB.QueryContext(ctx,
		`SELECT id, name FROM workspaces WHERE parent_id = $1 AND status != 'removed'`, id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to check children"})
		return
	}
	defer rows.Close()

	var children []map[string]string
	for rows.Next() {
		var childID, childName string
		if rows.Scan(&childID, &childName) == nil {
			children = append(children, map[string]string{"id": childID, "name": childName})
		}
	}

	// If has children and not confirmed, return children list for confirmation
	if len(children) > 0 && !confirm {
		c.JSON(http.StatusOK, gin.H{
			"status":         "confirmation_required",
			"message":        "This workspace has sub-workspaces. Delete with ?confirm=true to cascade delete.",
			"children":       children,
			"children_count": len(children),
		})
		return
	}

	// Cascade delete children
	for _, child := range children {
		childID := child["id"]
		// Stop container and remove config volume if provisioner available
		if h.provisioner != nil {
			h.provisioner.Stop(ctx, childID)
			if err := h.provisioner.RemoveVolume(ctx, childID); err != nil {
				log.Printf("Delete child %s volume removal warning: %v", childID, err)
			}
		}
		if _, err := db.DB.ExecContext(ctx, `UPDATE workspaces SET status = 'removed', updated_at = now() WHERE id = $1`, childID); err != nil {
			log.Printf("Delete child %s status update error: %v", childID, err)
		}
		if _, err := db.DB.ExecContext(ctx, `DELETE FROM canvas_layouts WHERE workspace_id = $1`, childID); err != nil {
			log.Printf("Delete child %s layout error: %v", childID, err)
		}
		h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_REMOVED", childID, map[string]interface{}{})
	}

	// Delete the workspace itself
	if h.provisioner != nil {
		h.provisioner.Stop(ctx, id)
		if err := h.provisioner.RemoveVolume(ctx, id); err != nil {
			log.Printf("Delete %s volume removal warning: %v", id, err)
		}
	}
	if _, err := db.DB.ExecContext(ctx, `UPDATE workspaces SET status = 'removed', updated_at = now() WHERE id = $1`, id); err != nil {
		log.Printf("Delete %s status update error: %v", id, err)
	}
	if _, err := db.DB.ExecContext(ctx, `DELETE FROM canvas_layouts WHERE workspace_id = $1`, id); err != nil {
		log.Printf("Delete %s layout error: %v", id, err)
	}

	h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_REMOVED", id, map[string]interface{}{
		"cascade_deleted": len(children),
	})

	c.JSON(http.StatusOK, gin.H{"status": "removed", "cascade_deleted": len(children)})
}

// provisionWorkspace handles async container deployment with timeout.
func (h *WorkspaceHandler) provisionWorkspace(workspaceID, templatePath string, configFiles map[string][]byte, payload models.CreateWorkspacePayload) {
	ctx, cancel := context.WithTimeout(context.Background(), provisioner.ProvisionTimeout)
	defer cancel()

	// Load secrets for this workspace from DB
	envVars := map[string]string{}
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
		db.DB.ExecContext(ctx,
			`UPDATE workspaces SET status = 'failed', updated_at = now() WHERE id = $1`, workspaceID)
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
	return provisioner.WorkspaceConfig{
		WorkspaceID:        workspaceID,
		TemplatePath:       templatePath,
		ConfigFiles:        configFiles,
		PluginsPath:        pluginsPath,
		WorkspacePath:      os.Getenv("WORKSPACE_DIR"), // If set, bind-mount host dir as /workspace
		Tier:               payload.Tier,
		Runtime:            payload.Runtime,
		EnvVars:            envVars,
		PlatformURL:        h.platformURL,
		AwarenessURL:       os.Getenv("AWARENESS_URL"),
		AwarenessNamespace: awarenessNamespace,
	}
}

// Restart handles POST /workspaces/:id/restart
// Works for offline, failed, or degraded workspaces. Stops any existing container, then re-provisions.
func (h *WorkspaceHandler) Restart(c *gin.Context) {
	id := c.Param("id")
	ctx := c.Request.Context()

	var status, wsName string
	var tier int
	err := db.DB.QueryRowContext(ctx,
		`SELECT status, name, tier FROM workspaces WHERE id = $1`, id,
	).Scan(&status, &wsName, &tier)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "lookup failed"})
		return
	}
	// Allow restart even when online (force restart) — stops existing container first

	if h.provisioner == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "provisioner not available"})
		return
	}

	// Stop existing container if any
	h.provisioner.Stop(ctx, id)

	// Reset to provisioning
	db.DB.ExecContext(ctx,
		`UPDATE workspaces SET status = 'provisioning', url = '', updated_at = now() WHERE id = $1`, id)
	h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_PROVISIONING", id, map[string]interface{}{
		"name": wsName,
		"tier": tier,
	})

	// Read template from request body or try to find matching config
	var body struct {
		Template string `json:"template"`
	}
	c.ShouldBindJSON(&body)

	// Resolve template path in priority order:
	// 1. Explicit template from request body
	// 2. Name-based match in templates directory
	// 3. No template — the volume already has configs from previous run (or generate defaults)
	var templatePath string
	var configFiles map[string][]byte
	configLabel := "existing-volume"

	template := body.Template
	if template == "" {
		template = findTemplateByName(h.configsDir, wsName)
	}
	if template != "" {
		candidatePath := filepath.Join(h.configsDir, template)
		if _, err := os.Stat(candidatePath); err == nil {
			templatePath = candidatePath
			configLabel = template
		}
	}

	// If no template found and this is a fresh start, generate default config
	if templatePath == "" {
		// The named volume may already have configs from the previous run.
		// Only generate defaults if the volume is new (checked by provisioner).
		log.Printf("Restart: reusing existing config volume for %s (%s)", wsName, id)
	}
	if templatePath != "" {
		log.Printf("Restart: using template %s for %s (%s)", templatePath, wsName, id)
	}

	payload := models.CreateWorkspacePayload{Name: wsName, Tier: tier}
	// Read runtime from template config.yaml for image selection
	if templatePath != "" {
		cfgData, _ := os.ReadFile(filepath.Join(templatePath, "config.yaml"))
		for _, line := range strings.Split(string(cfgData), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "runtime:") {
				payload.Runtime = strings.TrimSpace(strings.TrimPrefix(line, "runtime:"))
				break
			}
		}
	}
	go h.provisionWorkspace(id, templatePath, configFiles, payload)

	c.JSON(http.StatusOK, gin.H{"status": "provisioning", "config_dir": configLabel})
}

// RestartByID restarts a workspace by ID — for programmatic use (e.g., auto-restart after secret change).
func (h *WorkspaceHandler) RestartByID(workspaceID string) {
	if h.provisioner == nil {
		return
	}

	// Per-workspace mutex — skip if already restarting (last-write-wins)
	mu, _ := restartMu.LoadOrStore(workspaceID, &sync.Mutex{})
	wsMu := mu.(*sync.Mutex)
	if !wsMu.TryLock() {
		log.Printf("Auto-restart: skipping %s — restart already in progress", workspaceID)
		return
	}
	defer wsMu.Unlock()

	ctx := context.Background()

	var wsName, status string
	var tier int
	err := db.DB.QueryRowContext(ctx,
		`SELECT name, status, tier FROM workspaces WHERE id = $1 AND status != 'removed'`, workspaceID,
	).Scan(&wsName, &status, &tier)
	if err != nil {
		return
	}

	// If still provisioning, brief wait so container exists for Stop()
	if status == "provisioning" {
		log.Printf("Auto-restart: interrupting provisioning for %s (%s)", wsName, workspaceID)
		time.Sleep(10 * time.Second)
	}

	log.Printf("Auto-restart: restarting %s (%s) after secret change (was: %s)", wsName, workspaceID, status)

	h.provisioner.Stop(ctx, workspaceID)

	db.DB.ExecContext(ctx,
		`UPDATE workspaces SET status = 'provisioning', url = '', updated_at = now() WHERE id = $1`, workspaceID)
	h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_PROVISIONING", workspaceID, map[string]interface{}{
		"name": wsName, "tier": tier,
	})

	var templatePath string
	var configFiles map[string][]byte
	template := findTemplateByName(h.configsDir, wsName)
	if template != "" {
		candidatePath := filepath.Join(h.configsDir, template)
		if _, err := os.Stat(candidatePath); err == nil {
			templatePath = candidatePath
		}
	}

	payload := models.CreateWorkspacePayload{Name: wsName, Tier: tier}
	if templatePath != "" {
		cfgData, _ := os.ReadFile(filepath.Join(templatePath, "config.yaml"))
		for _, line := range strings.Split(string(cfgData), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "runtime:") {
				payload.Runtime = strings.TrimSpace(strings.TrimPrefix(line, "runtime:"))
				break
			}
		}
	}
	go h.provisionWorkspace(workspaceID, templatePath, configFiles, payload)
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

	if runtime != "langgraph" {
		configYAML += fmt.Sprintf("runtime_config:\n  model: %s\n  auth_token_file: .auth-token\n  timeout: 300\n", model)
	} else {
		configYAML += fmt.Sprintf("model: %s\n", model)
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

// ProxyA2A handles POST /workspaces/:id/a2a
// Proxies A2A JSON-RPC requests from the canvas to workspace agents,
// avoiding CORS and Docker network issues.
func (h *WorkspaceHandler) ProxyA2A(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	// Resolve workspace URL (cache first, then DB)
	agentURL, err := db.GetCachedURL(ctx, workspaceID)
	if err != nil {
		var urlNullable sql.NullString
		var status string
		err := db.DB.QueryRowContext(ctx,
			`SELECT url, status FROM workspaces WHERE id = $1`, workspaceID,
		).Scan(&urlNullable, &status)
		if err == sql.ErrNoRows {
			c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
			return
		}
		if err != nil {
			log.Printf("ProxyA2A lookup error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "lookup failed"})
			return
		}
		if !urlNullable.Valid || urlNullable.String == "" {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "workspace has no URL", "status": status})
			return
		}
		agentURL = urlNullable.String
		db.CacheURL(ctx, workspaceID, agentURL)
	}

	// Read the incoming request body (capped at 1MB)
	body, err := io.ReadAll(io.LimitReader(c.Request.Body, maxProxyRequestBody))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "failed to read request body"})
		return
	}

	// Normalize the request into a valid A2A JSON-RPC 2.0 message
	var payload map[string]interface{}
	if err := json.Unmarshal(body, &payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid JSON"})
		return
	}

	// Wrap in JSON-RPC envelope if missing
	if _, hasJSONRPC := payload["jsonrpc"]; !hasJSONRPC {
		payload = map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      uuid.New().String(),
			"method":  payload["method"],
			"params":  payload["params"],
		}
	}

	// Ensure params.message.messageId exists (required by a2a-sdk)
	if params, ok := payload["params"].(map[string]interface{}); ok {
		if msg, ok := params["message"].(map[string]interface{}); ok {
			if _, hasID := msg["messageId"]; !hasID {
				msg["messageId"] = uuid.New().String()
			}
		}
	}

	marshaledBody, marshalErr := json.Marshal(payload)
	if marshalErr != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to marshal request"})
		return
	}
	body = marshaledBody

	// Extract method for logging
	var a2aMethod string
	if m, ok := payload["method"].(string); ok {
		a2aMethod = m
	}

	// Extract caller workspace ID from X-Workspace-ID header (if agent-to-agent)
	callerID := c.GetHeader("X-Workspace-ID")

	// Forward to the agent — no timeout. Agent liveness is monitored via heartbeat;
	// if the agent dies, the TCP connection drops and the proxy returns an error.
	// Delegation chains (PM → Lead → Agent) can take arbitrarily long.
	// WithoutCancel: survives client disconnect but still cancels on server shutdown.
	startTime := time.Now()
	req, err := http.NewRequestWithContext(context.WithoutCancel(ctx), "POST", agentURL, bytes.NewReader(body))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create proxy request"})
		return
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := a2aClient.Do(req)
	durationMs := int(time.Since(startTime).Milliseconds())
	if err != nil {
		log.Printf("ProxyA2A forward error: %v", err)
		// Log failed A2A attempt (detached context — request may be done)
		errMsg := err.Error()
		var errWsName string
		db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&errWsName)
		if errWsName == "" {
			errWsName = workspaceID
		}
		summary := "A2A request to " + errWsName + " failed: " + errMsg
		go LogActivity(context.WithoutCancel(ctx), h.broadcaster, ActivityParams{
			WorkspaceID:  workspaceID,
			ActivityType: "a2a_receive",
			SourceID:     nilIfEmpty(callerID),
			TargetID:     &workspaceID,
			Method:       &a2aMethod,
			Summary:      &summary,
			RequestBody:  json.RawMessage(body),
			DurationMs:   &durationMs,
			Status:       "error",
			ErrorDetail:  &errMsg,
		})
		c.JSON(http.StatusBadGateway, gin.H{"error": "failed to reach workspace agent"})
		return
	}
	defer resp.Body.Close()

	// Read agent response (capped at 10MB)
	respBody, err := io.ReadAll(io.LimitReader(resp.Body, maxProxyResponseBody))
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "failed to read agent response"})
		return
	}

	// Log successful A2A communication
	logStatus := "ok"
	if resp.StatusCode >= 400 {
		logStatus = "error"
	}
	// Resolve workspace name for readable summary
	var wsNameForLog string
	db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsNameForLog)
	if wsNameForLog == "" {
		wsNameForLog = workspaceID
	}
	summary := a2aMethod + " → " + wsNameForLog
	go LogActivity(context.WithoutCancel(ctx), h.broadcaster, ActivityParams{
		WorkspaceID:  workspaceID,
		ActivityType: "a2a_receive",
		SourceID:     nilIfEmpty(callerID),
		TargetID:     &workspaceID,
		Method:       &a2aMethod,
		Summary:      &summary,
		RequestBody:  json.RawMessage(body),
		ResponseBody: json.RawMessage(respBody),
		DurationMs:   &durationMs,
		Status:       logStatus,
	})

	c.Data(resp.StatusCode, "application/json", respBody)
}

func nilIfEmpty(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}
