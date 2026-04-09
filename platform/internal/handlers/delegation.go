package handlers

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// DelegationHandler manages async delegation between workspaces.
// Delegations are fire-and-forget: the caller gets a task_id immediately,
// and the A2A request runs in the background.
type DelegationHandler struct {
	workspace   *WorkspaceHandler
	broadcaster *events.Broadcaster
}

func NewDelegationHandler(wh *WorkspaceHandler, b *events.Broadcaster) *DelegationHandler {
	return &DelegationHandler{workspace: wh, broadcaster: b}
}

// Delegate handles POST /workspaces/:id/delegate
// Sends an A2A message to the target workspace in the background.
// Returns immediately with a delegation_id.
func (h *DelegationHandler) Delegate(c *gin.Context) {
	sourceID := c.Param("id")
	ctx := c.Request.Context()

	var body struct {
		TargetID string `json:"target_id" binding:"required"`
		Task     string `json:"task" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	delegationID := uuid.New().String()

	// Store delegation in DB (request_body must be JSONB)
	taskJSON, _ := json.Marshal(map[string]string{"task": body.Task})
	_, err := db.DB.ExecContext(ctx, `
		INSERT INTO activity_logs (workspace_id, activity_type, method, source_id, target_id, summary, request_body, status)
		VALUES ($1, 'delegation', 'delegate', $2, $3, $4, $5::jsonb, 'pending')
	`, sourceID, sourceID, body.TargetID, "Delegating to "+body.TargetID, string(taskJSON))
	if err != nil {
		log.Printf("Delegation: failed to store: %v", err)
	}

	// Build A2A payload
	a2aBody, _ := json.Marshal(map[string]interface{}{
		"method": "message/send",
		"params": map[string]interface{}{
			"message": map[string]interface{}{
				"role":  "user",
				"parts": []map[string]interface{}{{"type": "text", "text": body.Task}},
			},
		},
	})

	// Fire-and-forget: send A2A in background goroutine
	go h.executeDelegation(sourceID, body.TargetID, delegationID, a2aBody)

	// Broadcast event so canvas shows delegation in real-time
	h.broadcaster.RecordAndBroadcast(ctx, "DELEGATION_SENT", sourceID, map[string]interface{}{
		"delegation_id": delegationID,
		"target_id":     body.TargetID,
		"task_preview":  truncate(body.Task, 100),
	})

	c.JSON(http.StatusAccepted, gin.H{
		"delegation_id": delegationID,
		"status":        "delegated",
		"target_id":     body.TargetID,
	})
}

// executeDelegation runs in a goroutine — sends A2A and stores the result.
func (h *DelegationHandler) executeDelegation(sourceID, targetID, delegationID string, a2aBody []byte) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()

	log.Printf("Delegation %s: %s → %s (background)", delegationID, sourceID, targetID)

	status, respBody, proxyErr := h.workspace.proxyA2ARequest(ctx, targetID, a2aBody, sourceID, true)

	if proxyErr != nil {
		log.Printf("Delegation %s: failed — %s", delegationID, proxyErr.Error())
		// Store failure
		db.DB.Exec(`
			INSERT INTO activity_logs (workspace_id, activity_type, method, source_id, target_id, summary, status, error_detail)
			VALUES ($1, 'delegation', 'delegate_result', $2, $3, $4, 'failed', $5)
		`, sourceID, sourceID, targetID, "Delegation failed", proxyErr.Error())

		h.broadcaster.RecordAndBroadcast(ctx, "DELEGATION_FAILED", sourceID, map[string]interface{}{
			"delegation_id": delegationID,
			"target_id":     targetID,
			"error":         proxyErr.Error(),
		})
		return
	}

	// Extract response text
	responseText := extractResponseText(respBody)
	log.Printf("Delegation %s: completed (status=%d, %d chars)", delegationID, status, len(responseText))

	// Store success (response_body must be JSONB)
	respJSON, _ := json.Marshal(map[string]string{"text": responseText})
	db.DB.Exec(`
		INSERT INTO activity_logs (workspace_id, activity_type, method, source_id, target_id, summary, response_body, status)
		VALUES ($1, 'delegation', 'delegate_result', $2, $3, $4, $5::jsonb, 'completed')
	`, sourceID, sourceID, targetID, "Delegation completed ("+truncate(responseText, 80)+")", string(respJSON))

	h.broadcaster.RecordAndBroadcast(ctx, "DELEGATION_COMPLETE", sourceID, map[string]interface{}{
		"delegation_id":    delegationID,
		"target_id":        targetID,
		"response_preview": truncate(responseText, 200),
	})
}

// ListDelegations handles GET /workspaces/:id/delegations
// Returns recent delegations for a workspace with their status.
func (h *DelegationHandler) ListDelegations(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	rows, err := db.DB.QueryContext(ctx, `
		SELECT id, activity_type, COALESCE(source_id::text, ''), COALESCE(target_id::text, ''),
		       COALESCE(summary, ''), COALESCE(status, ''), COALESCE(error_detail, ''),
		       COALESCE(response_body->>'text', ''), created_at
		FROM activity_logs
		WHERE workspace_id = $1 AND method IN ('delegate', 'delegate_result')
		ORDER BY created_at DESC
		LIMIT 50
	`, workspaceID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query failed"})
		return
	}
	defer rows.Close()

	var delegations []map[string]interface{}
	for rows.Next() {
		var id, actType, sourceID, targetID, summary, status, errorDetail, responseBody string
		var createdAt time.Time
		if err := rows.Scan(&id, &actType, &sourceID, &targetID, &summary, &status, &errorDetail, &responseBody, &createdAt); err != nil {
			continue
		}
		entry := map[string]interface{}{
			"id":         id,
			"type":       actType,
			"source_id":  sourceID,
			"target_id":  targetID,
			"summary":    summary,
			"status":     status,
			"created_at": createdAt,
		}
		if errorDetail != "" {
			entry["error"] = errorDetail
		}
		if responseBody != "" && len(responseBody) > 0 {
			entry["response_preview"] = truncate(responseBody, 300)
		}
		delegations = append(delegations, entry)
	}

	if delegations == nil {
		delegations = []map[string]interface{}{}
	}
	c.JSON(http.StatusOK, delegations)
}

// --- helpers ---

func extractResponseText(body []byte) string {
	var resp map[string]interface{}
	if json.Unmarshal(body, &resp) != nil {
		return string(body)
	}
	result, ok := resp["result"].(map[string]interface{})
	if !ok {
		return string(body)
	}
	// Check top-level parts
	if parts, ok := result["parts"].([]interface{}); ok {
		for _, p := range parts {
			if part, ok := p.(map[string]interface{}); ok {
				if kind, _ := part["kind"].(string); kind == "text" {
					if text, ok := part["text"].(string); ok {
						return text
					}
				}
			}
		}
	}
	// Check artifacts
	if artifacts, ok := result["artifacts"].([]interface{}); ok {
		for _, a := range artifacts {
			if art, ok := a.(map[string]interface{}); ok {
				if parts, ok := art["parts"].([]interface{}); ok {
					for _, p := range parts {
						if part, ok := p.(map[string]interface{}); ok {
							if kind, _ := part["kind"].(string); kind == "text" {
								if text, ok := part["text"].(string); ok {
									return text
								}
							}
						}
					}
				}
			}
		}
	}
	return string(body)
}

func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max] + "..."
}
