// Package provisioner manages Docker container lifecycle for workspace agents.
package provisioner

import (
	"archive/tar"
	"bytes"
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/network"
	"github.com/docker/docker/api/types/volume"
	"github.com/docker/docker/client"
	"github.com/docker/go-connections/nat"
)

// RuntimeImages maps runtime names to their Docker image tags.
// Each adapter has its own pre-built image extending workspace-template:base,
// with runtime-specific deps pre-installed for fast startup.
// Build all: workspace-template/Dockerfile (base), then each adapters/*/Dockerfile.
var RuntimeImages = map[string]string{
	"langgraph":   "workspace-template:langgraph",
	"claude-code": "workspace-template:claude-code",
	"openclaw":    "workspace-template:openclaw",
	"deepagents":  "workspace-template:deepagents",
	"crewai":      "workspace-template:crewai",
	"autogen":     "workspace-template:autogen",
}

const (
	// DefaultImage is the fallback workspace Docker image (langgraph is the most common runtime).
	DefaultImage = "workspace-template:langgraph"
	// NOTE: Every runtime MUST have an entry in RuntimeImages above. If a runtime is missing,
	// it falls back to DefaultImage which may have wrong deps. Add new runtimes to both
	// RuntimeImages AND create adapters/<runtime>/Dockerfile.

	// DefaultNetwork is the Docker network workspaces join.
	DefaultNetwork = "agent-molecule-net"

	// DefaultPort is the port the A2A server listens on inside the container.
	DefaultPort = "8000"

	// ProvisionTimeout is how long to wait for first heartbeat before marking as failed.
	ProvisionTimeout = 3 * time.Minute
)

// WorkspaceConfig holds the parameters needed to provision a workspace container.
type WorkspaceConfig struct {
	WorkspaceID        string
	TemplatePath       string            // Host path to template dir to copy from (e.g. claude-code-default/)
	ConfigFiles        map[string][]byte // Generated config files to write into /configs volume
	PluginsPath        string            // Host path to plugins directory (mounted at /plugins)
	WorkspacePath      string            // Host path to bind-mount as /workspace (if empty, uses Docker named volume)
	Tier               int
	Runtime            string            // "langgraph" (default) or "claude-code", "codex", "ollama", "custom"
	EnvVars            map[string]string // Additional env vars (API keys, etc.)
	PlatformURL        string
	AwarenessURL       string
	AwarenessNamespace string
}

