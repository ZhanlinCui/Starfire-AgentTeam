#!/usr/bin/env bash
set -euo pipefail

BASE="http://localhost:8080"
PASS=0
FAIL=0

check() {
  local desc="$1"
  local expected="$2"
  local actual="$3"
  if echo "$actual" | grep -qF "$expected"; then
    echo "PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $desc"
    echo "  expected to contain: $expected"
    echo "  got: $actual"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== API Integration Tests ==="
echo ""

# Test 1: Health
R=$(curl -s "$BASE/health")
check "GET /health" '"status":"ok"' "$R"

# Test 2: Empty list
R=$(curl -s "$BASE/workspaces")
check "GET /workspaces (empty)" '[]' "$R"

# Test 3: Create workspace A
R=$(curl -s -X POST "$BASE/workspaces" -H "Content-Type: application/json" -d '{"name":"Echo Agent","tier":1}')
check "POST /workspaces (create echo)" '"status":"provisioning"' "$R"
ECHO_ID=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Test 4: Create workspace B
R=$(curl -s -X POST "$BASE/workspaces" -H "Content-Type: application/json" -d '{"name":"Summarizer Agent","tier":1}')
check "POST /workspaces (create summarizer)" '"status":"provisioning"' "$R"
SUM_ID=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Test 5: List has 2
R=$(curl -s "$BASE/workspaces")
COUNT=$(echo "$R" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
check "GET /workspaces (count=2)" "2" "$COUNT"

# Test 6: Get single
R=$(curl -s "$BASE/workspaces/$ECHO_ID")
check "GET /workspaces/:id" '"name":"Echo Agent"' "$R"
check "GET /workspaces/:id (agent_card null)" '"agent_card":null' "$R"

# Test 7: Register echo
R=$(curl -s -X POST "$BASE/registry/register" -H "Content-Type: application/json" \
  -d "{\"id\":\"$ECHO_ID\",\"url\":\"http://localhost:8001\",\"agent_card\":{\"name\":\"Echo Agent\",\"skills\":[{\"id\":\"echo\",\"name\":\"Echo\"}]}}")
check "POST /registry/register (echo)" '"status":"registered"' "$R"

# Test 8: Register summarizer
R=$(curl -s -X POST "$BASE/registry/register" -H "Content-Type: application/json" \
  -d "{\"id\":\"$SUM_ID\",\"url\":\"http://localhost:8002\",\"agent_card\":{\"name\":\"Summarizer\",\"skills\":[{\"id\":\"summarize\",\"name\":\"Summarize\"}]}}")
check "POST /registry/register (summarizer)" '"status":"registered"' "$R"

# Test 9: Both online
R=$(curl -s "$BASE/workspaces/$ECHO_ID")
check "Echo is online" '"status":"online"' "$R"
check "Echo has agent_card" '"skills"' "$R"
check "Echo has url" '"url":"http://localhost:8001"' "$R"

# Test 10: Heartbeat
R=$(curl -s -X POST "$BASE/registry/heartbeat" -H "Content-Type: application/json" \
  -d "{\"workspace_id\":\"$ECHO_ID\",\"error_rate\":0.0,\"sample_error\":\"\",\"active_tasks\":2,\"uptime_seconds\":120}")
check "POST /registry/heartbeat" '"status":"ok"' "$R"

R=$(curl -s "$BASE/workspaces/$ECHO_ID")
check "Heartbeat updated active_tasks" '"active_tasks":2' "$R"
check "Heartbeat updated uptime" '"uptime_seconds":120' "$R"

# Test 11: Discover (no auth header — canvas)
R=$(curl -s "$BASE/registry/discover/$ECHO_ID")
check "GET /registry/discover/:id (canvas)" '"url":"http://localhost:8001"' "$R"

# Test 12: Discover (from sibling — allowed)
R=$(curl -s "$BASE/registry/discover/$ECHO_ID" -H "X-Workspace-ID: $SUM_ID")
check "GET /registry/discover/:id (sibling)" '"url"' "$R"

# Test 13: Peers (root siblings see each other)
R=$(curl -s "$BASE/registry/$ECHO_ID/peers")
check "GET /registry/:id/peers (has summarizer)" '"Summarizer' "$R"

R=$(curl -s "$BASE/registry/$SUM_ID/peers")
check "GET /registry/:id/peers (has echo)" '"Echo Agent"' "$R"

# Test 14: Check access (root siblings)
R=$(curl -s -X POST "$BASE/registry/check-access" -H "Content-Type: application/json" \
  -d "{\"caller_id\":\"$ECHO_ID\",\"target_id\":\"$SUM_ID\"}")
check "POST /registry/check-access (siblings allowed)" '"allowed":true' "$R"

# Test 15: PATCH workspace (update position)
R=$(curl -s -X PATCH "$BASE/workspaces/$ECHO_ID" -H "Content-Type: application/json" -d '{"x":100,"y":200}')
check "PATCH /workspaces/:id (position)" '"status":"updated"' "$R"

R=$(curl -s "$BASE/workspaces/$ECHO_ID")
check "Position saved (x=100)" '"x":100' "$R"
check "Position saved (y=200)" '"y":200' "$R"

# Test 16: PATCH workspace (update name)
R=$(curl -s -X PATCH "$BASE/workspaces/$ECHO_ID" -H "Content-Type: application/json" -d '{"name":"Echo Agent v2"}')
check "PATCH /workspaces/:id (name)" '"status":"updated"' "$R"

R=$(curl -s "$BASE/workspaces/$ECHO_ID")
check "Name updated" '"name":"Echo Agent v2"' "$R"

# Test 17: Events
R=$(curl -s "$BASE/events")
check "GET /events (has events)" 'WORKSPACE_ONLINE' "$R"

R=$(curl -s "$BASE/events/$ECHO_ID")
check "GET /events/:id (has events for echo)" 'WORKSPACE_ONLINE' "$R"

# Test 18: Update card
R=$(curl -s -X POST "$BASE/registry/update-card" -H "Content-Type: application/json" \
  -d "{\"workspace_id\":\"$ECHO_ID\",\"agent_card\":{\"name\":\"Echo Agent v2\",\"skills\":[{\"id\":\"echo\",\"name\":\"Echo\"},{\"id\":\"repeat\",\"name\":\"Repeat\"}]}}")
check "POST /registry/update-card" '"status":"updated"' "$R"

# Test 19: Degraded status transition
R=$(curl -s -X POST "$BASE/registry/heartbeat" -H "Content-Type: application/json" \
  -d "{\"workspace_id\":\"$ECHO_ID\",\"error_rate\":0.8,\"sample_error\":\"API rate limit\",\"active_tasks\":0,\"uptime_seconds\":200}")
check "Heartbeat (high error_rate)" '"status":"ok"' "$R"

R=$(curl -s "$BASE/workspaces/$ECHO_ID")
check "Status degraded" '"status":"degraded"' "$R"

# Test 20: Recovery
R=$(curl -s -X POST "$BASE/registry/heartbeat" -H "Content-Type: application/json" \
  -d "{\"workspace_id\":\"$ECHO_ID\",\"error_rate\":0.0,\"sample_error\":\"\",\"active_tasks\":0,\"uptime_seconds\":300}")
check "Heartbeat (recovered)" '"status":"ok"' "$R"

R=$(curl -s "$BASE/workspaces/$ECHO_ID")
check "Status back online" '"status":"online"' "$R"

# Test 21: Delete
R=$(curl -s -X DELETE "$BASE/workspaces/$ECHO_ID")
check "DELETE /workspaces/:id" '"status":"removed"' "$R"

R=$(curl -s "$BASE/workspaces")
COUNT=$(echo "$R" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
check "List after delete (count=1)" "1" "$COUNT"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
