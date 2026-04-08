"use client";

import { useMemo } from "react";
import { useCanvasStore, summarizeWorkspaceCapabilities, type WorkspaceNodeData } from "@/store/canvas";

interface Props {
  data: WorkspaceNodeData;
}

interface SkillEntry {
  id: string;
  name: string;
  description: string;
  tags: string[];
  examples: string[];
}

export function SkillsTab({ data }: Props) {
  const capability = summarizeWorkspaceCapabilities(data);
  const skills = useMemo(() => extractSkills(data.agentCard), [data.agentCard]);
  const setPanelTab = useCanvasStore((s) => s.setPanelTab);
  const promotionTask = data.currentTask.startsWith("Skill promotion:");

  return (
    <div className="p-4 space-y-4">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-500">Workspace skills</div>
            <h3 className="mt-1 text-sm font-semibold text-zinc-100">Installed skills</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <MetaPill label="Count" value={String(capability.skillCount)} />
            <MetaPill label="Runtime" value={capability.runtime || "unknown"} />
          </div>
        </div>
        <p className="mt-2 text-[11px] leading-5 text-zinc-500">
          This is the live skill directory for the selected workspace. It is derived from the Agent Card,
          so it updates when the workspace hot-reloads skills.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={() => setPanelTab("config")}
            className="rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1 text-[10px] text-zinc-300 hover:bg-zinc-900"
          >
            Open Config
          </button>
          <button
            onClick={() => setPanelTab("files")}
            className="rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1 text-[10px] text-zinc-300 hover:bg-zinc-900"
          >
            Open Files
          </button>
        </div>
      </div>

      {promotionTask && (
        <div className="rounded-xl border border-violet-800/30 bg-violet-950/20 p-3 text-[11px] text-violet-200/90">
          A skill promotion is currently in flight. The workspace is compressing a repeatable workflow into
          a new skill package.
        </div>
      )}

      {skills.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-900/40 p-6 text-center">
          <div className="text-sm text-zinc-100">No skills loaded</div>
          <p className="mt-2 text-[11px] leading-5 text-zinc-500">
            Add skills from the Config tab or let the runtime hot-load them from the workspace config.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {skills.map((skill) => (
            <div key={skill.id} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold text-zinc-100">{skill.name}</div>
                  <div className="mt-0.5 text-[10px] font-mono text-zinc-500">{skill.id}</div>
                </div>
                {skill.tags.length > 0 && (
                  <div className="flex flex-wrap justify-end gap-1.5">
                    {skill.tags.slice(0, 4).map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[9px] text-zinc-400"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {skill.description && (
                <p className="mt-2 text-[11px] leading-5 text-zinc-400">{skill.description}</p>
              )}

              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() => setPanelTab("config")}
                  className="rounded-full border border-zinc-700/70 bg-zinc-950/70 px-2.5 py-1 text-[9px] text-zinc-300 hover:bg-zinc-900"
                >
                  View in Config
                </button>
                <button
                  onClick={() => setPanelTab("files")}
                  className="rounded-full border border-zinc-700/70 bg-zinc-950/70 px-2.5 py-1 text-[9px] text-zinc-300 hover:bg-zinc-900"
                >
                  Open Files
                </button>
              </div>

              {skill.examples.length > 0 && (
                <div className="mt-2">
                  <div className="text-[9px] uppercase tracking-[0.2em] text-zinc-600">Examples</div>
                  <div className="mt-1 space-y-1">
                    {skill.examples.slice(0, 2).map((example, index) => (
                      <div
                        key={`${skill.id}-${index}`}
                        className="rounded-md border border-zinc-800 bg-zinc-950/60 px-2 py-1 text-[10px] text-zinc-300"
                      >
                        {example}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function extractSkills(agentCard: Record<string, unknown> | null): SkillEntry[] {
  if (!agentCard) return [];
  const rawSkills = agentCard.skills;
  if (!Array.isArray(rawSkills)) return [];

  return rawSkills
    .map((skill: Record<string, unknown>) => ({
      id: String(skill.id || skill.name || ""),
      name: String(skill.name || skill.id || "Unnamed skill"),
      description: String(skill.description || ""),
      tags: Array.isArray(skill.tags) ? skill.tags.map((tag) => String(tag)) : [],
      examples: Array.isArray(skill.examples) ? skill.examples.map((example) => String(example)) : [],
    }))
    .filter((skill) => skill.id.length > 0);
}

function MetaPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-zinc-700/60 bg-zinc-950/60 px-2 py-1 text-[9px] text-zinc-300">
      <span className="uppercase tracking-[0.18em] text-[8px] text-zinc-500">{label}</span>
      <span className="font-medium">{value}</span>
    </span>
  );
}
