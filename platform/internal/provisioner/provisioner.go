// Package provisioner manages Docker container lifecycle for workspace agents.
package provisioner

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/network"
	"github.com/docker/docker/client"
	"github.com/docker/go-connections/nat"
)

const (
	// DefaultImage is the workspace runtime Docker image (unified — handles all runtimes).
	DefaultImage = "workspace-template:latest"

	// DefaultNetwork is the Docker network workspaces join.
	DefaultNetwork = "agent-molecule-net"

	// DefaultPort is the port the A2A server listens on inside the container.
	DefaultPort = "8000"

	// ProvisionTimeout is how long to wait for first heartbeat before marking as failed.
	ProvisionTimeout = 3 * time.Minute
)

// WorkspaceConfig holds the parameters needed to provision a workspace container.
type WorkspaceConfig struct {
	WorkspaceID   string
	ConfigPath    string // Host path to workspace config directory
	PluginsPath   string // Host path to plugins directory (mounted at /plugins)
	WorkspacePath string // Host path to bind-mount as /workspace (if empty, uses Docker named volume)
	Tier          int
	Runtime       string            // "langgraph" (default) or "claude-code", "codex", "ollama", "custom"
	EnvVars       map[string]string // Additional env vars (API keys, etc.)
	PlatformURL   string
}

// Provisioner manages Docker containers for workspace agents.
type Provisioner struct {
	cli *client.Client
}

// New creates a new Provisioner connected to the local Docker daemon.
func New() (*Provisioner, error) {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Docker: %w", err)
	}
	return &Provisioner{cli: cli}, nil
}

// ContainerName returns the Docker container name for a workspace.
func ContainerName(workspaceID string) string {
	id := workspaceID
	if len(id) > 12 {
		id = id[:12]
	}
	return fmt.Sprintf("ws-%s", id)
}

// InternalURL returns the Docker-internal URL for a workspace container.
func InternalURL(workspaceID string) string {
	return fmt.Sprintf("http://%s:%s", ContainerName(workspaceID), DefaultPort)
}

