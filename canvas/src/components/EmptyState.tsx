"use client";

export function EmptyState() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-[1]">
      <div className="relative max-w-lg rounded-3xl border border-zinc-800/70 bg-zinc-950/70 px-6 py-7 text-center shadow-2xl shadow-black/30">
        <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-blue-500/50 to-transparent" />
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-sky-500/20 via-blue-500/20 to-violet-500/20 border border-blue-500/20 flex items-center justify-center">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="3" y="3" width="10" height="10" rx="2" stroke="#60a5fa" strokeWidth="1.5" opacity="0.65" />
            <rect x="15" y="3" width="10" height="10" rx="2" stroke="#60a5fa" strokeWidth="1.5" opacity="0.65" />
            <rect x="9" y="15" width="10" height="10" rx="2" stroke="#60a5fa" strokeWidth="1.5" opacity="0.65" />
            <path d="M8 13v2M20 13v4M14 13v2" stroke="#60a5fa" strokeWidth="1.5" strokeLinecap="round" opacity="0.45" />
          </svg>
        </div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-sky-400/80 mb-3">Start here</p>
        <h2 className="text-xl font-semibold text-zinc-100 mb-2">Build your first workspace team</h2>
        <p className="text-sm text-zinc-500 mb-6 leading-relaxed">
          Starfire starts fastest when you follow one clear path: deploy a template, open it, then chat or expand it into a team.
        </p>
        <div className="grid gap-3 text-left">
          <Step
            index="1"
            title="Open the template palette"
            body="Use the top-left palette to deploy a workspace template and bring in your first role."
            shortcut="Template palette"
          />
          <Step
            index="2"
            title="Search or inspect workspaces"
            body="Press ⌘K to search existing workspaces, or right-click a node to open its actions."
            shortcut="⌘K / right-click"
          />
          <Step
            index="3"
            title="Nest workspaces into teams"
            body="Drag one workspace onto another to create a parent-child team relationship."
            shortcut="Drag to nest"
          />
        </div>
      </div>
    </div>
  );
}

function Step({ index, title, body, shortcut }: { index: string; title: string; body: string; shortcut: string }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-zinc-800/60 bg-zinc-900/40 px-4 py-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-sky-500/30 bg-sky-500/10 text-[10px] font-semibold text-sky-300">
        {index}
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-zinc-100">{title}</h3>
          <span className="rounded-full border border-zinc-700/60 bg-zinc-950/60 px-2 py-0.5 text-[9px] uppercase tracking-[0.2em] text-zinc-500">
            {shortcut}
          </span>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-zinc-500">{body}</p>
      </div>
    </div>
  );
}
