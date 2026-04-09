package provisioner

import (
	"testing"

	"github.com/docker/docker/api/types/container"
)

// baseHostConfig returns a fresh HostConfig with typical pre-tier binds,
// mimicking what Start() builds before calling ApplyTierConfig.
func baseHostConfig(pluginsPath string) *container.HostConfig {
	binds := []string{
		"ws-abc123-configs:/configs",
		"ws-abc123-workspace:/workspace",
	}
	if pluginsPath != "" {
		binds = append(binds, pluginsPath+":/plugins:ro")
	}
	return &container.HostConfig{
		Binds: binds,
	}
}

func TestApplyTierConfig_Tier1_Sandboxed(t *testing.T) {
	configMount := "ws-abc123-configs:/configs"
	hc := baseHostConfig("")
	cfg := WorkspaceConfig{
		WorkspaceID: "abc123",
		Tier:        1,
	}

	ApplyTierConfig(hc, cfg, configMount, "ws-abc123")

	// T1 should strip /workspace mount — only config bind remains
	if len(hc.Binds) != 1 {
		t.Fatalf("T1: expected 1 bind (config only), got %d: %v", len(hc.Binds), hc.Binds)
	}
	if hc.Binds[0] != configMount {
		t.Errorf("T1: expected bind %q, got %q", configMount, hc.Binds[0])
	}

	// ReadonlyRootfs must be set
	if !hc.ReadonlyRootfs {
		t.Error("T1: expected ReadonlyRootfs=true")
	}

	// Tmpfs at /tmp must be set
	if _, ok := hc.Tmpfs["/tmp"]; !ok {
		t.Error("T1: expected tmpfs mount at /tmp")
	}

	// Must NOT be privileged
	if hc.Privileged {
		t.Error("T1: must not be privileged")
	}

	// Must NOT have host network
	if hc.NetworkMode == "host" {
		t.Error("T1: must not have host network")
	}
}

func TestApplyTierConfig_Tier1_NoGlobalPlugins(t *testing.T) {
	configMount := "ws-abc123-configs:/configs"
	hc := baseHostConfig("")
	cfg := WorkspaceConfig{
		WorkspaceID: "abc123",
		Tier:        1,
	}

	ApplyTierConfig(hc, cfg, configMount, "ws-abc123")

	// T1 should have only 1 bind: config (plugins are per-workspace in /configs/plugins/)
	if len(hc.Binds) != 1 {
		t.Fatalf("T1: expected 1 bind, got %d: %v", len(hc.Binds), hc.Binds)
	}
	if hc.Binds[0] != configMount {
		t.Errorf("T1: expected bind %q, got %q", configMount, hc.Binds[0])
	}
}

func TestApplyTierConfig_Tier2_Standard(t *testing.T) {
	configMount := "ws-abc123-configs:/configs"
	hc := baseHostConfig("")
	originalBinds := make([]string, len(hc.Binds))
	copy(originalBinds, hc.Binds)

	cfg := WorkspaceConfig{
		WorkspaceID: "abc123",
		Tier:        2,
	}

	ApplyTierConfig(hc, cfg, configMount, "ws-abc123")

	// T2 should NOT modify binds — /workspace mount stays
	if len(hc.Binds) != len(originalBinds) {
		t.Fatalf("T2: binds should be unchanged, got %v", hc.Binds)
	}

	// Memory limit: 512 MiB
	expectedMemory := int64(512 * 1024 * 1024)
	if hc.Resources.Memory != expectedMemory {
		t.Errorf("T2: expected Memory=%d (512m), got %d", expectedMemory, hc.Resources.Memory)
	}

	// CPU limit: 1.0 CPU (1e9 NanoCPUs)
	expectedCPU := int64(1_000_000_000)
	if hc.Resources.NanoCPUs != expectedCPU {
		t.Errorf("T2: expected NanoCPUs=%d (1.0 CPU), got %d", expectedCPU, hc.Resources.NanoCPUs)
	}

	// Must NOT be privileged
	if hc.Privileged {
		t.Error("T2: must not be privileged")
	}

	// Must NOT have host network
	if hc.NetworkMode == "host" {
		t.Error("T2: must not have host network")
	}

	// Must NOT have readonly rootfs
	if hc.ReadonlyRootfs {
		t.Error("T2: must not have ReadonlyRootfs")
	}
}

