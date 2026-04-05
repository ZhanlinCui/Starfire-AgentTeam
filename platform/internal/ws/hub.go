package ws

import (
	"encoding/json"
	"log"
	"sync"

	"github.com/agent-molecule/platform/internal/models"
	"github.com/gorilla/websocket"
)

// AccessChecker is a function that checks if two workspaces can communicate.
type AccessChecker func(callerID, targetID string) bool

type Client struct {
	Conn        *websocket.Conn
	WorkspaceID string // empty for canvas clients
	Send        chan []byte
}

type Hub struct {
	mu           sync.RWMutex
	clients      map[*Client]bool
	Register     chan *Client
	Unregister   chan *Client
	canCommunicate AccessChecker
}

func NewHub(canCommunicate AccessChecker) *Hub {
	return &Hub{
		clients:        make(map[*Client]bool),
		Register:       make(chan *Client),
		Unregister:     make(chan *Client),
		canCommunicate: canCommunicate,
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.Register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			log.Printf("WebSocket client connected (workspace=%q)", client.WorkspaceID)

		case client := <-h.Unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.Send)
			}
			h.mu.Unlock()
			log.Printf("WebSocket client disconnected (workspace=%q)", client.WorkspaceID)
		}
	}
}

// Broadcast sends a WSMessage to all appropriate clients.
// Canvas clients (no WorkspaceID) receive all events.
// Workspace clients only receive events about reachable peers.
func (h *Hub) Broadcast(msg models.WSMessage) {
	data, err := json.Marshal(msg)
	if err != nil {
		log.Printf("Error marshaling broadcast: %v", err)
		return
	}

	h.mu.RLock()
	defer h.mu.RUnlock()

	for client := range h.clients {
		// Canvas clients get everything
		if client.WorkspaceID == "" {
			select {
			case client.Send <- data:
			default:
			}
			continue
		}

		// Workspace clients: filter by CanCommunicate
		if msg.WorkspaceID != "" && h.canCommunicate != nil && h.canCommunicate(client.WorkspaceID, msg.WorkspaceID) {
			select {
			case client.Send <- data:
			default:
			}
		}
	}
}

// WritePump reads from client.Send and writes to the WebSocket.
func WritePump(client *Client) {
	defer client.Conn.Close()
	for msg := range client.Send {
		if err := client.Conn.WriteMessage(websocket.TextMessage, msg); err != nil {
			break
		}
	}
}

// Close disconnects all WebSocket clients gracefully.
func (h *Hub) Close() {
	h.mu.Lock()
	defer h.mu.Unlock()
	for client := range h.clients {
		close(client.Send)
		client.Conn.Close()
		delete(h.clients, client)
	}
	log.Printf("WebSocket hub closed (%d clients disconnected)", len(h.clients))
}

// ReadPump reads from WebSocket (keeps connection alive, discards messages).
func ReadPump(client *Client, hub *Hub) {
	defer func() {
		hub.Unregister <- client
		client.Conn.Close()
	}()
	for {
		_, _, err := client.Conn.ReadMessage()
		if err != nil {
			break
		}
	}
}
