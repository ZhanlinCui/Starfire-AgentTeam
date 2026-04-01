import { useCanvasStore } from "./canvas";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8080/ws";

export interface WSMessage {
  event: string;
  workspace_id: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

class ReconnectingSocket {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private url: string;

  constructor(url: string) {
    this.url = url;
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log("WebSocket connected");
      this.attempt = 0;
      this.rehydrate();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        useCanvasStore.getState().applyEvent(msg);
      } catch (e) {
        console.error("WebSocket message parse error:", e);
      }
    };

    this.ws.onclose = () => {
      console.log("WebSocket disconnected, reconnecting...");
      const delay = Math.min(1000 * 2 ** this.attempt, 30000);
      this.attempt++;
      setTimeout(() => this.connect(), delay);
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
  }

  private async rehydrate() {
    try {
      const { api } = await import("@/lib/api");
      const workspaces = await api.get<WorkspaceData[]>("/workspaces");
      useCanvasStore.getState().hydrate(workspaces);
    } catch (e) {
      console.error("Rehydration failed:", e);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export interface WorkspaceData {
  id: string;
  name: string;
  role: string;
  tier: number;
  status: string;
  agent_card: Record<string, unknown> | null;
  url: string;
  parent_id: string | null;
  active_tasks: number;
  last_error_rate: number;
  last_sample_error: string;
  uptime_seconds: number;
  x: number;
  y: number;
  collapsed: boolean;
}

let socket: ReconnectingSocket | null = null;

export function connectSocket() {
  if (!socket) {
    socket = new ReconnectingSocket(WS_URL);
  }
  socket.connect();
}

export function disconnectSocket() {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}
