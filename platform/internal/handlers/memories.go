package handlers

import (
	"fmt"
	"log"
	"net/http"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/registry"
	"github.com/gin-gonic/gin"
)

type MemoriesHandler struct{}

func NewMemoriesHandler() *MemoriesHandler {
	return &MemoriesHandler{}
}

// Commit handles POST /workspaces/:id/memories
// Stores a memory fact with a scope (LOCAL, TEAM, GLOBAL).
func (h *MemoriesHandler) Commit(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	var body struct {
		Content string `json:"content" binding:"required"`
		Scope   string `json:"scope" binding:"required"` // LOCAL, TEAM, GLOBAL
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if body.Scope != "LOCAL" && body.Scope != "TEAM" && body.Scope != "GLOBAL" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "scope must be LOCAL, TEAM, or GLOBAL"})
		return
	}

	// GLOBAL scope: only root workspaces (no parent) can write
	if body.Scope == "GLOBAL" {
		var parentID *string
		db.DB.QueryRowContext(ctx, `SELECT parent_id FROM workspaces WHERE id = $1`, workspaceID).Scan(&parentID)
		if parentID != nil {
			c.JSON(http.StatusForbidden, gin.H{"error": "only root workspaces can write GLOBAL memories"})
			return
		}
	}

	var memoryID string
	err := db.DB.QueryRowContext(ctx, `
		INSERT INTO agent_memories (workspace_id, content, scope)
		VALUES ($1, $2, $3) RETURNING id
	`, workspaceID, body.Content, body.Scope).Scan(&memoryID)
	if err != nil {
		log.Printf("Commit memory error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to store memory"})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"id": memoryID, "scope": body.Scope})
}

// Search handles GET /workspaces/:id/memories
// Searches memories visible to the requesting workspace.
func (h *MemoriesHandler) Search(c *gin.Context) {
	workspaceID := c.Param("id")
	scope := c.DefaultQuery("scope", "")
	query := c.DefaultQuery("q", "")
	ctx := c.Request.Context()

	// Get workspace info for access control
	var parentID *string
	db.DB.QueryRowContext(ctx, `SELECT parent_id FROM workspaces WHERE id = $1`, workspaceID).Scan(&parentID)

	// Build query based on scope and access rules
	var sqlQuery string
	var args []interface{}

	switch scope {
	case "LOCAL":
		// Only this workspace's memories
		sqlQuery = `SELECT id, workspace_id, content, scope, created_at FROM agent_memories WHERE workspace_id = $1 AND scope = 'LOCAL'`
		args = []interface{}{workspaceID}

	case "TEAM":
		// Team = self + parent + siblings (same parent_id)
		if parentID != nil {
			// Child workspace: team is parent + siblings sharing same parent_id
			sqlQuery = `SELECT m.id, m.workspace_id, m.content, m.scope, m.created_at
				FROM agent_memories m
				JOIN workspaces w ON w.id = m.workspace_id
				WHERE m.scope = 'TEAM' AND w.status != 'removed'
				AND (w.parent_id = $1 OR w.id = $1)`
			args = []interface{}{*parentID}
		} else {
			// Root workspace: team is self + direct children only
			sqlQuery = `SELECT m.id, m.workspace_id, m.content, m.scope, m.created_at
				FROM agent_memories m
				JOIN workspaces w ON w.id = m.workspace_id
				WHERE m.scope = 'TEAM' AND w.status != 'removed'
				AND (w.parent_id = $1 OR w.id = $1)`
			args = []interface{}{workspaceID}
		}

	case "GLOBAL":
		// All GLOBAL memories (readable by everyone)
		sqlQuery = `SELECT id, workspace_id, content, scope, created_at FROM agent_memories WHERE scope = 'GLOBAL'`
		args = []interface{}{}

	default:
		// All accessible memories
		sqlQuery = `SELECT id, workspace_id, content, scope, created_at FROM agent_memories WHERE workspace_id = $1`
		args = []interface{}{workspaceID}
	}

	// Add text search if query provided
	if query != "" {
		sqlQuery += ` AND content ILIKE $` + nextArg(len(args))
		args = append(args, "%"+query+"%")
	}

	sqlQuery += ` ORDER BY created_at DESC LIMIT 50`

	rows, err := db.DB.QueryContext(ctx, sqlQuery, args...)
	if err != nil {
		log.Printf("Search memories error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "search failed"})
		return
	}
	defer rows.Close()

	memories := make([]map[string]interface{}, 0)
	for rows.Next() {
		var id, wsID, content, memScope, createdAt string
		if rows.Scan(&id, &wsID, &content, &memScope, &createdAt) != nil {
			continue
		}

		// Access control check for TEAM scope
		if memScope == "TEAM" && wsID != workspaceID {
			if !registry.CanCommunicate(workspaceID, wsID) {
				continue // Skip memories from workspaces we can't reach
			}
		}

		memories = append(memories, map[string]interface{}{
			"id":           id,
			"workspace_id": wsID,
			"content":      content,
			"scope":        memScope,
			"created_at":   createdAt,
		})
	}

	c.JSON(http.StatusOK, memories)
}

// Delete handles DELETE /workspaces/:id/memories/:memoryId
func (h *MemoriesHandler) Delete(c *gin.Context) {
	workspaceID := c.Param("id")
	memoryID := c.Param("memoryId")
	ctx := c.Request.Context()

	result, err := db.DB.ExecContext(ctx,
		`DELETE FROM agent_memories WHERE id = $1 AND workspace_id = $2`, memoryID, workspaceID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "delete failed"})
		return
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "memory not found or not owned by this workspace"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "deleted"})
}

func nextArg(current int) string {
	return fmt.Sprintf("$%d", current+1)
}
