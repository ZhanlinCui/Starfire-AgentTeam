#!/usr/bin/env node
/**
 * Starfire MCP Server
 *
 * Exposes Starfire platform operations as MCP tools so any AI coding agent
 * (Claude Code, Cursor, Codex, OpenCode) can manage workspaces, agents,
 * skills, and memory.
 *
 * Transport: stdio (for local CLI integration)
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const PLATFORM_URL = process.env.STARFIRE_URL || "http://localhost:8080";

async function apiCall(method: string, path: string, body?: unknown) {
  try {
    const res = await fetch(`${PLATFORM_URL}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch {
      return { raw: text, status: res.status };
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`Starfire API error (${method} ${path}): ${msg}`);
    return { error: `Failed to reach Starfire platform at ${PLATFORM_URL}. Is it running?`, detail: msg };
  }
}

const server = new McpServer({
  name: "starfire",
  version: "1.0.0",
});

// === WORKSPACE TOOLS ===

server.tool(
  "list_workspaces",
  "List all workspaces with their status, skills, and hierarchy",
  {},
  async () => {
    const data = await apiCall("GET", "/workspaces");
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "create_workspace",
  "Create a new workspace node on the canvas",
  {
    name: z.string().describe("Workspace name"),
    role: z.string().optional().describe("Role description"),
    template: z.string().optional().describe("Template name from workspace-configs-templates/"),
    tier: z.number().min(1).max(4).default(1).describe("Tier (1=basic, 2=browser, 3=desktop, 4=VM)"),
    parent_id: z.string().optional().describe("Parent workspace ID for nesting"),
  },
  async ({ name, role, template, tier, parent_id }) => {
    const data = await apiCall("POST", "/workspaces", {
      name, role, template, tier, parent_id,
      canvas: { x: Math.random() * 400 + 100, y: Math.random() * 300 + 100 },
    });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "get_workspace",
  "Get detailed information about a specific workspace",
  { workspace_id: z.string().describe("Workspace ID") },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/workspaces/${workspace_id}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "delete_workspace",
  "Delete a workspace (cascades to children)",
  { workspace_id: z.string().describe("Workspace ID") },
  async ({ workspace_id }) => {
    const data = await apiCall("DELETE", `/workspaces/${workspace_id}?confirm=true`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "restart_workspace",
  "Restart an offline or failed workspace",
  { workspace_id: z.string().describe("Workspace ID") },
  async ({ workspace_id }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/restart`, {});
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

// === CHAT / A2A ===

server.tool(
  "chat_with_agent",
  "Send a message to a workspace agent and get a response",
  {
    workspace_id: z.string().describe("Workspace ID"),
    message: z.string().describe("Message to send"),
  },
  async ({ workspace_id, message }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/a2a`, {
      method: "message/send",
      params: {
        message: { role: "user", parts: [{ type: "text", text: message }] },
      },
    });
    // Extract text from response
    const parts = data?.result?.parts || [];
    const text = parts
      .filter((p: { kind?: string }) => p.kind === "text")
      .map((p: { text?: string }) => p.text || "")
      .join("\n");
    return { content: [{ type: "text", text: text || JSON.stringify(data, null, 2) }] };
  }
);

// === AGENT MANAGEMENT ===

server.tool(
  "assign_agent",
  "Assign an AI model to a workspace",
  {
    workspace_id: z.string().describe("Workspace ID"),
    model: z.string().describe("Model string (e.g., openrouter:anthropic/claude-3.5-haiku)"),
  },
  async ({ workspace_id, model }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/agent`, { model });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

// === SECRETS ===

server.tool(
  "set_secret",
  "Set an API key or environment variable for a workspace",
  {
    workspace_id: z.string().describe("Workspace ID"),
    key: z.string().describe("Secret key (e.g., ANTHROPIC_API_KEY)"),
    value: z.string().describe("Secret value"),
  },
  async ({ workspace_id, key, value }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/secrets`, { key, value });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "list_secrets",
  "List secret keys for a workspace (values never exposed)",
  { workspace_id: z.string().describe("Workspace ID") },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/workspaces/${workspace_id}/secrets`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

// === FILES ===

server.tool(
  "list_files",
  "List workspace config files (skills, prompts, config.yaml)",
  { workspace_id: z.string().describe("Workspace ID") },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/workspaces/${workspace_id}/files`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "read_file",
  "Read a workspace config file",
  {
    workspace_id: z.string().describe("Workspace ID"),
    path: z.string().describe("File path (e.g., system-prompt.md, skills/seo/SKILL.md)"),
  },
  async ({ workspace_id, path }) => {
    const data = await apiCall("GET", `/workspaces/${workspace_id}/files/${path}`);
    return { content: [{ type: "text", text: data?.content || JSON.stringify(data) }] };
  }
);

server.tool(
  "write_file",
  "Write or create a workspace config file",
  {
    workspace_id: z.string().describe("Workspace ID"),
    path: z.string().describe("File path"),
    content: z.string().describe("File content"),
  },
  async ({ workspace_id, path, content }) => {
    const data = await apiCall("PUT", `/workspaces/${workspace_id}/files/${path}`, { content });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "delete_file",
  "Delete a workspace file or folder",
  {
    workspace_id: z.string().describe("Workspace ID"),
    path: z.string().describe("File or folder path"),
  },
  async ({ workspace_id, path }) => {
    const data = await apiCall("DELETE", `/workspaces/${workspace_id}/files/${path}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

// === MEMORY (HMA) ===

server.tool(
  "commit_memory",
  "Store a fact in workspace memory (LOCAL, TEAM, or GLOBAL scope)",
  {
    workspace_id: z.string().describe("Workspace ID"),
    content: z.string().describe("Fact to remember"),
    scope: z.enum(["LOCAL", "TEAM", "GLOBAL"]).default("LOCAL").describe("Memory scope"),
  },
  async ({ workspace_id, content, scope }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/memories`, { content, scope });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "search_memory",
  "Search workspace memories",
  {
    workspace_id: z.string().describe("Workspace ID"),
    query: z.string().optional().describe("Search query"),
    scope: z.enum(["LOCAL", "TEAM", "GLOBAL", ""]).optional().describe("Filter by scope"),
  },
  async ({ workspace_id, query, scope }) => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (scope) params.set("scope", scope);
    const data = await apiCall("GET", `/workspaces/${workspace_id}/memories?${params}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

// === TEMPLATES ===

server.tool(
  "list_templates",
  "List available workspace templates",
  {},
  async () => {
    const data = await apiCall("GET", "/templates");
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

// === TEAM EXPANSION ===

server.tool(
  "expand_team",
  "Expand a workspace into a team of sub-workspaces",
  { workspace_id: z.string().describe("Workspace ID to expand") },
  async ({ workspace_id }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/expand`, {});
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "collapse_team",
  "Collapse a team back to a single workspace",
  { workspace_id: z.string().describe("Workspace ID to collapse") },
  async ({ workspace_id }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/collapse`, {});
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

// === APPROVALS ===

server.tool(
  "list_pending_approvals",
  "List all pending approval requests across workspaces",
  {},
  async () => {
    const data = await apiCall("GET", "/approvals/pending");
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "decide_approval",
  "Approve or deny a pending approval request",
  {
    workspace_id: z.string().describe("Workspace ID"),
    approval_id: z.string().describe("Approval ID"),
    decision: z.enum(["approved", "denied"]).describe("Decision"),
  },
  async ({ workspace_id, approval_id, decision }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/approvals/${approval_id}/decide`, {
      decision,
      decided_by: "mcp-client",
    });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

// === MISSING TOOLS — FULL COVERAGE ===

server.tool(
  "update_workspace",
  "Update workspace fields (name, role, tier, parent_id, position)",
  {
    workspace_id: z.string(),
    name: z.string().optional(),
    role: z.string().optional(),
    tier: z.number().optional(),
    parent_id: z.string().nullable().optional().describe("Set parent for nesting, null to un-nest"),
  },
  async ({ workspace_id, ...fields }) => {
    const data = await apiCall("PATCH", `/workspaces/${workspace_id}`, fields);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "replace_agent",
  "Replace the model on an existing workspace agent",
  { workspace_id: z.string(), model: z.string() },
  async ({ workspace_id, model }) => {
    const data = await apiCall("PATCH", `/workspaces/${workspace_id}/agent`, { model });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "remove_agent",
  "Remove the agent from a workspace",
  { workspace_id: z.string() },
  async ({ workspace_id }) => {
    const data = await apiCall("DELETE", `/workspaces/${workspace_id}/agent`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "move_agent",
  "Move an agent from one workspace to another",
  { workspace_id: z.string(), target_workspace_id: z.string() },
  async ({ workspace_id, target_workspace_id }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/agent/move`, { target_workspace_id });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "delete_secret",
  "Delete a secret from a workspace",
  { workspace_id: z.string(), key: z.string() },
  async ({ workspace_id, key }) => {
    const data = await apiCall("DELETE", `/workspaces/${workspace_id}/secrets/${encodeURIComponent(key)}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "get_config",
  "Get workspace runtime config as JSON",
  { workspace_id: z.string() },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/workspaces/${workspace_id}/config`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "update_config",
  "Update workspace runtime config",
  { workspace_id: z.string(), config: z.record(z.unknown()).describe("Config fields to update") },
  async ({ workspace_id, config }) => {
    const data = await apiCall("PATCH", `/workspaces/${workspace_id}/config`, config);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "list_peers",
  "List reachable peer workspaces (siblings, children, parent)",
  { workspace_id: z.string() },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/registry/${workspace_id}/peers`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "discover_workspace",
  "Resolve a workspace URL by ID (for A2A communication)",
  { workspace_id: z.string() },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/registry/discover/${workspace_id}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "check_access",
  "Check if two workspaces can communicate",
  { caller_id: z.string(), target_id: z.string() },
  async ({ caller_id, target_id }) => {
    const data = await apiCall("POST", `/registry/check-access`, { caller_id, target_id });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "list_events",
  "List structure events (global or per workspace)",
  { workspace_id: z.string().optional().describe("Filter to workspace, or omit for all") },
  async ({ workspace_id }) => {
    const path = workspace_id ? `/events/${workspace_id}` : "/events";
    const data = await apiCall("GET", path);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "export_bundle",
  "Export a workspace as a portable .bundle.json",
  { workspace_id: z.string() },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/bundles/export/${workspace_id}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "import_bundle",
  "Import a workspace from a bundle JSON object",
  { bundle: z.record(z.unknown()).describe("Bundle JSON object") },
  async ({ bundle }) => {
    const data = await apiCall("POST", `/bundles/import`, bundle);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "import_template",
  "Import agent files as a new workspace template",
  {
    name: z.string().describe("Template name"),
    files: z.record(z.string()).describe("Map of file path → content"),
  },
  async ({ name, files }) => {
    const data = await apiCall("POST", `/templates/import`, { name, files });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "replace_all_files",
  "Replace all workspace config files at once",
  {
    workspace_id: z.string(),
    files: z.record(z.string()).describe("Map of file path → content"),
  },
  async ({ workspace_id, files }) => {
    const data = await apiCall("PUT", `/workspaces/${workspace_id}/files`, { files });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "list_traces",
  "List recent LLM traces from Langfuse for a workspace",
  { workspace_id: z.string() },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/workspaces/${workspace_id}/traces`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "list_activity",
  "List activity logs for a workspace (A2A communications, tasks, errors)",
  {
    workspace_id: z.string(),
    type: z.enum(["a2a_receive", "a2a_send", "task_update", "agent_log", "error"]).optional().describe("Filter by activity type"),
    limit: z.number().optional().describe("Max entries to return (default 100, max 500)"),
  },
  async ({ workspace_id, type, limit }) => {
    const params = new URLSearchParams();
    if (type) params.set("type", type);
    if (limit) params.set("limit", String(limit));
    const qs = params.toString() ? `?${params.toString()}` : "";
    const data = await apiCall("GET", `/workspaces/${workspace_id}/activity${qs}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "delete_memory",
  "Delete a specific memory entry",
  { workspace_id: z.string(), memory_id: z.string() },
  async ({ workspace_id, memory_id }) => {
    const data = await apiCall("DELETE", `/workspaces/${workspace_id}/memories/${memory_id}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "get_model",
  "Get current model configuration for a workspace",
  { workspace_id: z.string() },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/workspaces/${workspace_id}/model`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "create_approval",
  "Create an approval request for a workspace",
  {
    workspace_id: z.string(),
    action: z.string().describe("What needs approval"),
    reason: z.string().optional().describe("Why it's needed"),
  },
  async ({ workspace_id, action, reason }) => {
    const data = await apiCall("POST", `/workspaces/${workspace_id}/approvals`, { action, reason });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "get_workspace_approvals",
  "List approval requests for a specific workspace",
  { workspace_id: z.string() },
  async ({ workspace_id }) => {
    const data = await apiCall("GET", `/workspaces/${workspace_id}/approvals`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

// === START SERVER ===

async function main() {
  // Validate platform connectivity on startup
  try {
    const res = await fetch(`${PLATFORM_URL}/health`);
    if (res.ok) {
      console.error(`Starfire platform connected: ${PLATFORM_URL}`);
    } else {
      console.error(`WARNING: Starfire platform at ${PLATFORM_URL} returned ${res.status}. Tools may fail.`);
    }
  } catch {
    console.error(`WARNING: Cannot reach Starfire platform at ${PLATFORM_URL}. Start it with: cd platform && go run ./cmd/server`);
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Starfire MCP server running on stdio (20 tools available)");
}

main().catch(console.error);
