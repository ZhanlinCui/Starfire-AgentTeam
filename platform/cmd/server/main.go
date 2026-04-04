package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/agent-molecule/platform/internal/registry"
	"github.com/agent-molecule/platform/internal/router"
	"github.com/agent-molecule/platform/internal/ws"
)

func main() {
	// Database
	databaseURL := envOr("DATABASE_URL", "postgres://dev:dev@localhost:5432/agentmolecule?sslmode=disable")
	if err := db.InitPostgres(databaseURL); err != nil {
		log.Fatalf("Postgres init failed: %v", err)
	}

	// Run migrations
	migrationsDir := findMigrationsDir()
	if migrationsDir != "" {
		if err := db.RunMigrations(migrationsDir); err != nil {
			log.Fatalf("Migrations failed: %v", err)
		}
	}

	// Redis
	redisURL := envOr("REDIS_URL", "redis://localhost:6379")
	if err := db.InitRedis(redisURL); err != nil {
		log.Fatalf("Redis init failed: %v", err)
	}

	// WebSocket Hub — inject CanCommunicate as a function to avoid import cycles
	hub := ws.NewHub(registry.CanCommunicate)
	go hub.Run()

	// Event Broadcaster
	broadcaster := events.NewBroadcaster(hub)

	// Start Redis pub/sub subscriber
	ctx := context.Background()
	go broadcaster.Subscribe(ctx)

	// Start Liveness Monitor — use broadcaster callback to avoid import cycles
	go registry.StartLivenessMonitor(ctx, func(innerCtx context.Context, workspaceID string) {
		if err := broadcaster.RecordAndBroadcast(innerCtx, "WORKSPACE_OFFLINE", workspaceID, map[string]interface{}{}); err != nil {
			log.Printf("Liveness broadcast error for %s: %v", workspaceID, err)
		}
	})

	// Provisioner (optional — gracefully degrades if Docker not available)
	var prov *provisioner.Provisioner
	if p, err := provisioner.New(); err != nil {
		log.Printf("Provisioner disabled (Docker not available): %v", err)
	} else {
		prov = p
		defer prov.Close()
	}

	port := envOr("PORT", "8080")
	platformURL := fmt.Sprintf("http://localhost:%s", port)
	configsDir := envOr("CONFIGS_DIR", findConfigsDir())

	// Router
	r := router.Setup(hub, broadcaster, prov, platformURL, configsDir)
	log.Printf("Platform starting on :%s", port)
	if err := r.Run(fmt.Sprintf(":%s", port)); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func findConfigsDir() string {
	candidates := []string{
		"workspace-configs-templates",
		"../workspace-configs-templates",
		"../../workspace-configs-templates",
	}
	for _, c := range candidates {
		if info, err := os.Stat(c); err == nil && info.IsDir() {
			abs, _ := filepath.Abs(c)
			return abs
		}
	}
	return "workspace-configs-templates"
}

func findMigrationsDir() string {
	candidates := []string{
		"migrations",
		"platform/migrations",
		"../migrations",
		"../../migrations",
	}

	if exe, err := os.Executable(); err == nil {
		dir := filepath.Dir(exe)
		candidates = append(candidates,
			filepath.Join(dir, "migrations"),
			filepath.Join(dir, "..", "migrations"),
			filepath.Join(dir, "..", "..", "migrations"),
		)
	}

	for _, c := range candidates {
		if info, err := os.Stat(c); err == nil && info.IsDir() {
			abs, _ := filepath.Abs(c)
			log.Printf("Found migrations at: %s", abs)
			return abs
		}
	}
	log.Println("No migrations directory found")
	return ""
}
