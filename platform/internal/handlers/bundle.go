package handlers

import (
	"net/http"

	"github.com/agent-molecule/platform/internal/bundle"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/gin-gonic/gin"
)

type BundleHandler struct {
	broadcaster *events.Broadcaster
	provisioner *provisioner.Provisioner
	platformURL string
	configsDir  string
}

func NewBundleHandler(b *events.Broadcaster, p *provisioner.Provisioner, platformURL, configsDir string) *BundleHandler {
	return &BundleHandler{
		broadcaster: b,
		provisioner: p,
		platformURL: platformURL,
		configsDir:  configsDir,
	}
}

// Export handles GET /bundles/export/:id
func (h *BundleHandler) Export(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	b, err := bundle.Export(ctx, workspaceID, h.configsDir)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, b)
}

// Import handles POST /bundles/import
func (h *BundleHandler) Import(c *gin.Context) {
	var b bundle.Bundle
	if err := c.ShouldBindJSON(&b); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()
	result := bundle.Import(ctx, &b, nil, h.broadcaster, h.provisioner, h.platformURL)

	c.JSON(http.StatusCreated, result)
}
