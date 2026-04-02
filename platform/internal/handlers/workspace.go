package handlers

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/models"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// maxProxyRequestBody is the maximum size of an A2A proxy request body (1MB).
const maxProxyRequestBody = 1 << 20

// maxProxyResponseBody is the maximum size of an A2A proxy response body (10MB).
const maxProxyResponseBody = 10 << 20

// a2aClient is a shared HTTP client for proxying A2A requests to workspace agents.
var a2aClient = &http.Client{Timeout: 120 * time.Second}

type WorkspaceHandler struct {
	broadcaster *events.Broadcaster
}

func NewWorkspaceHandler(b *events.Broadcaster) *WorkspaceHandler {
	return &WorkspaceHandler{broadcaster: b}
}

// Create handles POST /workspaces
func (h *WorkspaceHandler) Create(c *gin.Context) {
	var payload models.CreateWorkspacePayload
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	id := uuid.New().String()
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
		INSERT INTO workspaces (id, name, role, tier, status, parent_id)
		VALUES ($1, $2, $3, $4, 'provisioning', $5)
	`, id, payload.Name, role, payload.Tier, payload.ParentID)
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

	c.JSON(http.StatusCreated, gin.H{"id": id, "status": "provisioning"})
}

// scanWorkspaceRow is a helper to scan workspace+layout rows into a clean JSON map.
func scanWorkspaceRow(rows interface{ Scan(dest ...interface{}) error }) (map[string]interface{}, error) {
	var id, name, role, status, url, sampleError string
	var tier, activeTasks, uptimeSeconds int
	var errorRate, x, y float64
	var collapsed bool
	var parentID *string
	var agentCard []byte

	err := rows.Scan(&id, &name, &role, &tier, &status, &agentCard, &url,
		&parentID, &activeTasks, &errorRate, &sampleError, &uptimeSeconds,
		&x, &y, &collapsed)
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
		db.DB.ExecContext(ctx, `UPDATE workspaces SET name = $2, updated_at = now() WHERE id = $1`, id, name)
	}
	if role, ok := body["role"]; ok {
		// nil or null from JSON becomes nil interface → SQL NULL
		db.DB.ExecContext(ctx, `UPDATE workspaces SET role = $2, updated_at = now() WHERE id = $1`, id, role)
	}
	if tier, ok := body["tier"]; ok {
		db.DB.ExecContext(ctx, `UPDATE workspaces SET tier = $2, updated_at = now() WHERE id = $1`, id, tier)
	}
	if parentID, ok := body["parent_id"]; ok {
		// JSON null → Go nil → SQL NULL. JSON string → UUID text.
		db.DB.ExecContext(ctx, `UPDATE workspaces SET parent_id = $2, updated_at = now() WHERE id = $1`, id, parentID)
	}

	// Update canvas position if both x and y provided
	if x, xOk := body["x"]; xOk {
		if y, yOk := body["y"]; yOk {
			db.DB.ExecContext(ctx, `
				INSERT INTO canvas_layouts (workspace_id, x, y)
				VALUES ($1, $2, $3)
				ON CONFLICT (workspace_id) DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y
			`, id, x, y)
		}
	}

	c.JSON(http.StatusOK, gin.H{"status": "updated"})
}

// Delete handles DELETE /workspaces/:id
func (h *WorkspaceHandler) Delete(c *gin.Context) {
	id := c.Param("id")
	ctx := c.Request.Context()

	_, err := db.DB.ExecContext(ctx, `
		UPDATE workspaces SET status = 'removed', updated_at = now() WHERE id = $1
	`, id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to remove"})
		return
	}

	db.DB.ExecContext(ctx, `DELETE FROM canvas_layouts WHERE workspace_id = $1`, id)

	h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_REMOVED", id, map[string]interface{}{
		"forwarded_to": nil,
	})

	c.JSON(http.StatusOK, gin.H{"status": "removed"})
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

	// Build the JSON-RPC envelope if the client sent just method+params
	var payload map[string]interface{}
	if err := json.Unmarshal(body, &payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid JSON"})
		return
	}
	if _, hasJSONRPC := payload["jsonrpc"]; !hasJSONRPC {
		rpcID := uuid.New().String()
		envelope := map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      rpcID,
			"method":  payload["method"],
			"params":  payload["params"],
		}
		var marshalErr error
		body, marshalErr = json.Marshal(envelope)
		if marshalErr != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to build JSON-RPC envelope"})
			return
		}
	}

	// Forward to the agent
	req, err := http.NewRequestWithContext(ctx, "POST", agentURL, bytes.NewReader(body))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create proxy request"})
		return
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := a2aClient.Do(req)
	if err != nil {
		log.Printf("ProxyA2A forward error: %v", err)
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

	c.Data(resp.StatusCode, "application/json", respBody)
}