// ConfigVolumeName returns the Docker named volume for a workspace's configs.
func ConfigVolumeName(workspaceID string) string {
	id := workspaceID
	if len(id) > 12 {
		id = id[:12]
	}
	return fmt.Sprintf("ws-%s-configs", id)
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
	configVolume := ConfigVolumeName(cfg.WorkspaceID)

	// Create named volume for configs (idempotent — no-op if already exists)
	_, err := p.cli.VolumeCreate(ctx, volume.CreateOptions{
		Name: configVolume,
	})
	if err != nil {
		return "", fmt.Errorf("failed to create config volume %s: %w", configVolume, err)
	}
	log.Printf("Provisioner: config volume %s ready", configVolume)

	// Build environment variables
	env := []string{
		fmt.Sprintf("WORKSPACE_ID=%s", cfg.WorkspaceID),
		fmt.Sprintf("WORKSPACE_CONFIG_PATH=/configs"),
		fmt.Sprintf("PLATFORM_URL=%s", cfg.PlatformURL),
		fmt.Sprintf("TIER=%d", cfg.Tier),
		"PLUGINS_DIR=/plugins",
	}
	if cfg.AwarenessNamespace != "" && cfg.AwarenessURL != "" {
		env = append(env, fmt.Sprintf("AWARENESS_NAMESPACE=%s", cfg.AwarenessNamespace))
		env = append(env, fmt.Sprintf("AWARENESS_URL=%s", cfg.AwarenessURL))
	}
	for k, v := range cfg.EnvVars {
		env = append(env, fmt.Sprintf("%s=%s", k, v))
	}

	// Select image based on runtime (each adapter has its own pre-built image)
	image := DefaultImage
	if cfg.Runtime != "" {
		if img, ok := RuntimeImages[cfg.Runtime]; ok {
			image = img
		}
	}

	containerCfg := &container.Config{
		Image: image,
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

	// Mount configs as read-write named volume (agent and Files API need to write)
	// Plugins are installed per-workspace into /configs/plugins/ via the platform API.
	// No global /plugins mount — each workspace owns its plugin set.
	configMount := fmt.Sprintf("%s:/configs", configVolume)
	binds := []string{
		configMount,
		workspaceMount,
	}

	hostCfg := &container.HostConfig{
		Binds:         binds,
		RestartPolicy: container.RestartPolicy{Name: "unless-stopped"},
		PortBindings: nat.PortMap{
			nat.Port(DefaultPort + "/tcp"): []nat.PortBinding{
				{HostIP: "127.0.0.1", HostPort: ""}, // Ephemeral host port
			},
		},
	}

	// Apply tier-based container configuration
	ApplyTierConfig(hostCfg, cfg, configMount, name)

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

	// Copy template files into /configs if TemplatePath is set
	if cfg.TemplatePath != "" {
		if err := p.CopyTemplateToContainer(ctx, resp.ID, cfg.TemplatePath); err != nil {
			log.Printf("Provisioner: warning — failed to copy template to container %s: %v", name, err)
		}
	}

	// Write generated config files into /configs if ConfigFiles is set
	if len(cfg.ConfigFiles) > 0 {
		if err := p.WriteFilesToContainer(ctx, resp.ID, cfg.ConfigFiles); err != nil {
			log.Printf("Provisioner: warning — failed to write config files to container %s: %v", name, err)
		}
	}

	// Resolve the host-mapped port. Retry inspect up to 3 times if Docker hasn't
	// bound the ephemeral port yet (rare race under heavy load).
	hostURL := InternalURL(cfg.WorkspaceID) // fallback to Docker-internal
	for attempt := 0; attempt < 3; attempt++ {
		info, inspectErr := p.cli.ContainerInspect(ctx, resp.ID)
		if inspectErr != nil {
			break
		}
		portBindings := info.NetworkSettings.Ports[nat.Port(DefaultPort+"/tcp")]
		if len(portBindings) > 0 {
			hostPort := portBindings[0].HostPort
			hostIP := portBindings[0].HostIP
			if hostIP == "" {
				hostIP = "127.0.0.1"
			}
			hostURL = fmt.Sprintf("http://%s:%s", hostIP, hostPort)
			break
		}
		if attempt < 2 {
			time.Sleep(500 * time.Millisecond) // wait for Docker to bind the port
		}
	}

	log.Printf("Provisioner: started container %s for workspace %s at %s (internal: %s)", name, cfg.WorkspaceID, hostURL, InternalURL(cfg.WorkspaceID))
	return hostURL, nil
}

// ApplyTierConfig configures a HostConfig based on the workspace tier.
// Extracted from Start() so it can be tested independently.
//
//   - Tier 1 (Sandboxed):  readonly rootfs, tmpfs /tmp, strip /workspace mount
//   - Tier 2 (Standard):   resource limits (512 MiB memory, 1 CPU), no special flags (default)
//   - Tier 3 (Privileged):  privileged mode, host PID, Docker network (not host)
//   - Tier 4 (Full access): privileged, host PID, host network, Docker socket mount, all capabilities
//
// Unknown/zero tiers default to Tier 2 behavior (safe resource-limited container).
func ApplyTierConfig(hostCfg *container.HostConfig, cfg WorkspaceConfig, configMount, name string) {
	switch cfg.Tier {
	case 1:
		// Sandboxed: strip /workspace mount, keep only config (plugins are in /configs/plugins/)
		tier1Binds := []string{configMount}
		hostCfg.Binds = tier1Binds
		// Readonly root filesystem with tmpfs for /tmp (agent needs scratch space)
		hostCfg.ReadonlyRootfs = true
		hostCfg.Tmpfs = map[string]string{
			"/tmp": "rw,noexec,nosuid,size=64m",
		}
		log.Printf("Provisioner: T1 sandboxed mode for %s (readonly, no /workspace)", name)

	case 3:
		// Privileged access: privileged mode + host PID.
		// Keep the Docker network (not host network) so containers can still reach
		// each other by name. Host networking conflicts with Docker networks and
		// causes port collisions when multiple T3 containers run simultaneously.
		hostCfg.Privileged = true
		hostCfg.PidMode = "host"
		log.Printf("Provisioner: T3 privileged mode for %s (privileged, host PID)", name)

	case 4:
		// Full host access: everything from T3 + host network + Docker socket + all capabilities.
		// Use for workspaces that need to manage other containers or access host services directly.
		hostCfg.Privileged = true
		hostCfg.PidMode = "host"
		hostCfg.NetworkMode = "host"
		// Mount Docker socket so workspace can manage containers
		hostCfg.Binds = append(hostCfg.Binds, "/var/run/docker.sock:/var/run/docker.sock")
		log.Printf("Provisioner: T4 full-host mode for %s (privileged, host PID, host network, docker socket)", name)

	default:
		// Tier 2 (Standard) and unknown tiers: normal container with resource limits.
		// This is the safe default — no privileged access, reasonable resource caps.
		hostCfg.Resources.Memory = 512 * 1024 * 1024    // 512 MiB
		hostCfg.Resources.NanoCPUs = 1_000_000_000       // 1.0 CPU
		log.Printf("Provisioner: T2 standard mode for %s (512m memory, 1 CPU)", name)
	}
}

// CopyTemplateToContainer copies files from a host directory into /configs in the container.
func (p *Provisioner) CopyTemplateToContainer(ctx context.Context, containerID, templatePath string) error {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)

	err := filepath.Walk(templatePath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(templatePath, path)
		if err != nil {
			return err
		}
		if rel == "." {
			return nil
		}

		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		header.Name = rel

		if err := tw.WriteHeader(header); err != nil {
			return err
		}

		if !info.IsDir() {
			data, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			if _, err := tw.Write(data); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return fmt.Errorf("failed to create tar from %s: %w", templatePath, err)
	}
	if err := tw.Close(); err != nil {
		return fmt.Errorf("failed to close tar writer: %w", err)
	}

	return p.cli.CopyToContainer(ctx, containerID, "/configs", &buf, container.CopyToContainerOptions{})
}

// WriteFilesToContainer writes in-memory files into /configs in the container.
func (p *Provisioner) WriteFilesToContainer(ctx context.Context, containerID string, files map[string][]byte) error {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)

	createdDirs := map[string]bool{}
	for name, data := range files {
		// Create parent directories in tar (deduplicated)
		dir := filepath.Dir(name)
		if dir != "." && !createdDirs[dir] {
			if err := tw.WriteHeader(&tar.Header{
				Typeflag: tar.TypeDir,
				Name:     dir + "/",
				Mode:     0755,
			}); err != nil {
				return fmt.Errorf("failed to write tar dir header for %s: %w", dir, err)
			}
			createdDirs[dir] = true
		}

		header := &tar.Header{
			Name: name,
			Mode: 0644,
			Size: int64(len(data)),
		}
		if err := tw.WriteHeader(header); err != nil {
			return fmt.Errorf("failed to write tar header for %s: %w", name, err)
		}
		if _, err := tw.Write(data); err != nil {
			return fmt.Errorf("failed to write tar data for %s: %w", name, err)
		}
	}
	if err := tw.Close(); err != nil {
		return fmt.Errorf("failed to close tar writer: %w", err)
	}

	return p.cli.CopyToContainer(ctx, containerID, "/configs", &buf, container.CopyToContainerOptions{})
}

