#!/bin/bash
# Set up the full Reno Stars org chart on the Agent Molecule platform.
# Prerequisites: docker compose up, workspace-template:latest built, .auth-token in place.

set -euo pipefail
PLATFORM="http://localhost:8080"

echo "=== Setting up Reno Stars Org Chart ==="

# Clean existing
for id in $(curl -s $PLATFORM/workspaces | python3 -c "import sys,json; [print(w['id']) for w in json.load(sys.stdin)]" 2>/dev/null); do
    curl -s -X DELETE "$PLATFORM/workspaces/$id" > /dev/null
done
docker stop $(docker ps -q --filter "name=ws-") 2>/dev/null || true
docker rm $(docker ps -aq --filter "name=ws-") 2>/dev/null || true
find workspace-configs-templates -maxdepth 1 -name "ws-*" -type d -exec rm -r {} + 2>/dev/null || true

echo "Creating workspaces..."

# Root
ROOT=$(curl -s -X POST $PLATFORM/workspaces -H "Content-Type: application/json" \
  -d '{"name":"Reno Stars Business Intelligent","role":"Company brain — coordinates all teams, manages memory, handles escalations","runtime":"claude-code","tier":3,"canvas":{"x":400,"y":50}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Marketing Team
MKT=$(curl -s -X POST $PLATFORM/workspaces -H "Content-Type: application/json" \
  -d "{\"name\":\"Marketing Team\",\"role\":\"Coordinates social media, ads, and SEO efforts\",\"runtime\":\"claude-code\",\"tier\":1,\"parent_id\":\"$ROOT\",\"canvas\":{\"x\":150,\"y\":250}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Developer Team
DEV=$(curl -s -X POST $PLATFORM/workspaces -H "Content-Type: application/json" \
  -d "{\"name\":\"Developer Team\",\"role\":\"Website development, email service, invoice automation\",\"runtime\":\"claude-code\",\"tier\":2,\"parent_id\":\"$ROOT\",\"canvas\":{\"x\":650,\"y\":250}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Social Media (under Marketing)
SOCIAL=$(curl -s -X POST $PLATFORM/workspaces -H "Content-Type: application/json" \
  -d "{\"name\":\"Social Media\",\"role\":\"Facebook, Instagram, 小红书 content management\",\"runtime\":\"claude-code\",\"tier\":1,\"parent_id\":\"$MKT\",\"canvas\":{\"x\":0,\"y\":450}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Google Ads (under Marketing)
ADS=$(curl -s -X POST $PLATFORM/workspaces -H "Content-Type: application/json" \
  -d "{\"name\":\"Google Ads\",\"role\":\"Campaign optimization, keyword management, conversion tracking\",\"runtime\":\"claude-code\",\"tier\":1,\"parent_id\":\"$MKT\",\"canvas\":{\"x\":150,\"y\":450}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# SEO Team (under Marketing)
SEO=$(curl -s -X POST $PLATFORM/workspaces -H "Content-Type: application/json" \
  -d "{\"name\":\"SEO Team\",\"role\":\"Daily SEO audit, page building, GSC monitoring, indexing\",\"runtime\":\"claude-code\",\"tier\":2,\"parent_id\":\"$MKT\",\"canvas\":{\"x\":300,\"y\":450}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo ""
echo "Reno Stars Business Intelligent: $ROOT"
echo "├── Marketing Team: $MKT"
echo "│   ├── Social Media: $SOCIAL"
echo "│   ├── Google Ads: $ADS"
echo "│   └── SEO Team: $SEO"
echo "└── Developer Team: $DEV"

# Upload system prompts
echo ""
echo "Uploading system prompts..."

sleep 3

curl -s -X PUT "$PLATFORM/workspaces/$ROOT/files" -H "Content-Type: application/json" \
  -d "{\"files\":{\"system-prompt.md\":\"You are Reno Stars Business Intelligent, the central brain of Reno Stars Construction Inc, a Vancouver renovation company.\n\nYour role:\n- Coordinate the Marketing Team and Developer Team\n- Manage company memory and TODO lists\n- Handle health checks and system monitoring\n- Report to the owner via Telegram\n\nYou coordinate:\n- Marketing Team (ID: $MKT): handles social media, ads, and SEO\n- Developer Team (ID: $DEV): handles website code, email service, invoices\n\nYou CANNOT directly contact Social Media, Google Ads, or SEO Team — go through Marketing Team.\n\nCompany: Reno Stars | Phone: 778-960-7999 | Owner: Hongming Wang | Site: www.reno-stars.com\"}}" > /dev/null && echo "  ✅ Root"

curl -s -X PUT "$PLATFORM/workspaces/$MKT/files" -H "Content-Type: application/json" \
  -d "{\"files\":{\"system-prompt.md\":\"You are the Marketing Team coordinator for Reno Stars.\n\nYour direct reports:\n- Social Media (ID: $SOCIAL): Facebook, Instagram, 小红书\n- Google Ads (ID: $ADS): Campaign optimization, keywords, conversion tracking\n- SEO Team (ID: $SEO): Daily audit, page building, GSC monitoring, indexing\n\nWhen asked for status, delegate to your sub-teams and compile a summary.\"}}" > /dev/null && echo "  ✅ Marketing"

curl -s -X PUT "$PLATFORM/workspaces/$DEV/files" -H "Content-Type: application/json" \
  -d '{"files":{"system-prompt.md":"You are the Developer Team for Reno Stars.\n\nProjects:\n- reno-stars.com (Next.js, Vercel, Neon PostgreSQL)\n- Email AI service (Railway)\n- Invoice automation (MCP server)\n\nRules:\n- git pull --rebase before working, push when done\n- Run pnpm typecheck && pnpm lint && pnpm test:run before pushing\n- All content bilingual en/zh\n- Never fabricate content"}}' > /dev/null && echo "  ✅ Developer"

curl -s -X PUT "$PLATFORM/workspaces/$SOCIAL/files" -H "Content-Type: application/json" \
  -d '{"files":{"system-prompt.md":"You are the Social Media agent for Reno Stars.\n\nPlatforms:\n- Facebook (reno.stars.73): post from content bank every 6h\n- Instagram (@renostarsvancouver): 384 followers, 127 posts\n- 小红书: needs audit\n\nRules:\n- No markdown tables on Facebook — use bullet lists\n- No headers on WhatsApp — use bold or CAPS\n- Never fabricate content"}}' > /dev/null && echo "  ✅ Social Media"

curl -s -X PUT "$PLATFORM/workspaces/$ADS/files" -H "Content-Type: application/json" \
  -d '{"files":{"system-prompt.md":"You are the Google Ads specialist for Reno Stars.\n\nAccount: MCC 895-054-0400, CID 874-074-0439\nBest keyword: remodeling company near me (11.63% CTR, 20% conv rate)\n\nCampaigns:\n- AI Bathroom Renovation - EN\n- AI Kitchen Renovation - EN\n- AI Full Home Renovation - EN (best performer)\n- Chinese ads 2026\n\nTODO:\n- Add 15 Chinese keywords\n- Fix 2 disapproved CN sitelinks"}}' > /dev/null && echo "  ✅ Google Ads"

curl -s -X PUT "$PLATFORM/workspaces/$SEO/files" -H "Content-Type: application/json" \
  -d '{"files":{"system-prompt.md":"You are the SEO builder for reno-stars.com.\n\nYour job: ACTIVELY BUILD new pages every run based on GSC data.\n\nRules:\n- Push to Reno-Stars/reno-stars-nextjs (NOT the fork)\n- All content bilingual en/zh\n- Never fabricate content\n- Run pnpm typecheck && pnpm lint before pushing\n\nLatest stats: 453 pages indexed, +63% clicks this week, built 1 new blog post."}}' > /dev/null && echo "  ✅ SEO Team"

echo ""
echo "Waiting for all workspaces to come online..."
sleep 40

echo ""
curl -s $PLATFORM/workspaces | python3 -c "
import sys, json
ws = json.load(sys.stdin)
lookup = {w['id']: w['name'] for w in ws}
online = sum(1 for w in ws if w['status'] == 'online')
print(f'{online}/{len(ws)} online')
print()
for w in ws:
    parent = lookup.get(w.get('parent_id',''), '(root)')
    icon = '✅' if w['status'] == 'online' else '❌'
    print(f'  {icon} T{w[\"tier\"]} {w[\"name\"]:35s} → {parent}')
"

echo ""
echo "Verifying system prompts in containers..."
for ws in $(docker ps --filter "name=ws-" --format "{{.Names}}"); do
    has=$(docker exec $ws test -f /configs/system-prompt.md 2>/dev/null && echo "✅" || echo "❌")
    first=$(docker exec $ws head -c 40 /configs/system-prompt.md 2>/dev/null || echo "missing")
    echo "  $has $ws: $first..."
done

echo ""
echo "=== Reno Stars Org Chart Setup Complete ==="