func TestApplyTierConfig_Tier3_Privileged(t *testing.T) {
	configMount := "ws-abc123-configs:/configs"
	hc := baseHostConfig("")
	originalBinds := make([]string, len(hc.Binds))
	copy(originalBinds, hc.Binds)

	cfg := WorkspaceConfig{
		WorkspaceID: "abc123",
		Tier:        3,
	}

	ApplyTierConfig(hc, cfg, configMount, "ws-abc123")

	// T3 must be privileged
	if !hc.Privileged {
		t.Error("T3: expected Privileged=true")
	}

	// T3 must have host PID
	if hc.PidMode != "host" {
		t.Errorf("T3: expected PidMode=host, got %q", hc.PidMode)
	}

	// T3 must NOT have host network (to avoid port collisions)
	if hc.NetworkMode == "host" {
		t.Error("T3: must not have host network (use Docker network for inter-container discovery)")
	}

	// Binds should be unchanged (keeps /workspace)
	if len(hc.Binds) != len(originalBinds) {
		t.Fatalf("T3: binds should be unchanged, got %v", hc.Binds)
	}
}

func TestApplyTierConfig_Tier4_FullHost(t *testing.T) {
	configMount := "ws-abc123-configs:/configs"
	hc := baseHostConfig("")
	originalBindCount := len(hc.Binds)

	cfg := WorkspaceConfig{
		WorkspaceID: "abc123",
		Tier:        4,
	}

	ApplyTierConfig(hc, cfg, configMount, "ws-abc123")

	// T4 must be privileged (inherits from T3)
	if !hc.Privileged {
		t.Error("T4: expected Privileged=true")
	}

	// T4 must have host PID (inherits from T3)
	if hc.PidMode != "host" {
		t.Errorf("T4: expected PidMode=host, got %q", hc.PidMode)
	}

	// T4 must have host network
	if hc.NetworkMode != "host" {
		t.Errorf("T4: expected NetworkMode=host, got %q", hc.NetworkMode)
	}

	// T4 should add Docker socket mount to existing binds
	expectedBindCount := originalBindCount + 1
	if len(hc.Binds) != expectedBindCount {
		t.Fatalf("T4: expected %d binds (original + docker socket), got %d: %v",
			expectedBindCount, len(hc.Binds), hc.Binds)
	}

	// Last bind should be the Docker socket
	dockerSocket := "/var/run/docker.sock:/var/run/docker.sock"
	lastBind := hc.Binds[len(hc.Binds)-1]
	if lastBind != dockerSocket {
		t.Errorf("T4: expected docker socket bind %q, got %q", dockerSocket, lastBind)
	}
}

func TestApplyTierConfig_UnknownTier_DefaultsToT2(t *testing.T) {
	configMount := "ws-abc123-configs:/configs"
	hc := baseHostConfig("")

	cfg := WorkspaceConfig{
		WorkspaceID: "abc123",
		Tier:        99, // Unknown tier
	}

	ApplyTierConfig(hc, cfg, configMount, "ws-abc123")

	// Unknown tiers should get T2 resource limits as a safe default
	expectedMemory := int64(512 * 1024 * 1024)
	if hc.Resources.Memory != expectedMemory {
		t.Errorf("Unknown tier: expected Memory=%d (512m), got %d", expectedMemory, hc.Resources.Memory)
	}

	expectedCPU := int64(1_000_000_000)
	if hc.Resources.NanoCPUs != expectedCPU {
		t.Errorf("Unknown tier: expected NanoCPUs=%d (1.0 CPU), got %d", expectedCPU, hc.Resources.NanoCPUs)
	}

	// Must NOT be privileged
	if hc.Privileged {
		t.Error("Unknown tier: must not be privileged")
	}
}

