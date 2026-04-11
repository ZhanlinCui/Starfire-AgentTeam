package handlers

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/scheduler"
)

type ScheduleHandler struct{}

func NewScheduleHandler() *ScheduleHandler {
	return &ScheduleHandler{}
}

type scheduleResponse struct {
	ID          string     `json:"id"`
	WorkspaceID string     `json:"workspace_id"`
	Name        string     `json:"name"`
	CronExpr    string     `json:"cron_expr"`
	Timezone    string     `json:"timezone"`
	Prompt      string     `json:"prompt"`
	Enabled     bool       `json:"enabled"`
	LastRunAt   *time.Time `json:"last_run_at"`
	NextRunAt   *time.Time `json:"next_run_at"`
	RunCount    int        `json:"run_count"`
	LastStatus  string     `json:"last_status"`
	LastError   string     `json:"last_error"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
}

// List returns all schedules for a workspace.
func (h *ScheduleHandler) List(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	rows, err := db.DB.QueryContext(ctx, `
		SELECT id, workspace_id, name, cron_expr, timezone, prompt, enabled,
		       last_run_at, next_run_at, run_count, last_status, last_error,
		       created_at, updated_at
		FROM workspace_schedules
		WHERE workspace_id = $1
		ORDER BY created_at ASC
	`, workspaceID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to query schedules"})
		return
	}
	defer rows.Close()

	schedules := make([]scheduleResponse, 0)
	for rows.Next() {
		var s scheduleResponse
		if err := rows.Scan(
			&s.ID, &s.WorkspaceID, &s.Name, &s.CronExpr, &s.Timezone,
			&s.Prompt, &s.Enabled, &s.LastRunAt, &s.NextRunAt, &s.RunCount,
			&s.LastStatus, &s.LastError, &s.CreatedAt, &s.UpdatedAt,
		); err != nil {
			log.Printf("Schedules.List: scan error: %v", err)
			continue
		}
		schedules = append(schedules, s)
	}
	if err := rows.Err(); err != nil {
		log.Printf("Schedules.List: rows error: %v", err)
	}

	c.JSON(http.StatusOK, schedules)
}

type createScheduleRequest struct {
	Name     string `json:"name"`
	CronExpr string `json:"cron_expr" binding:"required"`
	Timezone string `json:"timezone"`
	Prompt   string `json:"prompt" binding:"required"`
	Enabled  *bool  `json:"enabled"`
}

// Create adds a new schedule for a workspace.
func (h *ScheduleHandler) Create(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	var body createScheduleRequest
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "cron_expr and prompt are required"})
		return
	}

	if body.Timezone == "" {
		body.Timezone = "UTC"
	}

	// Validate timezone
	if _, err := time.LoadLocation(body.Timezone); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid timezone: " + body.Timezone})
		return
	}

	// Validate and compute next run
	nextRun, err := scheduler.ComputeNextRun(body.CronExpr, body.Timezone, time.Now())
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	enabled := true
	if body.Enabled != nil {
		enabled = *body.Enabled
	}

	var id string
	err = db.DB.QueryRowContext(ctx, `
		INSERT INTO workspace_schedules (workspace_id, name, cron_expr, timezone, prompt, enabled, next_run_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id
	`, workspaceID, body.Name, body.CronExpr, body.Timezone, body.Prompt, enabled, nextRun).Scan(&id)
	if err != nil {
		log.Printf("Schedules.Create: insert error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create schedule"})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"id":          id,
		"status":      "created",
		"next_run_at": nextRun,
	})
}

// Update modifies a schedule.
func (h *ScheduleHandler) Update(c *gin.Context) {
	scheduleID := c.Param("scheduleId")
	ctx := c.Request.Context()

	var body map[string]interface{}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid JSON"})
		return
	}

	// If cron_expr or timezone changed, revalidate and recompute next_run
	cronExpr, cronChanged := body["cron_expr"].(string)
	tz, tzChanged := body["timezone"].(string)

	if cronChanged || tzChanged {
		// Get current values for any unchanged fields
		var currentCron, currentTZ string
		err := db.DB.QueryRowContext(ctx,
			`SELECT cron_expr, timezone FROM workspace_schedules WHERE id = $1`, scheduleID,
		).Scan(&currentCron, &currentTZ)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "schedule not found"})
			return
		}
		if !cronChanged {
			cronExpr = currentCron
		}
		if !tzChanged {
			tz = currentTZ
		}
		if _, err := time.LoadLocation(tz); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid timezone: " + tz})
			return
		}
		nextRun, err := scheduler.ComputeNextRun(cronExpr, tz, time.Now())
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		body["next_run_at"] = nextRun
	}

	// Build dynamic UPDATE
	setClauses := ""
	args := []interface{}{}
	argIdx := 1
	allowedFields := map[string]bool{
		"name": true, "cron_expr": true, "timezone": true,
		"prompt": true, "enabled": true, "next_run_at": true,
	}
	for key, val := range body {
		if !allowedFields[key] {
			continue
		}
		if setClauses != "" {
			setClauses += ", "
		}
		setClauses += key + " = $" + itoa(argIdx)
		args = append(args, val)
		argIdx++
	}
	if setClauses == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "no valid fields to update"})
		return
	}
	setClauses += ", updated_at = now()"
	args = append(args, scheduleID)

	query := "UPDATE workspace_schedules SET " + setClauses + " WHERE id = $" + itoa(argIdx)
	result, err := db.DB.ExecContext(ctx, query, args...)
	if err != nil {
		log.Printf("Schedules.Update: error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update schedule"})
		return
	}
	n, _ := result.RowsAffected()
	if n == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "schedule not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "updated"})
}

// Delete removes a schedule.
func (h *ScheduleHandler) Delete(c *gin.Context) {
	scheduleID := c.Param("scheduleId")
	ctx := c.Request.Context()

	result, err := db.DB.ExecContext(ctx,
		`DELETE FROM workspace_schedules WHERE id = $1`, scheduleID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete schedule"})
		return
	}
	n, _ := result.RowsAffected()
	if n == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "schedule not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "deleted"})
}

// RunNow manually fires a schedule immediately.
func (h *ScheduleHandler) RunNow(c *gin.Context) {
	scheduleID := c.Param("scheduleId")
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	var prompt string
	err := db.DB.QueryRowContext(ctx,
		`SELECT prompt FROM workspace_schedules WHERE id = $1 AND workspace_id = $2`,
		scheduleID, workspaceID,
	).Scan(&prompt)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "schedule not found"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read schedule"})
		return
	}

	// The actual A2A fire is done by the caller via the proxy — we just
	// return the prompt so the frontend can POST it to /workspaces/:id/a2a.
	// This keeps the handler stateless and avoids circular deps on WorkspaceHandler.
	c.JSON(http.StatusOK, gin.H{
		"status":       "fired",
		"workspace_id": workspaceID,
		"prompt":       prompt,
	})
}

// History returns recent runs for a schedule from activity_logs.
func (h *ScheduleHandler) History(c *gin.Context) {
	scheduleID := c.Param("scheduleId")
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	rows, err := db.DB.QueryContext(ctx, `
		SELECT created_at, duration_ms, status,
		       COALESCE(request_body::text, '{}') as request_body
		FROM activity_logs
		WHERE workspace_id = $1
		  AND activity_type = 'cron_run'
		  AND request_body->>'schedule_id' = $2
		ORDER BY created_at DESC
		LIMIT 20
	`, workspaceID, scheduleID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to query history"})
		return
	}
	defer rows.Close()

	type historyEntry struct {
		Timestamp  time.Time       `json:"timestamp"`
		DurationMs *int            `json:"duration_ms"`
		Status     *string         `json:"status"`
		Request    json.RawMessage `json:"request"`
	}

	entries := make([]historyEntry, 0)
	for rows.Next() {
		var e historyEntry
		var reqStr string
		if err := rows.Scan(&e.Timestamp, &e.DurationMs, &e.Status, &reqStr); err != nil {
			continue
		}
		e.Request = json.RawMessage(reqStr)
		entries = append(entries, e)
	}

	c.JSON(http.StatusOK, entries)
}

func itoa(n int) string {
	return fmt.Sprintf("%d", n)
}
