package registry

import (
	"context"
	"log"
	"time"

	"github.com/agent-molecule/platform/internal/db"
)

// ContainerChecker checks if a workspace container is running via Docker API.
type ContainerChecker interface {
	IsRunning(ctx context.Context, workspaceID string) (bool, error)
}

// StartHealthSweep periodically checks all "online" workspaces against Docker.
// If a container is gone, it immediately marks the workspace offline and calls onOffline —
// rather than waiting for the 60s Redis TTL to expire.
func StartHealthSweep(ctx context.Context, checker ContainerChecker, interval time.Duration, onOffline OfflineHandler) {
	if checker == nil {
		log.Println("Health sweep: disabled (no container checker)")
		return
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	log.Printf("Health sweep: started (interval=%s)", interval)

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			sweepOnlineWorkspaces(ctx, checker, onOffline)
		}
	}
}

func sweepOnlineWorkspaces(ctx context.Context, checker ContainerChecker, onOffline OfflineHandler) {
	// Skip external workspaces (runtime='external') — they have no Docker container
	rows, err := db.DB.QueryContext(ctx,
		`SELECT id FROM workspaces WHERE status IN ('online', 'degraded') AND COALESCE(runtime, 'langgraph') != 'external'`)
	if err != nil {
		log.Printf("Health sweep: query error: %v", err)
		return
	}
	defer rows.Close()

	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err == nil {
			ids = append(ids, id)
		}
	}

	for _, id := range ids {
		running, err := checker.IsRunning(ctx, id)
		if err != nil {
			continue // Docker API error — skip, don't false-positive
		}
		if running {
			continue
		}

		log.Printf("Health sweep: container for %s is gone — marking offline", id)

		_, err = db.DB.ExecContext(ctx,
			`UPDATE workspaces SET status = 'offline', updated_at = now()
			 WHERE id = $1 AND status NOT IN ('removed', 'provisioning')`, id)
		if err != nil {
			log.Printf("Health sweep: failed to mark %s offline: %v", id, err)
			continue
		}

		db.ClearWorkspaceKeys(ctx, id)

		if onOffline != nil {
			onOffline(ctx, id)
		}
	}
}
