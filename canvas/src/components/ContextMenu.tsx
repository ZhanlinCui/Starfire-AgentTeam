"use client";

import { useCallback, useEffect, useRef } from "react";
import { useCanvasStore, type WorkspaceNodeData } from "@/store/canvas";
import { api } from "@/lib/api";

interface MenuItem {
  label: string;
  icon: string;
  action: () => void;
  danger?: boolean;
  disabled?: boolean;
  divider?: boolean;
}

export function ContextMenu() {
  const contextMenu = useCanvasStore((s) => s.contextMenu);
  const closeContextMenu = useCanvasStore((s) => s.closeContextMenu);
  const removeNode = useCanvasStore((s) => s.removeNode);
  const updateNodeData = useCanvasStore((s) => s.updateNodeData);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const setPanelTab = useCanvasStore((s) => s.setPanelTab);
  const ref = useRef<HTMLDivElement>(null);

  // Close on click outside or Escape
  useEffect(() => {
    if (!contextMenu) return;
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as HTMLElement)) {
        closeContextMenu();
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeContextMenu();
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [contextMenu, closeContextMenu]);

  const handleExportBundle = useCallback(async () => {
    if (!contextMenu) return;
    try {
      const bundle = await api.get<Record<string, unknown>>(`/bundles/export/${contextMenu.nodeId}`);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(contextMenu.nodeData.name || "workspace").toLowerCase().replace(/\s+/g, "-")}.bundle.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed:", e);
    }
    closeContextMenu();
  }, [contextMenu, closeContextMenu]);

  const handleDuplicate = useCallback(async () => {
    if (!contextMenu) return;
    try {
      const bundle = await api.get<Record<string, unknown>>(`/bundles/export/${contextMenu.nodeId}`);
      await api.post("/bundles/import", bundle);
    } catch (e) {
      console.error("Duplicate failed:", e);
    }
    closeContextMenu();
  }, [contextMenu, closeContextMenu]);

  const handleRestart = useCallback(async () => {
    if (!contextMenu) return;
    try {
      await api.post(`/workspaces/${contextMenu.nodeId}/restart`, {});
      updateNodeData(contextMenu.nodeId, { status: "provisioning" });
    } catch (e) {
      console.error("Restart failed:", e);
    }
    closeContextMenu();
  }, [contextMenu, updateNodeData, closeContextMenu]);

  const handleDelete = useCallback(async () => {
    if (!contextMenu) return;
    try {
      await api.del(`/workspaces/${contextMenu.nodeId}`);
      removeNode(contextMenu.nodeId);
    } catch (e) {
      console.error("Delete failed:", e);
    }
    closeContextMenu();
  }, [contextMenu, removeNode, closeContextMenu]);

  const handleViewDetails = useCallback(() => {
    if (!contextMenu) return;
    selectNode(contextMenu.nodeId);
    setPanelTab("details");
    closeContextMenu();
  }, [contextMenu, selectNode, setPanelTab, closeContextMenu]);

  const handleOpenChat = useCallback(() => {
    if (!contextMenu) return;
    selectNode(contextMenu.nodeId);
    setPanelTab("chat");
    closeContextMenu();
  }, [contextMenu, selectNode, setPanelTab, closeContextMenu]);

  const handleOpenTerminal = useCallback(() => {
    if (!contextMenu) return;
    selectNode(contextMenu.nodeId);
    setPanelTab("terminal");
    closeContextMenu();
  }, [contextMenu, selectNode, setPanelTab, closeContextMenu]);

  const handleExpand = useCallback(async () => {
    if (!contextMenu) return;
    try {
      await api.post(`/workspaces/${contextMenu.nodeId}/expand`, {});
    } catch (e) {
      console.error("Expand failed:", e);
    }
    closeContextMenu();
  }, [contextMenu, closeContextMenu]);

  const handleCollapse = useCallback(async () => {
    if (!contextMenu) return;
    try {
      await api.post(`/workspaces/${contextMenu.nodeId}/collapse`, {});
    } catch (e) {
      console.error("Collapse failed:", e);
    }
    closeContextMenu();
  }, [contextMenu, closeContextMenu]);

  if (!contextMenu) return null;

  const isOfflineOrFailed = contextMenu.nodeData.status === "offline" || contextMenu.nodeData.status === "failed";
  const isOnline = contextMenu.nodeData.status === "online";

  // Check if workspace has children (is a team)
  const store = useCanvasStore.getState();
  const hasChildren = store.nodes.some((n) => n.data.parentId === contextMenu.nodeId);

  const items: MenuItem[] = [
    { label: "Details", icon: "i", action: handleViewDetails },
    { label: "Chat", icon: "💬", action: handleOpenChat, disabled: !isOnline },
    { label: "Terminal", icon: ">_", action: handleOpenTerminal, disabled: !isOnline },
    { label: "", icon: "", action: () => {}, divider: true },
    { label: "Export Bundle", icon: "📦", action: handleExportBundle },
    { label: "Duplicate", icon: "⧉", action: handleDuplicate },
    ...(hasChildren
      ? [{ label: "Collapse Team", icon: "◁", action: handleCollapse }]
      : [{ label: "Expand to Team", icon: "▷", action: handleExpand }]),
    { label: "", icon: "", action: () => {}, divider: true },
    { label: "Restart", icon: "↻", action: handleRestart, disabled: !isOfflineOrFailed },
    { label: "Delete", icon: "✕", action: handleDelete, danger: true },
  ];

  return (
    <div
      ref={ref}
      className="fixed z-[60] min-w-[180px] bg-zinc-900/95 backdrop-blur-md border border-zinc-700/60 rounded-xl shadow-2xl shadow-black/50 py-1.5 overflow-hidden"
      style={{ left: contextMenu.x, top: contextMenu.y }}
    >
      {/* Header */}
      <div className="px-3 py-1.5 border-b border-zinc-800/60 mb-1">
        <div className="text-[11px] font-semibold text-zinc-300 truncate">{contextMenu.nodeData.name}</div>
        <div className="text-[9px] text-zinc-500">{contextMenu.nodeData.status}</div>
      </div>

      {items.map((item, i) => {
        if (item.divider) {
          return <div key={i} className="h-px bg-zinc-800/60 my-1" />;
        }
        return (
          <button
            key={i}
            onClick={item.action}
            disabled={item.disabled}
            className={`w-full px-3 py-1.5 flex items-center gap-2.5 text-left text-[12px] transition-colors disabled:opacity-30 disabled:cursor-not-allowed ${
              item.danger
                ? "text-red-400 hover:bg-red-950/40 hover:text-red-300"
                : "text-zinc-300 hover:bg-zinc-800/60 hover:text-zinc-100"
            }`}
          >
            <span className="w-4 text-center text-[11px] shrink-0 opacity-60">{item.icon}</span>
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
