package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/ws"
	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

func init() {
	gin.SetMode(gin.TestMode)
}

// setupTestDB creates a sqlmock DB and assigns it to the global db.DB.
func setupTestDB(t *testing.T) sqlmock.Sqlmock {
	t.Helper()
	mockDB, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("failed to create sqlmock: %v", err)
	}
	db.DB = mockDB
	t.Cleanup(func() { mockDB.Close() })
	return mock
}

// setupTestRedis creates a miniredis instance and assigns it to the global db.RDB.
func setupTestRedis(t *testing.T) *miniredis.Miniredis {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("failed to start miniredis: %v", err)
	}
	db.RDB = redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { mr.Close() })
	return mr
}

// newTestBroadcaster creates a Broadcaster backed by a no-op WebSocket hub.
func newTestBroadcaster() *events.Broadcaster {
	hub := ws.NewHub(func(callerID, targetID string) bool { return true })
	return events.NewBroadcaster(hub)
}

// ---------- TestRegisterHandler ----------

func TestRegisterHandler(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewRegistryHandler(broadcaster)

	// Expect the upsert INSERT ... ON CONFLICT
	mock.ExpectExec("INSERT INTO workspaces").
		WithArgs("ws-123", "ws-123", "http://localhost:8000", `{"name":"test"}`).
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Expect the SELECT url query (for cache URL logic)
	mock.ExpectQuery("SELECT url FROM workspaces WHERE id =").
		WithArgs("ws-123").
		WillReturnRows(sqlmock.NewRows([]string{"url"}).AddRow("http://localhost:8000"))

	// Expect the RecordAndBroadcast INSERT into structure_events
	mock.ExpectExec("INSERT INTO structure_events").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)

	body := `{"id":"ws-123","url":"http://localhost:8000","agent_card":{"name":"test"}}`
	c.Request = httptest.NewRequest("POST", "/registry/register", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Register(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if resp["status"] != "registered" {
		t.Errorf("expected status 'registered', got %v", resp["status"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ---------- TestHeartbeatHandler ----------

func TestHeartbeatHandler_Normal(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewRegistryHandler(broadcaster)

	// Expect heartbeat UPDATE
	mock.ExpectExec("UPDATE workspaces SET").
		WithArgs("ws-123", 0.1, "", 2, 3600).
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Expect evaluateStatus SELECT
	mock.ExpectQuery("SELECT status FROM workspaces WHERE id =").
		WithArgs("ws-123").
		WillReturnRows(sqlmock.NewRows([]string{"status"}).AddRow("online"))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)

	body := `{"workspace_id":"ws-123","error_rate":0.1,"sample_error":"","active_tasks":2,"uptime_seconds":3600}`
	c.Request = httptest.NewRequest("POST", "/registry/heartbeat", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Heartbeat(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestHeartbeatHandler_Degraded(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewRegistryHandler(broadcaster)

	// Expect heartbeat UPDATE
	mock.ExpectExec("UPDATE workspaces SET").
		WithArgs("ws-123", 0.8, "connection timeout", 0, 7200).
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Expect evaluateStatus SELECT — currently online
	mock.ExpectQuery("SELECT status FROM workspaces WHERE id =").
		WithArgs("ws-123").
		WillReturnRows(sqlmock.NewRows([]string{"status"}).AddRow("online"))

	// Expect status transition to degraded
	mock.ExpectExec("UPDATE workspaces SET status = 'degraded'").
		WithArgs("ws-123").
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Expect RecordAndBroadcast INSERT for WORKSPACE_DEGRADED
	mock.ExpectExec("INSERT INTO structure_events").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)

	body := `{"workspace_id":"ws-123","error_rate":0.8,"sample_error":"connection timeout","active_tasks":0,"uptime_seconds":7200}`
	c.Request = httptest.NewRequest("POST", "/registry/heartbeat", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Heartbeat(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestHeartbeatHandler_Recovery(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewRegistryHandler(broadcaster)

	// Expect heartbeat UPDATE
	mock.ExpectExec("UPDATE workspaces SET").
		WithArgs("ws-123", 0.05, "", 1, 9000).
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Expect evaluateStatus SELECT — currently degraded
	mock.ExpectQuery("SELECT status FROM workspaces WHERE id =").
		WithArgs("ws-123").
		WillReturnRows(sqlmock.NewRows([]string{"status"}).AddRow("degraded"))

	// Expect status transition back to online
	mock.ExpectExec("UPDATE workspaces SET status = 'online'").
		WithArgs("ws-123").
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Expect RecordAndBroadcast INSERT for WORKSPACE_ONLINE
	mock.ExpectExec("INSERT INTO structure_events").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)

	body := `{"workspace_id":"ws-123","error_rate":0.05,"sample_error":"","active_tasks":1,"uptime_seconds":9000}`
	c.Request = httptest.NewRequest("POST", "/registry/heartbeat", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Heartbeat(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ---------- TestWorkspaceCreate ----------

func TestWorkspaceCreate(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", "/tmp/configs")

	// Expect workspace INSERT (uuid is dynamic, use AnyArg)
	mock.ExpectExec("INSERT INTO workspaces").
		WithArgs(sqlmock.AnyArg(), "Test Agent", nil, 1, (*string)(nil)).
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Expect canvas_layouts INSERT
	mock.ExpectExec("INSERT INTO canvas_layouts").
		WithArgs(sqlmock.AnyArg(), float64(100), float64(200)).
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Expect RecordAndBroadcast INSERT for WORKSPACE_PROVISIONING
	mock.ExpectExec("INSERT INTO structure_events").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)

	body := `{"name":"Test Agent","canvas":{"x":100,"y":200}}`
	c.Request = httptest.NewRequest("POST", "/workspaces", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Create(c)

	if w.Code != http.StatusCreated {
		t.Errorf("expected status 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if resp["status"] != "provisioning" {
		t.Errorf("expected status 'provisioning', got %v", resp["status"])
	}
	if resp["id"] == nil || resp["id"] == "" {
		t.Error("expected non-empty id in response")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ---------- TestWorkspaceList ----------

func TestWorkspaceList(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", "/tmp/configs")

	columns := []string{
		"id", "name", "role", "tier", "status", "agent_card", "url",
		"parent_id", "active_tasks", "last_error_rate", "last_sample_error",
		"uptime_seconds", "x", "y", "collapsed",
	}
	rows := sqlmock.NewRows(columns).
		AddRow("ws-1", "Agent One", "worker", 1, "online", []byte("null"), "http://localhost:8001",
			nil, 0, 0.0, "", 100, 10.0, 20.0, false).
		AddRow("ws-2", "Agent Two", "manager", 2, "provisioning", []byte("null"), "",
			nil, 0, 0.0, "", 0, 50.0, 60.0, false)

	mock.ExpectQuery("SELECT w.id, w.name").
		WillReturnRows(rows)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/workspaces", nil)

	handler.List(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if len(resp) != 2 {
		t.Errorf("expected 2 workspaces, got %d", len(resp))
	}
	if resp[0]["name"] != "Agent One" {
		t.Errorf("expected first workspace name 'Agent One', got %v", resp[0]["name"])
	}
	if resp[1]["status"] != "provisioning" {
		t.Errorf("expected second workspace status 'provisioning', got %v", resp[1]["status"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ---------- TestProxyA2A ----------

func TestProxyA2A_JSONRPCWrapping(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", "/tmp/configs")

	// Create a mock agent endpoint that captures the request
	var receivedBody map[string]interface{}
	agentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewDecoder(r.Body).Decode(&receivedBody)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"jsonrpc":"2.0","id":"1","result":{"status":"ok"}}`)
	}))
	defer agentServer.Close()

	// Cache the agent URL in Redis so the handler finds it
	mr.Set(fmt.Sprintf("ws:%s:url", "ws-proxy"), agentServer.URL)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-proxy"}}

	// Send a bare payload (no jsonrpc envelope)
	body := `{"method":"message/send","params":{"message":{"role":"user","parts":[{"text":"hello"}]}}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-proxy/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.ProxyA2A(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	// Verify the proxy wrapped the payload in a JSON-RPC envelope
	if receivedBody["jsonrpc"] != "2.0" {
		t.Errorf("expected jsonrpc '2.0', got %v", receivedBody["jsonrpc"])
	}
	if receivedBody["id"] == nil || receivedBody["id"] == "" {
		t.Error("expected non-empty id in JSON-RPC envelope")
	}
	if receivedBody["method"] != "message/send" {
		t.Errorf("expected method 'message/send', got %v", receivedBody["method"])
	}

	// Verify messageId was injected
	params, _ := receivedBody["params"].(map[string]interface{})
	msg, _ := params["message"].(map[string]interface{})
	if msg["messageId"] == nil || msg["messageId"] == "" {
		t.Error("expected messageId to be injected into params.message")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestProxyA2A_WorkspaceNotFound(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t) // empty Redis — no cached URL
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", "/tmp/configs")

	// Redis miss → DB lookup → no rows
	mock.ExpectQuery("SELECT url, status FROM workspaces WHERE id =").
		WithArgs("ws-missing").
		WillReturnRows(sqlmock.NewRows([]string{"url", "status"}))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-missing"}}

	body := `{"method":"message/send","params":{}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-missing/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.ProxyA2A(c)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected status 404, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestProxyA2A_WorkspaceOffline(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t) // empty Redis — no cached URL
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", "/tmp/configs")

	// Redis miss → DB lookup → workspace exists but URL is empty
	mock.ExpectQuery("SELECT url, status FROM workspaces WHERE id =").
		WithArgs("ws-offline").
		WillReturnRows(sqlmock.NewRows([]string{"url", "status"}).AddRow(nil, "offline"))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-offline"}}

	body := `{"method":"message/send","params":{}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-offline/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.ProxyA2A(c)

	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("expected status 503, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}
