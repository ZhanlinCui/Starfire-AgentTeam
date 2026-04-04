package handlers

import (
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
)

const terminalSessionTimeout = 30 * time.Minute

var termUpgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		origin := r.Header.Get("Origin")
		return origin == "" ||
			strings.HasPrefix(origin, "http://localhost:") ||
			strings.HasPrefix(origin, "https://localhost:")
	},
}

type TerminalHandler struct {
	docker *client.Client
}

func NewTerminalHandler(cli *client.Client) *TerminalHandler {
	return &TerminalHandler{docker: cli}
}

// HandleConnect handles WS /workspaces/:id/terminal
func (h *TerminalHandler) HandleConnect(c *gin.Context) {
	if h.docker == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Docker not available"})
		return
	}

	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	// Try multiple container name patterns:
	// 1. Provisioner naming: ws-{id[:12]}
	// 2. Workspace name from DB (normalized to lowercase-hyphen)
	candidates := []string{}
	if len(workspaceID) > 12 {
		candidates = append(candidates, "ws-"+workspaceID[:12])
	}
	candidates = append(candidates, "ws-"+workspaceID)

	// Look up workspace name for manual container naming
	var wsName string
	if _, err := h.docker.Ping(ctx); err == nil {
		db.DB.QueryRowContext(ctx, `SELECT LOWER(REPLACE(name, ' ', '-')) FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsName)
		if wsName != "" {
			candidates = append(candidates, wsName)
		}
	}

	// Find the first running container that matches
	var containerName string
	for _, name := range candidates {
		info, err := h.docker.ContainerInspect(ctx, name)
		if err == nil && info.State.Running {
			containerName = name
			break
		}
	}

	if containerName == "" {
		c.JSON(http.StatusNotFound, gin.H{"error": "container not running"})
		return
	}

	// Upgrade to WebSocket
	conn, err := termUpgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("Terminal WebSocket upgrade error: %v", err)
		return
	}
	defer conn.Close()

	// Set session timeout — auto-close after 30 minutes
	deadline := time.Now().Add(terminalSessionTimeout)
	conn.SetReadDeadline(deadline)
	conn.SetWriteDeadline(deadline)

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
	done := make(chan struct{})
	go func() {
		defer close(done)
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
		// Reset read deadline on activity
		conn.SetReadDeadline(time.Now().Add(terminalSessionTimeout))
	}

	<-done
}
