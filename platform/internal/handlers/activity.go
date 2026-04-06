package handlers

import (
	"context"
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/gin-gonic/gin"
)

type ActivityHandler struct {
	broadcaster *events.Broadcaster
}

func NewActivityHandler(b *events.Broadcaster) *ActivityHandler {
	return &ActivityHandler{broadcaster: b}
}

// List handles GET /workspaces/:id/activity?type=&limit=
func (h *ActivityHandler) List(c *gin.Context) {
	workspaceID := c.Param("id")
	activityType := c.Query("type")
	limitStr := c.DefaultQuery("limit", "100")

	limit := 100
	if n, err := strconv.Atoi(limitStr); err == nil && n > 0 {
		limit = n
		if limit > 500 {
			limit = 500
		}
	}

	var rows *sql.Rows
	var err error

	if activityType != "" {
		rows, err = db.DB.QueryContext(c.Request.Context(), `
			SELECT id, workspace_id, activity_type, source_id, target_id, method,
				   summary, request_body, response_body, duration_ms, status, error_detail, created_at
			FROM activity_logs
			WHERE workspace_id = $1 AND activity_type = $2
			ORDER BY created_at DESC
			LIMIT $3
		`, workspaceID, activityType, limit)
	} else {
		rows, err = db.DB.QueryContext(c.Request.Context(), `
			SELECT id, workspace_id, activity_type, source_id, target_id, method,
				   summary, request_body, response_body, duration_ms, status, error_detail, created_at
			FROM activity_logs
			WHERE workspace_id = $1
			ORDER BY created_at DESC
			LIMIT $2
		`, workspaceID, limit)
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query failed"})
		return
	}
	defer rows.Close()

	activities := make([]map[string]interface{}, 0)
	for rows.Next() {
		var id, wsID, actType, status string
		var sourceID, targetID, method, summary, errorDetail *string
		var reqBody, respBody []byte
		var durationMs *int
		var createdAt time.Time

		if err := rows.Scan(&id, &wsID, &actType, &sourceID, &targetID, &method,
			&summary, &reqBody, &respBody, &durationMs, &status, &errorDetail, &createdAt); err != nil {
			log.Printf("Activity scan error: %v", err)
			continue
		}

		entry := map[string]interface{}{
			"id":            id,
			"workspace_id":  wsID,
			"activity_type": actType,
			"source_id":     sourceID,
			"target_id":     targetID,
			"method":        method,
			"summary":       summary,
			"duration_ms":   durationMs,
			"status":        status,
			"error_detail":  errorDetail,
			"created_at":    createdAt,
		}
		if reqBody != nil {
			entry["request_body"] = json.RawMessage(reqBody)
		}
		if respBody != nil {
			entry["response_body"] = json.RawMessage(respBody)
		}
		activities = append(activities, entry)
	}
	c.JSON(http.StatusOK, activities)
}

// Report handles POST /workspaces/:id/activity — agents self-report activity logs.
func (h *ActivityHandler) Report(c *gin.Context) {
	workspaceID := c.Param("id")
	var body struct {
		ActivityType string      `json:"activity_type" binding:"required"`
		Method       string      `json:"method"`
		Summary      string      `json:"summary"`
		TargetID     string      `json:"target_id"`
		Status       string      `json:"status"`
		ErrorDetail  string      `json:"error_detail"`
		DurationMs   *int        `json:"duration_ms"`
		Metadata     interface{} `json:"metadata"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate activity type
	switch body.ActivityType {
	case "a2a_send", "a2a_receive", "task_update", "agent_log", "error":
		// valid
	default:
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid activity_type, must be one of: a2a_send, a2a_receive, task_update, agent_log, error"})
		return
	}

	status := body.Status
	if status == "" {
		status = "ok"
	}

	LogActivity(c.Request.Context(), h.broadcaster, ActivityParams{
		WorkspaceID:  workspaceID,
		ActivityType: body.ActivityType,
		SourceID:     &workspaceID,
		TargetID:     nilIfEmpty(body.TargetID),
		Method:       nilIfEmpty(body.Method),
		Summary:      nilIfEmpty(body.Summary),
		RequestBody:  body.Metadata,
		DurationMs:   body.DurationMs,
		Status:       status,
		ErrorDetail:  nilIfEmpty(body.ErrorDetail),
	})

	c.JSON(http.StatusOK, gin.H{"status": "logged"})
}

// LogActivity inserts an activity log and optionally broadcasts via WebSocket.
func LogActivity(ctx context.Context, broadcaster *events.Broadcaster, params ActivityParams) {
	reqJSON, _ := json.Marshal(params.RequestBody)
	respJSON, _ := json.Marshal(params.ResponseBody)

	var reqStr, respStr *string
	if params.RequestBody != nil {
		s := string(reqJSON)
		reqStr = &s
	}
	if params.ResponseBody != nil {
		s := string(respJSON)
		respStr = &s
	}

	_, err := db.DB.ExecContext(ctx, `
		INSERT INTO activity_logs (workspace_id, activity_type, source_id, target_id, method, summary, request_body, response_body, duration_ms, status, error_detail)
		VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11)
	`, params.WorkspaceID, params.ActivityType, params.SourceID, params.TargetID,
		params.Method, params.Summary, reqStr, respStr,
		params.DurationMs, params.Status, params.ErrorDetail)
	if err != nil {
		log.Printf("LogActivity insert error: %v", err)
		return
	}

	// Broadcast ACTIVITY_LOGGED event
	if broadcaster != nil {
		broadcaster.BroadcastOnly(params.WorkspaceID, "ACTIVITY_LOGGED", map[string]interface{}{
			"activity_type": params.ActivityType,
			"method":        params.Method,
			"summary":       params.Summary,
			"status":        params.Status,
			"source_id":     params.SourceID,
			"target_id":     params.TargetID,
			"duration_ms":   params.DurationMs,
		})
	}
}

type ActivityParams struct {
	WorkspaceID  string
	ActivityType string // a2a_send, a2a_receive, task_update, agent_log, error
	SourceID     *string
	TargetID     *string
	Method       *string
	Summary      *string
	RequestBody  interface{}
	ResponseBody interface{}
	DurationMs   *int
	Status       string // ok, error, timeout
	ErrorDetail  *string
}
