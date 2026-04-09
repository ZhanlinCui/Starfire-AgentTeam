package handlers

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
)

// ==================== List secrets ====================

func TestSecretsList_Success(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	mock.ExpectQuery("SELECT key, created_at, updated_at FROM workspace_secrets").
		WithArgs("550e8400-e29b-41d4-a716-446655440000").
		WillReturnRows(sqlmock.NewRows([]string{"key", "created_at", "updated_at"}).
			AddRow("API_KEY", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z").
			AddRow("DB_PASSWORD", "2024-01-02T00:00:00Z", "2024-01-03T00:00:00Z"))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets", nil)

	handler.List(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if len(resp) != 2 {
		t.Errorf("expected 2 secrets, got %d", len(resp))
	}
	if resp[0]["key"] != "API_KEY" {
		t.Errorf("expected first key 'API_KEY', got %v", resp[0]["key"])
	}
	if resp[0]["has_value"] != true {
		t.Errorf("expected has_value true, got %v", resp[0]["has_value"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestSecretsList_Empty(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	mock.ExpectQuery("SELECT key, created_at, updated_at FROM workspace_secrets").
		WithArgs("550e8400-e29b-41d4-a716-446655440000").
		WillReturnRows(sqlmock.NewRows([]string{"key", "created_at", "updated_at"}))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets", nil)

	handler.List(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if len(resp) != 0 {
		t.Errorf("expected 0 secrets, got %d", len(resp))
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestSecretsList_InvalidWorkspaceID(t *testing.T) {
	setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "not-a-uuid"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/not-a-uuid/secrets", nil)

	handler.List(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if resp["error"] != "invalid workspace ID" {
		t.Errorf("expected error 'invalid workspace ID', got %v", resp["error"])
	}
}

func TestSecretsList_DBError(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	mock.ExpectQuery("SELECT key, created_at, updated_at FROM workspace_secrets").
		WithArgs("550e8400-e29b-41d4-a716-446655440000").
		WillReturnError(sql.ErrConnDone)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets", nil)

	handler.List(c)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ==================== Set secret ====================

func TestSecretsSet_InvalidWorkspaceID(t *testing.T) {
	setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "bad-id"}}

	body := `{"key":"API_KEY","value":"secret123"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/bad-id/secrets", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Set(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d: %s", w.Code, w.Body.String())
	}
}

func TestSecretsSet_MissingKey(t *testing.T) {
	setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"}}

	body := `{"value":"secret123"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Set(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d: %s", w.Code, w.Body.String())
	}
}

func TestSecretsSet_MissingValue(t *testing.T) {
	setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"}}

	body := `{"key":"API_KEY"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Set(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d: %s", w.Code, w.Body.String())
	}
}

func TestSecretsSet_Success(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	// The crypto.Encrypt will use plaintext mode if SECRETS_ENCRYPTION_KEY is not set
	mock.ExpectExec("INSERT INTO workspace_secrets").
		WithArgs("550e8400-e29b-41d4-a716-446655440000", "API_KEY", sqlmock.AnyArg()).
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"}}

	body := `{"key":"API_KEY","value":"sk-test123"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Set(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if resp["status"] != "saved" {
		t.Errorf("expected status 'saved', got %v", resp["status"])
	}
	if resp["key"] != "API_KEY" {
		t.Errorf("expected key 'API_KEY', got %v", resp["key"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestSecretsSet_AutoRestart(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)

	// Track whether restart was called via channel (replaces time.Sleep)
	done := make(chan string, 1)
	restartFunc := func(wsID string) {
		done <- wsID
	}
	handler := NewSecretsHandler(restartFunc)

	mock.ExpectExec("INSERT INTO workspace_secrets").
		WithArgs("550e8400-e29b-41d4-a716-446655440000", "DB_PASS", sqlmock.AnyArg()).
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"}}

	body := `{"key":"DB_PASS","value":"password123"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Set(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	select {
	case wsID := <-done:
		if wsID != "550e8400-e29b-41d4-a716-446655440000" {
			t.Errorf("expected restart to be called with workspace ID, got %q", wsID)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("restart callback not called within timeout")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestSecretsSet_DBError(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	mock.ExpectExec("INSERT INTO workspace_secrets").
		WithArgs("550e8400-e29b-41d4-a716-446655440000", "API_KEY", sqlmock.AnyArg()).
		WillReturnError(sql.ErrConnDone)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"}}

	body := `{"key":"API_KEY","value":"secret"}`
	c.Request = httptest.NewRequest("POST", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets", bytes.NewBufferString(body))
	c.Request.Header.Set("Content-Type", "application/json")

	handler.Set(c)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ==================== Delete secret ====================

func TestSecretsDelete_Success(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	mock.ExpectExec("DELETE FROM workspace_secrets WHERE workspace_id").
		WithArgs("550e8400-e29b-41d4-a716-446655440000", "API_KEY").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{
		{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"},
		{Key: "key", Value: "API_KEY"},
	}
	c.Request = httptest.NewRequest("DELETE", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets/API_KEY", nil)

	handler.Delete(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if resp["status"] != "deleted" {
		t.Errorf("expected status 'deleted', got %v", resp["status"])
	}
	if resp["key"] != "API_KEY" {
		t.Errorf("expected key 'API_KEY', got %v", resp["key"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestSecretsDelete_NotFound(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	mock.ExpectExec("DELETE FROM workspace_secrets WHERE workspace_id").
		WithArgs("550e8400-e29b-41d4-a716-446655440000", "MISSING_KEY").
		WillReturnResult(sqlmock.NewResult(0, 0)) // 0 rows affected

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{
		{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"},
		{Key: "key", Value: "MISSING_KEY"},
	}
	c.Request = httptest.NewRequest("DELETE", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets/MISSING_KEY", nil)

	handler.Delete(c)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected status 404, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestSecretsDelete_InvalidWorkspaceID(t *testing.T) {
	setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{
		{Key: "id", Value: "invalid"},
		{Key: "key", Value: "API_KEY"},
	}
	c.Request = httptest.NewRequest("DELETE", "/workspaces/invalid/secrets/API_KEY", nil)

	handler.Delete(c)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d: %s", w.Code, w.Body.String())
	}
}

func TestSecretsDelete_DBError(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	mock.ExpectExec("DELETE FROM workspace_secrets WHERE workspace_id").
		WithArgs("550e8400-e29b-41d4-a716-446655440000", "API_KEY").
		WillReturnError(sql.ErrConnDone)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{
		{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"},
		{Key: "key", Value: "API_KEY"},
	}
	c.Request = httptest.NewRequest("DELETE", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets/API_KEY", nil)

	handler.Delete(c)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestSecretsDelete_AutoRestart(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)

	done := make(chan string, 1)
	restartFunc := func(wsID string) {
		done <- wsID
	}
	handler := NewSecretsHandler(restartFunc)

	mock.ExpectExec("DELETE FROM workspace_secrets WHERE workspace_id").
		WithArgs("550e8400-e29b-41d4-a716-446655440000", "OLD_KEY").
		WillReturnResult(sqlmock.NewResult(0, 1))

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{
		{Key: "id", Value: "550e8400-e29b-41d4-a716-446655440000"},
		{Key: "key", Value: "OLD_KEY"},
	}
	c.Request = httptest.NewRequest("DELETE", "/workspaces/550e8400-e29b-41d4-a716-446655440000/secrets/OLD_KEY", nil)

	handler.Delete(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	select {
	case wsID := <-done:
		if wsID != "550e8400-e29b-41d4-a716-446655440000" {
			t.Errorf("expected restart called for workspace, got %q", wsID)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("restart callback not called within timeout")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

// ==================== GetModel ====================

func TestSecretsGetModel_Default(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	// No MODEL_PROVIDER secret
	mock.ExpectQuery("SELECT encrypted_value FROM workspace_secrets").
		WithArgs("ws-model").
		WillReturnError(sql.ErrNoRows)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-model"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/ws-model/model", nil)

	handler.GetModel(c)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if resp["model"] != "" {
		t.Errorf("expected empty model, got %v", resp["model"])
	}
	if resp["source"] != "default" {
		t.Errorf("expected source 'default', got %v", resp["source"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}

func TestSecretsGetModel_DBError(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)
	handler := NewSecretsHandler(nil)

	mock.ExpectQuery("SELECT encrypted_value FROM workspace_secrets").
		WithArgs("ws-model-err").
		WillReturnError(sql.ErrConnDone)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "ws-model-err"}}
	c.Request = httptest.NewRequest("GET", "/workspaces/ws-model-err/model", nil)

	handler.GetModel(c)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected status 500, got %d: %s", w.Code, w.Body.String())
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unmet sqlmock expectations: %v", err)
	}
}
