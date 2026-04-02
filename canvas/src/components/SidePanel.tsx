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

const TABS: { id: PanelTab; label: string }[] = [
  { id: "details", label: "Details" },
  { id: "chat", label: "Chat" },
  { id: "settings", label: "Settings" },
  { id: "terminal", label: "Terminal" },
  { id: "config", label: "Config" },
  { id: "memory", label: "Memory" },
  { id: "events", label: "Events" },
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

  return (
    <div className="fixed top-0 right-0 h-full w-[480px] bg-zinc-900/95 backdrop-blur-md border-l border-zinc-800/80 flex flex-col z-50 shadow-2xl shadow-black/40">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-zinc-800/60">
        <div className="flex items-center gap-2.5 min-w-0">
          <StatusDot status={node.data.status} size="md" />
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-zinc-100 truncate leading-tight">
              {node.data.name}
            </h2>
            {node.data.role && (
              <span className="text-[11px] text-zinc-500 truncate block">
                {node.data.role}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={() => selectNode(null)}
          className="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800/60 overflow-x-auto bg-zinc-900/50">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setPanelTab(tab.id)}
            className={`shrink-0 px-3.5 py-2.5 text-[11px] font-medium tracking-wide transition-colors ${
              panelTab === tab.id
                ? "text-zinc-100 border-b-2 border-blue-500"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
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
    </div>
  );
}
