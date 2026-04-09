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

export const PLATFORM_URL = process.env.STARFIRE_URL || "http://localhost:8080";

export async function apiCall(method: string, path: string, body?: unknown) {
  try {
    const res = await fetch(`${PLATFORM_URL}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const text = await res.text();
      return { error: `HTTP ${res.status}`, detail: text };
    }
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch {
      return { raw: text, status: res.status };
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`Starfire API error (${method} ${path}): ${msg}`);
    return { error: `Platform unreachable at ${PLATFORM_URL}`, detail: msg };
  }
}

// ============================================================
// Tool handler functions (exported for unit testing)
// ============================================================

export async function handleListWorkspaces() {
  const data = await apiCall("GET", "/workspaces");
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleCreateWorkspace(params: {
  name: string;
  role?: string;
  template?: string;
  tier?: number;
  parent_id?: string;
}) {
  const { name, role, template, tier, parent_id } = params;
  const data = await apiCall("POST", "/workspaces", {
    name, role, template, tier, parent_id,
    canvas: { x: Math.random() * 400 + 100, y: Math.random() * 300 + 100 },
  });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleGetWorkspace(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/workspaces/${params.workspace_id}`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleDeleteWorkspace(params: { workspace_id: string }) {
  const data = await apiCall("DELETE", `/workspaces/${params.workspace_id}?confirm=true`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleRestartWorkspace(params: { workspace_id: string }) {
  const data = await apiCall("POST", `/workspaces/${params.workspace_id}/restart`, {});
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleChatWithAgent(params: { workspace_id: string; message: string }) {
  const { workspace_id, message } = params;
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
  return { content: [{ type: "text" as const, text: text || JSON.stringify(data, null, 2) }] };
}

export async function handleAssignAgent(params: { workspace_id: string; model: string }) {
  const { workspace_id, model } = params;
  const data = await apiCall("POST", `/workspaces/${workspace_id}/agent`, { model });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleSetSecret(params: { workspace_id: string; key: string; value: string }) {
  const { workspace_id, key, value } = params;
  const data = await apiCall("POST", `/workspaces/${workspace_id}/secrets`, { key, value });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleListSecrets(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/workspaces/${params.workspace_id}/secrets`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleListFiles(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/workspaces/${params.workspace_id}/files`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleReadFile(params: { workspace_id: string; path: string }) {
  const { workspace_id, path } = params;
  const data = await apiCall("GET", `/workspaces/${workspace_id}/files/${path}`);
  return { content: [{ type: "text" as const, text: data?.content || JSON.stringify(data) }] };
}

export async function handleWriteFile(params: { workspace_id: string; path: string; content: string }) {
  const { workspace_id, path, content } = params;
  const data = await apiCall("PUT", `/workspaces/${workspace_id}/files/${path}`, { content });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleDeleteFile(params: { workspace_id: string; path: string }) {
  const { workspace_id, path } = params;
  const data = await apiCall("DELETE", `/workspaces/${workspace_id}/files/${path}`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleCommitMemory(params: {
  workspace_id: string;
  content: string;
  scope: "LOCAL" | "TEAM" | "GLOBAL";
}) {
  const { workspace_id, content, scope } = params;
  const data = await apiCall("POST", `/workspaces/${workspace_id}/memories`, { content, scope });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleSearchMemory(params: {
  workspace_id: string;
  query?: string;
  scope?: "LOCAL" | "TEAM" | "GLOBAL" | "";
}) {
  const { workspace_id, query, scope } = params;
  const urlParams = new URLSearchParams();
  if (query) urlParams.set("q", query);
  if (scope) urlParams.set("scope", scope);
  const data = await apiCall("GET", `/workspaces/${workspace_id}/memories?${urlParams}`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleListTemplates() {
  const data = await apiCall("GET", "/templates");
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleExpandTeam(params: { workspace_id: string }) {
  const data = await apiCall("POST", `/workspaces/${params.workspace_id}/expand`, {});
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleCollapseTeam(params: { workspace_id: string }) {
  const data = await apiCall("POST", `/workspaces/${params.workspace_id}/collapse`, {});
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleListPendingApprovals() {
  const data = await apiCall("GET", "/approvals/pending");
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleDecideApproval(params: {
  workspace_id: string;
  approval_id: string;
  decision: "approved" | "denied";
}) {
  const { workspace_id, approval_id, decision } = params;
  const data = await apiCall(
    "POST",
    `/workspaces/${workspace_id}/approvals/${approval_id}/decide`,
    { decision, decided_by: "mcp-client" }
  );
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleUpdateWorkspace(params: {
  workspace_id: string;
  name?: string;
  role?: string;
  tier?: number;
  parent_id?: string | null;
}) {
  const { workspace_id, ...fields } = params;
  const data = await apiCall("PATCH", `/workspaces/${workspace_id}`, fields);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleReplaceAgent(params: { workspace_id: string; model: string }) {
  const { workspace_id, model } = params;
  const data = await apiCall("PATCH", `/workspaces/${workspace_id}/agent`, { model });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleRemoveAgent(params: { workspace_id: string }) {
  const data = await apiCall("DELETE", `/workspaces/${params.workspace_id}/agent`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleMoveAgent(params: { workspace_id: string; target_workspace_id: string }) {
  const { workspace_id, target_workspace_id } = params;
  const data = await apiCall("POST", `/workspaces/${workspace_id}/agent/move`, { target_workspace_id });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleDeleteSecret(params: { workspace_id: string; key: string }) {
  const { workspace_id, key } = params;
  const data = await apiCall("DELETE", `/workspaces/${workspace_id}/secrets/${encodeURIComponent(key)}`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleGetConfig(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/workspaces/${params.workspace_id}/config`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleUpdateConfig(params: { workspace_id: string; config: Record<string, unknown> }) {
  const { workspace_id, config } = params;
  const data = await apiCall("PATCH", `/workspaces/${workspace_id}/config`, config);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleListPeers(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/registry/${params.workspace_id}/peers`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleDiscoverWorkspace(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/registry/discover/${params.workspace_id}`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleCheckAccess(params: { caller_id: string; target_id: string }) {
  const { caller_id, target_id } = params;
  const data = await apiCall("POST", `/registry/check-access`, { caller_id, target_id });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleListEvents(params: { workspace_id?: string }) {
  const path = params.workspace_id ? `/events/${params.workspace_id}` : "/events";
  const data = await apiCall("GET", path);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleExportBundle(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/bundles/export/${params.workspace_id}`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleImportBundle(params: { bundle: Record<string, unknown> }) {
  const data = await apiCall("POST", `/bundles/import`, params.bundle);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleImportTemplate(params: { name: string; files: Record<string, string> }) {
  const { name, files } = params;
  const data = await apiCall("POST", `/templates/import`, { name, files });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleReplaceAllFiles(params: {
  workspace_id: string;
  files: Record<string, string>;
}) {
  const { workspace_id, files } = params;
  const data = await apiCall("PUT", `/workspaces/${workspace_id}/files`, { files });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleListTraces(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/workspaces/${params.workspace_id}/traces`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleListActivity(params: {
  workspace_id: string;
  type?: "a2a_receive" | "a2a_send" | "task_update" | "agent_log" | "error";
  limit?: number;
}) {
  const { workspace_id, type, limit } = params;
  const urlParams = new URLSearchParams();
  if (type) urlParams.set("type", type);
  if (limit) urlParams.set("limit", String(limit));
  const qs = urlParams.toString() ? `?${urlParams.toString()}` : "";
  const data = await apiCall("GET", `/workspaces/${workspace_id}/activity${qs}`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleDeleteMemory(params: { workspace_id: string; memory_id: string }) {
  const { workspace_id, memory_id } = params;
  const data = await apiCall("DELETE", `/workspaces/${workspace_id}/memories/${memory_id}`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleGetModel(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/workspaces/${params.workspace_id}/model`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleCreateApproval(params: {
  workspace_id: string;
  action: string;
  reason?: string;
}) {
  const { workspace_id, action, reason } = params;
  const data = await apiCall("POST", `/workspaces/${workspace_id}/approvals`, { action, reason });
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

export async function handleGetWorkspaceApprovals(params: { workspace_id: string }) {
  const data = await apiCall("GET", `/workspaces/${params.workspace_id}/approvals`);
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

// ============================================================
// MCP Server registration
// ============================================================

export function createServer() {
  const srv = new McpServer({
    name: "starfire",
    version: "1.0.0",
  });

  // === WORKSPACE TOOLS ===

  srv.tool("list_workspaces", "List all workspaces with their status, skills, and hierarchy", {}, handleListWorkspaces);

  srv.tool(
    "create_workspace",
    "Create a new workspace node on the canvas",
    {
      name: z.string().describe("Workspace name"),
      role: z.string().optional().describe("Role description"),
      template: z.string().optional().describe("Template name from workspace-configs-templates/"),
      tier: z.number().min(1).max(4).default(1).describe("Tier (1=basic, 2=browser, 3=desktop, 4=VM)"),
      parent_id: z.string().optional().describe("Parent workspace ID for nesting"),
    },
    handleCreateWorkspace
  );

  srv.tool(
    "get_workspace",
    "Get detailed information about a specific workspace",
    { workspace_id: z.string().describe("Workspace ID") },
    handleGetWorkspace
  );

  srv.tool(
    "delete_workspace",
    "Delete a workspace (cascades to children)",
    { workspace_id: z.string().describe("Workspace ID") },
    handleDeleteWorkspace
  );

  srv.tool(
    "restart_workspace",
    "Restart an offline or failed workspace",
    { workspace_id: z.string().describe("Workspace ID") },
    handleRestartWorkspace
  );

  // === CHAT / A2A ===

  srv.tool(
    "chat_with_agent",
    "Send a message to a workspace agent and get a response",
    {
      workspace_id: z.string().describe("Workspace ID"),
      message: z.string().describe("Message to send"),
    },
    handleChatWithAgent
  );

  // === AGENT MANAGEMENT ===

  srv.tool(
    "assign_agent",
    "Assign an AI model to a workspace",
    {
      workspace_id: z.string().describe("Workspace ID"),
      model: z.string().describe("Model string (e.g., openrouter:anthropic/claude-3.5-haiku)"),
    },
    handleAssignAgent
  );

  // === SECRETS ===

  srv.tool(
    "set_secret",
    "Set an API key or environment variable for a workspace",
    {
      workspace_id: z.string().describe("Workspace ID"),
      key: z.string().describe("Secret key (e.g., ANTHROPIC_API_KEY)"),
      value: z.string().describe("Secret value"),
    },
    handleSetSecret
  );

  srv.tool(
    "list_secrets",
    "List secret keys for a workspace (values never exposed)",
    { workspace_id: z.string().describe("Workspace ID") },
    handleListSecrets
  );

  // === FILES ===

  srv.tool(
    "list_files",
    "List workspace config files (skills, prompts, config.yaml)",
    { workspace_id: z.string().describe("Workspace ID") },
    handleListFiles
  );

  srv.tool(
    "read_file",
    "Read a workspace config file",
    {
      workspace_id: z.string().describe("Workspace ID"),
      path: z.string().describe("File path (e.g., system-prompt.md, skills/seo/SKILL.md)"),
    },
    handleReadFile
  );

  srv.tool(
    "write_file",
    "Write or create a workspace config file",
    {
      workspace_id: z.string().describe("Workspace ID"),
      path: z.string().describe("File path"),
      content: z.string().describe("File content"),
    },
    handleWriteFile
  );

  srv.tool(
    "delete_file",
    "Delete a workspace file or folder",
    {
      workspace_id: z.string().describe("Workspace ID"),
      path: z.string().describe("File or folder path"),
    },
    handleDeleteFile
  );

  // === MEMORY (HMA) ===

  srv.tool(
    "commit_memory",
    "Store a fact in workspace memory (LOCAL, TEAM, or GLOBAL scope)",
    {
      workspace_id: z.string().describe("Workspace ID"),
      content: z.string().describe("Fact to remember"),
      scope: z.enum(["LOCAL", "TEAM", "GLOBAL"]).default("LOCAL").describe("Memory scope"),
    },
    handleCommitMemory
  );

  srv.tool(
    "search_memory",
    "Search workspace memories",
    {
      workspace_id: z.string().describe("Workspace ID"),
      query: z.string().optional().describe("Search query"),
      scope: z.enum(["LOCAL", "TEAM", "GLOBAL", ""]).optional().describe("Filter by scope"),
    },
    handleSearchMemory
  );

  // === TEMPLATES ===

  srv.tool("list_templates", "List available workspace templates", {}, handleListTemplates);

  // === TEAM EXPANSION ===

  srv.tool(
    "expand_team",
    "Expand a workspace into a team of sub-workspaces",
    { workspace_id: z.string().describe("Workspace ID to expand") },
    handleExpandTeam
  );

  srv.tool(
    "collapse_team",
    "Collapse a team back to a single workspace",
    { workspace_id: z.string().describe("Workspace ID to collapse") },
    handleCollapseTeam
  );

  // === APPROVALS ===

  srv.tool(
    "list_pending_approvals",
    "List all pending approval requests across workspaces",
    {},
    handleListPendingApprovals
  );

  srv.tool(
    "decide_approval",
    "Approve or deny a pending approval request",
    {
      workspace_id: z.string().describe("Workspace ID"),
      approval_id: z.string().describe("Approval ID"),
      decision: z.enum(["approved", "denied"]).describe("Decision"),
    },
    handleDecideApproval
  );

  // === MISSING TOOLS — FULL COVERAGE ===

  srv.tool(
    "update_workspace",
    "Update workspace fields (name, role, tier, parent_id, position)",
    {
      workspace_id: z.string(),
      name: z.string().optional(),
      role: z.string().optional(),
      tier: z.number().optional(),
      parent_id: z.string().nullable().optional().describe("Set parent for nesting, null to un-nest"),
    },
    handleUpdateWorkspace
  );

  srv.tool(
    "replace_agent",
    "Replace the model on an existing workspace agent",
    { workspace_id: z.string(), model: z.string() },
    handleReplaceAgent
  );

  srv.tool(
    "remove_agent",
    "Remove the agent from a workspace",
    { workspace_id: z.string() },
    handleRemoveAgent
  );

  srv.tool(
    "move_agent",
    "Move an agent from one workspace to another",
    { workspace_id: z.string(), target_workspace_id: z.string() },
    handleMoveAgent
  );

  srv.tool(
    "delete_secret",
    "Delete a secret from a workspace",
    { workspace_id: z.string(), key: z.string() },
    handleDeleteSecret
  );

  srv.tool(
    "get_config",
    "Get workspace runtime config as JSON",
    { workspace_id: z.string() },
    handleGetConfig
  );

  srv.tool(
    "update_config",
    "Update workspace runtime config",
    { workspace_id: z.string(), config: z.record(z.unknown()).describe("Config fields to update") },
    handleUpdateConfig
  );

  srv.tool(
    "list_peers",
    "List reachable peer workspaces (siblings, children, parent)",
    { workspace_id: z.string() },
    handleListPeers
  );

  srv.tool(
    "discover_workspace",
    "Resolve a workspace URL by ID (for A2A communication)",
    { workspace_id: z.string() },
    handleDiscoverWorkspace
  );

  srv.tool(
    "check_access",
    "Check if two workspaces can communicate",
    { caller_id: z.string(), target_id: z.string() },
    handleCheckAccess
  );

  srv.tool(
    "list_events",
    "List structure events (global or per workspace)",
    { workspace_id: z.string().optional().describe("Filter to workspace, or omit for all") },
    handleListEvents
  );

  srv.tool(
    "export_bundle",
    "Export a workspace as a portable .bundle.json",
    { workspace_id: z.string() },
    handleExportBundle
  );

  srv.tool(
    "import_bundle",
    "Import a workspace from a bundle JSON object",
    { bundle: z.record(z.unknown()).describe("Bundle JSON object") },
    handleImportBundle
  );

  srv.tool(
    "import_template",
    "Import agent files as a new workspace template",
    {
      name: z.string().describe("Template name"),
      files: z.record(z.string()).describe("Map of file path → content"),
    },
    handleImportTemplate
  );

  srv.tool(
    "replace_all_files",
    "Replace all workspace config files at once",
    {
      workspace_id: z.string(),
      files: z.record(z.string()).describe("Map of file path → content"),
    },
    handleReplaceAllFiles
  );

  srv.tool(
    "list_traces",
    "List recent LLM traces from Langfuse for a workspace",
    { workspace_id: z.string() },
    handleListTraces
  );

  srv.tool(
    "list_activity",
    "List activity logs for a workspace (A2A communications, tasks, errors)",
    {
      workspace_id: z.string(),
      type: z
        .enum(["a2a_receive", "a2a_send", "task_update", "agent_log", "error"])
        .optional()
        .describe("Filter by activity type"),
      limit: z.number().optional().describe("Max entries to return (default 100, max 500)"),
    },
    handleListActivity
  );

  srv.tool(
    "delete_memory",
    "Delete a specific memory entry",
    { workspace_id: z.string(), memory_id: z.string() },
    handleDeleteMemory
  );

  srv.tool(
    "get_model",
    "Get current model configuration for a workspace",
    { workspace_id: z.string() },
    handleGetModel
  );

  srv.tool(
    "create_approval",
    "Create an approval request for a workspace",
    {
      workspace_id: z.string(),
      action: z.string().describe("What needs approval"),
      reason: z.string().optional().describe("Why it's needed"),
    },
    handleCreateApproval
  );

  srv.tool(
    "get_workspace_approvals",
    "List approval requests for a specific workspace",
    { workspace_id: z.string() },
    handleGetWorkspaceApprovals
  );

  return srv;
}

// ============================================================
// Main entry point — only runs when executed directly
// ============================================================

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

  const server = createServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Starfire MCP server running on stdio (20 tools available)");
}

// Only auto-start when run directly (not when imported for testing).
// JEST_WORKER_ID is set automatically by Jest in every worker process.
if (!process.env.JEST_WORKER_ID) {
  main().catch(console.error);
}
