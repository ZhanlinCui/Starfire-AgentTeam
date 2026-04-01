"use client";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { useCanvasStore, type WorkspaceNodeData } from "@/store/canvas";
import { STATUS_COLORS } from "./StatusDot";

const TIER_LABELS: Record<number, string> = {
  1: "T1",
  2: "T2",
  3: "T3",
  4: "T4",
};

export function WorkspaceNode({ id, data }: NodeProps<Node<WorkspaceNodeData>>) {
  const statusColor = STATUS_COLORS[data.status] || "bg-zinc-600";
  const tierLabel = TIER_LABELS[data.tier] || `T${data.tier}`;
  const selectedNodeId = useCanvasStore((s) => s.selectedNodeId);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const isSelected = selectedNodeId === id;

  const skills = getSkillNames(data.agentCard as Record<string, unknown> | null);

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        selectNode(isSelected ? null : id);
      }}
      className={`rounded-lg border bg-zinc-900 shadow-lg min-w-[180px] px-3 py-2 cursor-pointer transition-all ${
        isSelected
          ? "border-blue-500 ring-1 ring-blue-500/50 shadow-blue-500/20"
          : "border-zinc-700 hover:border-zinc-500"
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-zinc-600" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${statusColor}`} />
          <span className="text-sm font-medium text-zinc-100 truncate max-w-[120px]">
            {data.name}
          </span>
        </div>
        <span className="text-[10px] font-mono text-zinc-500 bg-zinc-800 px-1 rounded">
          {tierLabel}
        </span>
      </div>

      {/* Role */}
      {data.role && (
        <div className="text-[10px] text-zinc-500 mb-1">{data.role}</div>
      )}

      {/* Skills */}
      {skills.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {skills.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className="text-[9px] text-zinc-400 bg-zinc-800 px-1.5 py-0.5 rounded"
            >
              {skill}
            </span>
          ))}
          {skills.length > 3 && (
            <span className="text-[9px] text-zinc-500">
              +{skills.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Active tasks */}
      {data.activeTasks > 0 && (
        <div className="text-[10px] text-amber-400">
          {data.activeTasks} active task
          {data.activeTasks > 1 ? "s" : ""}
        </div>
      )}

      {/* Degraded warning */}
      {data.status === "degraded" && data.lastSampleError && (
        <div
          className="text-[9px] text-yellow-400 truncate mt-1"
          title={data.lastSampleError}
        >
          {data.lastSampleError}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-zinc-600"
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
