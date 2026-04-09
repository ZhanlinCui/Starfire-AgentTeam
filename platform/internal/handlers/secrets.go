package handlers

import (
	"database/sql"
	"log"
	"net/http"
	"regexp"

	"github.com/agent-molecule/platform/internal/crypto"
	"github.com/agent-molecule/platform/internal/db"
	"github.com/gin-gonic/gin"
)

var uuidRegex = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)

type SecretsHandler struct {
	restartFunc func(workspaceID string) // Optional: auto-restart after secret change
}

func NewSecretsHandler(restartFunc func(string)) *SecretsHandler {
	return &SecretsHandler{restartFunc: restartFunc}
}

// List handles GET /workspaces/:id/secrets
// Returns a merged view: workspace-level overrides + inherited global secrets.
// Each entry includes a "scope" field ("workspace" or "global") so the frontend
// can distinguish overrides from inherited defaults. Never exposes values.
func (h *SecretsHandler) List(c *gin.Context) {
	workspaceID := c.Param("id")
	if !uuidRegex.MatchString(workspaceID) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid workspace ID"})
		return
	}
	ctx := c.Request.Context()

	// 1. Workspace-level secrets
	wsKeys := map[string]bool{}
	secrets := make([]map[string]interface{}, 0)

	rows, err := db.DB.QueryContext(ctx,
		`SELECT key, created_at, updated_at FROM workspace_secrets WHERE workspace_id = $1 ORDER BY key`,
		workspaceID)
	if err != nil {
		log.Printf("List secrets error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query failed"})
		return
	}
	defer rows.Close()

	for rows.Next() {
		var key, createdAt, updatedAt string
		if err := rows.Scan(&key, &createdAt, &updatedAt); err != nil {
			continue
		}
		wsKeys[key] = true
		secrets = append(secrets, map[string]interface{}{
			"key":        key,
			"has_value":  true,
			"scope":      "workspace",
			"created_at": createdAt,
			"updated_at": updatedAt,
		})
	}

	// 2. Global secrets not overridden at workspace level
	globalRows, err := db.DB.QueryContext(ctx,
		`SELECT key, created_at, updated_at FROM global_secrets ORDER BY key`)
	if err != nil {
		log.Printf("List global secrets (merged) error: %v", err)
		// Non-fatal: return workspace secrets only
		c.JSON(http.StatusOK, secrets)
		return
	}
	defer globalRows.Close()

	for globalRows.Next() {
		var key, createdAt, updatedAt string
		if err := globalRows.Scan(&key, &createdAt, &updatedAt); err != nil {
			continue
		}
		if wsKeys[key] {
			continue // workspace override exists — skip global
		}
		secrets = append(secrets, map[string]interface{}{
			"key":        key,
			"has_value":  true,
			"scope":      "global",
			"created_at": createdAt,
			"updated_at": updatedAt,
		})
	}

	c.JSON(http.StatusOK, secrets)
}

