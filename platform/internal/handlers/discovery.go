package handlers

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/registry"
	"github.com/gin-gonic/gin"
)

type DiscoveryHandler struct{}

func NewDiscoveryHandler() *DiscoveryHandler {
	return &DiscoveryHandler{}
}

// Discover handles GET /registry/discover/:id
func (h *DiscoveryHandler) Discover(c *gin.Context) {
	targetID := c.Param("id")
	callerID := c.GetHeader("X-Workspace-ID")

	if callerID != "" {
		if !registry.CanCommunicate(callerID, targetID) {
			c.JSON(http.StatusForbidden, gin.H{"error": "not authorized to discover this workspace"})
			return
		}
	}

	ctx := c.Request.Context()

	// Workspace-to-workspace: return Docker-internal URL (containers can't reach host ports)
	// Canvas/external: return host-accessible URL
	if callerID != "" {
		// Try cached internal URL first
		if internalURL, err := db.GetCachedInternalURL(ctx, targetID); err == nil && internalURL != "" {
			c.JSON(http.StatusOK, gin.H{"id": targetID, "url": internalURL})
			return
		}
		// Fallback: construct internal URL from workspace ID (container name convention: ws-<first12chars>)
		shortID := targetID
		if len(shortID) > 12 {
			shortID = shortID[:12]
		}
		internalURL := fmt.Sprintf("http://ws-%s:8000", shortID)
		// Cache it for next time
		db.CacheInternalURL(ctx, targetID, internalURL)
		c.JSON(http.StatusOK, gin.H{"id": targetID, "url": internalURL})
		return
	}
	if url, err := db.GetCachedURL(ctx, targetID); err == nil {
		c.JSON(http.StatusOK, gin.H{"id": targetID, "url": url})
		return
	}

	var url sql.NullString
	var status string
	var forwardedTo sql.NullString
	err := db.DB.QueryRowContext(ctx,
		`SELECT url, status, forwarded_to FROM workspaces WHERE id = $1`, targetID,
	).Scan(&url, &status, &forwardedTo)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "lookup failed"})
		return
	}

	// Follow forwarding chain (max 5 hops to prevent loops)
	resolvedID := targetID
	for i := 0; i < 5 && forwardedTo.Valid && forwardedTo.String != ""; i++ {
		resolvedID = forwardedTo.String
		err = db.DB.QueryRowContext(ctx,
			`SELECT url, status, forwarded_to FROM workspaces WHERE id = $1`, resolvedID,
		).Scan(&url, &status, &forwardedTo)
		if err != nil {
			break
		}
	}

	if !url.Valid || url.String == "" {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "workspace has no URL", "status": status})
		return
	}

	db.CacheURL(ctx, resolvedID, url.String)
	c.JSON(http.StatusOK, gin.H{
		"id":     resolvedID,
		"url":    url.String,
		"status": status,
	})
}

// Peers handles GET /registry/:id/peers
func (h *DiscoveryHandler) Peers(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	var parentID sql.NullString
	err := db.DB.QueryRowContext(ctx, `SELECT parent_id FROM workspaces WHERE id = $1`, workspaceID).
		Scan(&parentID)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "workspace not found"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "lookup failed"})
		return
	}

	var peers []map[string]interface{}

	// Siblings
	if parentID.Valid {
		siblings, _ := queryPeerMaps(`
			SELECT w.id, w.name, COALESCE(w.role, ''), w.tier, w.status,
				   COALESCE(w.agent_card, 'null'::jsonb), COALESCE(w.url, ''),
				   w.parent_id, w.active_tasks
			FROM workspaces w WHERE w.parent_id = $1 AND w.id != $2 AND w.status != 'removed'`,
			parentID.String, workspaceID)
		peers = append(peers, siblings...)
	} else {
		siblings, _ := queryPeerMaps(`
			SELECT w.id, w.name, COALESCE(w.role, ''), w.tier, w.status,
				   COALESCE(w.agent_card, 'null'::jsonb), COALESCE(w.url, ''),
				   w.parent_id, w.active_tasks
			FROM workspaces w WHERE w.parent_id IS NULL AND w.id != $1 AND w.status != 'removed'`,
			workspaceID)
		peers = append(peers, siblings...)
	}

	// Children
	children, _ := queryPeerMaps(`
		SELECT w.id, w.name, COALESCE(w.role, ''), w.tier, w.status,
			   COALESCE(w.agent_card, 'null'::jsonb), COALESCE(w.url, ''),
			   w.parent_id, w.active_tasks
		FROM workspaces w WHERE w.parent_id = $1 AND w.status != 'removed'`, workspaceID)
	peers = append(peers, children...)

	// Parent
	if parentID.Valid {
		parent, _ := queryPeerMaps(`
			SELECT w.id, w.name, COALESCE(w.role, ''), w.tier, w.status,
				   COALESCE(w.agent_card, 'null'::jsonb), COALESCE(w.url, ''),
				   w.parent_id, w.active_tasks
			FROM workspaces w WHERE w.id = $1 AND w.status != 'removed'`, parentID.String)
		peers = append(peers, parent...)
	}

	if peers == nil {
		peers = make([]map[string]interface{}, 0)
	}
	c.JSON(http.StatusOK, peers)
}

// queryPeerMaps returns clean JSON-serializable maps instead of Workspace structs.
func queryPeerMaps(query string, args ...interface{}) ([]map[string]interface{}, error) {
	rows, err := db.DB.Query(query, args...)
	if err != nil {
		log.Printf("queryPeerMaps error: %v", err)
		return nil, err
	}
	defer rows.Close()

	var result []map[string]interface{}
	for rows.Next() {
		var id, name, role, status, url string
		var tier, activeTasks int
		var parentID *string
		var agentCard []byte

		err := rows.Scan(&id, &name, &role, &tier, &status, &agentCard, &url, &parentID, &activeTasks)
		if err != nil {
			log.Printf("queryPeerMaps scan error: %v", err)
			continue
		}

		peer := map[string]interface{}{
			"id":           id,
			"name":         name,
			"tier":         tier,
			"status":       status,
			"url":          url,
			"parent_id":    parentID,
			"active_tasks": activeTasks,
		}

		if role != "" {
			peer["role"] = role
		} else {
			peer["role"] = nil
		}

		if len(agentCard) > 0 && string(agentCard) != "null" {
			peer["agent_card"] = json.RawMessage(agentCard)
		} else {
			peer["agent_card"] = nil
		}

		result = append(result, peer)
	}
	return result, nil
}

// CheckAccess handles POST /registry/check-access
func (h *DiscoveryHandler) CheckAccess(c *gin.Context) {
	var payload struct {
		CallerID string `json:"caller_id" binding:"required"`
		TargetID string `json:"target_id" binding:"required"`
	}
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	allowed := registry.CanCommunicate(payload.CallerID, payload.TargetID)
	c.JSON(http.StatusOK, gin.H{"allowed": allowed})
}
