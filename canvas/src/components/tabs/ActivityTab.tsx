"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

interface Props {
  workspaceId: string;
}

interface ActivityEntry {
  id: string;
  workspace_id: string;
  activity_type: string;
  source_id: string | null;
  target_id: string | null;
  method: string | null;
  summary: string | null;
  request_body: Record<string, unknown> | null;
  response_body: Record<string, unknown> | null;
  duration_ms: number | null;
  status: string;
  error_detail: string | null;
  created_at: string;
}

type FilterType = "all" | "a2a_receive" | "a2a_send" | "task_update" | "agent_log" | "error";

const FILTERS: { id: FilterType; label: string; icon: string }[] = [
  { id: "all", label: "All", icon: "●" },
  { id: "a2a_receive", label: "A2A In", icon: "↙" },
  { id: "a2a_send", label: "A2A Out", icon: "↗" },
  { id: "task_update", label: "Tasks", icon: "◆" },
  { id: "agent_log", label: "Logs", icon: "▸" },
  { id: "error", label: "Errors", icon: "!" },
];

const TYPE_COLORS: Record<string, { text: string; bg: string; border: string }> = {
  a2a_receive: { text: "text-blue-400", bg: "bg-blue-950/30", border: "border-blue-800/30" },
  a2a_send: { text: "text-cyan-400", bg: "bg-cyan-950/30", border: "border-cyan-800/30" },
  task_update: { text: "text-amber-400", bg: "bg-amber-950/30", border: "border-amber-800/30" },
  agent_log: { text: "text-zinc-400", bg: "bg-zinc-800/30", border: "border-zinc-700/30" },
  error: { text: "text-red-400", bg: "bg-red-950/30", border: "border-red-800/30" },
};

const STATUS_ICONS: Record<string, { icon: string; color: string }> = {
  ok: { icon: "✓", color: "text-emerald-400" },
  error: { icon: "✕", color: "text-red-400" },
  timeout: { icon: "⏱", color: "text-amber-400" },
};

