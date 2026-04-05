package handlers

import (
	"database/sql"
	"encoding/json"
	"log"
	"net/http"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/gin-gonic/gin"
)

type ApprovalsHandler struct {
	broadcaster *events.Broadcaster
}

func NewApprovalsHandler(b *events.Broadcaster) *ApprovalsHandler {
	return &ApprovalsHandler{broadcaster: b}
}

// Create handles POST /workspaces/:id/approvals
// Creates a new approval request from a workspace agent.
func (h *ApprovalsHandler) Create(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	var body struct {
		TaskID  string                 `json:"task_id"`
		Action  string                 `json:"action" binding:"required"`
		Reason  string                 `json:"reason"`
		Context map[string]interface{} `json:"context"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var approvalID string
	err := db.DB.QueryRowContext(ctx, `
		INSERT INTO approval_requests (workspace_id, task_id, action, reason, context)
		VALUES ($1, $2, $3, $4, $5::jsonb)
		RETURNING id
	`, workspaceID, body.TaskID, body.Action, body.Reason, toJSONB(body.Context)).Scan(&approvalID)
	if err != nil {
		log.Printf("Create approval error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create approval"})
		return
	}

	// Broadcast to canvas
	h.broadcaster.RecordAndBroadcast(ctx, "APPROVAL_REQUESTED", workspaceID, map[string]interface{}{
		"approval_id": approvalID,
		"action":      body.Action,
		"reason":      body.Reason,
		"task_id":     body.TaskID,
	})

	// Try to escalate to parent workspace
	var parentID *string
	db.DB.QueryRowContext(ctx, `SELECT parent_id FROM workspaces WHERE id = $1`, workspaceID).Scan(&parentID)
	if parentID != nil {
		h.broadcaster.RecordAndBroadcast(ctx, "APPROVAL_ESCALATED", *parentID, map[string]interface{}{
			"approval_id":        approvalID,
			"from_workspace_id":  workspaceID,
			"action":             body.Action,
			"reason":             body.Reason,
		})
	}

	c.JSON(http.StatusCreated, gin.H{"approval_id": approvalID, "status": "pending"})
}

// List handles GET /workspaces/:id/approvals
func (h *ApprovalsHandler) List(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()
	statusFilter := c.DefaultQuery("status", "")

	query := `SELECT id, task_id, action, reason, status, decided_by, decided_at, created_at
		FROM approval_requests WHERE workspace_id = $1`
	args := []interface{}{workspaceID}

	if statusFilter != "" {
		query += ` AND status = $2`
		args = append(args, statusFilter)
	}
	query += ` ORDER BY created_at DESC LIMIT 50`

	rows, err := db.DB.QueryContext(ctx, query, args...)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query failed"})
		return
	}
	defer rows.Close()

	approvals := make([]map[string]interface{}, 0)
	for rows.Next() {
		var id, action, status string
		var taskID, reason, decidedBy sql.NullString
		var decidedAt sql.NullTime
		var createdAt string
		if rows.Scan(&id, &taskID, &action, &reason, &status, &decidedBy, &decidedAt, &createdAt) != nil {
			continue
		}
		approvals = append(approvals, map[string]interface{}{
			"id":         id,
			"task_id":    nullStr(taskID),
			"action":     action,
			"reason":     nullStr(reason),
			"status":     status,
			"decided_by": nullStr(decidedBy),
			"decided_at": nullTime(decidedAt),
			"created_at": createdAt,
		})
	}

	c.JSON(http.StatusOK, approvals)
}

// Decide handles POST /workspaces/:id/approvals/:approvalId/decide
func (h *ApprovalsHandler) Decide(c *gin.Context) {
	workspaceID := c.Param("id")
	approvalID := c.Param("approvalId")
	ctx := c.Request.Context()

	var body struct {
		Decision  string `json:"decision" binding:"required"` // "approved" or "denied"
		DecidedBy string `json:"decided_by"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if body.Decision != "approved" && body.Decision != "denied" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "decision must be 'approved' or 'denied'"})
		return
	}

	decidedBy := body.DecidedBy
	if decidedBy == "" {
		decidedBy = "human"
	}

	result, err := db.DB.ExecContext(ctx, `
		UPDATE approval_requests
		SET status = $1, decided_by = $2, decided_at = now()
		WHERE id = $3 AND workspace_id = $4 AND status = 'pending'
	`, body.Decision, decidedBy, approvalID, workspaceID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update"})
		return
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "approval not found or already decided"})
		return
	}

	eventType := "APPROVAL_APPROVED"
	if body.Decision == "denied" {
		eventType = "APPROVAL_DENIED"
	}

	h.broadcaster.RecordAndBroadcast(ctx, eventType, workspaceID, map[string]interface{}{
		"approval_id": approvalID,
		"decision":    body.Decision,
		"decided_by":  decidedBy,
	})

	c.JSON(http.StatusOK, gin.H{"status": body.Decision, "approval_id": approvalID})
}

func toJSONB(m map[string]interface{}) string {
	if m == nil {
		return "{}"
	}
	data, _ := json.Marshal(m)
	return string(data)
}

func nullStr(ns sql.NullString) interface{} {
	if ns.Valid {
		return ns.String
	}
	return nil
}

func nullTime(nt sql.NullTime) interface{} {
	if nt.Valid {
		return nt.Time
	}
	return nil
}
