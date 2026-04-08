package main

import (
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
