package handlers

import (
	"context"
	"io"
	"log"
	"net/http"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
)

var wsUpgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type TerminalHandler struct {
	docker *client.Client
}

func NewTerminalHandler() *TerminalHandler {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		log.Printf("Terminal handler: Docker not available: %v", err)
		return &TerminalHandler{}
	}
	return &TerminalHandler{docker: cli}
}

// HandleConnect handles WS /workspaces/:id/terminal
// Upgrades to WebSocket, creates a docker exec session, and bridges stdin/stdout.
func (h *TerminalHandler) HandleConnect(c *gin.Context) {
	if h.docker == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Docker not available"})
		return
	}

	workspaceID := c.Param("id")

	// Find the container name
	containerName := "ws-" + workspaceID
	if len(workspaceID) > 12 {
		containerName = "ws-" + workspaceID[:12]
	}

	// Verify container is running
	ctx := context.Background()
	info, err := h.docker.ContainerInspect(ctx, containerName)
	if err != nil || !info.State.Running {
		c.JSON(http.StatusNotFound, gin.H{"error": "container not running"})
		return
	}

	// Upgrade to WebSocket
	conn, err := wsUpgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("Terminal WebSocket upgrade error: %v", err)
		return
	}
	defer conn.Close()

	// Create exec instance
	execCfg := container.ExecOptions{
		Cmd:          []string{"/bin/sh"},
		AttachStdin:  true,
		AttachStdout: true,
		AttachStderr: true,
		Tty:          true,
	}

	execID, err := h.docker.ContainerExecCreate(ctx, containerName, execCfg)
	if err != nil {
		log.Printf("Terminal exec create error: %v", err)
		conn.WriteMessage(websocket.TextMessage, []byte("Error: failed to create shell session\r\n"))
		return
	}

	// Attach to exec
	resp, err := h.docker.ContainerExecAttach(ctx, execID.ID, container.ExecAttachOptions{Tty: true})
	if err != nil {
		log.Printf("Terminal exec attach error: %v", err)
		conn.WriteMessage(websocket.TextMessage, []byte("Error: failed to attach to shell\r\n"))
		return
	}
	defer resp.Close()

	// Bridge: container stdout → WebSocket
	go func() {
		buf := make([]byte, 4096)
		for {
			n, err := resp.Reader.Read(buf)
			if n > 0 {
				if writeErr := conn.WriteMessage(websocket.BinaryMessage, buf[:n]); writeErr != nil {
					return
				}
			}
			if err != nil {
				if err != io.EOF {
					log.Printf("Terminal read error: %v", err)
				}
				conn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""))
				return
			}
		}
	}()

	// Bridge: WebSocket → container stdin
	for {
		_, msg, err := conn.ReadMessage()
		if err != nil {
			break
		}
		if _, err := resp.Conn.Write(msg); err != nil {
			break
		}
	}
}
