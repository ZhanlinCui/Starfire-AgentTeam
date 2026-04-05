package router

import (
	"context"
	"time"

	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/handlers"
	"github.com/agent-molecule/platform/internal/middleware"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/agent-molecule/platform/internal/ws"
	"github.com/docker/docker/client"
	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
)

func Setup(hub *ws.Hub, broadcaster *events.Broadcaster, prov *provisioner.Provisioner, platformURL, configsDir string) *gin.Engine {
	r := gin.Default()

	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"http://localhost:3000", "http://localhost:3001"},
		AllowMethods:     []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "X-Workspace-ID"},
		AllowCredentials: true,
	}))

	// Rate limiting — 100 requests per minute per IP
	limiter := middleware.NewRateLimiter(100, time.Minute, context.Background())
	r.Use(limiter.Middleware())

	// Health
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// Workspaces CRUD
	wh := handlers.NewWorkspaceHandler(broadcaster, prov, platformURL, configsDir)
	r.POST("/workspaces", wh.Create)
	r.GET("/workspaces", wh.List)
	r.GET("/workspaces/:id", wh.Get)
	r.PATCH("/workspaces/:id", wh.Update)
	r.DELETE("/workspaces/:id", wh.Delete)
	r.POST("/workspaces/:id/restart", wh.Restart)
	r.POST("/workspaces/:id/a2a", wh.ProxyA2A)

	// Traces (Langfuse proxy)
	trh := handlers.NewTracesHandler()
	r.GET("/workspaces/:id/traces", trh.List)

	// Agent Memories (HMA)
	memsh := handlers.NewMemoriesHandler()
	r.POST("/workspaces/:id/memories", memsh.Commit)
	r.GET("/workspaces/:id/memories", memsh.Search)
	r.DELETE("/workspaces/:id/memories/:memoryId", memsh.Delete)

	// Approvals
	apph := handlers.NewApprovalsHandler(broadcaster)
	r.GET("/approvals/pending", apph.ListAll)
	r.POST("/workspaces/:id/approvals", apph.Create)
	r.GET("/workspaces/:id/approvals", apph.List)
	r.POST("/workspaces/:id/approvals/:approvalId/decide", apph.Decide)

	// Team Expansion
	teamh := handlers.NewTeamHandler(broadcaster, prov, platformURL, configsDir)
	r.POST("/workspaces/:id/expand", teamh.Expand)
	r.POST("/workspaces/:id/collapse", teamh.Collapse)

	// Agents
	ah := handlers.NewAgentHandler(broadcaster)
	r.POST("/workspaces/:id/agent", ah.Assign)
	r.PATCH("/workspaces/:id/agent", ah.Replace)
	r.DELETE("/workspaces/:id/agent", ah.Remove)
	r.POST("/workspaces/:id/agent/move", ah.Move)

	// Registry
	rh := handlers.NewRegistryHandler(broadcaster)
	r.POST("/registry/register", rh.Register)
	r.POST("/registry/heartbeat", rh.Heartbeat)
	r.POST("/registry/update-card", rh.UpdateCard)

	// Discovery
	dh := handlers.NewDiscoveryHandler()
	r.GET("/registry/discover/:id", dh.Discover)
	r.GET("/registry/:id/peers", dh.Peers)
	r.POST("/registry/check-access", dh.CheckAccess)

	// Events
	eh := handlers.NewEventsHandler()
	r.GET("/events", eh.List)
	r.GET("/events/:workspaceId", eh.ListByWorkspace)

	// Config
	cfgh := handlers.NewConfigHandler()
	r.GET("/workspaces/:id/config", cfgh.Get)
	r.PATCH("/workspaces/:id/config", cfgh.Patch)

	// Memory
	memh := handlers.NewMemoryHandler()
	r.GET("/workspaces/:id/memory", memh.List)
	r.GET("/workspaces/:id/memory/:key", memh.Get)
	r.POST("/workspaces/:id/memory", memh.Set)
	r.DELETE("/workspaces/:id/memory/:key", memh.Delete)

	// Secrets
	sech := handlers.NewSecretsHandler()
	r.GET("/workspaces/:id/secrets", sech.List)
	r.POST("/workspaces/:id/secrets", sech.Set)
	r.DELETE("/workspaces/:id/secrets/:key", sech.Delete)
	r.GET("/workspaces/:id/model", sech.GetModel)

	// Terminal — shares Docker client with provisioner
	var dockerCli *client.Client
	if prov != nil {
		dockerCli = prov.DockerClient()
	}
	th := handlers.NewTerminalHandler(dockerCli)
	r.GET("/workspaces/:id/terminal", th.HandleConnect)

	// Canvas Viewport
	vh := handlers.NewViewportHandler()
	r.GET("/canvas/viewport", vh.Get)
	r.PUT("/canvas/viewport", vh.Save)

	// Templates
	tmplh := handlers.NewTemplatesHandler(configsDir)
	r.GET("/templates", tmplh.List)
	r.POST("/templates/import", tmplh.Import)
	r.GET("/workspaces/:id/shared-context", tmplh.SharedContext)
	r.PUT("/workspaces/:id/files", tmplh.ReplaceFiles)
	r.GET("/workspaces/:id/files", tmplh.ListFiles)
	r.GET("/workspaces/:id/files/*path", tmplh.ReadFile)
	r.PUT("/workspaces/:id/files/*path", tmplh.WriteFile)
	r.DELETE("/workspaces/:id/files/*path", tmplh.DeleteFile)

	// Bundles
	bh := handlers.NewBundleHandler(broadcaster, prov, platformURL, configsDir)
	r.GET("/bundles/export/:id", bh.Export)
	r.POST("/bundles/import", bh.Import)

	// WebSocket
	sh := handlers.NewSocketHandler(hub)
	r.GET("/ws", sh.HandleConnect)

	return r
}
