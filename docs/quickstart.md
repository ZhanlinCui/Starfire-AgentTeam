# Quickstart Guide

Get Starfire running locally in under 5 minutes. By the end, you'll have a working AI agent team on a visual canvas.

## Prerequisites

- **Docker** (v24+) with Docker Compose v2
- **Node.js** (v20+) — for the Canvas frontend
- **Go** (v1.25+) — for the Platform backend
- An **Anthropic API key** (get one at [console.anthropic.com](https://console.anthropic.com))

## Step 1: Start Infrastructure

```bash
# Clone the repo
git clone https://github.com/yourusername/starfire.git
cd starfire

# Start Postgres, Redis, and Langfuse
docker compose -f docker-compose.infra.yml up -d
```

Wait ~30 seconds for Postgres to initialize.

## Step 2: Start the Platform

```bash
cd platform
go run ./cmd/server
```

The platform API starts on `http://localhost:8080`. It manages workspaces, proxies A2A requests, and provisions agent containers.

## Step 3: Start the Canvas

In a new terminal:

```bash
cd canvas
npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

## Step 4: Create Your First Agent

1. The canvas shows a **Welcome** screen with templates
2. Click any template (e.g., "General Assistant") or **Create blank workspace**
3. The agent container starts provisioning automatically

## Step 5: Set Your API Key

1. Select the new workspace node on the canvas
2. Open the **Config** tab in the side panel
3. Expand **Secrets & API Keys**
4. Set your `ANTHROPIC_API_KEY`
5. The workspace auto-restarts with the new key

## Step 6: Chat with Your Agent

1. Switch to the **Chat** tab
2. Type a message and press Enter
3. The agent responds in real-time via WebSocket

You're up and running!

---

## What's Next?

### Deploy a Team
Right-click any workspace and select **Expand to Team**. The agent splits into a Team Lead + specialized sub-agents — all coordinating automatically via A2A protocol.

### Nest Workspaces
Drag one workspace onto another to create a hierarchy. Children report to parents, siblings collaborate, and the org chart enforces access control.

### Add Skills
Open the **Skills** tab to attach capabilities to your agent — web search, file management, code execution, and more.

### Multi-Provider Models
Start with LiteLLM for unified model routing:
```bash
docker compose --profile multi-provider up
```
Then set `MODEL_PROVIDER` to any supported model (Claude, GPT-4, Deepseek, Ollama).

### Cloud Deployment
Use the one-click deploy buttons in the README for Railway or Render, or self-host on any Docker-capable VM.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Agent shows "offline" | Check Docker is running. Try right-click > Restart. |
| "Agent not responding" | Verify your API key is set in Config > Secrets. |
| No templates shown | Ensure the platform is running on `:8080`. |
| WebSocket disconnects | Check browser console. The canvas auto-reconnects. |

## Architecture at a Glance

```
Browser  ──HTTP/WS──>  Canvas (Next.js :3000)
                           │
                       HTTP/WS
                           │
                       Platform (Go :8080)
                        ┌──┴──┐
                    Postgres  Redis
                        │
                    Docker API
                        │
              ┌─────────┼─────────┐
          Agent-1    Agent-2    Agent-N
         (Python)   (Python)   (Python)
              └─────A2A JSON-RPC──┘
```

For full architecture details, see [Architecture](./architecture/architecture.md).
