"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useCanvasStore, type WorkspaceNodeData } from "@/store/canvas";
import { StatusDot } from "../StatusDot";

interface Props {
  workspaceId: string;
  data: WorkspaceNodeData;
}

interface PeerData {
  id: string;
  name: string;
  role: string | null;
  status: string;
  tier: number;
}

export function DetailsTab({ workspaceId, data }: Props) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(data.name);
  const [role, setRole] = useState(data.role || "");
  const [tier, setTier] = useState(data.tier);
  const [peers, setPeers] = useState<PeerData[]>([]);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [peersError, setPeersError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);
  const [restartError, setRestartError] = useState<string | null>(null);
  const updateNodeData = useCanvasStore((s) => s.updateNodeData);
  const removeNode = useCanvasStore((s) => s.removeNode);
  const selectNode = useCanvasStore((s) => s.selectNode);

  useEffect(() => {
    setName(data.name);
    setRole(data.role || "");
    setTier(data.tier);
  }, [data.name, data.role, data.tier]);

  const loadPeers = useCallback(async () => {
    setPeersError(null);
    try {
      const peerList = await api.get<PeerData[]>(`/registry/${workspaceId}/peers`);
      setPeers(peerList);
    } catch (e) {
      setPeersError(e instanceof Error ? e.message : "Failed to load peers");
    }
  }, [workspaceId]);

  useEffect(() => {
    loadPeers();
  }, [loadPeers]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await api.patch(`/workspaces/${workspaceId}`, { name, role: role || null, tier });
      updateNodeData(workspaceId, { name, role: role || "", tier });
      setEditing(false);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleteError(null);
    try {
      await api.del(`/workspaces/${workspaceId}`);
      removeNode(workspaceId);
      selectNode(null);
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const handleRestart = async () => {
    setRestarting(true);
    setRestartError(null);
    try {
      await api.post(`/workspaces/${workspaceId}/restart`, {});
      updateNodeData(workspaceId, { status: "provisioning" });
    } catch (e) {
      setRestartError(e instanceof Error ? e.message : "Failed to restart");
    } finally {
      setRestarting(false);
    }
  };

  const isRestartable = data.status === "offline" || data.status === "failed" || data.status === "degraded";

  const agentCard = data.agentCard;
  const skills = getSkills(agentCard);

  return (
    <div className="p-4 space-y-4">
      {/* Editable fields */}
      <Section title="Workspace">
        {editing ? (
          <div className="space-y-2">
            <Field label="Name">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-sm text-zinc-100 focus:outline-none focus:border-blue-500"
              />
            </Field>
            <Field label="Role">
              <input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. SEO Specialist"
                className="w-full bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-sm text-zinc-100 focus:outline-none focus:border-blue-500"
              />
            </Field>
            <Field label="Tier">
              <select
                value={tier}
                onChange={(e) => setTier(Number(e.target.value))}
                className="w-full bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-sm text-zinc-100 focus:outline-none focus:border-blue-500"
              >
                <option value={1}>Tier 1 — No privileges</option>
                <option value={2}>Tier 2 — Browser</option>
                <option value={3}>Tier 3 — Desktop</option>
                <option value={4}>Tier 4 — VM</option>
              </select>
            </Field>
            {saveError && (
              <div className="px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
                {saveError}
              </div>
            )}
            <div className="flex gap-2 pt-1">
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-xs rounded text-white disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => { setEditing(false); setSaveError(null); setName(data.name); setRole(data.role || ""); setTier(data.tier); }}
                className="px-3 py-1 bg-zinc-700 hover:bg-zinc-600 text-xs rounded text-zinc-300"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-1.5">
            <Row label="Name" value={data.name} />
            <Row label="Role" value={data.role || "—"} />
            <Row label="Tier" value={`T${data.tier}`} />
            <Row label="Status" value={data.status} />
            <Row label="URL" value={data.url || "—"} mono />
            <Row label="Parent" value={data.parentId || "root"} mono />
            <Row label="Active Tasks" value={String(data.activeTasks)} />
            {data.status === "degraded" && (
              <Row label="Error Rate" value={`${(data.lastErrorRate * 100).toFixed(0)}%`} />
            )}
            {isRestartable && (
              <div className="pt-2">
                {restartError && (
                  <div className="mb-2 px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
                    {restartError}
                  </div>
                )}
                <button
                  onClick={handleRestart}
                  disabled={restarting}
                  className="px-3 py-1 bg-green-700 hover:bg-green-600 text-xs rounded text-white disabled:opacity-50"
                >
                  {restarting ? "Restarting..." : data.status === "failed" ? "Retry" : "Restart"}
                </button>
              </div>
            )}
            <button
              onClick={() => setEditing(true)}
              className="mt-2 px-3 py-1 bg-zinc-700 hover:bg-zinc-600 text-xs rounded text-zinc-300"
            >
              Edit
            </button>
          </div>
        )}
      </Section>

      {/* Agent Card / Skills */}
      {skills.length > 0 && (
        <Section title="Skills">
          <div className="space-y-1">
            {skills.map((s) => (
              <div key={s.id} className="flex items-start gap-2">
                <span className="text-xs text-blue-400 font-mono shrink-0">{s.id}</span>
                {s.description && (
                  <span className="text-xs text-zinc-500">{s.description}</span>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Agent Management */}
      <Section title="Agent">
        <AgentManager workspaceId={workspaceId} />
      </Section>

      {/* Agent Card — editable */}
      <Section title="Agent Card">
        <AgentCardEditor workspaceId={workspaceId} card={agentCard} />
      </Section>

      {/* Peers */}
      <Section title={`Peers (${peers.length})`}>
        {peersError ? (
          <p className="text-xs text-red-400">{peersError}</p>
        ) : peers.length === 0 ? (
          <p className="text-xs text-zinc-500">No reachable peers</p>
        ) : (
          <div className="space-y-1">
            {peers.map((p) => (
              <button
                key={p.id}
                onClick={() => selectNode(p.id)}
                className="w-full flex items-center gap-2 px-2 py-1 rounded hover:bg-zinc-800 text-left"
              >
                <StatusDot status={p.status} />
                <span className="text-xs text-zinc-200">{p.name}</span>
                {p.role && <span className="text-[10px] text-zinc-500">{p.role}</span>}
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* Delete */}
      <Section title="Danger Zone">
        {deleteError && (
          <div className="mb-2 px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
            {deleteError}
          </div>
        )}
        {confirmDelete ? (
          <div className="flex gap-2">
            <button
              onClick={handleDelete}
              className="px-3 py-1 bg-red-600 hover:bg-red-500 text-xs rounded text-white"
            >
              Confirm Delete
            </button>
            <button
              onClick={() => { setConfirmDelete(false); setDeleteError(null); }}
              className="px-3 py-1 bg-zinc-700 hover:bg-zinc-600 text-xs rounded text-zinc-300"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="px-3 py-1 bg-zinc-800 hover:bg-red-900 border border-zinc-700 hover:border-red-700 text-xs rounded text-zinc-400 hover:text-red-400 transition-colors"
          >
            Delete Workspace
          </button>
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">{title}</h3>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[10px] text-zinc-500 block mb-0.5">{label}</label>
      {children}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className={`text-xs text-zinc-200 ${mono ? "font-mono" : ""} text-right max-w-[200px] truncate`}>
        {value}
      </span>
    </div>
  );
}

function AgentManager({ workspaceId }: { workspaceId: string }) {
  const [agent, setAgent] = useState<{ agent_id: string; model: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [model, setModel] = useState("");
  const [showAssign, setShowAssign] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    // Try to get current agent by checking the agents table
    // For MVP, we show the model from the workspace config
    api.get<{ model: string; source: string }>(`/workspaces/${workspaceId}/model`)
      .then((res) => {
        if (res.model) {
          setAgent({ agent_id: "", model: res.model });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspaceId]);

  const handleAssign = async () => {
    if (!model.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.post<{ agent_id: string; model: string }>(
        `/workspaces/${workspaceId}/agent`,
        { model: model.trim() }
      );
      setAgent(res);
      setShowAssign(false);
      setModel("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to assign");
    } finally {
      setSaving(false);
    }
  };

  const handleReplace = async () => {
    if (!model.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.patch<{ agent_id: string; model: string }>(
        `/workspaces/${workspaceId}/agent`,
        { model: model.trim() }
      );
      setAgent(res);
      setShowAssign(false);
      setModel("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to replace");
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    setError(null);
    try {
      await api.del(`/workspaces/${workspaceId}/agent`);
      setAgent(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove");
    }
  };

  if (loading) return <div className="text-xs text-zinc-500">Loading...</div>;

  return (
    <div className="space-y-2">
      {error && (
        <div className="px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">{error}</div>
      )}

      {agent ? (
        <div className="bg-zinc-800/40 border border-zinc-700/40 rounded-lg p-2.5">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[10px] text-zinc-500">Current Model</div>
              <div className="text-xs text-zinc-200 font-mono">{agent.model}</div>
            </div>
            <div className="flex gap-1.5">
              <button
                onClick={() => { setShowAssign(true); setModel(agent.model); }}
                className="text-[10px] text-blue-400 hover:text-blue-300"
              >
                Replace
              </button>
              <button
                onClick={handleRemove}
                className="text-[10px] text-red-400 hover:text-red-300"
              >
                Remove
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-xs text-zinc-500">No agent assigned</div>
      )}

      {(showAssign || !agent) && (
        <div className="flex gap-2">
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="anthropic:claude-sonnet-4-6"
            className="flex-1 bg-zinc-800/60 border border-zinc-700/50 rounded-lg px-2.5 py-1.5 text-xs font-mono text-zinc-100 focus:outline-none focus:border-blue-500/60"
          />
          <button
            onClick={agent ? handleReplace : handleAssign}
            disabled={!model.trim() || saving}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-[10px] rounded-lg text-white disabled:opacity-30"
          >
            {saving ? "..." : agent ? "Replace" : "Assign"}
          </button>
          {showAssign && agent && (
            <button
              onClick={() => setShowAssign(false)}
              className="px-2 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-[10px] rounded-lg text-zinc-300"
            >
              Cancel
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function AgentCardEditor({ workspaceId, card }: { workspaceId: string; card: Record<string, unknown> | null }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const startEditing = () => {
    setDraft(JSON.stringify(card || {}, null, 2));
    setEditing(true);
    setError(null);
    setSuccess(false);
  };

  const handleSave = async () => {
    setError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(draft);
    } catch {
      setError("Invalid JSON");
      return;
    }

    setSaving(true);
    try {
      await api.post("/registry/update-card", {
        workspace_id: workspaceId,
        agent_card: parsed,
      });
      setSuccess(true);
      setEditing(false);
      setTimeout(() => setSuccess(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update agent card");
    } finally {
      setSaving(false);
    }
  };

  if (!editing) {
    return (
      <div>
        {card ? (
          <pre className="text-[10px] text-zinc-400 bg-zinc-800 rounded p-2 overflow-x-auto max-h-48">
            {JSON.stringify(card, null, 2)}
          </pre>
        ) : (
          <p className="text-xs text-zinc-500">No agent card</p>
        )}
        {success && (
          <div className="mt-2 px-3 py-1.5 bg-green-900/30 border border-green-800 rounded text-xs text-green-400">
            Agent card updated
          </div>
        )}
        <button
          onClick={startEditing}
          className="mt-2 px-3 py-1 bg-zinc-700 hover:bg-zinc-600 text-xs rounded text-zinc-300"
        >
          Edit Agent Card
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        spellCheck={false}
        rows={12}
        className="w-full bg-zinc-800 border border-zinc-600 rounded p-2 text-[10px] font-mono text-zinc-200 focus:outline-none focus:border-blue-500 resize-none"
      />
      {error && (
        <div className="px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
          {error}
        </div>
      )}
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-xs rounded text-white disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save"}
        </button>
        <button
          onClick={() => setEditing(false)}
          className="px-3 py-1 bg-zinc-700 hover:bg-zinc-600 text-xs rounded text-zinc-300"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function getSkills(card: Record<string, unknown> | null): { id: string; description?: string }[] {
  if (!card) return [];
  const skills = card.skills;
  if (!Array.isArray(skills)) return [];
  return skills.map((s: Record<string, unknown>) => ({
    id: String(s.id || s.name || ""),
    description: s.description ? String(s.description) : undefined,
  })).filter((s) => s.id);
}
