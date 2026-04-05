# Starfire MCP Server

MCP server that exposes Starfire platform operations as tools for AI coding agents.

## 20 Tools Available

| Tool | Description |
|------|-------------|
| `list_workspaces` | List all workspaces with status and skills |
| `create_workspace` | Create a new workspace (with optional template) |
| `get_workspace` | Get workspace details |
| `delete_workspace` | Delete workspace (cascades to children) |
| `restart_workspace` | Restart offline/failed workspace |
| `chat_with_agent` | Send message and get AI response |
| `assign_agent` | Assign model to workspace |
| `set_secret` | Set API key or env var |
| `list_secrets` | List secret keys (no values) |
| `list_files` | List workspace config files |
| `read_file` | Read a config file |
| `write_file` | Create or update a file |
| `delete_file` | Delete file or folder |
| `commit_memory` | Store fact (LOCAL/TEAM/GLOBAL) |
| `search_memory` | Search workspace memories |
| `list_templates` | List available templates |
| `expand_team` | Expand workspace to team |
| `collapse_team` | Collapse team to single workspace |
| `list_pending_approvals` | List pending approval requests |
| `decide_approval` | Approve or deny a request |

## Setup

### Claude Code

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "starfire": {
      "command": "node",
      "args": ["./mcp-server/dist/index.js"],
      "env": {
        "STARFIRE_URL": "http://localhost:8080"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "starfire": {
      "command": "node",
      "args": ["./mcp-server/dist/index.js"],
      "env": {
        "STARFIRE_URL": "http://localhost:8080"
      }
    }
  }
}
```

### Codex / OpenCode

```bash
# Run directly
STARFIRE_URL=http://localhost:8080 node mcp-server/dist/index.js
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STARFIRE_URL` | `http://localhost:8080` | Platform API URL |

## Examples

```
You: "Create an SEO agent workspace using the seo-agent template"
Agent: [calls create_workspace with template="seo-agent"]

You: "Set the OpenRouter API key for the SEO workspace"
Agent: [calls set_secret with key="OPENROUTER_API_KEY"]

You: "Ask the SEO agent to audit my homepage"
Agent: [calls chat_with_agent with message="Audit https://example.com for SEO"]

You: "What skills does the coding agent have?"
Agent: [calls get_workspace, reads agent_card.skills]
```
