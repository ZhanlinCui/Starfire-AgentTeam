package registry

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/agent-molecule/platform/internal/db"
	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

// mockChecker implements ContainerChecker for testing.
type mockChecker struct {
	mu      sync.Mutex
	running map[string]bool
}

func (m *mockChecker) IsRunning(_ context.Context, workspaceID string) (bool, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.running[workspaceID], nil
}

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

func TestSweepOnlineWorkspaces_DeadContainer(t *testing.T) {
	mock := setupTestDB(t)
	mr := setupTestRedis(t)

	// Set up Redis keys for a workspace that's about to be detected as dead
	mr.Set("ws:ws-dead-123", "online")
	mr.Set("ws:ws-dead-123:url", "http://127.0.0.1:32000")
	mr.Set("ws:ws-dead-123:internal_url", "http://ws-ws-dead-123:8000")

	// Mock: query returns one online workspace
	rows := sqlmock.NewRows([]string{"id"}).AddRow("ws-dead-123")
	mock.ExpectQuery("SELECT id FROM workspaces WHERE status IN").
		WillReturnRows(rows)

	// Mock: update to offline
	mock.ExpectExec("UPDATE workspaces SET status = 'offline'").
		WithArgs("ws-dead-123").
		WillReturnResult(sqlmock.NewResult(0, 1))

	checker := &mockChecker{running: map[string]bool{
		"ws-dead-123": false, // container is dead
	}}

	var offlineCalled []string
	var mu sync.Mutex
	onOffline := func(_ context.Context, id string) {
		mu.Lock()
		offlineCalled = append(offlineCalled, id)
		mu.Unlock()
	}

	sweepOnlineWorkspaces(context.Background(), checker, onOffline)

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("unmet SQL expectations: %v", err)
	}

	mu.Lock()
	defer mu.Unlock()
	if len(offlineCalled) != 1 || offlineCalled[0] != "ws-dead-123" {
		t.Fatalf("expected onOffline for ws-dead-123, got: %v", offlineCalled)
	}

	// Redis keys should be cleared
	if mr.Exists("ws:ws-dead-123") {
		t.Error("expected liveness key to be deleted")
	}
	if mr.Exists("ws:ws-dead-123:url") {
		t.Error("expected URL cache to be deleted")
	}
	if mr.Exists("ws:ws-dead-123:internal_url") {
		t.Error("expected internal URL cache to be deleted")
	}
}

func TestSweepOnlineWorkspaces_RunningContainer(t *testing.T) {
	mock := setupTestDB(t)
	setupTestRedis(t)

	rows := sqlmock.NewRows([]string{"id"}).AddRow("ws-alive-456")
	mock.ExpectQuery("SELECT id FROM workspaces WHERE status IN").
		WillReturnRows(rows)

	// No UPDATE expected — container is running
	checker := &mockChecker{running: map[string]bool{
		"ws-alive-456": true,
	}}

	offlineCalled := false
	sweepOnlineWorkspaces(context.Background(), checker, func(_ context.Context, id string) {
		offlineCalled = true
	})

	if offlineCalled {
		t.Error("onOffline should not be called for running container")
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("unmet SQL expectations: %v", err)
	}
}

func TestStartHealthSweep_NilChecker(t *testing.T) {
	// Should return immediately without panicking
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	done := make(chan struct{})
	go func() {
		StartHealthSweep(ctx, nil, time.Second, nil)
		close(done)
	}()

	select {
	case <-done:
		// Good — returned immediately
	case <-time.After(2 * time.Second):
		t.Fatal("StartHealthSweep with nil checker should return immediately")
	}
}