// Set handles POST /workspaces/:id/secrets
func (h *SecretsHandler) Set(c *gin.Context) {
	workspaceID := c.Param("id")
	if !uuidRegex.MatchString(workspaceID) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid workspace ID"})
		return
	}
	ctx := c.Request.Context()

	var body struct {
		Key   string `json:"key" binding:"required"`
		Value string `json:"value" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Encrypt the value (AES-256-GCM if SECRETS_ENCRYPTION_KEY is set, plaintext otherwise)
	encrypted, err := crypto.Encrypt([]byte(body.Value))
	if err != nil {
		log.Printf("Encrypt secret error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to encrypt secret"})
		return
	}

	_, err = db.DB.ExecContext(ctx, `
		INSERT INTO workspace_secrets (workspace_id, key, encrypted_value)
		VALUES ($1, $2, $3)
		ON CONFLICT (workspace_id, key) DO UPDATE SET encrypted_value = $3, updated_at = now()
	`, workspaceID, body.Key, encrypted)
	if err != nil {
		log.Printf("Set secret error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to save secret"})
		return
	}

	// Auto-restart workspace to pick up new secret
	if h.restartFunc != nil {
		go h.restartFunc(workspaceID)
	}

	c.JSON(http.StatusOK, gin.H{"status": "saved", "key": body.Key})
}

// Delete handles DELETE /workspaces/:id/secrets/:key
func (h *SecretsHandler) Delete(c *gin.Context) {
	workspaceID := c.Param("id")
	if !uuidRegex.MatchString(workspaceID) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid workspace ID"})
		return
	}
	key := c.Param("key")
	ctx := c.Request.Context()

	result, err := db.DB.ExecContext(ctx,
		`DELETE FROM workspace_secrets WHERE workspace_id = $1 AND key = $2`,
		workspaceID, key)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete secret"})
		return
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "secret not found"})
		return
	}

	// Auto-restart workspace to pick up removed secret
	if h.restartFunc != nil {
		go h.restartFunc(workspaceID)
	}

	c.JSON(http.StatusOK, gin.H{"status": "deleted", "key": key})
}

// ---------------------------------------------------------------------------
// Global secrets — platform-wide API keys that apply to all workspaces.
// Workspace-level secrets with the same key override globals.
// ---------------------------------------------------------------------------

// ListGlobal handles GET /admin/secrets
func (h *SecretsHandler) ListGlobal(c *gin.Context) {
	ctx := c.Request.Context()
	rows, err := db.DB.QueryContext(ctx,
		`SELECT key, created_at, updated_at FROM global_secrets ORDER BY key`)
	if err != nil {
		log.Printf("List global secrets error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query failed"})
		return
	}
	defer rows.Close()

	secrets := make([]map[string]interface{}, 0)
	for rows.Next() {
		var key, createdAt, updatedAt string
		if err := rows.Scan(&key, &createdAt, &updatedAt); err != nil {
			continue
		}
		secrets = append(secrets, map[string]interface{}{
			"key":        key,
			"has_value":  true,
			"created_at": createdAt,
			"updated_at": updatedAt,
			"scope":      "global",
		})
	}
	c.JSON(http.StatusOK, secrets)
}

// SetGlobal handles POST /admin/secrets
func (h *SecretsHandler) SetGlobal(c *gin.Context) {
	ctx := c.Request.Context()
	var body struct {
		Key   string `json:"key" binding:"required"`
		Value string `json:"value" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	encrypted, err := crypto.Encrypt([]byte(body.Value))
	if err != nil {
		log.Printf("Encrypt global secret error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to encrypt"})
		return
	}

	_, err = db.DB.ExecContext(ctx, `
		INSERT INTO global_secrets (key, encrypted_value)
		VALUES ($1, $2)
		ON CONFLICT (key) DO UPDATE SET encrypted_value = $2, updated_at = now()
	`, body.Key, encrypted)
	if err != nil {
		log.Printf("Set global secret error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to save"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "saved", "key": body.Key, "scope": "global"})
}

// DeleteGlobal handles DELETE /admin/secrets/:key
func (h *SecretsHandler) DeleteGlobal(c *gin.Context) {
	key := c.Param("key")
	ctx := c.Request.Context()

	result, err := db.DB.ExecContext(ctx,
		`DELETE FROM global_secrets WHERE key = $1`, key)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete"})
		return
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "secret not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "deleted", "key": key, "scope": "global"})
}

// GetModel handles GET /workspaces/:id/model
// Returns the current model configuration for a workspace.
func (h *SecretsHandler) GetModel(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	// Check if MODEL_PROVIDER secret exists
	var modelBytes []byte
	err := db.DB.QueryRowContext(ctx,
		`SELECT encrypted_value FROM workspace_secrets WHERE workspace_id = $1 AND key = 'MODEL_PROVIDER'`,
		workspaceID).Scan(&modelBytes)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusOK, gin.H{"model": "", "source": "default"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query failed"})
		return
	}

	decrypted, err := crypto.Decrypt(modelBytes)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to decrypt"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"model": string(decrypted), "source": "workspace_secrets"})
}
