package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
)

// ---------- Delegate: missing target_id → 400 ----------

func TestDelegate_MissingTargetID(t *testing.T) {
	setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	wh := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())
	dh := NewDelegationHandler(wh, broadcaster)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-source"}}
	body := `{"task":"do something"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-source/delegate", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	dh.Delegate(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// ---------- Delegate: missing task → 400 ----------

func TestDelegate_MissingTask(t *testing.T) {
	setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	wh := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())
	dh := NewDelegationHandler(wh, broadcaster)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-source"}}
	body := `{"target_id":"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-source/delegate", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	dh.Delegate(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// ---------- Delegate: invalid UUID target_id → 400 ----------

func TestDelegate_InvalidUUIDTargetID(t *testing.T) {
	setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	wh := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())
	dh := NewDelegationHandler(wh, broadcaster)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-source"}}
	body := `{"target_id":"not-a-valid-uuid","task":"do something"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-source/delegate", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	dh.Delegate(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["error"] != "target_id must be a valid UUID" {
		t.Errorf("expected UUID error message, got %v", resp["error"])
	}
}

// ---------- Delegate: success → 202 with delegation_id ----------

func TestDelegate_Success(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	wh := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())
	dh := NewDelegationHandler(wh, broadcaster)

	targetID := "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

	// Expect INSERT into activity_logs for delegation tracking
	mock.ExpectExec("INSERT INTO activity_logs").
		WithArgs("ws-source", "ws-source", targetID, "Delegating to "+targetID, sqlmock.AnyArg(), ).
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Expect RecordAndBroadcast INSERT into structure_events
	mock.ExpectExec("INSERT INTO structure_events").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-source"}}
	body := fmt.Sprintf(`{"target_id":"%s","task":"write unit tests"}`, targetID)
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-source/delegate", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	dh.Delegate(c)

	if w.Code != http.StatusAccepted {
		t.Errorf("expected 202, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if resp["delegation_id"] == nil || resp["delegation_id"] == "" {
		t.Error("expected non-empty delegation_id in response")
	}
	if resp["status"] != "delegated" {
		t.Errorf("expected status 'delegated', got %v", resp["status"])
	}
	if resp["target_id"] != targetID {
		t.Errorf("expected target_id %s, got %v", targetID, resp["target_id"])
	}
	// Should NOT have a warning when DB insert succeeds
	if resp["warning"] != nil {
		t.Errorf("expected no warning, got %v", resp["warning"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ---------- Delegate: DB insert fails → still 202 with warning ----------

func TestDelegate_DBInsertFails_Still202WithWarning(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	wh := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())
	dh := NewDelegationHandler(wh, broadcaster)

	targetID := "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

	// DB insert fails
	mock.ExpectExec("INSERT INTO activity_logs").
		WithArgs("ws-source", "ws-source", targetID, "Delegating to "+targetID, sqlmock.AnyArg()).
		WillReturnError(fmt.Errorf("database connection lost"))

	// RecordAndBroadcast still fires
	mock.ExpectExec("INSERT INTO structure_events").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-source"}}
	body := fmt.Sprintf(`{"target_id":"%s","task":"write unit tests"}`, targetID)
	c.Request = httptest.NewRequest("POST", "/workspaces/ws-source/delegate", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	dh.Delegate(c)

	if w.Code != http.StatusAccepted {
		t.Errorf("expected 202, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["warning"] == nil {
		t.Error("expected warning when DB insert fails")
	}
	if resp["delegation_id"] == nil || resp["delegation_id"] == "" {
		t.Error("expected non-empty delegation_id even on DB failure")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ---------- ListDelegations: empty results → 200 with [] ----------

func TestListDelegations_Empty(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	wh := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())
	dh := NewDelegationHandler(wh, broadcaster)

	rows := sqlmock.NewRows([]string{
		"id", "activity_type", "source_id", "target_id",
		"summary", "status", "error_detail", "response_body",
		"delegation_id", "created_at",
	})
	mock.ExpectQuery("SELECT id, activity_type").
		WithArgs("ws-source").
		WillReturnRows(rows)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-source"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/ws-source/delegations", nil)

	dh.ListDelegations(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp []interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if len(resp) != 0 {
		t.Errorf("expected empty array, got %d entries", len(resp))
	}
}

// ---------- ListDelegations: with results → 200 with entries ----------

func TestListDelegations_WithResults(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	wh := NewWorkspaceHandler(broadcaster, nil, "http://localhost:8080", t.TempDir())
	dh := NewDelegationHandler(wh, broadcaster)

	now := time.Now()
	rows := sqlmock.NewRows([]string{
		"id", "activity_type", "source_id", "target_id",
		"summary", "status", "error_detail", "response_body",
		"delegation_id", "created_at",
	}).
		AddRow("1", "delegation", "ws-source", "ws-target",
			"Delegating to ws-target", "pending", "", "",
			"del-111", now).
		AddRow("2", "delegation", "ws-source", "ws-target",
			"Delegation completed (hello world)", "completed", "", "hello world",
			"del-111", now.Add(time.Minute))

	mock.ExpectQuery("SELECT id, activity_type").
		WithArgs("ws-source").
		WillReturnRows(rows)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-source"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/ws-source/delegations", nil)

	dh.ListDelegations(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if len(resp) != 2 {
		t.Fatalf("expected 2 entries, got %d", len(resp))
	}

	// Check first entry (pending delegation)
	if resp[0]["type"] != "delegation" {
		t.Errorf("expected type 'delegation', got %v", resp[0]["type"])
	}
	if resp[0]["status"] != "pending" {
		t.Errorf("expected status 'pending', got %v", resp[0]["status"])
	}
	if resp[0]["delegation_id"] != "del-111" {
		t.Errorf("expected delegation_id 'del-111', got %v", resp[0]["delegation_id"])
	}
	if resp[0]["source_id"] != "ws-source" {
		t.Errorf("expected source_id 'ws-source', got %v", resp[0]["source_id"])
	}
	if resp[0]["target_id"] != "ws-target" {
		t.Errorf("expected target_id 'ws-target', got %v", resp[0]["target_id"])
	}

	// Check second entry (completed, has response_preview)
	if resp[1]["status"] != "completed" {
		t.Errorf("expected status 'completed', got %v", resp[1]["status"])
	}
	if resp[1]["response_preview"] != "hello world" {
		t.Errorf("expected response_preview 'hello world', got %v", resp[1]["response_preview"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}
