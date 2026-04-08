#!/usr/bin/env bash
# build-all.sh — Rebuild base + all runtime images in the correct order.
#
# Usage:
#   bash workspace-template/build-all.sh                        # Build all
#   bash workspace-template/build-all.sh claude-code langgraph  # Build specific runtimes only
#
# The base image must be built first, then each adapter extends it.
# Adapter directory names use underscores (claude_code), Docker tags use hyphens (claude-code).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[build]${NC} $1" >&2; }
err() { echo -e "${RED}[error]${NC} $1" >&2; }

# Convert between dir name (underscore) and tag name (hyphen)
dir_to_tag() { echo "${1//_/-}"; }
tag_to_dir() { echo "${1//-/_}"; }

# Step 1: Build base image (always — all runtimes depend on it)
log "Building workspace-template:base ..."
if ! docker build -t workspace-template:base -f Dockerfile . ; then
  err "Base image build failed"
  exit 1
fi
log "Base image built"

# Step 2: Determine which runtimes to build
RUNTIMES=()
if [ $# -gt 0 ]; then
  for arg in "$@"; do
    dir="$(tag_to_dir "$arg")"
    if [ -f "adapters/$dir/Dockerfile" ]; then
      RUNTIMES+=("$dir")
    else
      err "No Dockerfile for runtime: $arg (looked in adapters/$dir/)"
      exit 1
    fi
  done
else
  for df in adapters/*/Dockerfile; do
    RUNTIMES+=("$(basename "$(dirname "$df")")")
  done
fi

# Step 3: Build each runtime image
FAILED=()
for dir_name in "${RUNTIMES[@]}"; do
  tag="$(dir_to_tag "$dir_name")"
  log "Building workspace-template:$tag ..."
  if docker build -t "workspace-template:$tag" -f "adapters/$dir_name/Dockerfile" . ; then
    log "workspace-template:$tag built"
  else
    err "workspace-template:$tag FAILED"
    FAILED+=("$tag")
  fi
done

echo ""
if [ ${#FAILED[@]} -eq 0 ]; then
  log "All ${#RUNTIMES[@]} runtime images built successfully"
else
  err "${#FAILED[@]} failed: ${FAILED[*]}"
  exit 1
fi
