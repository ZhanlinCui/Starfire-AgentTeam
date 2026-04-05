"use client";

import { useMemo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { useCanvasStore, type WorkspaceNodeData } from "@/store/canvas";

const STATUS_CONFIG: Record<string, { dot: string; glow: string; label: string; bar: string }> = {
  online: { dot: "bg-emerald-400", glow: "shadow-emerald-400/50", label: "Online", bar: "from-emerald-500/20 to-transparent" },
  offline: { dot: "bg-zinc-500", glow: "", label: "Offline", bar: "from-zinc-600/10 to-transparent" },
  degraded: { dot: "bg-amber-400", glow: "shadow-amber-400/50", label: "Degraded", bar: "from-amber-500/20 to-transparent" },
  failed: { dot: "bg-red-400", glow: "shadow-red-400/50", label: "Failed", bar: "from-red-500/20 to-transparent" },
  provisioning: { dot: "bg-sky-400 animate-pulse", glow: "shadow-sky-400/50", label: "Starting", bar: "from-sky-500/20 to-transparent" },
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

  // Get children to render embedded inside this node
  // Use stable selector: get all nodes, then filter in useMemo
  const allNodes = useCanvasStore((s) => s.nodes);
  const children = useMemo(
    () => allNodes.filter((n) => n.data.parentId === id),
    [allNodes, id]
  );
  const hasChildren = children.length > 0;

  const skills = getSkillNames(data.agentCard as Record<string, unknown> | null);

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        selectNode(isSelected ? null : id);
      }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        if (hasChildren) {
          window.dispatchEvent(new CustomEvent("starfire:zoom-to-team", { detail: { nodeId: id } }));
        }
      }}
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
        openContextMenu({ x: e.clientX, y: e.clientY, nodeId: id, nodeData: data as unknown as import("@/store/canvas").WorkspaceNodeData });
      }}
      className={`
        group relative rounded-xl
        ${hasChildren ? "min-w-[320px] max-w-[450px]" : "min-w-[210px] max-w-[280px]"}
        cursor-pointer overflow-hidden
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
      {/* Status gradient bar at top */}
      <div className={`absolute inset-x-0 top-0 h-8 bg-gradient-to-b ${statusCfg.bar} pointer-events-none`} />

      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-1 !rounded-full !bg-zinc-600/80 !border-0 !-top-0.5 hover:!bg-blue-400 hover:!h-1.5 transition-all"
      />

      <div className="relative px-3.5 py-2.5">
        {/* Header row */}
        <div className="flex items-center justify-between gap-2 mb-1">
          <div className="flex items-center gap-2 min-w-0">
            <div className={`w-2 h-2 rounded-full shrink-0 ${statusCfg.dot} ${statusCfg.glow} shadow-sm`} />
            <span className="text-[13px] font-semibold text-zinc-100 truncate leading-tight">
              {data.name}
            </span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {hasChildren && (
              <span className="text-[8px] font-mono text-violet-300 bg-violet-900/40 border border-violet-700/30 px-1.5 py-0.5 rounded-md">
                {children.length} sub
              </span>
            )}
            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-md ${tierCfg.color}`}>
              {tierCfg.label}
            </span>
          </div>
        </div>

        {/* Role */}
        {data.role && (
          <div className="text-[10px] text-zinc-400 mb-1.5 leading-tight">{data.role}</div>
        )}

        {/* Skills */}
        {skills.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-1.5">
            {skills.slice(0, 4).map((skill) => (
              <span
                key={skill}
                className={`text-[8px] px-1.5 py-0.5 rounded-md border ${
                  isOnline
                    ? "text-emerald-300/80 bg-emerald-950/30 border-emerald-800/30"
                    : "text-zinc-400 bg-zinc-800/60 border-zinc-700/40"
                }`}
              >
                {skill}
              </span>
            ))}
            {skills.length > 4 && (
              <span className="text-[8px] text-zinc-500 self-center">
                +{skills.length - 4}
              </span>
            )}
          </div>
        )}

        {/* Embedded children — rendered INSIDE the parent node */}
        {hasChildren && (
          <div className="mt-2 pt-2 border-t border-zinc-700/30">
            <div className="text-[8px] text-zinc-500 uppercase tracking-widest mb-1.5">Team Members</div>
            <div className="grid grid-cols-2 gap-1.5">
              {children.map((child) => {
                const childStatus = STATUS_CONFIG[child.data.status] || STATUS_CONFIG.offline;
                return (
                  <button
                    key={child.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      selectNode(child.id);
                    }}
                    className="flex items-center gap-1.5 px-2 py-1.5 bg-zinc-800/50 hover:bg-zinc-700/50 border border-zinc-700/30 rounded-lg text-left transition-colors"
                  >
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${childStatus.dot}`} />
                    <div className="min-w-0">
                      <div className="text-[9px] text-zinc-200 truncate">{child.data.name}</div>
                      {child.data.role && (
                        <div className="text-[7px] text-zinc-500 truncate">{child.data.role}</div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Bottom row: status / active tasks */}
        <div className="flex items-center justify-between mt-0.5">
          {data.status !== "online" && (
            <div className={`text-[8px] uppercase tracking-widest font-medium ${
              data.status === "failed" ? "text-red-400" :
              data.status === "degraded" ? "text-amber-400" :
              data.status === "provisioning" ? "text-sky-400" :
              "text-zinc-500"
            }`}>
              {statusCfg.label}
            </div>
          )}
          {data.status === "online" && <div />}

          {data.activeTasks > 0 && (
            <div className="flex items-center gap-1">
              <div className="w-1 h-1 rounded-full bg-amber-400 animate-pulse" />
              <span className="text-[8px] text-amber-300/80 tabular-nums">
                {data.activeTasks} task{data.activeTasks > 1 ? "s" : ""}
              </span>
            </div>
          )}
        </div>

        {/* Degraded error preview */}
        {data.status === "degraded" && data.lastSampleError && (
          <div
            className="text-[8px] text-amber-300/60 truncate mt-1 bg-amber-950/20 px-1.5 py-0.5 rounded border border-amber-800/20"
            title={data.lastSampleError}
          >
            {data.lastSampleError}
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-1 !rounded-full !bg-zinc-600/80 !border-0 !-bottom-0.5 hover:!bg-blue-400 hover:!h-1.5 transition-all"
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
