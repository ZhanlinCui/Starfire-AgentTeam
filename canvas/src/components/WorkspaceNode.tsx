"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { WorkspaceNodeData } from "@/store/canvas";

const STATUS_COLORS: Record<string, string> = {
  online: "bg-green-500",
  offline: "bg-zinc-500",
  degraded: "bg-yellow-500",
  failed: "bg-red-500",
  provisioning: "bg-blue-500",
};

const TIER_LABELS: Record<number, string> = {
  1: "T1",
  2: "T2",
  3: "T3",
  4: "T4",
};

export function WorkspaceNode({ data }: NodeProps) {
  const nodeData = data as unknown as WorkspaceNodeData;
  const statusColor = STATUS_COLORS[nodeData.status] || "bg-zinc-600";
  const tierLabel = TIER_LABELS[nodeData.tier] || `T${nodeData.tier}`;

  const skills = getSkillNames(nodeData.agentCard);

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-900 shadow-lg min-w-[180px] px-3 py-2">
      <Handle type="target" position={Position.Top} className="!bg-zinc-600" />

      {/* Header */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${statusColor}`} />
          <span className="text-sm font-medium text-zinc-100 truncate max-w-[120px]">
            {nodeData.name}
          </span>
        </div>
        <span className="text-[10px] font-mono text-zinc-500 bg-zinc-800 px-1 rounded">
          {tierLabel}
        </span>
      </div>

      {/* Role */}
      {nodeData.role && (
        <div className="text-[10px] text-zinc-500 mb-1">{nodeData.role}</div>
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
      {nodeData.activeTasks > 0 && (
        <div className="text-[10px] text-amber-400">
          {nodeData.activeTasks} active task
          {nodeData.activeTasks > 1 ? "s" : ""}
        </div>
      )}

      {/* Degraded warning */}
      {nodeData.status === "degraded" && nodeData.lastSampleError && (
        <div
          className="text-[9px] text-yellow-400 truncate mt-1"
          title={nodeData.lastSampleError}
        >
          {nodeData.lastSampleError}
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
