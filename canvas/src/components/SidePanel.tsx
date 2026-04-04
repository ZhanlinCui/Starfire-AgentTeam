"use client";

import { useCanvasStore, type PanelTab } from "@/store/canvas";
import { StatusDot } from "./StatusDot";
import { DetailsTab } from "./tabs/DetailsTab";
import { ChatTab } from "./tabs/ChatTab";
import { ConfigTab } from "./tabs/ConfigTab";
import { SettingsTab } from "./tabs/SettingsTab";
import { TerminalTab } from "./tabs/TerminalTab";
import { MemoryTab } from "./tabs/MemoryTab";
import { EventsTab } from "./tabs/EventsTab";

const TABS: { id: PanelTab; label: string; icon: string }[] = [
  { id: "details", label: "Details", icon: "◉" },
  { id: "chat", label: "Chat", icon: "◈" },
  { id: "settings", label: "Settings", icon: "⚙" },
  { id: "terminal", label: "Terminal", icon: "▸" },
  { id: "config", label: "Config", icon: "{}" },
  { id: "memory", label: "Memory", icon: "◇" },
  { id: "events", label: "Events", icon: "◊" },
];

export function SidePanel() {
  const selectedNodeId = useCanvasStore((s) => s.selectedNodeId);
  const panelTab = useCanvasStore((s) => s.panelTab);
  const setPanelTab = useCanvasStore((s) => s.setPanelTab);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const node = useCanvasStore((s) =>
    s.nodes.find((n) => n.id === s.selectedNodeId)
  );

  if (!selectedNodeId || !node) return null;

  const isOnline = node.data.status === "online";

  return (
    <div className="fixed top-0 right-0 h-full w-[480px] bg-zinc-950/95 backdrop-blur-xl border-l border-zinc-800/50 flex flex-col z-50 shadow-2xl shadow-black/50 animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800/40 bg-zinc-900/30">
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative">
            <StatusDot status={node.data.status} size="md" />
          </div>
          <div className="min-w-0">
            <h2 className="text-[14px] font-semibold text-zinc-100 truncate leading-tight">
              {node.data.name}
            </h2>
            <div className="flex items-center gap-2 mt-0.5">
              {node.data.role && (
                <span className="text-[10px] text-zinc-500 truncate">
                  {node.data.role}
                </span>
              )}
              <span className={`text-[9px] px-1.5 py-0.5 rounded-md font-mono ${
                isOnline ? "text-emerald-400 bg-emerald-950/30" : "text-zinc-500 bg-zinc-800/50"
              }`}>
                T{node.data.tier}
              </span>
            </div>
          </div>
        </div>
        <button
          onClick={() => selectNode(null)}
          className="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800/60 transition-colors"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800/40 overflow-x-auto bg-zinc-900/20 px-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setPanelTab(tab.id)}
            className={`shrink-0 px-3 py-2.5 text-[10px] font-medium tracking-wide transition-all rounded-t-lg mx-0.5 ${
              panelTab === tab.id
                ? "text-zinc-100 bg-zinc-800/40 border-b-2 border-blue-500"
                : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/20"
            }`}
          >
            <span className="mr-1 opacity-50">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto">
        {panelTab === "details" && <DetailsTab workspaceId={selectedNodeId} data={node.data} />}
        {panelTab === "chat" && <ChatTab workspaceId={selectedNodeId} data={node.data} />}
        {panelTab === "settings" && <SettingsTab workspaceId={selectedNodeId} />}
        {panelTab === "terminal" && <TerminalTab workspaceId={selectedNodeId} />}
        {panelTab === "config" && <ConfigTab workspaceId={selectedNodeId} />}
        {panelTab === "memory" && <MemoryTab workspaceId={selectedNodeId} />}
        {panelTab === "events" && <EventsTab workspaceId={selectedNodeId} />}
      </div>

      {/* Footer — workspace ID */}
      <div className="px-5 py-2 border-t border-zinc-800/40 bg-zinc-900/20">
        <span className="text-[9px] font-mono text-zinc-600 select-all">
          {selectedNodeId}
        </span>
      </div>
    </div>
  );
}
