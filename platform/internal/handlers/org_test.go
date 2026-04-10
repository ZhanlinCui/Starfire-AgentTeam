package handlers

import (
	"strings"
	"testing"

	"gopkg.in/yaml.v3"
)

func TestOrgDefaults_InitialPrompt_YAMLParsing(t *testing.T) {
	raw := `
runtime: claude-code
tier: 2
initial_prompt: |
  Clone the repo and read CLAUDE.md.
  Report ready status.
`
	var defaults OrgDefaults
	if err := yaml.Unmarshal([]byte(raw), &defaults); err != nil {
		t.Fatalf("failed to parse YAML: %v", err)
	}
	if defaults.Runtime != "claude-code" {
		t.Errorf("expected runtime 'claude-code', got %q", defaults.Runtime)
	}
	if !strings.Contains(defaults.InitialPrompt, "Clone the repo") {
		t.Errorf("expected InitialPrompt to contain 'Clone the repo', got %q", defaults.InitialPrompt)
	}
	if !strings.Contains(defaults.InitialPrompt, "Report ready") {
		t.Errorf("expected InitialPrompt to contain 'Report ready', got %q", defaults.InitialPrompt)
	}
}

func TestOrgWorkspace_InitialPrompt_Override(t *testing.T) {
	raw := `
name: Frontend Engineer
role: Next.js canvas
initial_prompt: Custom FE prompt
`
	var ws OrgWorkspace
	if err := yaml.Unmarshal([]byte(raw), &ws); err != nil {
		t.Fatalf("failed to parse YAML: %v", err)
	}
	if ws.InitialPrompt != "Custom FE prompt" {
		t.Errorf("expected 'Custom FE prompt', got %q", ws.InitialPrompt)
	}
}

func TestInitialPrompt_ConfigYAML_Injection(t *testing.T) {
	// Simulate what createWorkspaceTree does: append initial_prompt to config.yaml
	configYAML := "name: Test\nruntime: claude-code\n"
	initialPrompt := "Clone the repo.\nRead CLAUDE.md.\nReport ready."

	trimmed := strings.TrimSpace(initialPrompt)
	lines := strings.Split(trimmed, "\n")
	for i, line := range lines {
		lines[i] = strings.TrimRight(line, " \t")
	}
	indented := strings.Join(lines, "\n  ")
	result := configYAML + "initial_prompt: |\n  " + indented + "\n"

	// Parse result as YAML to verify it's valid
	var parsed map[string]interface{}
	if err := yaml.Unmarshal([]byte(result), &parsed); err != nil {
		t.Fatalf("generated YAML is invalid: %v\n---\n%s", err, result)
	}

	prompt, ok := parsed["initial_prompt"].(string)
	if !ok {
		t.Fatalf("initial_prompt not found or not a string in parsed YAML")
	}
	if !strings.Contains(prompt, "Clone the repo") {
		t.Errorf("expected prompt to contain 'Clone the repo', got %q", prompt)
	}
	if !strings.Contains(prompt, "Read CLAUDE.md") {
		t.Errorf("expected prompt to contain 'Read CLAUDE.md', got %q", prompt)
	}
}

func TestInitialPrompt_ConfigYAML_Empty(t *testing.T) {
	// When initial_prompt is empty, nothing should be appended
	configYAML := "name: Test\nruntime: langgraph\n"
	initialPrompt := ""

	result := configYAML
	if initialPrompt != "" {
		// This block shouldn't execute
		result += "initial_prompt: |\n  " + initialPrompt + "\n"
	}

	var parsed map[string]interface{}
	if err := yaml.Unmarshal([]byte(result), &parsed); err != nil {
		t.Fatalf("generated YAML is invalid: %v", err)
	}
	if _, exists := parsed["initial_prompt"]; exists {
		t.Error("initial_prompt should not exist in config when empty")
	}
}

func TestInitialPrompt_SpecialChars(t *testing.T) {
	// Ensure YAML-special characters in prompt don't break parsing
	initialPrompt := `Run: git clone https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git
Check "config.yaml" for settings
Use key: value pairs`

	configYAML := "name: Test\n"
	trimmed := strings.TrimSpace(initialPrompt)
	lines := strings.Split(trimmed, "\n")
	for i, line := range lines {
		lines[i] = strings.TrimRight(line, " \t")
	}
	indented := strings.Join(lines, "\n  ")
	result := configYAML + "initial_prompt: |\n  " + indented + "\n"

	var parsed map[string]interface{}
	if err := yaml.Unmarshal([]byte(result), &parsed); err != nil {
		t.Fatalf("generated YAML with special chars is invalid: %v\n---\n%s", err, result)
	}

	prompt := parsed["initial_prompt"].(string)
	if !strings.Contains(prompt, "${GITHUB_TOKEN}") {
		t.Error("expected prompt to preserve ${GITHUB_TOKEN}")
	}
	if !strings.Contains(prompt, `"config.yaml"`) {
		t.Error("expected prompt to preserve quoted strings")
	}
}
