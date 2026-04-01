package router

import (
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/handlers"
	"github.com/agent-molecule/platform/internal/ws"
	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
)

func Setup(hub *ws.Hub, broadcaster *events.Broadcaster) *gin.Engine {
	r := gin.Default()

	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"http://localhost:3000", "http://localhost:3001"},
		AllowMethods:     []string{"GET", "POST", "PATCH", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "X-Workspace-ID"},
		AllowCredentials: true,
	}))

	// Health
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// Workspaces CRUD
	wh := handlers.NewWorkspaceHandler(broadcaster)
	r.POST("/workspaces", wh.Create)
	r.GET("/workspaces", wh.List)
	r.GET("/workspaces/:id", wh.Get)
	r.PATCH("/workspaces/:id", wh.Update)
	r.DELETE("/workspaces/:id", wh.Delete)

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

	// WebSocket
	sh := handlers.NewSocketHandler(hub)
	r.GET("/ws", sh.HandleConnect)

	return r
}
