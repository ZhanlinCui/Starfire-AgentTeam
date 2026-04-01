package handlers

import (
	"fmt"
	"log"
	"net/http"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/models"
	"github.com/gin-gonic/gin"
)

type RegistryHandler struct {
	broadcaster *events.Broadcaster
}

func NewRegistryHandler(b *events.Broadcaster) *RegistryHandler {
	return &RegistryHandler{broadcaster: b}
}

// Register handles POST /registry/register
// Upserts workspace, sets Redis TTL, broadcasts WORKSPACE_ONLINE.
func (h *RegistryHandler) Register(c *gin.Context) {
	var payload models.RegisterPayload
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()
	agentCardStr := string(payload.AgentCard)

	// Upsert workspace: update url, agent_card, status if already exists.
	// On INSERT (workspace not yet created via POST /workspaces), use ID as name placeholder.
	_, err := db.DB.ExecContext(ctx, `
		INSERT INTO workspaces (id, name, url, agent_card, status, last_heartbeat_at)
		VALUES ($1, $2, $3, $4::jsonb, 'online', now())
		ON CONFLICT (id) DO UPDATE SET
			url = EXCLUDED.url,
			agent_card = EXCLUDED.agent_card,
			status = 'online',
			last_heartbeat_at = now(),
			updated_at = now()
	`, payload.ID, payload.ID, payload.URL, agentCardStr)
	if err != nil {
		log.Printf("Registry register error: %v (id=%s)", err, payload.ID)
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to register: %v", err)})
		return
	}

	// Set Redis liveness key
	if err := db.SetOnline(ctx, payload.ID); err != nil {
		log.Printf("Registry redis error: %v", err)
	}

	// Cache URL
	if err := db.CacheURL(ctx, payload.ID, payload.URL); err != nil {
		log.Printf("Registry cache url error: %v", err)
	}

	// Broadcast WORKSPACE_ONLINE
	if err := h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_ONLINE", payload.ID, map[string]interface{}{
		"url":        payload.URL,
		"agent_card": payload.AgentCard,
	}); err != nil {
		log.Printf("Registry broadcast error: %v", err)
	}

	c.JSON(http.StatusOK, gin.H{"status": "registered"})
}

// Heartbeat handles POST /registry/heartbeat
func (h *RegistryHandler) Heartbeat(c *gin.Context) {
	var payload models.HeartbeatPayload
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()

	// Update heartbeat columns
	_, err := db.DB.ExecContext(ctx, `
		UPDATE workspaces SET
			last_heartbeat_at = now(),
			last_error_rate   = $2,
			last_sample_error = $3,
			active_tasks      = $4,
			uptime_seconds    = $5,
			updated_at        = now()
		WHERE id = $1
	`, payload.WorkspaceID, payload.ErrorRate, payload.SampleError,
		payload.ActiveTasks, payload.UptimeSeconds)
	if err != nil {
		log.Printf("Heartbeat update error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update"})
		return
	}

	// Refresh Redis TTL
	if err := db.RefreshTTL(ctx, payload.WorkspaceID); err != nil {
		log.Printf("Heartbeat redis error: %v", err)
	}

	// Evaluate status transitions
	h.evaluateStatus(c, payload)

	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

func (h *RegistryHandler) evaluateStatus(c *gin.Context, payload models.HeartbeatPayload) {
	ctx := c.Request.Context()

	var currentStatus string
	err := db.DB.QueryRowContext(ctx, `SELECT status FROM workspaces WHERE id = $1`, payload.WorkspaceID).
		Scan(&currentStatus)
	if err != nil {
		return
	}

	if currentStatus == "online" && payload.ErrorRate >= 0.5 {
		db.DB.ExecContext(ctx, `UPDATE workspaces SET status = 'degraded', updated_at = now() WHERE id = $1`, payload.WorkspaceID)
		h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_DEGRADED", payload.WorkspaceID, map[string]interface{}{
			"error_rate":   payload.ErrorRate,
			"sample_error": payload.SampleError,
		})
	}

	if currentStatus == "degraded" && payload.ErrorRate < 0.1 {
		db.DB.ExecContext(ctx, `UPDATE workspaces SET status = 'online', updated_at = now() WHERE id = $1`, payload.WorkspaceID)
		h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_ONLINE", payload.WorkspaceID, map[string]interface{}{})
	}
}

// UpdateCard handles POST /registry/update-card
func (h *RegistryHandler) UpdateCard(c *gin.Context) {
	var payload models.UpdateCardPayload
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	agentCardStr := string(payload.AgentCard)
	_, err := db.DB.ExecContext(c.Request.Context(), `
		UPDATE workspaces SET agent_card = $2::jsonb, updated_at = now() WHERE id = $1
	`, payload.WorkspaceID, agentCardStr)
	if err != nil {
		log.Printf("UpdateCard error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update card"})
		return
	}

	h.broadcaster.RecordAndBroadcast(c.Request.Context(), "AGENT_CARD_UPDATED", payload.WorkspaceID, map[string]interface{}{
		"agent_card": payload.AgentCard,
	})

	c.JSON(http.StatusOK, gin.H{"status": "updated"})
}
