"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import { useCanvasStore, type WorkspaceNodeData } from "@/store/canvas";
import { WS_URL } from "@/store/socket";

interface Props {
  workspaceId: string;
  data: WorkspaceNodeData;
}

interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  timestamp: string; // ISO string for serialization
}

interface ChatSession {
  id: string;
  name: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

function createMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return { id: crypto.randomUUID(), role, content, timestamp: new Date().toISOString() };
}

// --- LocalStorage persistence ---
function getStorageKey(workspaceId: string) {
  return `starfire-chat-${workspaceId}`;
}

function loadSessions(workspaceId: string): ChatSession[] {
  try {
    const raw = localStorage.getItem(getStorageKey(workspaceId));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveSessions(workspaceId: string, sessions: ChatSession[]) {
  try {
    localStorage.setItem(getStorageKey(workspaceId), JSON.stringify(sessions));
  } catch {
    // localStorage full — silently fail
  }
}

export function ChatTab({ workspaceId, data }: Props) {
  const [initData] = useState(() => {
    const s = loadSessions(workspaceId);
    return { sessions: s, activeId: s.length > 0 ? s[s.length - 1].id : "" };
  });
  const [sessions, setSessions] = useState<ChatSession[]>(initData.sessions);
  const [activeSessionId, setActiveSessionId] = useState<string>(initData.activeId);
  const [input, setInput] = useState("");
  // Resume processing indicator if agent has an active task (survives page refresh)
  const [sending, setSending] = useState(!!data.currentTask);
  const [thinkingElapsed, setThinkingElapsed] = useState(0);
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const cleanupRef = useRef<(() => void) | undefined>(undefined);
  const currentTaskRef = useRef(data.currentTask);
  const sendingFromAPIRef = useRef(false); // tracks whether WE initiated the send
  const [agentReachable, setAgentReachable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId) || null,
    [sessions, activeSessionId]
  );
  const messages = activeSession?.messages || [];

  // Persist sessions to localStorage on every change
  useEffect(() => {
    saveSessions(workspaceId, sessions);
  }, [workspaceId, sessions]);

  // Reload sessions when workspace changes
  useEffect(() => {
    const loaded = loadSessions(workspaceId);
    setSessions(loaded);
    setActiveSessionId(loaded.length > 0 ? loaded[loaded.length - 1].id : "");
  }, [workspaceId]);

  const checkAgent = useCallback(async () => {
    try {
      const res = await api.get<{ url: string; status: string }>(
        `/registry/discover/${workspaceId}`
      );
      setAgentReachable(!!res.url);
      setError(null);
    } catch {
      setAgentReachable(false);
      setError(
        data.status === "offline" ? "Agent is offline" : "Agent not available"
      );
    }
  }, [workspaceId, data.status]);

  useEffect(() => {
    checkAgent();
  }, [checkAgent]);

  // Keep currentTaskRef in sync
  useEffect(() => {
    currentTaskRef.current = data.currentTask;
  }, [data.currentTask]);

  // Clean up poll timer on unmount
  useEffect(() => () => cleanupRef.current?.(), []);

  // On page load/refresh: if agent has an active task, start polling for the response.
  useEffect(() => {
    if (!sending || sendingFromAPIRef.current) return;
    const lastMsgTime = messages.length > 0
      ? messages[messages.length - 1].timestamp
      : new Date(Date.now() - 600_000).toISOString();
    const pollTimer = pollForResponse(lastMsgTime);
    cleanupRef.current = () => clearInterval(pollTimer);
    return () => cleanupRef.current?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Resolve workspace ID → name for activity display
  const resolveWorkspaceName = useCallback((id: string) => {
    const nodes = useCanvasStore.getState().nodes;
    const node = nodes.find((n) => n.id === id);
    return (node?.data as WorkspaceNodeData)?.name || id.slice(0, 8);
  }, []);

  // Elapsed timer while sending
  useEffect(() => {
    if (!sending) {
      setThinkingElapsed(0);
      return;
    }
    const startTime = Date.now();
    const timer = setInterval(() => {
      setThinkingElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [sending]);

  // Live activity feed via WebSocket — listen for ACTIVITY_LOGGED events while sending
  useEffect(() => {
    if (!sending) {
      setActivityLog([]);
      return;
    }
    setActivityLog(["Processing with Claude..."]);

    const ws = new WebSocket(WS_URL);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === "ACTIVITY_LOGGED") {
          const p = msg.payload || {};
          const type = p.activity_type as string;
          const method = (p.method as string) || "";
          const status = (p.status as string) || "";
          const targetId = (p.target_id as string) || "";
          const durationMs = p.duration_ms as number | undefined;

          let line = "";
          if (type === "a2a_receive" && method === "message/send") {
            const targetName = resolveWorkspaceName(targetId || msg.workspace_id);
            if (status === "ok" && durationMs) {
              const sec = Math.round(durationMs / 1000);
              line = `← ${targetName} responded (${sec}s)`;
            } else if (status === "error") {
              line = `⚠ ${targetName} error`;
            }
          } else if (type === "a2a_send") {
            const targetName = resolveWorkspaceName(targetId);
            line = `→ Delegating to ${targetName}...`;
          } else if (type === "task_update") {
            const summary = (p.summary as string) || "";
            if (summary) line = `⟳ ${summary}`;
          } else if (type === "agent_log") {
            const summary = (p.summary as string) || "";
            if (summary) line = summary.slice(0, 80);
          }

          if (line) {
            setActivityLog((prev) => [...prev.slice(-8), line]); // Keep last 9 entries
          }
        } else if (msg.event === "TASK_UPDATED" && msg.workspace_id === workspaceId) {
          const task = (msg.payload?.current_task as string) || "";
          if (task) {
            setActivityLog((prev) => [...prev.slice(-8), `⟳ ${task}`]);
          }
        }
      } catch { /* ignore parse errors */ }
    };

    return () => {
      ws.close();
    };
  }, [sending, workspaceId, resolveWorkspaceName]);

  const createNewSession = useCallback(() => {
    const session: ChatSession = {
      id: crypto.randomUUID(),
      name: `Session ${sessions.length + 1}`,
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setSessions((prev) => [...prev, session]);
    setActiveSessionId(session.id);
  }, [sessions.length]);

  // Auto-create first session if none exist
  useEffect(() => {
    if (sessions.length === 0) {
      createNewSession();
    }
  }, [sessions.length, createNewSession]);

  const addMessage = useCallback(
    (msg: ChatMessage) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, messages: [...s.messages, msg], updatedAt: new Date().toISOString() }
            : s
        )
      );
    },
    [activeSessionId]
  );

  // Poll activity log for agent response — survives page refresh, tab switches, etc.
  const pollForResponse = useCallback(
    (sentAfter: string) => {
      const pollInterval = setInterval(async () => {
        try {
          const activities = await api.get<Array<{
            activity_type: string;
            status: string;
            created_at: string;
            response_body: Record<string, unknown> | null;
            error_detail: string | null;
          }>>(`/workspaces/${workspaceId}/activity?type=a2a_receive&limit=3`);

          // Find a response that came after we sent the message
          for (const a of activities) {
            if (a.created_at <= sentAfter) continue;
            if (!a.response_body) continue;

            // Found it — extract text
            const text = extractResponseText(a.response_body);
            if (!text) continue;

            clearInterval(pollInterval);
            if (a.status === "error" || text.toLowerCase().startsWith("agent error")) {
              addMessage(createMessage("system", text));
            } else {
              addMessage(createMessage("agent", text));
            }
            setSending(false);
            sendingFromAPIRef.current = false;
            return;
          }
        } catch {
          // Poll failed — keep trying
        }

        // Also check if agent stopped working (no more current_task)
        // but only after giving it time to start (30s grace period)
        const elapsed = (Date.now() - new Date(sentAfter).getTime()) / 1000;
        if (elapsed > 30 && !currentTaskRef.current) {
          // Agent finished but we didn't find a response — check one more time
          try {
            const activities = await api.get<Array<{
              activity_type: string;
              created_at: string;
              response_body: Record<string, unknown> | null;
            }>>(`/workspaces/${workspaceId}/activity?type=a2a_receive&limit=1`);
            if (activities[0]?.created_at > sentAfter && activities[0]?.response_body) {
              const text = extractResponseText(activities[0].response_body);
              if (text) {
                clearInterval(pollInterval);
                addMessage(createMessage("agent", text));
                setSending(false);
                sendingFromAPIRef.current = false;
                return;
              }
            }
          } catch { /* ignore */ }
        }
      }, 3000);

      return pollInterval;
    },
    [workspaceId, addMessage]
  );

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || !agentReachable || sending) return;

    setInput("");
    addMessage(createMessage("user", text));
    setSending(true);
    sendingFromAPIRef.current = true;
    setError(null);

    const sentAt = new Date().toISOString();

    // Clean up any previous poll
    cleanupRef.current?.();

    // Fire the A2A request — don't wait for the response.
    // The poll loop picks up the result from the activity log.
    api.post(`/workspaces/${workspaceId}/a2a`, {
      method: "message/send",
      params: {
        message: {
          role: "user",
          messageId: crypto.randomUUID(),
          parts: [{ kind: "text", text }],
        },
      },
    }).catch(() => {}); // Ignore — we poll for the result instead

    // Start polling for the response
    const pollTimer = pollForResponse(sentAt);
    cleanupRef.current = () => clearInterval(pollTimer);
  };

  const deleteSession = (sessionId: string) => {
    setSessions((prev) => {
      const filtered = prev.filter((s) => s.id !== sessionId);
      if (sessionId === activeSessionId && filtered.length > 0) {
        setActiveSessionId(filtered[filtered.length - 1].id);
      }
      return filtered;
    });
  };

  const isOnline = data.status === "online" || data.status === "degraded";

  return (
    <div className="flex h-full">
      {/* Session sidebar */}
      {sidebarOpen && (
        <div className="w-48 border-r border-zinc-700 flex flex-col bg-zinc-900/50">
          <div className="p-2 border-b border-zinc-800">
            <button
              onClick={createNewSession}
              className="w-full text-[10px] px-2 py-1.5 bg-blue-600/20 border border-blue-500/30 text-blue-300 rounded hover:bg-blue-600/30 transition-colors"
            >
              + New Session
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {sessions.map((s) => (
              <div
                key={s.id}
                onClick={() => setActiveSessionId(s.id)}
                className={`px-2 py-1.5 cursor-pointer border-b border-zinc-800/50 group flex items-center justify-between ${
                  s.id === activeSessionId
                    ? "bg-blue-950/30 border-l-2 border-l-blue-500"
                    : "hover:bg-zinc-800/30"
                }`}
              >
                <div className="min-w-0">
                  <div className="text-[10px] text-zinc-300 truncate">{s.name}</div>
                  <div className="text-[8px] text-zinc-600">
                    {s.messages.length} msg · {new Date(s.updatedAt).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(s.id);
                  }}
                  className="text-zinc-600 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chat area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Chat header */}
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-zinc-800/50">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
            title={sidebarOpen ? "Hide sessions" : "Show sessions"}
          >
            {sidebarOpen ? "◀" : "▶"} Sessions ({sessions.length})
          </button>
          {activeSession && (
            <span className="text-[9px] text-zinc-600 truncate ml-2">
              {activeSession.name} · {messages.length} messages
            </span>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-center py-8">
              {isOnline && agentReachable ? (
                <div className="text-zinc-500 text-xs">Send a message to {data.name}</div>
              ) : isOnline && !agentReachable ? (
                <div>
                  <div className="text-amber-400 text-xs">{data.name} is registered but not responding</div>
                  <div className="text-zinc-600 text-[10px] mt-1">The agent container may not be running. Try restarting.</div>
                </div>
              ) : (
                <div className="text-zinc-500 text-xs">{data.name} is {data.status} — chat unavailable</div>
              )}
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : msg.role === "system"
                    ? "bg-red-900/50 text-red-300 border border-red-800"
                    : "bg-zinc-800 text-zinc-200"
                }`}
              >
                {msg.role === "agent" ? (
                  <div className="prose prose-sm prose-invert max-w-none break-words [&>p]:my-1 [&>ul]:my-1 [&>ol]:my-1 [&>li]:my-0.5 [&>h1]:text-base [&>h2]:text-sm [&>h3]:text-sm [&>pre]:bg-zinc-900 [&>pre]:text-xs [&>code]:text-xs [&>code]:bg-zinc-900/50 [&>code]:px-1 [&>code]:rounded">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                )}
                <p className="text-[9px] mt-1 opacity-50">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex justify-start">
              <div className="bg-zinc-800 text-zinc-300 rounded-lg px-3 py-2.5 text-sm max-w-[85%] border border-zinc-700/50">
                <div className="flex items-center gap-2 mb-1.5">
                  <div className="flex gap-0.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                    <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                    <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <span className="text-[10px] text-zinc-500">
                    {thinkingElapsed > 0 ? `${thinkingElapsed}s` : "..."}
                  </span>
                </div>
                <div className="space-y-0.5">
                  {activityLog.map((line, i) => (
                    <div
                      key={`${i}-${line}`}
                      className={`text-[11px] ${
                        i === activityLog.length - 1
                          ? "text-zinc-300"
                          : "text-zinc-500"
                      } ${line.startsWith("←") ? "text-green-400/80" : ""} ${
                        line.startsWith("→") ? "text-blue-400/80" : ""
                      } ${line.startsWith("⚠") ? "text-red-400/80" : ""}`}
                    >
                      {line}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Error banner */}
        {error && (
          <div className="mx-4 mb-2 px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
            {error}
            <button onClick={checkAgent} className="ml-2 underline hover:text-red-300">
              Retry
            </button>
          </div>
        )}

        {/* Input */}
        <div className="p-4 border-t border-zinc-700">
          <div className="flex gap-2 items-end">
            <textarea
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                // Auto-resize: reset height then set to scrollHeight
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              disabled={!isOnline || !agentReachable || sending}
              placeholder={
                !isOnline ? `Agent is ${data.status}` :
                !agentReachable ? "Agent not responding — try restarting" :
                "Send a message... (Shift+Enter for new line)"
              }
              rows={1}
              className="flex-1 bg-zinc-800 border border-zinc-600 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 resize-none overflow-y-auto"
              style={{ maxHeight: "200px" }}
            />
            <button
              onClick={sendMessage}
              disabled={!isOnline || !agentReachable || sending || !input.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm text-white disabled:opacity-30 disabled:hover:bg-blue-600 transition-colors shrink-0"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function extractAgentText(task: Record<string, unknown>): string {
  try {
    const directTexts = extractTextsFromParts(task.parts);
    if (directTexts) return directTexts;

    const artifacts = task.artifacts as Array<Record<string, unknown>> | undefined;
    if (artifacts && artifacts.length > 0) {
      const texts = extractTextsFromParts(artifacts[0].parts);
      if (texts) return texts;
    }

    const status = task.status as Record<string, unknown> | undefined;
    if (status?.message) {
      const msg = status.message as Record<string, unknown>;
      const texts = extractTextsFromParts(msg.parts);
      if (texts) return texts;
    }

    if (typeof task === "string") return task;
    return "(Could not extract response text)";
  } catch {
    return "(Failed to parse response)";
  }
}

function extractTextsFromParts(parts: unknown): string | null {
  if (!Array.isArray(parts)) return null;
  const texts = parts
    .filter((p: Record<string, unknown>) => p.type === "text" || p.kind === "text")
    .map((p: Record<string, unknown>) => String(p.text || ""))
    .filter(Boolean);
  return texts.length > 0 ? texts.join("\n") : null;
}

/** Extract text from an activity log response_body (multiple possible formats) */
function extractResponseText(body: Record<string, unknown>): string {
  try {
    // {result: "text"} — from MCP server delegation logs
    if (typeof body.result === "string") return body.result;

    // A2A JSON-RPC response: {result: {parts: [{kind: "text", text: "..."}]}}
    const result = body.result as Record<string, unknown> | undefined;
    if (result) {
      const parts = (result.parts || []) as Array<Record<string, unknown>>;
      for (const p of parts) {
        const t = (p.text as string) || "";
        if (t) return t;
        const root = p.root as Record<string, unknown> | undefined;
        if (root?.text) return root.text as string;
      }
    }

    // {task: "text"} — request body format, shouldn't be in response but handle it
    if (typeof body.task === "string") return body.task;
  } catch { /* ignore */ }
  return "";
}
