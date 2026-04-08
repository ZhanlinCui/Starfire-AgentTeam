package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
)

func TestSessionSearchReturnsActivityAndMemory(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	broadcaster := newTestBroadcaster()
	handler := NewActivityHandler(broadcaster)

	rows := sqlmock.NewRows([]string{
		"kind", "id", "workspace_id", "label", "content", "method", "status", "request_body", "response_body", "created_at",
	}).
		AddRow("activity", "act-1", "ws-123", "task_update", "Working on docs", "POST", "ok", `{"task":"docs"}`, `{"ok":true}`, time.Now()).
		AddRow("activity", "act-2", "ws-123", "skill_promotion", "Promoted repeatable workflow", "memory/skill-promotion", "ok", `{"promote_to_skill":true}`, `{"id":"mem-2"}`, time.Now()).
		AddRow("memory", "mem-1", "ws-123", "TEAM", "remember the docs path", "", "", nil, nil, time.Now())

	mock.ExpectQuery("WITH session_items AS").
		WithArgs("ws-123", "%docs%", 50).
		WillReturnRows(rows)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/workspaces/ws-123/session-search?q=docs", bytes.NewBufferString(""))
	c.Request.Header.Set("Content-Type", "application/json")
	c.Params = gin.Params{{Key: "id", Value: "ws-123"}}

	handler.SessionSearch(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp []map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if len(resp) != 3 {
		t.Fatalf("expected 3 results, got %d", len(resp))
	}
	if resp[0]["kind"] != "activity" || resp[1]["kind"] != "activity" || resp[2]["kind"] != "memory" {
		t.Fatalf("unexpected result kinds: %#v", resp)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("unmet sqlmock expectations: %v", err)
	}
}
