"use client";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { useCanvasStore, type WorkspaceNodeData } from "@/store/canvas";

const STATUS_CONFIG: Record<string, { dot: string; glow: string; label: string }> = {
  online: { dot: "bg-emerald-400", glow: "shadow-emerald-400/50", label: "Online" },
  offline: { dot: "bg-zinc-500", glow: "", label: "Offline" },
  degraded: { dot: "bg-amber-400", glow: "shadow-amber-400/50", label: "Degraded" },
  failed: { dot: "bg-red-400", glow: "shadow-red-400/50", label: "Failed" },
  provisioning: { dot: "bg-sky-400 animate-pulse", glow: "shadow-sky-400/50", label: "Starting" },
};

const TIER_CONFIG: Record<number, { label: string; color: string }> = {
  1: { label: "T1", color: "text-zinc-500 bg-zinc-800/80" },
  2: { label: "T2", color: "text-sky-400 bg-sky-950/50" },
  3: { label: "T3", color: "text-violet-400 bg-violet-950/50" },
  4: { label: "T4", color: "text-amber-400 bg-amber-950/50" },
};

export function WorkspaceNode({ id, data }: NodeProps<Node<WorkspaceNodeData>>) {
  const statusCfg = STATUS_CONFIG[data.status] || STATUS_CONFIG.offline;
  const tierCfg = TIER_CONFIG[data.tier] || { label: `T${data.tier}`, color: "text-zinc-500 bg-zinc-800" };
  const selectedNodeId = useCanvasStore((s) => s.selectedNodeId);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const openContextMenu = useCanvasStore((s) => s.openContextMenu);
  const isDragTarget = useCanvasStore((s) => s.dragOverNodeId === id);
  const isSelected = selectedNodeId === id;
  const isOnline = data.status === "online";

  const skills = getSkillNames(data.agentCard as Record<string, unknown> | null);

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        selectNode(isSelected ? null : id);
      }}
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
        openContextMenu({ x: e.clientX, y: e.clientY, nodeId: id, nodeData: data as unknown as import("@/store/canvas").WorkspaceNodeData });
      }}
      className={`
        group relative rounded-xl min-w-[200px] max-w-[260px]
        px-3.5 py-2.5 cursor-pointer
        transition-all duration-200 ease-out
        ${isDragTarget
          ? "bg-emerald-950/40 border-2 border-emerald-400/60 ring-2 ring-emerald-400/20 scale-[1.03]"
          : isSelected
          ? "bg-zinc-900/95 border border-blue-500/70 ring-1 ring-blue-500/30 shadow-lg shadow-blue-500/10"
          : "bg-zinc-900/90 border border-zinc-700/80 hover:border-zinc-500/60 shadow-lg shadow-black/30 hover:shadow-xl hover:shadow-black/40"
        }
        backdrop-blur-sm
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2 !h-2 !bg-zinc-600 !border-zinc-500 !-top-1 hover:!bg-blue-400 transition-colors"
      />

      {/* Header row */}
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <div className={`w-2 h-2 rounded-full shrink-0 ${statusCfg.dot} ${statusCfg.glow} shadow-sm`} />
          <span className="text-[13px] font-semibold text-zinc-100 truncate leading-tight">
            {data.name}
          </span>
        </div>
        <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-md shrink-0 ${tierCfg.color}`}>
          {tierCfg.label}
        </span>
      </div>

      {/* Role */}
      {data.role && (
        <div className="text-[10px] text-zinc-400 mb-1.5 leading-tight">{data.role}</div>
      )}

      {/* Skills */}
      {skills.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1.5">
          {skills.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className={`text-[9px] px-1.5 py-0.5 rounded-md border ${
                isOnline
                  ? "text-emerald-300/80 bg-emerald-950/30 border-emerald-800/30"
                  : "text-zinc-400 bg-zinc-800/60 border-zinc-700/40"
              }`}
            >
              {skill}
            </span>
          ))}
          {skills.length > 3 && (
            <span className="text-[9px] text-zinc-500 self-center">
              +{skills.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Active tasks badge */}
      {data.activeTasks > 0 && (
        <div className="flex items-center gap-1 mt-0.5">
          <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
          <span className="text-[9px] text-amber-300/80">
            {data.activeTasks} active
          </span>
        </div>
      )}

      {/* Degraded warning */}
      {data.status === "degraded" && data.lastSampleError && (
        <div
          className="text-[9px] text-amber-300/70 truncate mt-1 bg-amber-950/20 px-1.5 py-0.5 rounded"
          title={data.lastSampleError}
        >
          {data.lastSampleError}
        </div>
      )}

      {/* Status label for non-online */}
      {data.status !== "online" && data.status !== "provisioning" && (
        <div className="text-[9px] text-zinc-500 mt-1 uppercase tracking-wider">
          {statusCfg.label}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2 !h-2 !bg-zinc-600 !border-zinc-500 !-bottom-1 hover:!bg-blue-400 transition-colors"
      />
    </div>
  );
}

function getSkillNames(agentCard: Record<string, unknown> | null): string[] {
  if (!agentCard) return [];
  const skills = agentCard.skills;
  if (!Array.isArray(skills)) return [];
  return skills.map((s: Record<string, unknown>) =>
    String(s.name || s.id || "")
  ).filter(Boolean);
}