export function ActivityTab({ workspaceId }: Props) {
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterType>("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadActivities = useCallback(async () => {
    try {
      const typeParam = filter !== "all" ? `?type=${filter}` : "";
      const data = await api.get<ActivityEntry[]>(`/workspaces/${workspaceId}/activity${typeParam}`);
      setActivities(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load activity");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, filter]);

  useEffect(() => {
    setLoading(true);
    loadActivities();
  }, [loadActivities]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(loadActivities, 5000);
    return () => clearInterval(interval);
  }, [loadActivities, autoRefresh]);

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="px-3 pt-3 pb-2 border-b border-zinc-800/40">
        <div className="flex items-center gap-1 flex-wrap">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`px-2 py-1 text-[9px] rounded-md font-medium transition-all ${
                filter === f.id
                  ? "bg-zinc-700 text-zinc-100 ring-1 ring-zinc-600"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60"
              }`}
            >
              <span className="mr-0.5 opacity-60">{f.icon}</span> {f.label}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`text-[9px] px-1.5 py-0.5 rounded ${
                autoRefresh ? "text-emerald-400 bg-emerald-950/30" : "text-zinc-500"
              }`}
              title={autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
            >
              {autoRefresh ? "⟳ Live" : "⟳ Paused"}
            </button>
            <button
              onClick={loadActivities}
              className="px-2 py-1 bg-zinc-700 hover:bg-zinc-600 text-[9px] rounded text-zinc-300"
            >
              Refresh
            </button>
          </div>
        </div>
        <div className="mt-1.5 text-[9px] text-zinc-500">
          {activities.length} {filter === "all" ? "activities" : filter.replace("_", " ") + " entries"}
        </div>
      </div>

      {/* Activity list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        {loading && activities.length === 0 && (
          <div className="text-xs text-zinc-500 text-center py-8">Loading activity...</div>
        )}

        {error && (
          <div className="px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
            {error}
          </div>
        )}

        {!loading && !error && activities.length === 0 && (
          <div className="text-center py-8">
            <div className="text-zinc-600 text-xs">No activity recorded yet</div>
            <div className="text-zinc-700 text-[9px] mt-1">
              Activity logs appear when agents communicate or perform tasks
            </div>
          </div>
        )}

        {activities.map((entry) => (
          <ActivityRow
            key={entry.id}
            entry={entry}
            expanded={expanded === entry.id}
            onToggle={() => setExpanded(expanded === entry.id ? null : entry.id)}
          />
        ))}
      </div>
    </div>
  );
}

function ActivityRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: ActivityEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  const typeStyle = TYPE_COLORS[entry.activity_type] || TYPE_COLORS.agent_log;
  const statusStyle = STATUS_ICONS[entry.status] || STATUS_ICONS.ok;
  const isA2A = entry.activity_type.startsWith("a2a_");
  const isError = entry.status === "error";

  return (
    <div
      className={`rounded-lg border transition-colors ${
        isError
          ? "bg-red-950/20 border-red-900/30"
          : "bg-zinc-800/60 border-zinc-700/40"
      }`}
    >
      <button onClick={onToggle} className="w-full text-left px-3 py-2">
        {/* Top row: type badge + method + time */}
        <div className="flex items-center gap-2">
          <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded ${typeStyle.text} ${typeStyle.bg} border ${typeStyle.border}`}>
            {formatType(entry.activity_type)}
          </span>

          {entry.method && (
            <span className="text-[10px] font-mono text-zinc-300 truncate">
              {entry.method}
            </span>
          )}

          <span className={`text-[9px] ml-auto shrink-0 ${statusStyle.color}`}>
            {statusStyle.icon}
          </span>

          {entry.duration_ms != null && (
            <span className="text-[8px] text-zinc-500 font-mono tabular-nums shrink-0">
              {entry.duration_ms}ms
            </span>
          )}

          <span className="text-[8px] text-zinc-600 shrink-0">
            {formatTime(entry.created_at)}
          </span>

          <span className="text-[9px] text-zinc-600">
            {expanded ? "▼" : "▶"}
          </span>
        </div>

        {/* Summary */}
        {entry.summary && (
          <div className="text-[10px] text-zinc-400 mt-1 truncate">
            {entry.summary}
          </div>
        )}

        {/* A2A flow indicator */}
        {isA2A && (entry.source_id || entry.target_id) && (
          <div className="flex items-center gap-1 mt-1">
            {entry.source_id && (
              <span className="text-[8px] font-mono text-cyan-400/60 truncate max-w-[120px]" title={entry.source_id}>
                {entry.source_id.slice(0, 8)}
              </span>
            )}
            <span className="text-[8px] text-zinc-600">→</span>
            {entry.target_id && (
              <span className="text-[8px] font-mono text-blue-400/60 truncate max-w-[120px]" title={entry.target_id}>
                {entry.target_id.slice(0, 8)}
              </span>
            )}
          </div>
        )}

        {/* Error detail */}
        {isError && entry.error_detail && (
          <div className="text-[9px] text-red-400/80 mt-1 truncate">
            {entry.error_detail}
          </div>
        )}
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-zinc-700/30 mt-1 pt-2">
          {entry.source_id && (
            <Detail label="Source" value={entry.source_id} mono />
          )}
          {entry.target_id && (
            <Detail label="Target" value={entry.target_id} mono />
          )}
          {entry.error_detail && (
            <Detail label="Error" value={entry.error_detail} error />
          )}
          {entry.request_body && (
            <JsonBlock label="Request" data={entry.request_body} />
          )}
          {entry.response_body && (
            <JsonBlock label="Response" data={entry.response_body} />
          )}
          <div className="text-[8px] text-zinc-600 font-mono select-all">
            ID: {entry.id}
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ label, value, mono, error: isError }: { label: string; value: string; mono?: boolean; error?: boolean }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-[8px] text-zinc-500 uppercase tracking-wider w-14 shrink-0 pt-0.5">{label}</span>
      <span className={`text-[9px] break-all ${isError ? "text-red-400" : "text-zinc-300"} ${mono ? "font-mono" : ""}`}>
        {value}
      </span>
    </div>
  );
}

function JsonBlock({ label, data }: { label: string; data: Record<string, unknown> }) {
  return (
    <div>
      <div className="text-[8px] text-zinc-500 uppercase tracking-wider mb-1">{label}</div>
      <pre className="text-[9px] text-zinc-300 bg-zinc-900/80 rounded p-2 overflow-x-auto max-h-48 font-mono">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

function formatType(type: string): string {
  switch (type) {
    case "a2a_receive": return "A2A IN";
    case "a2a_send": return "A2A OUT";
    case "task_update": return "TASK";
    case "agent_log": return "LOG";
    case "error": return "ERROR";
    default: return type.toUpperCase();
  }
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();

  if (diff < 60_000) return `${Math.floor(diff / 1000)}s`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
  return d.toLocaleDateString();
}