func TestApplyTierConfig_ZeroTier_DefaultsToT2(t *testing.T) {
	configMount := "ws-abc123-configs:/configs"
	hc := baseHostConfig("")

	cfg := WorkspaceConfig{
		WorkspaceID: "abc123",
		Tier:        0, // Unset / zero-value
	}

	ApplyTierConfig(hc, cfg, configMount, "ws-abc123")

	// Zero tier (default int value) should also get T2 resource limits
	expectedMemory := int64(512 * 1024 * 1024)
	if hc.Resources.Memory != expectedMemory {
		t.Errorf("Tier 0: expected Memory=%d, got %d", expectedMemory, hc.Resources.Memory)
	}
	if hc.Privileged {
		t.Error("Tier 0: must not be privileged")
	}
}

// TestTierEscalation verifies that lower tiers don't accidentally
// get higher-tier privileges.
func TestTierEscalation(t *testing.T) {
	tests := []struct {
		tier              int
		expectPrivileged  bool
		expectHostNetwork bool
		expectHostPID     bool
		expectReadonly    bool
	}{
		{1, false, false, false, true},
		{2, false, false, false, false},
		{3, true, false, true, false},
		{4, true, true, true, false},
	}

	for _, tt := range tests {
		t.Run("tier_"+string(rune('0'+tt.tier)), func(t *testing.T) {
			configMount := "ws-test-configs:/configs"
			hc := baseHostConfig("")
			cfg := WorkspaceConfig{
				WorkspaceID: "test",
				Tier:        tt.tier,
			}

			ApplyTierConfig(hc, cfg, configMount, "ws-test")

			if hc.Privileged != tt.expectPrivileged {
				t.Errorf("Tier %d: Privileged=%v, want %v", tt.tier, hc.Privileged, tt.expectPrivileged)
			}
			if (hc.NetworkMode == "host") != tt.expectHostNetwork {
				t.Errorf("Tier %d: NetworkMode=%q, wantHost=%v", tt.tier, hc.NetworkMode, tt.expectHostNetwork)
			}
			if (hc.PidMode == "host") != tt.expectHostPID {
				t.Errorf("Tier %d: PidMode=%q, wantHost=%v", tt.tier, hc.PidMode, tt.expectHostPID)
			}
			if hc.ReadonlyRootfs != tt.expectReadonly {
				t.Errorf("Tier %d: ReadonlyRootfs=%v, want %v", tt.tier, hc.ReadonlyRootfs, tt.expectReadonly)
			}
		})
	}
}

// TestContainerName verifies the naming convention.
func TestContainerName(t *testing.T) {
	tests := []struct {
		id   string
		want string
	}{
		{"short", "ws-short"},
		{"exactly12ch", "ws-exactly12ch"},
		{"longer-than-twelve-characters", "ws-longer-than-"},
		{"abc", "ws-abc"},
	}

	for _, tt := range tests {
		got := ContainerName(tt.id)
		if got != tt.want {
			t.Errorf("ContainerName(%q) = %q, want %q", tt.id, got, tt.want)
		}
	}
}

// TestConfigVolumeName verifies config volume naming.
func TestConfigVolumeName(t *testing.T) {
	tests := []struct {
		id   string
		want string
	}{
		{"short", "ws-short-configs"},
		{"exactly12ch", "ws-exactly12ch-configs"},
		{"longer-than-twelve-characters", "ws-longer-than--configs"},
		{"abc", "ws-abc-configs"},
	}

	for _, tt := range tests {
		got := ConfigVolumeName(tt.id)
		if got != tt.want {
			t.Errorf("ConfigVolumeName(%q) = %q, want %q", tt.id, got, tt.want)
		}
	}
}
