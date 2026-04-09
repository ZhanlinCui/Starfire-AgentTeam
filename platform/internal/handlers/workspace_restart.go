package handlers

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/models"
	"github.com/gin-gonic/gin"
)

// restartMu prevents concurrent RestartByID calls for the same workspace
var restartMu sync.Map // map[workspaceID]*sync.Mutex

// Restart handles POST /workspaces/:id/restart
// Works for offline, failed, or degraded workspaces. Stops any existing container, then re-provisions.
func (h *WorkspaceHandler) Restart(c *gin.Context) {
	id := c.Param("id")
	ctx := c.Request.Context()

	var status, wsName, dbRuntime string
	var tier int
	err := db.DB.QueryRowContext(ctx,
		`SELECT status, name, tier, COALESCE(runtime, 'langgraph') FROM workspaces WHERE id = $1`, id,
	).Scan(&status, &wsName, &tier, &dbRuntime)
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
		Template       string `json:"template"`
		ApplyTemplate  bool   `json:"apply_template"`  // force re-apply runtime-default template (e.g. after runtime change)
	}
	c.ShouldBindJSON(&body)

	// Resolve template path in priority order:
	// 1. Explicit template from request body
	// 2. Runtime-specific default template (e.g. claude-code-default/)
	// 3. Name-based match in templates directory
	// 4. No template — the volume already has configs from previous run
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

	if templatePath == "" {
		log.Printf("Restart: reusing existing config volume for %s (%s)", wsName, id)
	} else {
		log.Printf("Restart: using template %s for %s (%s)", templatePath, wsName, id)
	}

	// Runtime comes from DB — single source of truth, no Docker gymnastics needed
	payload := models.CreateWorkspacePayload{Name: wsName, Tier: tier, Runtime: dbRuntime}
	log.Printf("Restart: workspace %s (%s) runtime=%q", wsName, id, dbRuntime)

	// Apply runtime-default template ONLY when explicitly requested via "apply_template": true.
	// Use case: runtime was changed via Config tab — need new runtime's base files.
	// Normal restarts preserve existing config volume (user's model, skills, prompts).
	if templatePath == "" && body.ApplyTemplate && dbRuntime != "" {
		runtimeTemplate := filepath.Join(h.configsDir, dbRuntime+"-default")
		if _, err := os.Stat(runtimeTemplate); err == nil {
			templatePath = runtimeTemplate
			configLabel = dbRuntime + "-default"
			log.Printf("Restart: applying template %s (runtime change)", configLabel)
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

	var wsName, status, dbRuntime string
	var tier int
	err := db.DB.QueryRowContext(ctx,
		`SELECT name, status, tier, COALESCE(runtime, 'langgraph') FROM workspaces WHERE id = $1 AND status NOT IN ('removed', 'paused')`, workspaceID,
	).Scan(&wsName, &status, &tier, &dbRuntime)
	if err != nil {
		return // includes paused — don't auto-restart paused workspaces
	}

	// If still provisioning, brief wait so container exists for Stop()
	if status == "provisioning" {
		log.Printf("Auto-restart: interrupting provisioning for %s (%s)", wsName, workspaceID)
		time.Sleep(10 * time.Second)
	}

	log.Printf("Auto-restart: restarting %s (%s) runtime=%q after secret change (was: %s)", wsName, workspaceID, dbRuntime, status)

	h.provisioner.Stop(ctx, workspaceID)

	db.DB.ExecContext(ctx,
		`UPDATE workspaces SET status = 'provisioning', url = '', updated_at = now() WHERE id = $1`, workspaceID)
	h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_PROVISIONING", workspaceID, map[string]interface{}{
		"name": wsName, "tier": tier,
	})

	// Runtime from DB — no more config file parsing
	payload := models.CreateWorkspacePayload{Name: wsName, Tier: tier, Runtime: dbRuntime}

	// On auto-restart, do NOT re-apply templates — preserve existing config volume.
	go h.provisionWorkspace(workspaceID, "", nil, payload)
}

// Pause handles POST /workspaces/:id/pause
// Stops the container and sets status to 'paused'. The workspace remains on the canvas
// but won't receive heartbeats, won't be auto-restarted, and won't consume resources.
// Config volume is preserved — resume will re-provision with the same config.
func (h *WorkspaceHandler) Pause(c *gin.Context) {
	id := c.Param("id")
	ctx := c.Request.Context()

	var status, wsName string
	err := db.DB.QueryRowContext(ctx,
		`SELECT status, name FROM workspaces WHERE id = $1 AND status NOT IN ('removed', 'paused')`, id,
	).Scan(&status, &wsName)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found or already paused"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "lookup failed"})
		return
	}

	// Stop container if provisioner is available
	if h.provisioner != nil {
		h.provisioner.Stop(ctx, id)
	}

	// Mark as paused — health sweep and liveness monitor will skip this workspace
	db.DB.ExecContext(ctx,
		`UPDATE workspaces SET status = 'paused', url = '', updated_at = now() WHERE id = $1`, id)
	db.ClearWorkspaceKeys(ctx, id)

	h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_PAUSED", id, map[string]interface{}{
		"name": wsName,
	})

	log.Printf("Paused workspace %s (%s)", wsName, id)
	c.JSON(http.StatusOK, gin.H{"status": "paused"})
}

// Resume handles POST /workspaces/:id/resume
// Re-provisions a paused workspace. Config volume is preserved from before the pause.
func (h *WorkspaceHandler) Resume(c *gin.Context) {
	id := c.Param("id")
	ctx := c.Request.Context()

	var wsName, dbRuntime string
	var tier int
	err := db.DB.QueryRowContext(ctx,
		`SELECT name, tier, COALESCE(runtime, 'langgraph') FROM workspaces WHERE id = $1 AND status = 'paused'`, id,
	).Scan(&wsName, &tier, &dbRuntime)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found or not paused"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "lookup failed"})
		return
	}

	if h.provisioner == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "provisioner not available"})
		return
	}

	db.DB.ExecContext(ctx,
		`UPDATE workspaces SET status = 'provisioning', updated_at = now() WHERE id = $1`, id)
	h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_PROVISIONING", id, map[string]interface{}{
		"name": wsName, "tier": tier,
	})

	payload := models.CreateWorkspacePayload{Name: wsName, Tier: tier, Runtime: dbRuntime}
	// Resume uses existing config volume — no template needed
	go h.provisionWorkspace(id, "", nil, payload)

	log.Printf("Resuming workspace %s (%s)", wsName, id)
	c.JSON(http.StatusOK, gin.H{"status": "provisioning"})
}
