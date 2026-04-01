"use client";

import { useEffect } from "react";
import { Canvas } from "@/components/Canvas";
import { connectSocket, disconnectSocket } from "@/store/socket";
import { useCanvasStore } from "@/store/canvas";
import { api } from "@/lib/api";
import type { WorkspaceData } from "@/store/socket";

export default function Home() {
  useEffect(() => {
    // Connect WebSocket first to avoid missing events
    connectSocket();

    // Then hydrate from HTTP
    api
      .get<WorkspaceData[]>("/workspaces")
      .then((workspaces) => {
        useCanvasStore.getState().hydrate(workspaces);
      })
      .catch((err) => {
        console.error("Initial hydration failed:", err);
      });

    return () => {
      disconnectSocket();
    };
  }, []);

  return <Canvas />;
}