// Start provisions and starts a workspace container.
func (p *Provisioner) Start(ctx context.Context, cfg WorkspaceConfig) (string, error) {
	name := ContainerName(cfg.WorkspaceID)

	// Build environment variables
	env := []string{
		fmt.Sprintf("WORKSPACE_ID=%s", cfg.WorkspaceID),
		fmt.Sprintf("WORKSPACE_CONFIG_PATH=/configs"),
		fmt.Sprintf("PLATFORM_URL=%s", cfg.PlatformURL),
		fmt.Sprintf("TIER=%d", cfg.Tier),
		"PLUGINS_DIR=/plugins",
	}
	for k, v := range cfg.EnvVars {
		env = append(env, fmt.Sprintf("%s=%s", k, v))
	}

	// Container config — single unified image handles all runtimes via config.yaml
	containerCfg := &container.Config{
		Image: DefaultImage,
		Env:   env,
		ExposedPorts: nat.PortSet{
			nat.Port(DefaultPort + "/tcp"): {},
		},
	}

	// Host config with volume mounts
	var workspaceMount string
	if cfg.WorkspacePath != "" {
		// Bind-mount host directory — all agents share the same codebase
		workspaceMount = fmt.Sprintf("%s:/workspace", cfg.WorkspacePath)
		log.Printf("Provisioner: bind-mounting host %s as /workspace", cfg.WorkspacePath)
	} else {
		// Isolated Docker named volume per workspace
		volumeName := fmt.Sprintf("ws-%s-workspace", cfg.WorkspaceID)
		workspaceMount = fmt.Sprintf("%s:/workspace", volumeName)
		log.Printf("Provisioner: workspace volume %s (created by Docker if new)", volumeName)
	}
	binds := []string{
		fmt.Sprintf("%s:/configs:ro", cfg.ConfigPath),
		workspaceMount,
	}
	if cfg.PluginsPath != "" {
		binds = append(binds, fmt.Sprintf("%s:/plugins:ro", cfg.PluginsPath))
	}

	hostCfg := &container.HostConfig{
		Binds: binds,
		RestartPolicy: container.RestartPolicy{Name: "unless-stopped"},
		PortBindings: nat.PortMap{
			nat.Port(DefaultPort + "/tcp"): []nat.PortBinding{
				{HostIP: "127.0.0.1", HostPort: ""}, // Ephemeral host port
			},
		},
	}

	// Tier-based flags
	// Note: ReadonlyRootfs is disabled because CLI runtimes (Claude Code, Codex)
	// need writable filesystem for their runtime data (.claude/, .npm/, tmp files).
	// Tier 1 still restricts the workspace volume (no writable /workspace).
	if cfg.Tier == 1 {
		tier1Binds := []string{fmt.Sprintf("%s:/configs:ro", cfg.ConfigPath)}
		if cfg.PluginsPath != "" {
			tier1Binds = append(tier1Binds, fmt.Sprintf("%s:/plugins:ro", cfg.PluginsPath))
		}
		hostCfg.Binds = tier1Binds
	}

	// Network config — join agent-molecule-net with container name as alias
	networkCfg := &network.NetworkingConfig{
		EndpointsConfig: map[string]*network.EndpointSettings{
			DefaultNetwork: {
				Aliases: []string{name},
			},
		},
	}

	// Create and start container
	resp, err := p.cli.ContainerCreate(ctx, containerCfg, hostCfg, networkCfg, nil, name)
	if err != nil {
		return "", fmt.Errorf("failed to create container: %w", err)
	}

	if err := p.cli.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
		// Clean up created container on start failure
		_ = p.cli.ContainerRemove(ctx, resp.ID, container.RemoveOptions{Force: true})
		return "", fmt.Errorf("failed to start container: %w", err)
	}

	// Resolve the host-mapped port so the platform can reach the container from the host.
	// The provisioner uses ephemeral port binding (127.0.0.1:0 → 8000/tcp), so we need
	// to inspect the container to find the actual assigned port.
	hostURL := InternalURL(cfg.WorkspaceID) // fallback to Docker-internal
	info, inspectErr := p.cli.ContainerInspect(ctx, resp.ID)
	if inspectErr == nil {
		portBindings := info.NetworkSettings.Ports[nat.Port(DefaultPort+"/tcp")]
		if len(portBindings) > 0 {
			hostPort := portBindings[0].HostPort
			hostIP := portBindings[0].HostIP
			if hostIP == "" {
				hostIP = "127.0.0.1"
			}
			hostURL = fmt.Sprintf("http://%s:%s", hostIP, hostPort)
		}
	}

	log.Printf("Provisioner: started container %s for workspace %s at %s (internal: %s)", name, cfg.WorkspaceID, hostURL, InternalURL(cfg.WorkspaceID))
	return hostURL, nil
}

// Stop stops and removes a workspace container.
func (p *Provisioner) Stop(ctx context.Context, workspaceID string) error {
	name := ContainerName(workspaceID)
	timeout := 10

	if err := p.cli.ContainerStop(ctx, name, container.StopOptions{Timeout: &timeout}); err != nil {
		log.Printf("Provisioner: stop warning for %s: %v", name, err)
	}

	if err := p.cli.ContainerRemove(ctx, name, container.RemoveOptions{Force: true}); err != nil {
		return fmt.Errorf("failed to remove container %s: %w", name, err)
	}

	log.Printf("Provisioner: stopped and removed container %s", name)
	return nil
}

// IsRunning checks if a workspace container is currently running.
func (p *Provisioner) IsRunning(ctx context.Context, workspaceID string) (bool, error) {
	name := ContainerName(workspaceID)
	info, err := p.cli.ContainerInspect(ctx, name)
	if err != nil {
		return false, nil // Container doesn't exist
	}
	return info.State.Running, nil
}

// DockerClient returns the underlying Docker client for sharing with other handlers.
func (p *Provisioner) DockerClient() *client.Client {
	return p.cli
}

// Close cleans up the Docker client.
func (p *Provisioner) Close() error {
	return p.cli.Close()
}
