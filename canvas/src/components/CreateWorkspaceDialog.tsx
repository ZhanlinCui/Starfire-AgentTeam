"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function CreateWorkspaceButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-sm font-medium rounded-lg text-white shadow-lg transition-colors"
      >
        + New Workspace
      </button>

      {open && <CreateDialog onClose={() => setOpen(false)} />}
    </>
  );
}

function CreateDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [tier, setTier] = useState(1);
  const [parentId, setParentId] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }

    setCreating(true);
    setError(null);

    try {
      await api.post("/workspaces", {
        name: name.trim(),
        role: role.trim() || undefined,
        tier,
        parent_id: parentId.trim() || undefined,
        canvas: { x: Math.random() * 400 + 100, y: Math.random() * 300 + 100 },
      });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create workspace");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl w-[380px] p-5">
        <h2 className="text-sm font-semibold text-zinc-100 mb-4">Create Workspace</h2>

        <div className="space-y-3">
          <div>
            <label className="text-[10px] text-zinc-500 block mb-0.5">Name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. SEO Agent"
              autoFocus
              className="w-full bg-zinc-800 border border-zinc-600 rounded px-2.5 py-1.5 text-sm text-zinc-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="text-[10px] text-zinc-500 block mb-0.5">Role</label>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g. SEO Specialist"
              className="w-full bg-zinc-800 border border-zinc-600 rounded px-2.5 py-1.5 text-sm text-zinc-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="text-[10px] text-zinc-500 block mb-0.5">Tier</label>
            <select
              value={tier}
              onChange={(e) => setTier(Number(e.target.value))}
              className="w-full bg-zinc-800 border border-zinc-600 rounded px-2.5 py-1.5 text-sm text-zinc-100 focus:outline-none focus:border-blue-500"
            >
              <option value={1}>Tier 1 — No privileges</option>
              <option value={2}>Tier 2 — Browser</option>
              <option value={3}>Tier 3 — Desktop</option>
              <option value={4}>Tier 4 — VM</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] text-zinc-500 block mb-0.5">Parent Workspace ID</label>
            <input
              value={parentId}
              onChange={(e) => setParentId(e.target.value)}
              placeholder="Leave empty for root-level"
              className="w-full bg-zinc-800 border border-zinc-600 rounded px-2.5 py-1.5 text-sm text-zinc-100 font-mono focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {error && (
          <div className="mt-3 px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2 mt-5">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-sm rounded text-zinc-300"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-sm rounded text-white disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
