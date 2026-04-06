/**
 * Claude Code Workspace Runtime for Agent Molecule
 *
 * A lightweight A2A-compatible workspace that uses Claude Code CLI
 * as the agent brain instead of Python/LangGraph.
 *
 * Flow:
 * 1. Load config from /configs
 * 2. Register with platform
 * 3. Start heartbeat
 * 4. Listen for A2A JSON-RPC requests
 * 5. On message/send → invoke claude --print with the task
 * 6. Return response via A2A
 */

import { createServer, type IncomingMessage, type ServerResponse } from 'http';
import { execSync, spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

// --- Config ---

const WORKSPACE_ID = process.env.WORKSPACE_ID || 'workspace-default';
const CONFIG_PATH = process.env.WORKSPACE_CONFIG_PATH || '/configs';
const PLATFORM_URL = process.env.PLATFORM_URL || 'http://platform:8080';
const PORT = parseInt(process.env.PORT || '8000');
const CLAUDE_MODEL = process.env.CLAUDE_MODEL || 'sonnet';
const HEARTBEAT_INTERVAL = 30_000; // 30s

interface WorkspaceConfig {
  name: string;
  description: string;
  model: string;
  system_prompt?: string;
  skills?: string[];
  version?: string;
}

function loadConfig(): WorkspaceConfig {
  const configFile = join(CONFIG_PATH, 'config.yaml');
  const defaultConfig: WorkspaceConfig = {
    name: WORKSPACE_ID,
    description: 'Claude Code workspace',
    model: CLAUDE_MODEL,
    version: '1.0.0',
  };

  if (!existsSync(configFile)) {
    // Try config.json
    const jsonFile = join(CONFIG_PATH, 'config.json');
    if (existsSync(jsonFile)) {
      try {
        return { ...defaultConfig, ...JSON.parse(readFileSync(jsonFile, 'utf-8')) };
      } catch {}
    }
    return defaultConfig;
  }

  // Simple YAML parsing for key: value pairs
  try {
    const yaml = readFileSync(configFile, 'utf-8');
    const parsed: Record<string, string> = {};
    for (const line of yaml.split('\n')) {
      const match = line.match(/^(\w+):\s*(.+)/);
      if (match) parsed[match[1]] = match[2].trim().replace(/^["']|["']$/g, '');
    }
    return {
      name: parsed.name || defaultConfig.name,
      description: parsed.description || defaultConfig.description,
      model: parsed.model || defaultConfig.model,
      version: parsed.version || defaultConfig.version,
    };
  } catch {
    return defaultConfig;
  }
}

// Load system prompt if it exists
function loadSystemPrompt(): string | null {
  const promptFile = join(CONFIG_PATH, 'system-prompt.md');
  if (existsSync(promptFile)) {
    return readFileSync(promptFile, 'utf-8');
  }
  return null;
}

// --- Claude Code Invocation ---

async function invokeClaudeCode(message: string, systemPrompt: string | null): Promise<string> {
  return new Promise((resolve, reject) => {
    const args = ['--print', '--dangerously-skip-permissions'];
    if (CLAUDE_MODEL) {
      args.push('--model', CLAUDE_MODEL);
    }
    if (systemPrompt) {
      args.push('--system-prompt', systemPrompt);
    }
    args.push('-p', message);

    const child = spawn('claude', args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      timeout: 300_000, // 5 min timeout
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
    child.stderr.on('data', (d: Buffer) => { stderr += d.toString(); });
    child.on('close', (code) => {
      if (code === 0) {
        resolve(stdout.trim());
      } else {
        reject(new Error(`Claude Code exited with ${code}: ${stderr.slice(0, 500)}`));
      }
    });
    child.on('error', reject);
  });
}

// --- Platform Registration ---

async function register(config: WorkspaceConfig, url: string) {
  const hostname = process.env.HOSTNAME || '127.0.0.1';
  const workspaceUrl = `http://${hostname}:${PORT}`;

  try {
    const resp = await fetch(`${PLATFORM_URL}/registry/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: WORKSPACE_ID,
        url: workspaceUrl,
        agent_card: {
          name: config.name,
          description: config.description,
          version: config.version || '1.0.0',
          url: workspaceUrl,
          runtime: 'claude-code',
          capabilities: { streaming: false, pushNotifications: false },
          skills: [],
        },
      }),
    });
    console.log(`Registered with platform: ${resp.status}`);
  } catch (e: any) {
    console.error(`Warning: failed to register: ${e.message}`);
  }
}

// --- Heartbeat ---

let currentTask = '';

function startHeartbeat() {
  setInterval(async () => {
    try {
      const body: any = { id: WORKSPACE_ID, active_tasks: currentTask ? 1 : 0 };
      if (currentTask) body.current_task = currentTask;
      await fetch(`${PLATFORM_URL}/registry/heartbeat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch {}
  }, HEARTBEAT_INTERVAL);
}

// --- A2A JSON-RPC Server ---

function parseBody(req: IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk: Buffer) => { body += chunk.toString(); });
    req.on('end', () => {
      try { resolve(JSON.parse(body)); } catch (e) { reject(e); }
    });
    req.on('error', reject);
  });
}

