package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

const skillConfigFixture = `name: Demo
description: Demo agent
version: 1.0.0
tier: 1
model: anthropic:claude-sonnet-4-6

prompt_files:
  - system-prompt.md

skills:
  - brainstorming
  - memory-curation

tools: []
`

func TestParseSkillsFromConfig(t *testing.T) {
	skills, err := parseSkillsFromConfig(skillConfigFixture)
	if err != nil {
		t.Fatalf("parseSkillsFromConfig failed: %v", err)
	}
	want := []string{"brainstorming", "memory-curation"}
	if len(skills) != len(want) {
		t.Fatalf("expected %d skills, got %d", len(want), len(skills))
	}
	for i, s := range want {
		if skills[i] != s {
			t.Fatalf("skill %d = %q, want %q", i, skills[i], s)
		}
	}
}

func TestReplaceSkillsInConfig(t *testing.T) {
	updated, err := replaceSkillsInConfig(skillConfigFixture, []string{"brainstorming", "memory-curation", "skill-authoring"})
	if err != nil {
		t.Fatalf("replaceSkillsInConfig failed: %v", err)
	}
	if !strings.Contains(updated, "  - skill-authoring") {
		t.Fatalf("updated config missing new skill: %s", updated)
	}
}

func TestUpsertSkill(t *testing.T) {
	next, changed := upsertSkill([]string{"brainstorming"}, "skill-authoring", true)
	if !changed || len(next) != 2 {
		t.Fatalf("expected skill add to change list, got changed=%v next=%v", changed, next)
	}
	next, changed = upsertSkill(next, "brainstorming", true)
	if changed {
		t.Fatalf("expected duplicate add to be ignored, got next=%v", next)
	}
	next, changed = upsertSkill(next, "brainstorming", false)
	if !changed || len(next) != 1 || next[0] != "skill-authoring" {
		t.Fatalf("expected removal to leave one skill, got changed=%v next=%v", changed, next)
	}
}

func TestBuildAgentSkillCmdIncludesAudit(t *testing.T) {
	cmd := buildAgentSkillCmd()
	found := false
	for _, child := range cmd.Commands() {
		if child.Name() == "audit" {
			found = true
			break
		}
	}
	if !found {
		t.Fatal("expected skill command to include audit subcommand")
	}
}

func TestAuditWorkspaceSkills(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/workspaces/ws-1/files/config.yaml", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Fatalf("unexpected method: %s", r.Method)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"path":    "config.yaml",
			"content": "name: Demo\nskills:\n  - good-skill\n  - missing-skill\n",
			"size":    52,
		})
	})
	mux.HandleFunc("/workspaces/ws-1/files/skills/good-skill/SKILL.md", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"path": "skills/good-skill/SKILL.md",
			"content": "---\nname: Good Skill\ndescription: Works well\nversion: 1.0.0\n---\nUse this skill carefully.\n",
			"size": 92,
		})
	})
	mux.HandleFunc("/workspaces/ws-1/files/skills/missing-skill/SKILL.md", func(w http.ResponseWriter, r *http.Request) {
		http.NotFound(w, r)
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	client := NewPlatformClient(server.URL)
	results, err := auditWorkspaceSkills(client, "ws-1")
	if err != nil {
		t.Fatalf("auditWorkspaceSkills failed: %v", err)
	}
	if len(results) != 2 {
		t.Fatalf("expected 2 results, got %d", len(results))
	}

	if results[0].Skill != "good-skill" || results[0].Status != "PASS" {
		t.Fatalf("expected first skill to pass, got %+v", results[0])
	}
	if results[1].Skill != "missing-skill" || results[1].Status != "FAIL" {
		t.Fatalf("expected second skill to fail, got %+v", results[1])
	}
	if !strings.Contains(strings.Join(results[1].Issues, " "), "SKILL.md") {
		t.Fatalf("expected missing file issue, got %+v", results[1])
	}
}
