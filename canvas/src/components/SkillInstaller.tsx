"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { showToast } from "./Toaster";

interface Props {
  workspaceId: string;
}

export function SkillInstaller({ workspaceId }: Props) {
  const [skillName, setSkillName] = useState("");
  const [installing, setInstalling] = useState(false);

  const handleInstall = async () => {
    const name = skillName.trim();
    if (!name) return;

    setInstalling(true);
    try {
      // Create the skill directory with a basic SKILL.md
      await api.put(`/workspaces/${workspaceId}/files/skills/${name}/SKILL.md`, {
        content: `---\nname: ${name}\ndescription: Installed skill\n---\n\n# ${name}\n\nSkill instructions go here.\n`,
      });
      showToast(`Skill "${name}" installed`, "success");
      setSkillName("");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Install failed", "error");
    } finally {
      setInstalling(false);
    }
  };

  const handleClawHub = async () => {
    const name = skillName.trim();
    if (!name) return;

    setInstalling(true);
    try {
      // Run clawhub install inside the workspace container via shell
      const resp = await api.post<{
        result?: { parts?: Array<{ kind: string; text: string }> };
      }>(`/workspaces/${workspaceId}/a2a`, {
        method: "message/send",
        params: {
          message: {
            role: "user",
            parts: [{ type: "text", text: `Install the ClawHub skill "${name}" by running: npx clawhub@latest install ${name}` }],
          },
        },
      });
      showToast(`ClawHub install for "${name}" requested`, "info");
      setSkillName("");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "ClawHub install failed", "error");
    } finally {
      setInstalling(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-1.5">
        <input
          value={skillName}
          onChange={(e) => setSkillName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleInstall()}
          placeholder="skill-name"
          className="flex-1 bg-zinc-800/60 border border-zinc-700/50 rounded-lg px-2.5 py-1.5 text-[10px] font-mono text-zinc-100 focus:outline-none focus:border-blue-500/60"
        />
        <button
          onClick={handleInstall}
          disabled={!skillName.trim() || installing}
          className="px-2.5 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 rounded-lg text-[10px] text-blue-300 disabled:opacity-30"
        >
          Add
        </button>
      </div>
      <button
        onClick={handleClawHub}
        disabled={!skillName.trim() || installing}
        className="w-full px-2.5 py-1.5 bg-violet-600/10 hover:bg-violet-600/20 border border-violet-500/20 rounded-lg text-[10px] text-violet-300 disabled:opacity-30 transition-colors"
      >
        {installing ? "Installing..." : `Install from ClawHub`}
      </button>
    </div>
  );
}
