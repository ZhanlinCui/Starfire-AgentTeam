#!/usr/bin/env bash
# Setup the default org: PM + 3 team leads + 11 sub-agents
# All use claude-code runtime with shared OAuth token.
#
# Usage:
#   bash scripts/setup-default-org.sh [PLATFORM_URL]
#
# Requires: curl, jq, platform running with claude-code-default template

set -euo pipefail

PLATFORM="${1:-http://localhost:8080}"

echo "Creating default org via $PLATFORM ..."

# --- Helper ---
create_workspace() {
  local name="$1" role="$2" tier="${3:-2}" parent="${4:-}" template="${5:-claude-code-default}"
  local body="{\"name\":\"$name\",\"role\":\"$role\",\"tier\":$tier,\"template\":\"$template\""
  [ -n "$parent" ] && body="$body,\"parent_id\":\"$parent\""
  body="$body}"
  local id
  id=$(curl -s -X POST "$PLATFORM/workspaces" -H 'Content-Type: application/json' -d "$body" | jq -r '.id')
  echo "$id"
}

set_prompt() {
  local id="$1" prompt="$2"
  curl -s -X PUT "$PLATFORM/workspaces/$id/files/system-prompt.md" \
    -H 'Content-Type: application/json' \
    -d "{\"content\":$(echo "$prompt" | jq -Rs .)}" > /dev/null
}

wait_online() {
  local id="$1" name="$2"
  for i in $(seq 1 30); do
    local status
    status=$(curl -s "$PLATFORM/workspaces/$id" | jq -r '.status' 2>/dev/null)
    [ "$status" = "online" ] && return 0
    sleep 2
  done
  echo "  WARNING: $name ($id) did not come online within 60s"
}

# --- PM ---
echo ""
echo "=== Creating PM ==="
PM_ID=$(create_workspace "PM" "Project Manager — coordinates Marketing, Research, Dev")
echo "  PM: $PM_ID"
set_prompt "$PM_ID" 'You are the PM (Project Manager) for Agent Molecule, an AI agent orchestration platform.

You coordinate three team leads and their reports:
- Marketing Lead — oversees Content Writer, SEO Specialist, Social Media Manager
- Research Lead — oversees Market Analyst, Tech Researcher, Competitive Intelligence
- Dev Lead — oversees Frontend Engineer, Backend Engineer, DevOps Engineer, Security Auditor, QA Engineer

Your responsibilities:
- Break high-level objectives into team-level tasks
- Delegate work to the appropriate team lead via A2A messaging
- Track progress across all teams and resolve cross-team dependencies
- Escalate blockers and synthesize status reports
- Prioritize work based on impact and urgency

When delegating, specify clear deliverables and timelines. When a lead reports back, synthesize results and determine next steps.

The project repository is at /workspace. Read CLAUDE.md for architecture and current state.'

# --- Marketing Team ---
echo ""
echo "=== Creating Marketing Team ==="
MKT_ID=$(create_workspace "Marketing Lead" "Marketing strategy and team coordination" 2 "$PM_ID")
echo "  Marketing Lead: $MKT_ID"
set_prompt "$MKT_ID" 'You are the Marketing Lead for Agent Molecule, an AI agent orchestration platform.

Your team members:
- Content Writer — technical blog posts, tutorials, documentation
- SEO Specialist — keyword research, on-page optimization, search ranking strategy
- Social Media Manager — social posts, community engagement, developer relations

Your responsibilities:
- Lead marketing strategy and campaign planning
- Delegate tasks to your team via A2A messaging
- Ensure consistent brand messaging across all channels
- Coordinate content calendar and publishing schedule
- Report marketing progress to PM when asked

When assigning work, provide clear briefs with target audience, key messages, and deadlines.
The project repository is at /workspace. Read docs/ for product positioning and roadmap context.'

CW_ID=$(create_workspace "Content Writer" "Technical blog posts and documentation" 2 "$MKT_ID")
echo "  Content Writer: $CW_ID"
SEO_ID=$(create_workspace "SEO Specialist" "Search optimization and keyword strategy" 2 "$MKT_ID")
echo "  SEO Specialist: $SEO_ID"
SM_ID=$(create_workspace "Social Media Manager" "Social presence and community engagement" 2 "$MKT_ID")
echo "  Social Media Manager: $SM_ID"