function jsonRpcResponse(id: any, result: any): string {
  return JSON.stringify({ jsonrpc: '2.0', id, result });
}

function jsonRpcError(id: any, code: number, message: string): string {
  return JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } });
}

async function handleA2ARequest(req: IncomingMessage, res: ServerResponse, config: WorkspaceConfig, systemPrompt: string | null) {
  if (req.method === 'GET' && req.url === '/.well-known/agent.json') {
    // Agent card discovery
    const hostname = process.env.HOSTNAME || '127.0.0.1';
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      name: config.name,
      description: config.description,
      version: config.version || '1.0.0',
      url: `http://${hostname}:${PORT}`,
      runtime: 'claude-code',
      capabilities: { streaming: false, pushNotifications: false },
      skills: [],
      defaultInputModes: ['text/plain'],
      defaultOutputModes: ['text/plain'],
    }));
    return;
  }

  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', runtime: 'claude-code' }));
    return;
  }

  if (req.method !== 'POST') {
    res.writeHead(405);
    res.end('Method Not Allowed');
    return;
  }

  let body: any;
  try {
    body = await parseBody(req);
  } catch {
    res.writeHead(400);
    res.end(jsonRpcError(null, -32700, 'Parse error'));
    return;
  }

  const { id, method, params } = body;

  if (method === 'message/send') {
    const message = params?.message?.parts?.map((p: any) => p.text || '').join('\n') || '';
    if (!message) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(jsonRpcError(id, -32602, 'No message text found'));
      return;
    }

    currentTask = message.slice(0, 100);
    console.log(`Task received: ${currentTask}...`);

    // Report activity to platform
    try {
      await fetch(`${PLATFORM_URL}/workspaces/${WORKSPACE_ID}/activity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'a2a_receive',
          summary: `Received: ${message.slice(0, 100)}`,
          detail: message,
        }),
      });
    } catch {}

    try {
      const result = await invokeClaudeCode(message, systemPrompt);
      currentTask = '';

      // Report completion
      try {
        await fetch(`${PLATFORM_URL}/workspaces/${WORKSPACE_ID}/activity`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'task_update',
            summary: `Completed: ${message.slice(0, 60)}`,
            detail: result.slice(0, 500),
          }),
        });
      } catch {}

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(jsonRpcResponse(id, {
        id: `task-${Date.now()}`,
        status: { state: 'completed' },
        artifacts: [{
          parts: [{ type: 'text', text: result }],
        }],
      }));
    } catch (e: any) {
      currentTask = '';
      console.error(`Claude Code error: ${e.message}`);

      // Report error
      try {
        await fetch(`${PLATFORM_URL}/workspaces/${WORKSPACE_ID}/activity`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'error',
            summary: `Failed: ${message.slice(0, 60)}`,
            error_detail: e.message,
          }),
        });
      } catch {}

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(jsonRpcError(id, -32000, e.message));
    }
    return;
  }

  // Unknown method
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(jsonRpcError(id, -32601, `Method not found: ${method}`));
}

// --- Main ---

async function main() {
  const config = loadConfig();
  const systemPrompt = loadSystemPrompt();

  console.log(`Workspace: ${WORKSPACE_ID}`);
  console.log(`Name: ${config.name}`);
  console.log(`Model: ${config.model || CLAUDE_MODEL}`);
  console.log(`System prompt: ${systemPrompt ? `loaded (${systemPrompt.length} chars)` : 'none'}`);

  // Start HTTP server
  const server = createServer((req, res) => {
    handleA2ARequest(req, res, config, systemPrompt).catch((err) => {
      console.error(`Request error: ${err.message}`);
      res.writeHead(500);
      res.end(JSON.stringify({ error: err.message }));
    });
  });

  server.listen(PORT, '0.0.0.0', async () => {
    console.log(`A2A server listening on port ${PORT}`);
    await register(config, `http://0.0.0.0:${PORT}`);
    startHeartbeat();
  });
}

main().catch(console.error);
