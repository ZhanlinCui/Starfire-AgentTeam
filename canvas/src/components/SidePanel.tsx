"use client";

import { useCanvasStore, type PanelTab } from "@/store/canvas";
import { StatusDot } from "./StatusDot";
import { DetailsTab } from "./tabs/DetailsTab";
import { ChatTab } from "./tabs/ChatTab";
import { ConfigTab } from "./tabs/ConfigTab";
import { MemoryTab } from "./tabs/MemoryTab";
import { EventsTab } from "./tabs/EventsTab";

const TABS: { id: PanelTab; label: string }[] = [
  { id: "details", label: "Details" },
  { id: "chat", label: "Chat" },
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
    <div className="fixed top-0 right-0 h-full w-[420px] bg-zinc-900 border-l border-zinc-700 flex flex-col z-50 shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700">
        <div className="flex items-center gap-2 min-w-0">
          <StatusDot status={node.data.status} size="md" />
          <h2 className="text-sm font-semibold text-zinc-100 truncate">
            {node.data.name}
          </h2>
          {node.data.role && (
            <span className="text-xs text-zinc-500 truncate">
              — {node.data.role}
            </span>
          )}
        </div>
        <button
          onClick={() => selectNode(null)}
          className="text-zinc-500 hover:text-zinc-300 text-lg leading-none px-1"
        >
          ✕
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-700">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setPanelTab(tab.id)}
            className={`flex-1 py-2 text-xs font-medium transition-colors ${
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
        {panelTab === "config" && <ConfigTab workspaceId={selectedNodeId} />}
        {panelTab === "memory" && <MemoryTab workspaceId={selectedNodeId} />}
        {panelTab === "events" && <EventsTab workspaceId={selectedNodeId} />}
      </div>
    </div>
  );
}

