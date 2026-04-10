package handlers

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/registry"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// maxProxyRequestBody is the maximum size of an A2A proxy request body (1MB).
const maxProxyRequestBody = 1 << 20

// maxProxyResponseBody is the maximum size of an A2A proxy response body (10MB).
const maxProxyResponseBody = 10 << 20

// a2aClient is a shared HTTP client for proxying A2A requests to workspace agents.
// No client-level timeout — timeouts are enforced per-request via context deadlines:
// canvas = 5 min (Rule 3), agent-to-agent = 30 min (DoS cap).
var a2aClient = &http.Client{}

type proxyA2AError struct {
	Status   int
	Response gin.H
}

func (e *proxyA2AError) Error() string {
	if e == nil || e.Response == nil {
		return "proxy a2a error"
	}
	if msg, ok := e.Response["error"].(string); ok && msg != "" {
		return msg
	}
	return "proxy a2a error"
}

// ProxyA2A handles POST /workspaces/:id/a2a
// Proxies A2A JSON-RPC requests from the canvas to workspace agents,
// avoiding CORS and Docker network issues.
func (h *WorkspaceHandler) ProxyA2A(c *gin.Context) {
	workspaceID := c.Param("id")
	ctx := c.Request.Context()

	// Read the incoming request body (capped at 1MB)
	body, err := io.ReadAll(io.LimitReader(c.Request.Body, maxProxyRequestBody))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "failed to read request body"})
		return
	}

	status, respBody, proxyErr := h.proxyA2ARequest(ctx, workspaceID, body, c.GetHeader("X-Workspace-ID"), true)
	if proxyErr != nil {
		c.JSON(proxyErr.Status, proxyErr.Response)
		return
	}

	c.Data(status, "application/json", respBody)
}

