"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import type { WorkspaceNodeData } from "@/store/canvas";

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
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions(workspaceId));
  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const loaded = loadSessions(workspaceId);
    return loaded.length > 0 ? loaded[loaded.length - 1].id : "";
  });
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || !agentReachable || sending) return;

    setInput("");
    addMessage(createMessage("user", text));
    setSending(true);
    setError(null);

    try {
      const res = await api.post<{
        result?: Record<string, unknown>;
        error?: { code: number; message: string };
      }>(`/workspaces/${workspaceId}/a2a`, {
        method: "message/send",
        params: {
          message: {
            role: "user",
            messageId: crypto.randomUUID(),
            parts: [{ kind: "text", text }],
          },
        },
      });

      if (res.error) {
        addMessage(createMessage("system", `Agent error: ${res.error.message}`));
      } else if (res.result) {
        const agentText = extractAgentText(res.result);
        addMessage(createMessage("agent", agentText || "(empty response)"));
      } else {
        addMessage(createMessage("system", "No response from agent"));
      }
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : "Unknown error";
      addMessage(createMessage("system", `Error: ${errMsg}`));
    } finally {
      setSending(false);
    }
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
            <div className="text-center text-zinc-500 text-xs py-8">
              {isOnline
                ? `Send a message to ${data.name}`
                : `${data.name} is ${data.status} — chat unavailable`}
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
                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                <p className="text-[9px] mt-1 opacity-50">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex justify-start">
              <div className="bg-zinc-800 text-zinc-400 rounded-lg px-3 py-2 text-sm">
                <span className="animate-pulse">Thinking...</span>
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
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              disabled={!isOnline || !agentReachable || sending}
              placeholder={
                isOnline ? "Send a message..." : `Agent is ${data.status}`
              }
              className="flex-1 bg-zinc-800 border border-zinc-600 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={!isOnline || !agentReachable || sending || !input.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm text-white disabled:opacity-30 disabled:hover:bg-blue-600 transition-colors"
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
