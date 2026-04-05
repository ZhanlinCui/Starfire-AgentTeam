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

type SecretsHandler struct{}

func NewSecretsHandler() *SecretsHandler {
	return &SecretsHandler{}
}

// List handles GET /workspaces/:id/secrets
// Returns keys only — never exposes values to the frontend.
func (h *SecretsHandler) List(c *gin.Context) {
	workspaceID := c.Param("id")
	if !uuidRegex.MatchString(workspaceID) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid workspace ID"})
		return
	}
	ctx := c.Request.Context()

	rows, err := db.DB.QueryContext(ctx,
		`SELECT key, created_at, updated_at FROM workspace_secrets WHERE workspace_id = $1 ORDER BY key`,
		workspaceID)
	if err != nil {
		log.Printf("List secrets error: %v", err)
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

	c.JSON(http.StatusOK, gin.H{"status": "deleted", "key": key})
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
