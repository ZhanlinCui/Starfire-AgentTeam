package handlers

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
)

// ==================== ProxyA2A — invalid JSON body ====================

func TestProxyA2A_InvalidJSON(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	// Cache a URL so the handler doesn't fall back to DB
	mr.Set(fmt.Sprintf("ws:%s:url", "ws-badjson"), "http://localhost:9999")

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-badjson"}}

	c.Request = httptest.NewRequest("POST", "/workspaces/ws-badjson/a2a", bytes.NewBufferString("not json"))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.ProxyA2A(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if resp["error"] != "invalid JSON" {
		t.Errorf("expected error 'invalid JSON', got %v", resp["error"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ==================== ProxyA2A — already-wrapped JSON-RPC ====================

func TestProxyA2A_AlreadyWrappedJSONRPC(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	// Create a mock agent that captures the forwarded request
	var receivedBody map[string]interface{}
	agentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewDecoder(r.Body).Decode(&receivedBody)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"jsonrpc":"2.0","id":"original-id","result":{"status":"ok"}}`)
	}))
	defer agentServer.Close()

	mr.Set(fmt.Sprintf("ws:%s:url", "ws-wrapped"), agentServer.URL)

	// Expect async activity log
	mock.ExpectExec("INSERT INTO activity_logs").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-wrapped"}}

	// Send an already-wrapped JSON-RPC body
	body := `{"jsonrpc":"2.0","id":"original-id","method":"message/send","params":{"message":{"role":"user","parts":[{"text":"hello"}]}}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-wrapped/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.ProxyA2A(c)

	// Give the async LogActivity goroutine a moment
	time.Sleep(50 * time.Millisecond)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	// Verify the proxy preserved the original ID (didn't re-wrap)
	if receivedBody["id"] != "original-id" {
		t.Errorf("expected original id to be preserved, got %v", receivedBody["id"])
	}
	if receivedBody["jsonrpc"] != "2.0" {
		t.Errorf("expected jsonrpc '2.0', got %v", receivedBody["jsonrpc"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ==================== ProxyA2A — DB lookup fallback (Redis miss) ====================

func TestProxyA2A_DBLookupFallback(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t) // empty Redis — no cached URL
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	// Create mock agent
	agentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"jsonrpc":"2.0","id":"1","result":{"status":"ok"}}`)
	}))
	defer agentServer.Close()

	// Redis miss → DB lookup → returns URL
	mock.ExpectQuery("SELECT url, status FROM workspaces WHERE id =").
		WithArgs("ws-db-fallback").
		WillReturnRows(sqlmock.NewRows([]string{"url", "status"}).AddRow(agentServer.URL, "online"))

	// Expect async activity log
	mock.ExpectExec("INSERT INTO activity_logs").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-db-fallback"}}

	body := `{"method":"message/send","params":{"message":{"role":"user","parts":[{"text":"hello"}]}}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-db-fallback/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.ProxyA2A(c)

	time.Sleep(50 * time.Millisecond)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ==================== ProxyA2A — DB lookup error (500) ====================

func TestProxyA2A_DBLookupError(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t) // empty Redis
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	// Redis miss → DB lookup → error
	mock.ExpectQuery("SELECT url, status FROM workspaces WHERE id =").
		WithArgs("ws-dberr").
		WillReturnError(sql.ErrConnDone)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-dberr"}}

	body := `{"method":"message/send","params":{}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-dberr/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.ProxyA2A(c)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ==================== ProxyA2A — agent returns error status ====================

func TestProxyA2A_AgentReturnsError(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	agentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprint(w, `{"jsonrpc":"2.0","id":"1","error":{"code":-32000,"message":"agent error"}}`)
	}))
	defer agentServer.Close()

	mr.Set(fmt.Sprintf("ws:%s:url", "ws-agent-err"), agentServer.URL)

	// Expect async activity log (with "error" status since agent returned 500)
	mock.ExpectExec("INSERT INTO activity_logs").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-agent-err"}}

	body := `{"method":"message/send","params":{"message":{"role":"user","parts":[{"text":"fail"}]}}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-agent-err/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.ProxyA2A(c)

	time.Sleep(50 * time.Millisecond)

	// The proxy returns the agent's status code as-is
	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500 (agent error), got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ==================== ProxyA2A — messageId injection ====================

func TestProxyA2A_MessageIDInjected(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	var receivedBody map[string]interface{}
	agentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewDecoder(r.Body).Decode(&receivedBody)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"jsonrpc":"2.0","id":"1","result":{"status":"ok"}}`)
	}))
	defer agentServer.Close()

	mr.Set(fmt.Sprintf("ws:%s:url", "ws-msgid"), agentServer.URL)

	mock.ExpectExec("INSERT INTO activity_logs").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-msgid"}}

	// Send message without messageId — should be injected
	body := `{"method":"message/send","params":{"message":{"role":"user","parts":[{"text":"hello"}]}}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-msgid/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.ProxyA2A(c)

	time.Sleep(50 * time.Millisecond)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
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

// ==================== ProxyA2A — X-Workspace-ID header ====================

func TestProxyA2A_CallerIDPropagated(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	agentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"jsonrpc":"2.0","id":"1","result":{}}`)
	}))
	defer agentServer.Close()

	mr.Set(fmt.Sprintf("ws:%s:url", "ws-target"), agentServer.URL)

	// Access control: caller and target must be siblings (same parent_id)
	mock.ExpectQuery("SELECT id, parent_id FROM workspaces WHERE id = ").
		WithArgs("ws-caller").
		WillReturnRows(sqlmock.NewRows([]string{"id", "parent_id"}).AddRow("ws-caller", "ws-parent"))
	mock.ExpectQuery("SELECT id, parent_id FROM workspaces WHERE id = ").
		WithArgs("ws-target").
		WillReturnRows(sqlmock.NewRows([]string{"id", "parent_id"}).AddRow("ws-target", "ws-parent"))

	// Expect activity log with source_id set
	mock.ExpectExec("INSERT INTO activity_logs").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-target"}}

	body := `{"method":"message/send","params":{"message":{"role":"user","parts":[{"text":"test"}]}}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-target/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")
	c.Request.Header.Set("X-Workspace-ID", "ws-caller")

	handler.ProxyA2A(c)

	time.Sleep(50 * time.Millisecond)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// mockCanCommunicate sets up sqlmock expectations for CanCommunicate(caller, target).
// allowed=true sets up rows that satisfy the access policy (siblings under same parent).
// allowed=false sets up rows that don't (different parents).
func mockCanCommunicate(mock sqlmock.Sqlmock, caller, target string, allowed bool) {
	callerParent := "shared-parent"
	targetParent := "shared-parent"
	if !allowed {
		targetParent = "different-parent"
	}
	mock.ExpectQuery("SELECT id, parent_id FROM workspaces WHERE id = ").
		WithArgs(caller).
		WillReturnRows(sqlmock.NewRows([]string{"id", "parent_id"}).AddRow(caller, callerParent))
	mock.ExpectQuery("SELECT id, parent_id FROM workspaces WHERE id = ").
		WithArgs(target).
		WillReturnRows(sqlmock.NewRows([]string{"id", "parent_id"}).AddRow(target, targetParent))
}

// ==================== ProxyA2A — Access Control ====================

func TestProxyA2A_AccessDenied_DifferentParents(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	mr.Set(fmt.Sprintf("ws:%s:url", "ws-target"), "http://localhost:1")

	mockCanCommunicate(mock, "ws-caller", "ws-target", false)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-target"}}

	body := `{"method":"message/send","params":{"message":{"role":"user","parts":[{"text":"hi"}]}}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-target/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")
	c.Request.Header.Set("X-Workspace-ID", "ws-caller")

	handler.ProxyA2A(c)

	if w.Code != http.StatusForbidden {
		t.Errorf("expected 403, got %d: %s", w.Code, w.Body.String())
	}
}

func TestProxyA2A_AllowedSelf_SkipsAccessCheck(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	agentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"jsonrpc":"2.0","id":"1","result":{}}`)
	}))
	defer agentServer.Close()
	mr.Set(fmt.Sprintf("ws:%s:url", "ws-self"), agentServer.URL)

	mock.ExpectExec("INSERT INTO activity_logs").WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-self"}}

	body := `{"method":"message/send","params":{"message":{"role":"user","parts":[{"text":"hi"}]}}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-self/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")
	c.Request.Header.Set("X-Workspace-ID", "ws-self")

	handler.ProxyA2A(c)
	time.Sleep(50 * time.Millisecond)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200 for self-call, got %d: %s", w.Code, w.Body.String())
	}
}

func TestProxyA2A_SystemCaller_BypassesAccessCheck(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())

	agentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"jsonrpc":"2.0","id":"1","result":{}}`)
	}))
	defer agentServer.Close()
	mr.Set(fmt.Sprintf("ws:%s:url", "ws-target"), agentServer.URL)

	mock.ExpectExec("INSERT INTO activity_logs").WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-target"}}

	body := `{"method":"message/send","params":{"message":{"role":"user","parts":[{"text":"hi"}]}}}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-target/a2a", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")
	c.Request.Header.Set("X-Workspace-ID", "webhook:github")

	handler.ProxyA2A(c)
	time.Sleep(50 * time.Millisecond)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200 for system caller, got %d: %s", w.Code, w.Body.String())
	}
}

func TestIsSystemCaller(t *testing.T) {
	cases := []struct {
		caller   string
		expected bool
	}{
		{"webhook:github", true},
		{"system:scheduler", true},
		{"test:fake", true},
		{"ws-uuid-123", false},
		{"", false},
		{"webhook", false},
		{"foo:bar", false},
	}
	for _, tc := range cases {
		got := isSystemCaller(tc.caller)
		if got != tc.expected {
			t.Errorf("isSystemCaller(%q) = %v, want %v", tc.caller, got, tc.expected)
		}
	}
}

// ==================== detectPlatformInDocker ====================

func TestDetectPlatformInDocker_EnvVar(t *testing.T) {
	cases := []struct {
		env      string
		expected bool
	}{
		{"1", true},
		{"true", true},
		{"TRUE", true},
		{"True", true},
		{"yes", false},  // strconv.ParseBool doesn't accept "yes"
		{"0", false},
		{"false", false},
		{"bogus", false}, // unparseable → fall through to /.dockerenv check
	}
	// Tests touch the global env var; guarantee cleanup after each case.
	for _, tc := range cases {
		t.Run(tc.env, func(t *testing.T) {
			t.Setenv("STARFIRE_IN_DOCKER", tc.env)
			// Mask any real /.dockerenv that might exist on the CI host
			// by asserting only the env-var path is exercised here; if
			// env is unparseable we still fall through to the file check.
			got := detectPlatformInDocker()
			if tc.env != "bogus" && got != tc.expected {
				t.Errorf("STARFIRE_IN_DOCKER=%q → detectPlatformInDocker() = %v, want %v",
					tc.env, got, tc.expected)
			}
		})
	}
}

func TestSetPlatformInDockerForTest(t *testing.T) {
	original := platformInDocker
	restore := setPlatformInDockerForTest(!original)
	if platformInDocker == original {
		t.Errorf("setPlatformInDockerForTest did not change platformInDocker")
	}
	restore()
	if platformInDocker != original {
		t.Errorf("restore function did not reset platformInDocker to %v (got %v)",
			original, platformInDocker)
	}
}
