#!/usr/bin/env bash
# setup-org.sh — Creates the default Agent Molecule org hierarchy.
# Requires: platform running at localhost:8080, .auth-token in claude-code-default/
#
# Usage:
#   bash setup-org.sh          # Create org from scratch
#
# The platform must be started with WORKSPACE_DIR set so agents can access the repo:
#   WORKSPACE_DIR=/path/to/Starfire-AgentTeam /tmp/platform-server

set -euo pipefail
BASE="http://localhost:8080"
WAIT_SECS=5

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[setup]${NC} $1" >&2; }
warn() { echo -e "${YELLOW}[warn]${NC} $1" >&2; }
err()  { echo -e "${RED}[error]${NC} $1" >&2; }

if ! curl -sf "$BASE/health" > /dev/null 2>&1; then
  err "Platform not running at $BASE — start it first"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOKEN_FILE="$SCRIPT_DIR/workspace-configs-templates/claude-code-default/.auth-token"
if [ ! -f "$TOKEN_FILE" ] || [ ! -s "$TOKEN_FILE" ]; then
  warn "No .auth-token found — extracting from macOS keychain..."
  TOKEN_JSON=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null || true)
  if [ -n "$TOKEN_JSON" ]; then
    echo "$TOKEN_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('claudeAiOauth',{}).get('accessToken',''))" > "$TOKEN_FILE"
    log "OAuth token saved"
  else
    err "No OAuth token found. Write your token to: $TOKEN_FILE"
    exit 1
  fi
fi

# Copy auth token to all org templates (containers mount these directly)
for dir in "$SCRIPT_DIR"/workspace-configs-templates/org-*/; do
  cp "$TOKEN_FILE" "$dir/.auth-token" 2>/dev/null
done
log "Auth token distributed to all org templates"

# Helper: create workspace and return ID
create_ws() {
  local name="$1" role="$2" template="$3" parent_id="${4:-}" x="${5:-0}" y="${6:-0}"

  local json="{\"name\":\"$name\",\"role\":\"$role\",\"template\":\"$template\",\"runtime\":\"claude-code\",\"tier\":2,\"canvas\":{\"x\":$x,\"y\":$y}"
  if [ -n "$parent_id" ]; then
    json="$json,\"parent_id\":\"$parent_id\""
  fi
  json="$json}"

  local resp id
  resp=$(curl -sf -X POST "$BASE/workspaces" -H "Content-Type: application/json" -d "$json" 2>/dev/null)
  id=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
  if [ -z "$id" ]; then
    err "Failed to create $name: $resp"
    return 1
  fi
  log "Created $name ($id)"
  echo "$id"
}

log "=== Agent Molecule Org Setup ==="
log ""

# Root: PM
log "Creating PM (root)..."
PM_ID=$(create_ws "PM" "Project Manager — coordinates Marketing, Research, Dev" "org-pm" "" 400 50)
sleep $WAIT_SECS

# Marketing Team
log ""
log "Creating Marketing team..."
MKT_ID=$(create_ws "Marketing Lead" "Marketing strategy and team coordination" "org-marketing-lead" "$PM_ID" 50 250)
sleep 1
CW_ID=$(create_ws "Content Writer" "Technical blog posts and documentation" "org-content-writer" "$MKT_ID" 0 0)
SEO_ID=$(create_ws "SEO Specialist" "Search optimization and keyword strategy" "org-seo-specialist" "$MKT_ID" 0 0)
SM_ID=$(create_ws "Social Media Manager" "Social presence and community engagement" "org-social-media" "$MKT_ID" 0 0)
sleep $WAIT_SECS

# Research Team
log ""
log "Creating Research team..."
RES_ID=$(create_ws "Research Lead" "Market analysis and technical research" "org-research-lead" "$PM_ID" 400 250)
sleep 1
MA_ID=$(create_ws "Market Analyst" "Market sizing, trends, user research" "org-market-analyst" "$RES_ID" 0 0)
TR_ID=$(create_ws "Technical Researcher" "AI frameworks and protocol evaluation" "org-tech-researcher" "$RES_ID" 0 0)
CI_ID=$(create_ws "Competitive Intelligence" "Competitor tracking and feature comparison" "org-competitive-intel" "$RES_ID" 0 0)
sleep $WAIT_SECS

# Dev Team
log ""
log "Creating Dev team..."
DEV_ID=$(create_ws "Dev Lead" "Engineering planning and team coordination" "org-dev-lead" "$PM_ID" 750 250)
sleep 1
FE_ID=$(create_ws "Frontend Engineer" "Next.js canvas, React Flow, Zustand" "org-frontend-eng" "$DEV_ID" 0 0)
BE_ID=$(create_ws "Backend Engineer" "Go platform, Postgres, Redis, A2A" "org-backend-eng" "$DEV_ID" 0 0)
DO_ID=$(create_ws "DevOps Engineer" "CI/CD, Docker, infrastructure" "org-devops-eng" "$DEV_ID" 0 0)
SA_ID=$(create_ws "Security Auditor" "Security auditing and vulnerability assessment" "org-security-audit" "$DEV_ID" 0 0)
QA_ID=$(create_ws "QA Engineer" "Testing, quality assurance, test automation" "org-qa-engineer" "$DEV_ID" 0 0)

log ""
log "=== Org Setup Complete ==="
log ""
log "Hierarchy:"
log "  PM ($PM_ID)"
log "  ├── Marketing Lead ($MKT_ID)"
log "  │   ├── Content Writer ($CW_ID)"
log "  │   ├── SEO Specialist ($SEO_ID)"
log "  │   └── Social Media Manager ($SM_ID)"
log "  ├── Research Lead ($RES_ID)"
log "  │   ├── Market Analyst ($MA_ID)"
log "  │   ├── Technical Researcher ($TR_ID)"
log "  │   └── Competitive Intelligence ($CI_ID)"
log "  └── Dev Lead ($DEV_ID)"
log "      ├── Frontend Engineer ($FE_ID)"
log "      ├── Backend Engineer ($BE_ID)"
log "      ├── DevOps Engineer ($DO_ID)"
log "      ├── Security Auditor ($SA_ID)"
log "      └── QA Engineer ($QA_ID)"
log ""
log "Total: 15 workspaces (all Claude Code runtime)"
log "Open http://localhost:3000 to see the canvas"
