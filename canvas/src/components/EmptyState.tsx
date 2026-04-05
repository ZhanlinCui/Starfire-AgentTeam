"use client";

export function EmptyState() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-[1]">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-blue-500/20 flex items-center justify-center">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="3" y="3" width="10" height="10" rx="2" stroke="#6366f1" strokeWidth="1.5" opacity="0.6" />
            <rect x="15" y="3" width="10" height="10" rx="2" stroke="#6366f1" strokeWidth="1.5" opacity="0.6" />
            <rect x="9" y="15" width="10" height="10" rx="2" stroke="#6366f1" strokeWidth="1.5" opacity="0.6" />
            <path d="M8 13v2M20 13v4M14 13v2" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-zinc-300 mb-2">Build Your AI Organization</h2>
        <p className="text-sm text-zinc-500 mb-6 leading-relaxed">
          Create workspace nodes, assign agents, and connect them into teams.
          Each workspace is a role with a swappable AI inside.
        </p>
        <div className="flex flex-col gap-2 text-xs text-zinc-600">
          <div className="flex items-center justify-center gap-2">
            <kbd className="px-1.5 py-0.5 bg-zinc-800/60 border border-zinc-700/40 rounded text-zinc-500">Click</kbd>
            <span>the template palette (top-left) to deploy an agent</span>
          </div>
          <div className="flex items-center justify-center gap-2">
            <kbd className="px-1.5 py-0.5 bg-zinc-800/60 border border-zinc-700/40 rounded text-zinc-500">⌘K</kbd>
            <span>to search workspaces</span>
          </div>
          <div className="flex items-center justify-center gap-2">
            <kbd className="px-1.5 py-0.5 bg-zinc-800/60 border border-zinc-700/40 rounded text-zinc-500">Right-click</kbd>
            <span>a node for export, duplicate, expand</span>
          </div>
          <div className="flex items-center justify-center gap-2">
            <kbd className="px-1.5 py-0.5 bg-zinc-800/60 border border-zinc-700/40 rounded text-zinc-500">Drag</kbd>
            <span>a node onto another to nest it</span>
          </div>
        </div>
      </div>
    </div>
  );
}
