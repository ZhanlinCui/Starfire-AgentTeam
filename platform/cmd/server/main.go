package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/agent-molecule/platform/internal/crypto"
	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/agent-molecule/platform/internal/registry"
	"github.com/agent-molecule/platform/internal/router"
	"github.com/agent-molecule/platform/internal/ws"
)

func main() {
	// Secrets encryption (optional — disabled if SECRETS_ENCRYPTION_KEY not set)
	crypto.Init()
	if crypto.IsEnabled() {
		log.Println("Secrets encryption: AES-256-GCM enabled")
	} else {
		log.Println("Secrets encryption: disabled (set SECRETS_ENCRYPTION_KEY for production)")
	}

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
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
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
	platformURL := envOr("PLATFORM_URL", fmt.Sprintf("http://host.docker.internal:%s", port))
	configsDir := envOr("CONFIGS_DIR", findConfigsDir())

	// Router
	r := router.Setup(hub, broadcaster, prov, platformURL, configsDir)

	// HTTP server with graceful shutdown
	srv := &http.Server{
		Addr:    fmt.Sprintf(":%s", port),
		Handler: r,
	}

	// Start server in goroutine
	go func() {
		log.Printf("Platform starting on :%s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down gracefully...")

	// Cancel background goroutines (liveness monitor, Redis subscriber)
	cancel()

	// Drain HTTP connections (30s timeout)
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("Server forced shutdown: %v", err)
	}

	// Close WebSocket hub
	hub.Close()

	log.Println("Platform stopped")
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
			// Verify the directory has at least one template with a config.yaml
			entries, _ := os.ReadDir(c)
			hasTemplate := false
			for _, e := range entries {
				if e.IsDir() {
					if _, err := os.Stat(filepath.Join(c, e.Name(), "config.yaml")); err == nil {
						hasTemplate = true
						break
					}
				}
			}
			if !hasTemplate {
				continue
			}
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
