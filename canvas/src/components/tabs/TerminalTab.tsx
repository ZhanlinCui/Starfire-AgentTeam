"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  workspaceId: string;
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL?.replace("/ws", "") || "ws://localhost:8080";

export function TerminalTab({ workspaceId }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<unknown>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected" | "error">("disconnected");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let terminal: { dispose: () => void } | null = null;
    let socket: WebSocket | null = null;

    async function init() {
      if (!containerRef.current) return;

      // Dynamic import to avoid SSR issues
      const { Terminal } = await import("xterm");
      const { FitAddon } = await import("@xterm/addon-fit");

      const fitAddon = new FitAddon();
      const term = new Terminal({
        theme: {
          background: "#18181b",
          foreground: "#e4e4e7",
          cursor: "#3b82f6",
          selectionBackground: "#3b82f644",
        },
        fontFamily: "JetBrains Mono, Menlo, Monaco, monospace",
        fontSize: 12,
        cursorBlink: true,
      });

      term.loadAddon(fitAddon);
      term.open(containerRef.current);
      fitAddon.fit();

      terminal = term;
      termRef.current = term;

      // Connect WebSocket to platform terminal proxy
      setStatus("connecting");
      const wsUrl = `${WS_URL}/workspaces/${workspaceId}/terminal`;
      socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.binaryType = "arraybuffer";

      socket.onopen = () => {
        setStatus("connected");
        setErrorMsg(null);
        term.writeln("\x1b[32mConnected to workspace shell\x1b[0m");
        term.writeln("");
        fitAddon.fit();
      };

      socket.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          term.write(new Uint8Array(event.data));
        } else {
          term.write(event.data);
        }
      };

      socket.onclose = () => {
        setStatus("disconnected");
        term.writeln("");
        term.writeln("\x1b[33mSession ended\x1b[0m");
      };

      socket.onerror = () => {
        setStatus("error");
        setErrorMsg("Failed to connect — is the workspace container running?");
      };

      // Send keystrokes to container
      term.onData((data: string) => {
        if (socket?.readyState === WebSocket.OPEN) {
          socket.send(data);
        }
      });

      // Handle resize
      const observer = new ResizeObserver(() => fitAddon.fit());
      observer.observe(containerRef.current);

      return () => observer.disconnect();
    }

    const cleanup = init();

    return () => {
      cleanup?.then?.((fn) => fn?.());
      socket?.close();
      terminal?.dispose();
    };
  }, [workspaceId]);

  const reconnect = () => {
    wsRef.current?.close();
    setStatus("connecting");
    // Re-mount by changing key
    setErrorMsg(null);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Status bar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-zinc-700 bg-zinc-800/50">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            status === "connected" ? "bg-green-500" :
            status === "connecting" ? "bg-yellow-500 animate-pulse" :
            status === "error" ? "bg-red-500" : "bg-zinc-500"
          }`} />
          <span className="text-[10px] text-zinc-400">
            {status === "connected" ? "Shell active" :
             status === "connecting" ? "Connecting..." :
             status === "error" ? "Connection failed" : "Disconnected"}
          </span>
        </div>
        {(status === "disconnected" || status === "error") && (
          <button
            onClick={reconnect}
            className="text-[10px] text-blue-400 hover:text-blue-300"
          >
            Reconnect
          </button>
        )}
      </div>

      {/* Error message */}
      {errorMsg && (
        <div className="mx-3 mt-2 px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
          {errorMsg}
        </div>
      )}

      {/* Terminal */}
      <div ref={containerRef} className="flex-1 p-1" />
    </div>
  );
}
