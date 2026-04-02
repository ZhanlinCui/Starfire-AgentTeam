"use client";

import { useState, useRef, useEffect, useCallback } from "react";
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
  timestamp: Date;
}

function createMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return { id: crypto.randomUUID(), role, content, timestamp: new Date() };
}

export function ChatTab({ workspaceId, data }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [agentReachable, setAgentReachable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

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
        data.status === "offline"
          ? "Agent is offline"
          : "Agent not available"
      );
    }
  }, [workspaceId, data.status]);

  useEffect(() => {
    checkAgent();
  }, [checkAgent]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || !agentReachable || sending) return;

    setInput("");
    setMessages((prev) => [...prev, createMessage("user", text)]);
    setSending(true);
    setError(null);

    try {
      // Proxy A2A message/send through the platform to avoid CORS/network issues
      const res = await api.post<{
        result?: Record<string, unknown>;
        error?: { code: number; message: string };
      }>(
        `/workspaces/${workspaceId}/a2a`,
        {
          method: "message/send",
          params: {
            message: {
              role: "user",
              parts: [{ type: "text", text }],
            },
          },
        }
      );

      // Handle JSON-RPC error response
      if (res.error) {
        setMessages((prev) => [
          ...prev,
          createMessage("system", `Agent error: ${res.error!.message}`),
        ]);
      } else if (res.result) {
        const agentText = extractAgentText(res.result);
        setMessages((prev) => [
          ...prev,
          createMessage("agent", agentText || "(empty response)"),
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          createMessage("system", "No response from agent"),
        ]);
      }
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : "Unknown error";
      setMessages((prev) => [
        ...prev,
        createMessage("system", `Error: ${errMsg}`),
      ]);
    } finally {
      setSending(false);
    }
  };

  const isOnline = data.status === "online" || data.status === "degraded";

  return (
    <div className="flex flex-col h-full">
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
                {msg.timestamp.toLocaleTimeString()}
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
  );
}

function extractAgentText(task: Record<string, unknown>): string {
  // A2A task result has artifacts[] or status.message
  try {
    const artifacts = task.artifacts as Array<Record<string, unknown>> | undefined;
    if (artifacts && artifacts.length > 0) {
      const parts = artifacts[0].parts as Array<Record<string, unknown>> | undefined;
      if (parts) {
        return parts
          .filter((p) => p.type === "text")
          .map((p) => String(p.text || ""))
          .join("\n");
      }
    }

    // Fallback: check status.message
    const status = task.status as Record<string, unknown> | undefined;
    if (status?.message) {
      const msg = status.message as Record<string, unknown>;
      const parts = msg.parts as Array<Record<string, unknown>> | undefined;
      if (parts) {
        return parts
          .filter((p) => p.type === "text")
          .map((p) => String(p.text || ""))
          .join("\n");
      }
    }

    return JSON.stringify(task, null, 2);
  } catch {
    return JSON.stringify(task, null, 2);
  }
}
