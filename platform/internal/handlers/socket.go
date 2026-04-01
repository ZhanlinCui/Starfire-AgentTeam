package handlers

import (
	"log"
	"net/http"

	"github.com/agent-molecule/platform/internal/ws"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins in development
	},
}

type SocketHandler struct {
	hub *ws.Hub
}

func NewSocketHandler(hub *ws.Hub) *SocketHandler {
	return &SocketHandler{hub: hub}
}

// HandleConnect handles WebSocket upgrade at GET /ws.
// Canvas clients connect without X-Workspace-ID — they receive all events.
// Workspace agents send X-Workspace-ID — events are filtered by CanCommunicate.
func (h *SocketHandler) HandleConnect(c *gin.Context) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}

	workspaceID := c.GetHeader("X-Workspace-ID")

	client := &ws.Client{
		Conn:        conn,
		WorkspaceID: workspaceID,
		Send:        make(chan []byte, 256),
	}

	h.hub.Register <- client

	go ws.WritePump(client)
	go ws.ReadPump(client, h.hub)
}