// CopyToContainer exposes CopyToContainer from the Docker client for use by other packages.
func (p *Provisioner) CopyToContainer(ctx context.Context, containerID, dstPath string, content io.Reader) error {
	return p.cli.CopyToContainer(ctx, containerID, dstPath, content, container.CopyToContainerOptions{})
}

// ExecRead runs "cat <filePath>" in an existing container and returns the output.
// Used to read config files from a running container before stopping it.
func (p *Provisioner) ExecRead(ctx context.Context, containerName, filePath string) ([]byte, error) {
	exec, err := p.cli.ContainerExecCreate(ctx, containerName, container.ExecOptions{
		Cmd:          []string{"cat", filePath},
		AttachStdout: true,
	})
	if err != nil {
		return nil, err
	}
	attach, err := p.cli.ContainerExecAttach(ctx, exec.ID, container.ExecAttachOptions{})
	if err != nil {
		return nil, err
	}
	defer attach.Close()
	data, err := io.ReadAll(attach.Reader)
	if err != nil {
		return nil, err
	}
	// Docker multiplexed stream: strip 8-byte headers
	var clean []byte
	for len(data) >= 8 {
		size := int(data[4])<<24 | int(data[5])<<16 | int(data[6])<<8 | int(data[7])
		if 8+size > len(data) {
			break
		}
		clean = append(clean, data[8:8+size]...)
		data = data[8+size:]
	}
	return clean, nil
}

// ReadFromVolume reads a file from a Docker named volume using a throwaway container.
// Used as a fallback when ExecRead fails (container already stopped).
func (p *Provisioner) ReadFromVolume(ctx context.Context, volumeName, filePath string) ([]byte, error) {
	resp, err := p.cli.ContainerCreate(ctx, &container.Config{
		Image: "alpine",
		Cmd:   []string{"cat", "/vol/" + filePath},
	}, &container.HostConfig{
		Binds: []string{volumeName + ":/vol:ro"},
	}, nil, nil, "")
	if err != nil {
		return nil, err
	}
	defer p.cli.ContainerRemove(ctx, resp.ID, container.RemoveOptions{Force: true})

	if err := p.cli.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
		return nil, err
	}
	waitCh, errCh := p.cli.ContainerWait(ctx, resp.ID, container.WaitConditionNotRunning)
	select {
	case <-waitCh:
	case err := <-errCh:
		if err != nil {
			return nil, err
		}
	}
	reader, err := p.cli.ContainerLogs(ctx, resp.ID, container.LogsOptions{ShowStdout: true})
	if err != nil {
		return nil, err
	}
	defer reader.Close()
	data, err := io.ReadAll(reader)
	if err != nil {
		return nil, err
	}
	// Strip Docker multiplexed stream headers
	var clean []byte
	for len(data) >= 8 {
		size := int(data[4])<<24 | int(data[5])<<16 | int(data[6])<<8 | int(data[7])
		if 8+size > len(data) {
			break
		}
		clean = append(clean, data[8:8+size]...)
		data = data[8+size:]
	}
	return clean, nil
}

// RemoveVolume removes the config volume for a workspace.
func (p *Provisioner) RemoveVolume(ctx context.Context, workspaceID string) error {
	volName := ConfigVolumeName(workspaceID)
	if err := p.cli.VolumeRemove(ctx, volName, true); err != nil {
		return fmt.Errorf("failed to remove volume %s: %w", volName, err)
	}
	log.Printf("Provisioner: removed config volume %s", volName)
	return nil
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
