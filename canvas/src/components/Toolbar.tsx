"use client";

import { useCanvasStore } from "@/store/canvas";

export function Toolbar() {
  const nodes = useCanvasStore((s) => s.nodes);

  const rootNodes = nodes.filter((n) => !n.data.parentId);
  const childNodes = nodes.filter((n) => !!n.data.parentId);
  const counts = {
    total: nodes.length,
    roots: rootNodes.length,
    children: childNodes.length,
    online: nodes.filter((n) => n.data.status === "online").length,
    offline: nodes.filter((n) => n.data.status === "offline").length,
    failed: nodes.filter((n) => n.data.status === "failed").length,
    provisioning: nodes.filter((n) => n.data.status === "provisioning").length,
  };

  return (
    <div className="fixed top-3 left-1/2 -translate-x-1/2 z-20 flex items-center gap-3 bg-zinc-900/80 backdrop-blur-md border border-zinc-800/60 rounded-xl px-4 py-2 shadow-xl shadow-black/20">
      {/* Logo / Title */}
      <div className="flex items-center gap-2 pr-3 border-r border-zinc-800/60">
        <div className="w-5 h-5 rounded-md bg-gradient-to-br from-blue-500 to-violet-500 flex items-center justify-center">
          <span className="text-[9px] font-bold text-white">S</span>
        </div>
        <span className="text-[11px] font-semibold text-zinc-300 tracking-wide">Starfire</span>
      </div>

      {/* Status counts */}
      <div className="flex items-center gap-2.5">
        <StatusPill color="bg-emerald-400" count={counts.online} label="online" />
        {counts.offline > 0 && (
          <StatusPill color="bg-zinc-500" count={counts.offline} label="offline" />
        )}
        {counts.provisioning > 0 && (
          <StatusPill color="bg-sky-400 animate-pulse" count={counts.provisioning} label="starting" />
        )}
        {counts.failed > 0 && (
          <StatusPill color="bg-red-400" count={counts.failed} label="failed" />
        )}
      </div>

      {/* Total */}
      <div className="pl-3 border-l border-zinc-800/60">
        <span className="text-[10px] text-zinc-500">
          {counts.roots} workspace{counts.roots !== 1 ? "s" : ""}
          {counts.children > 0 && <span className="text-zinc-600"> + {counts.children} sub</span>}
        </span>
      </div>

      {/* Search shortcut */}
      <button
        onClick={() => useCanvasStore.getState().setSearchOpen(true)}
        className="flex items-center gap-1.5 px-2.5 py-1 bg-zinc-800/50 hover:bg-zinc-700/50 border border-zinc-700/40 rounded-lg transition-colors"
      >
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className="text-zinc-500">
          <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M11 11l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <span className="text-[10px] text-zinc-500">Search</span>
        <kbd className="text-[8px] text-zinc-600 bg-zinc-900/60 px-1 py-0.5 rounded border border-zinc-700/30">⌘K</kbd>
      </button>
    </div>
  );
}

function StatusPill({ color, count, label }: { color: string; count: number; label: string }) {
  return (
    <div className="flex items-center gap-1.5" title={`${count} ${label}`}>
      <div className={`w-1.5 h-1.5 rounded-full ${color}`} />
      <span className="text-[10px] text-zinc-400 tabular-nums">{count}</span>
    </div>
  );
}
