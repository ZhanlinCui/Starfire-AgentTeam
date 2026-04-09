package handlers

import (
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/models"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

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
	if payload.Runtime == "" {
		payload.Runtime = "langgraph"
	}

	ctx := c.Request.Context()

	// Convert empty role to NULL
	var role interface{}
	if payload.Role != "" {
		role = payload.Role
	}

	// Convert empty workspace_dir to NULL
	var workspaceDir interface{}
	if payload.WorkspaceDir != "" {
		workspaceDir = payload.WorkspaceDir
	}

	// Insert workspace with runtime persisted in DB
	_, err := db.DB.ExecContext(ctx, `
		INSERT INTO workspaces (id, name, role, tier, runtime, awareness_namespace, status, parent_id, workspace_dir)
		VALUES ($1, $2, $3, $4, $5, $6, 'provisioning', $7, $8)
	`, id, payload.Name, role, payload.Tier, payload.Runtime, awarenessNamespace, payload.ParentID, workspaceDir)
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

	// External workspaces: no container provisioning — just set the URL and mark online
	if payload.External {
		if payload.URL != "" {
			db.DB.ExecContext(ctx, `UPDATE workspaces SET url = $1, status = 'online', updated_at = now() WHERE id = $2`, payload.URL, id)
			if err := db.CacheURL(ctx, id, payload.URL); err != nil {
				log.Printf("External workspace: failed to cache URL for %s: %v", id, err)
			}
		} else {
			db.DB.ExecContext(ctx, `UPDATE workspaces SET status = 'online', updated_at = now() WHERE id = $1`, id)
		}
		h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_ONLINE", id, map[string]interface{}{
			"name": payload.Name, "external": true,
		})
		log.Printf("Created external workspace %s (%s) at %s", payload.Name, id, payload.URL)
		c.JSON(http.StatusCreated, gin.H{
			"id":       id,
			"status":   "online",
			"external": true,
		})
		return
	}

	// Auto-provision — start a container
	if h.provisioner != nil {
		var templatePath string
		var configFiles map[string][]byte
		if payload.Template != "" {
			candidatePath := filepath.Join(h.configsDir, payload.Template)
			if _, err := os.Stat(candidatePath); err == nil {
				templatePath = candidatePath
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
				// Template not found — try runtime-default template, then generate config
				log.Printf("Create: template %q not found, falling back for %s", payload.Template, payload.Name)
				runtimeDefault := filepath.Join(h.configsDir, payload.Runtime+"-default")
				if _, err := os.Stat(runtimeDefault); err == nil {
					templatePath = runtimeDefault
					log.Printf("Create: using runtime-default template %s for %s", payload.Runtime+"-default", payload.Name)
				} else {
					configFiles = h.ensureDefaultConfig(id, payload)
					log.Printf("Create: generating default config for %s (runtime=%s)", payload.Name, payload.Runtime)
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
	var id, name, role, status, url, sampleError, currentTask, runtime, workspaceDir string
	var tier, activeTasks, uptimeSeconds int
	var errorRate, x, y float64
	var collapsed bool
	var parentID *string
	var agentCard []byte

	err := rows.Scan(&id, &name, &role, &tier, &status, &agentCard, &url,
		&parentID, &activeTasks, &errorRate, &sampleError, &uptimeSeconds,
		&currentTask, &runtime, &workspaceDir, &x, &y, &collapsed)
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
		"runtime":           runtime,
		"workspace_dir":     nilIfEmpty(workspaceDir),
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
		   COALESCE(w.current_task, ''), COALESCE(w.runtime, 'langgraph'),
		   COALESCE(w.workspace_dir, ''),
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
			   COALESCE(w.current_task, ''), COALESCE(w.runtime, 'langgraph'),
			   COALESCE(w.workspace_dir, ''),
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
	if runtime, ok := body["runtime"]; ok {
		if _, err := db.DB.ExecContext(ctx, `UPDATE workspaces SET runtime = $2, updated_at = now() WHERE id = $1`, id, runtime); err != nil {
			log.Printf("Update runtime error for %s: %v", id, err)
		}
	}
	if wsDir, ok := body["workspace_dir"]; ok {
		if _, err := db.DB.ExecContext(ctx, `UPDATE workspaces SET workspace_dir = $2, updated_at = now() WHERE id = $1`, id, wsDir); err != nil {
			log.Printf("Update workspace_dir error for %s: %v", id, err)
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
