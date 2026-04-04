#!/usr/bin/env bash
# import-ecc.sh — Import Everything Claude Code into Starfire as workspace templates.
#
# Usage:
#   ./import-ecc.sh                    # Import curated skills (10 most useful)
#   ./import-ecc.sh --all              # Import ALL 156 skills as separate templates
#   ./import-ecc.sh --skill tdd-workflow  # Import a specific skill
#
# Requires: git, internet access (clones from GitHub if not cached)

set -euo pipefail

ECC_REPO="https://github.com/affaan-m/everything-claude-code.git"
ECC_DIR="/tmp/everything-claude-code"
TEMPLATES_DIR="workspace-configs-templates"
MODE="${1:-curated}"

# Clone or update ECC
if [[ -d "$ECC_DIR/.git" ]]; then
  echo "Using cached ECC repo at $ECC_DIR"
  cd "$ECC_DIR" && git pull --quiet 2>/dev/null || true
  cd - >/dev/null
else
  echo "Cloning ECC repo..."
  git clone --depth 1 "$ECC_REPO" "$ECC_DIR" 2>&1 | tail -1
fi

SKILLS_SRC="$ECC_DIR/.agents/skills"

import_skill() {
  local skill_name="$1"
  local dest_template="$2"

  if [[ ! -d "$SKILLS_SRC/$skill_name" ]]; then
    echo "  SKIP $skill_name (not found)"
    return
  fi

  mkdir -p "$dest_template/skills"
  cp -r "$SKILLS_SRC/$skill_name" "$dest_template/skills/"
  echo "  OK $skill_name"
}

case "$MODE" in
  --all)
    echo "=== Importing ALL ECC skills as individual templates ==="
    count=0
    for skill_dir in "$SKILLS_SRC"/*/; do
      skill_name=$(basename "$skill_dir")
      dest="$TEMPLATES_DIR/ecc-$skill_name"

      if [[ -d "$dest" ]]; then
        echo "  SKIP $skill_name (already exists)"
        continue
      fi

      mkdir -p "$dest/skills"
      cp -r "$skill_dir" "$dest/skills/$skill_name"

      # Copy core ECC files
      cp "$ECC_DIR/CLAUDE.md" "$dest/" 2>/dev/null || true
      cp "$ECC_DIR/AGENTS.md" "$dest/" 2>/dev/null || true

      # Generate config
      display_name=$(echo "ECC $skill_name" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2)}1')
      cat > "$dest/config.yaml" << EOF
name: $display_name
description: ECC skill — $skill_name. From github.com/affaan-m/everything-claude-code
version: 1.9.0
tier: 1
model: anthropic:claude-sonnet-4-6
prompt_files:
  - CLAUDE.md
  - AGENTS.md
skills:
  - $skill_name
tools: []
a2a:
  port: 8000
  streaming: true
  push_notifications: true
env:
  required:
    - ANTHROPIC_API_KEY
EOF
      count=$((count + 1))
    done
    echo ""
    echo "Imported $count ECC skill templates"
    ;;

  --skill)
    skill="${2:?Usage: ./import-ecc.sh --skill <skill-name>}"
    dest="$TEMPLATES_DIR/ecc-$skill"
    echo "=== Importing single ECC skill: $skill ==="

    if [[ -d "$dest" ]]; then
      echo "Template already exists at $dest"
      exit 1
    fi

    mkdir -p "$dest/skills"
    cp -r "$SKILLS_SRC/$skill" "$dest/skills/" 2>/dev/null || { echo "Skill not found: $skill"; exit 1; }
    cp "$ECC_DIR/CLAUDE.md" "$dest/" 2>/dev/null || true
    cp "$ECC_DIR/AGENTS.md" "$dest/" 2>/dev/null || true

    display_name=$(echo "ECC $skill" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2)}1')
    cat > "$dest/config.yaml" << EOF
name: $display_name
description: ECC skill — $skill. From github.com/affaan-m/everything-claude-code
version: 1.9.0
tier: 1
model: anthropic:claude-sonnet-4-6
prompt_files:
  - CLAUDE.md
  - AGENTS.md
skills:
  - $skill
tools: []
a2a:
  port: 8000
  streaming: true
  push_notifications: true
env:
  required:
    - ANTHROPIC_API_KEY
EOF
    echo "Imported as $dest"
    ;;

  *)
    # Curated — the main ecc-coding-agent template already exists
    echo "=== ECC Curated Template ==="
    echo ""
    echo "The curated ECC Coding Agent template is already at:"
    echo "  workspace-configs-templates/ecc-coding-agent/"
    echo ""
    echo "It includes the 10 most useful skills:"
    echo "  coding-standards, tdd-workflow, e2e-testing, security-review,"
    echo "  api-design, backend-patterns, frontend-patterns, deep-research,"
    echo "  shell-exec"
    echo ""
    echo "To import more:"
    echo "  ./import-ecc.sh --skill <name>     # Import one skill"
    echo "  ./import-ecc.sh --all              # Import all 156 skills"
    echo ""
    echo "Available skills:"
    ls "$SKILLS_SRC" 2>/dev/null | tr '\n' ', ' | sed 's/,$/\n/'
    ;;
esac