func (h *WorkspaceHandler) proxyA2ARequest(ctx context.Context, workspaceID string, body []byte, callerID string, logActivity bool) (int, []byte, *proxyA2AError) {
	// Access control: workspace-to-workspace requests must pass CanCommunicate check.
	// Canvas requests (callerID == "") and system callers (webhook:*, system:*)
	// are trusted. Self-calls (callerID == workspaceID) are always allowed.
	if callerID != "" && callerID != workspaceID && !strings.Contains(callerID, ":") {
		if !registry.CanCommunicate(callerID, workspaceID) {
			log.Printf("ProxyA2A: access denied %s → %s", callerID, workspaceID)
			return 0, nil, &proxyA2AError{
				Status:   http.StatusForbidden,
				Response: gin.H{"error": "access denied: workspaces cannot communicate per hierarchy rules"},
			}
		}
	}

	// Resolve workspace URL (cache first, then DB)
	agentURL, err := db.GetCachedURL(ctx, workspaceID)
	if err != nil {
		var urlNullable sql.NullString
		var status string
		err := db.DB.QueryRowContext(ctx,
			`SELECT url, status FROM workspaces WHERE id = $1`, workspaceID,
		).Scan(&urlNullable, &status)
		if err == sql.ErrNoRows {
			return 0, nil, &proxyA2AError{
				Status:   http.StatusNotFound,
				Response: gin.H{"error": "workspace not found"},
			}
		}
		if err != nil {
			log.Printf("ProxyA2A lookup error: %v", err)
			return 0, nil, &proxyA2AError{
				Status:   http.StatusInternalServerError,
				Response: gin.H{"error": "lookup failed"},
			}
		}
		if !urlNullable.Valid || urlNullable.String == "" {
			return 0, nil, &proxyA2AError{
				Status:   http.StatusServiceUnavailable,
				Response: gin.H{"error": "workspace has no URL", "status": status},
			}
		}
		agentURL = urlNullable.String
		_ = db.CacheURL(ctx, workspaceID, agentURL)
	}

	// Normalize the request into a valid A2A JSON-RPC 2.0 message
	var payload map[string]interface{}
	if err := json.Unmarshal(body, &payload); err != nil {
		return 0, nil, &proxyA2AError{
			Status:   http.StatusBadRequest,
			Response: gin.H{"error": "invalid JSON"},
		}
	}

	// Wrap in JSON-RPC envelope if missing
	if _, hasJSONRPC := payload["jsonrpc"]; !hasJSONRPC {
		payload = map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      uuid.New().String(),
			"method":  payload["method"],
			"params":  payload["params"],
		}
	}

	// Ensure params.message.messageId exists (required by a2a-sdk)
	if params, ok := payload["params"].(map[string]interface{}); ok {
		if msg, ok := params["message"].(map[string]interface{}); ok {
			if _, hasID := msg["messageId"]; !hasID {
				msg["messageId"] = uuid.New().String()
			}
		}
	}

	marshaledBody, marshalErr := json.Marshal(payload)
	if marshalErr != nil {
		return 0, nil, &proxyA2AError{
			Status:   http.StatusInternalServerError,
			Response: gin.H{"error": "failed to marshal request"},
		}
	}
	body = marshaledBody

	// Extract method for logging
	var a2aMethod string
	if m, ok := payload["method"].(string); ok {
		a2aMethod = m
	}

	// Forward to the agent. Uses WithoutCancel so delegation chains survive client
	// disconnect (browser tab close). Canvas requests get 5-min timeout; agent-to-agent
	// gets 30-min DoS safety cap.
	startTime := time.Now()
	forwardCtx := context.WithoutCancel(ctx)
	if callerID == "" {
		var cancel context.CancelFunc
		forwardCtx, cancel = context.WithTimeout(forwardCtx, 5*time.Minute)
		defer cancel()
	} else {
		var cancel context.CancelFunc
		forwardCtx, cancel = context.WithTimeout(forwardCtx, 30*time.Minute)
		defer cancel()
	}
	req, err := http.NewRequestWithContext(forwardCtx, "POST", agentURL, bytes.NewReader(body))
	if err != nil {
		return 0, nil, &proxyA2AError{
			Status:   http.StatusInternalServerError,
			Response: gin.H{"error": "failed to create proxy request"},
		}
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := a2aClient.Do(req)
	durationMs := int(time.Since(startTime).Milliseconds())
	if err != nil {
		log.Printf("ProxyA2A forward error: %v", err)

		// Reactive health check: if the request failed, check if the container is actually dead.
		// Skip for external workspaces (no Docker container).
		containerDead := false
		var wsRuntime string
		db.DB.QueryRowContext(ctx, `SELECT COALESCE(runtime, 'langgraph') FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsRuntime)
		if h.provisioner != nil && wsRuntime != "external" {
			if running, _ := h.provisioner.IsRunning(ctx, workspaceID); !running {
				containerDead = true
				log.Printf("ProxyA2A: container for %s is dead — marking offline and triggering restart", workspaceID)
				if _, err := db.DB.ExecContext(ctx, `UPDATE workspaces SET status = 'offline', updated_at = now() WHERE id = $1 AND status NOT IN ('removed', 'provisioning')`, workspaceID); err != nil {
					log.Printf("ProxyA2A: failed to mark workspace %s offline: %v", workspaceID, err)
				}
				db.ClearWorkspaceKeys(ctx, workspaceID)
				h.broadcaster.RecordAndBroadcast(ctx, "WORKSPACE_OFFLINE", workspaceID, map[string]interface{}{})
				go h.RestartByID(workspaceID)
			}
		}

		if logActivity {
			// Log failed A2A attempt (detached context — request may be done)
			errMsg := err.Error()
			var errWsName string
			db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&errWsName)
			if errWsName == "" {
				errWsName = workspaceID
			}
			summary := "A2A request to " + errWsName + " failed: " + errMsg
			go func(parent context.Context) {
				logCtx, cancel := context.WithTimeout(context.WithoutCancel(parent), 30*time.Second)
				defer cancel()
				LogActivity(logCtx, h.broadcaster, ActivityParams{
					WorkspaceID:  workspaceID,
					ActivityType: "a2a_receive",
					SourceID:     nilIfEmpty(callerID),
					TargetID:     &workspaceID,
					Method:       &a2aMethod,
					Summary:      &summary,
					RequestBody:  json.RawMessage(body),
					DurationMs:   &durationMs,
					Status:       "error",
					ErrorDetail:  &errMsg,
				})
			}(ctx)
		}
		if containerDead {
			return 0, nil, &proxyA2AError{
				Status:   http.StatusServiceUnavailable,
				Response: gin.H{"error": "workspace agent unreachable — container restart triggered", "restarting": true},
			}
		}
		return 0, nil, &proxyA2AError{
			Status:   http.StatusBadGateway,
			Response: gin.H{"error": "failed to reach workspace agent"},
		}
	}
	defer resp.Body.Close()

	// Read agent response (capped at 10MB)
	respBody, err := io.ReadAll(io.LimitReader(resp.Body, maxProxyResponseBody))
	if err != nil {
		return 0, nil, &proxyA2AError{
			Status:   http.StatusBadGateway,
			Response: gin.H{"error": "failed to read agent response"},
		}
	}

	if logActivity {
		// Log successful A2A communication
		logStatus := "ok"
		if resp.StatusCode >= 400 {
			logStatus = "error"
		}
		// Resolve workspace name for readable summary
		var wsNameForLog string
		db.DB.QueryRowContext(ctx, `SELECT name FROM workspaces WHERE id = $1`, workspaceID).Scan(&wsNameForLog)
		if wsNameForLog == "" {
			wsNameForLog = workspaceID
		}
		summary := a2aMethod + " → " + wsNameForLog
		go func(parent context.Context) {
			logCtx, cancel := context.WithTimeout(context.WithoutCancel(parent), 30*time.Second)
			defer cancel()
			LogActivity(logCtx, h.broadcaster, ActivityParams{
				WorkspaceID:  workspaceID,
				ActivityType: "a2a_receive",
				SourceID:     nilIfEmpty(callerID),
				TargetID:     &workspaceID,
				Method:       &a2aMethod,
				Summary:      &summary,
				RequestBody:  json.RawMessage(body),
				ResponseBody: json.RawMessage(respBody),
				DurationMs:   &durationMs,
				Status:       logStatus,
			})
		}(ctx)

		// For canvas-initiated requests, broadcast the response via WebSocket
		// so the frontend receives it instantly without polling.
		if callerID == "" && resp.StatusCode < 400 {
			h.broadcaster.BroadcastOnly(workspaceID, "A2A_RESPONSE", map[string]interface{}{
				"response_body": json.RawMessage(respBody),
				"method":        a2aMethod,
				"duration_ms":   durationMs,
			})
		}
	}
	return resp.StatusCode, respBody, nil
}

func nilIfEmpty(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}