# --- Research Team ---
echo ""
echo "=== Creating Research Team ==="
RES_ID=$(create_workspace "Research Lead" "Market analysis and technical research coordination" 2 "$PM_ID")
echo "  Research Lead: $RES_ID"
set_prompt "$RES_ID" 'You are the Research Lead for Agent Molecule, an AI agent orchestration platform.

Your team members:
- Market Analyst — market sizing, trends, user research
- Technical Researcher — evaluate AI frameworks, protocols, and tools
- Competitive Intelligence Analyst — track competitors, feature comparison matrices

Your responsibilities:
- Direct research priorities aligned with product strategy
- Delegate research tasks to your team via A2A messaging
- Synthesize findings into actionable recommendations
- Identify opportunities and threats in the AI agent space
- Report key insights to PM when asked

Ensure research is thorough, evidence-based, and tied to strategic decisions.
The project repository is at /workspace. Read docs/ for product roadmap context.'

MA_ID=$(create_workspace "Market Analyst" "Market sizing, trends, user research" 2 "$RES_ID")
echo "  Market Analyst: $MA_ID"
TR_ID=$(create_workspace "Technical Researcher" "AI frameworks and protocol evaluation" 2 "$RES_ID")
echo "  Technical Researcher: $TR_ID"
CI_ID=$(create_workspace "Competitive Intelligence" "Competitor tracking and feature comparison" 2 "$RES_ID")
echo "  Competitive Intelligence: $CI_ID"

# --- Dev Team ---
echo ""
echo "=== Creating Dev Team ==="
DEV_ID=$(create_workspace "Dev Lead" "Engineering planning and team coordination" 2 "$PM_ID")
echo "  Dev Lead: $DEV_ID"
set_prompt "$DEV_ID" 'You are the Dev Lead for Agent Molecule, an AI agent orchestration platform.

Your team members:
- Frontend Engineer — Next.js canvas, React Flow, Zustand state management
- Backend Engineer — Go platform, Postgres, Redis, A2A protocol
- DevOps Engineer — Docker, CI/CD pipelines, infrastructure, monitoring
- Security Auditor — vulnerability assessment, dependency audits, compliance
- QA Engineer — testing, test automation, quality assurance

Your responsibilities:
- Plan and prioritize engineering work across the team
- Delegate tasks to engineers via A2A messaging
- Review architecture decisions and code quality
- Ensure standards are met (tests, reviews, documentation)
- Report engineering status to PM when asked

The project repository is at /workspace. Read CLAUDE.md for architecture overview and docs/ for detailed specs.'

FE_ID=$(create_workspace "Frontend Engineer" "Next.js canvas, React Flow, Zustand" 2 "$DEV_ID")
echo "  Frontend Engineer: $FE_ID"
BE_ID=$(create_workspace "Backend Engineer" "Go platform, Postgres, Redis, A2A" 2 "$DEV_ID")
echo "  Backend Engineer: $BE_ID"
DO_ID=$(create_workspace "DevOps Engineer" "CI/CD, Docker, infrastructure" 2 "$DEV_ID")
echo "  DevOps Engineer: $DO_ID"
SA_ID=$(create_workspace "Security Auditor" "Security auditing and vulnerability assessment" 2 "$DEV_ID")
echo "  Security Auditor: $SA_ID"
QA_ID=$(create_workspace "QA Engineer" "Testing, quality assurance, and test automation" 2 "$DEV_ID")
echo "  QA Engineer: $QA_ID"

# --- Summary ---
echo ""
echo "=== Done ==="
echo "Created 15 workspaces:"
echo "  PM: $PM_ID"
echo "  Marketing: $MKT_ID ($CW_ID, $SEO_ID, $SM_ID)"
echo "  Research: $RES_ID ($MA_ID, $TR_ID, $CI_ID)"
echo "  Dev: $DEV_ID ($FE_ID, $BE_ID, $DO_ID, $SA_ID, $QA_ID)"
echo ""
echo "All workspaces use template 'claude-code-default'."
echo "Set your OAuth token: PUT /workspaces/:id/files/.auth-token"
