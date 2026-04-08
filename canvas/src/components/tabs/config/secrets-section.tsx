"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { Section } from "./form-inputs";

interface SecretEntry {
  key: string;
  has_value: boolean;
  created_at: string;
  updated_at: string;
}

const COMMON_KEYS = [
  { key: "ANTHROPIC_API_KEY", label: "Anthropic API Key" },
  { key: "OPENAI_API_KEY", label: "OpenAI API Key" },
  { key: "GOOGLE_API_KEY", label: "Google AI API Key" },
  { key: "SERP_API_KEY", label: "SERP API Key" },
  { key: "MODEL_PROVIDER", label: "Model Override (e.g. anthropic:claude-sonnet-4-6)" },
];

function QuickSetRow({ label, secretKey, isSet, onSave, onDelete }: {
  label: string; secretKey: string; isSet: boolean;
  onSave: (value: string) => void; onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  return (
    <div className="bg-zinc-800/50 rounded px-3 py-2 border border-zinc-700/50">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] text-zinc-300">{label}</div>
          <div className="text-[9px] font-mono text-zinc-600">{secretKey}</div>
        </div>
        <div className="flex items-center gap-2">
          {isSet && <span className="text-[8px] text-green-500 bg-green-900/30 px-1.5 py-0.5 rounded">Set</span>}
          {!editing && isSet && <button onClick={onDelete} className="text-[9px] text-red-400 hover:text-red-300">Remove</button>}
          <button onClick={() => setEditing(!editing)} className="text-[9px] text-blue-400 hover:text-blue-300">
            {editing ? "Cancel" : isSet ? "Update" : "Set"}
          </button>
        </div>
      </div>
      {editing && (
        <div className="flex gap-2 mt-2">
          <input
            value={value} onChange={(e) => setValue(e.target.value)}
            placeholder={secretKey === "MODEL_PROVIDER" ? "anthropic:claude-sonnet-4-6" : "sk-..."}
            type={secretKey === "MODEL_PROVIDER" ? "text" : "password"} autoFocus
            className="flex-1 bg-zinc-900 border border-zinc-600 rounded px-2 py-1 text-[10px] text-zinc-100 font-mono focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={() => { onSave(value); setEditing(false); setValue(""); }}
            disabled={!value}
            className="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-[10px] rounded text-white disabled:opacity-30"
          >Save</button>
        </div>
      )}
    </div>
  );
}

export function SecretsSection({ workspaceId }: { workspaceId: string }) {
  const [secrets, setSecrets] = useState<SecretEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");

  const loadSecrets = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<SecretEntry[]>(`/workspaces/${workspaceId}/secrets`);
      setSecrets(data);
    } catch { setSecrets([]); }
    finally { setLoading(false); }
  }, [workspaceId]);

  useEffect(() => { loadSecrets(); }, [loadSecrets]);

  const handleSave = async (key: string, value: string) => {
    setError(null);
    try {
      await api.post(`/workspaces/${workspaceId}/secrets`, { key, value });
      // Platform auto-restarts workspace after secret change — no needsRestart flag needed
      setNewKey(""); setNewValue(""); setShowAdd(false);
      loadSecrets();
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to save"); }
  };

  const handleDelete = async (key: string) => {
    setError(null);
    try {
      await api.del(`/workspaces/${workspaceId}/secrets/${encodeURIComponent(key)}`);
      // Platform auto-restarts workspace after secret deletion
      setSecrets((prev) => prev.filter((s) => s.key !== key));
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to delete"); }
  };

  const configuredKeys = new Set(secrets.map((s) => s.key));

  return (
    <Section title="Secrets & API Keys" defaultOpen={false}>
      {loading ? (
        <div className="text-[10px] text-zinc-500">Loading secrets...</div>
      ) : (
        <div className="space-y-2">
          {error && <div className="px-2 py-1 bg-red-900/30 border border-red-800 rounded text-[10px] text-red-400">{error}</div>}

          {COMMON_KEYS.map(({ key, label }) => (
            <QuickSetRow key={key} label={label} secretKey={key} isSet={configuredKeys.has(key)}
              onSave={(v) => handleSave(key, v)} onDelete={() => handleDelete(key)} />
          ))}

          {secrets.filter((s) => !COMMON_KEYS.some((c) => c.key === s.key)).map((s) => (
            <div key={s.key} className="flex items-center justify-between py-1 px-2">
              <span className="text-[10px] font-mono text-blue-400">{s.key}</span>
              <div className="flex items-center gap-2">
                <span className="text-[8px] text-green-500">Set</span>
                <button onClick={() => handleDelete(s.key)} className="text-[9px] text-red-400 hover:text-red-300">Remove</button>
              </div>
            </div>
          ))}

          {showAdd ? (
            <div className="bg-zinc-800/50 rounded p-2 space-y-1.5 border border-zinc-700/50">
              <input value={newKey} onChange={(e) => setNewKey(e.target.value.toUpperCase())} placeholder="KEY_NAME"
                className="w-full bg-zinc-900 border border-zinc-600 rounded px-2 py-1 text-[10px] font-mono text-zinc-100 focus:outline-none focus:border-blue-500" />
              <input value={newValue} onChange={(e) => setNewValue(e.target.value)} placeholder="Value" type="password"
                className="w-full bg-zinc-900 border border-zinc-600 rounded px-2 py-1 text-[10px] text-zinc-100 focus:outline-none focus:border-blue-500" />
              <div className="flex gap-2">
                <button onClick={() => { if (newKey && newValue) handleSave(newKey, newValue); }} disabled={!newKey || !newValue}
                  className="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-[10px] rounded text-white disabled:opacity-30">Save</button>
                <button onClick={() => { setShowAdd(false); setNewKey(""); setNewValue(""); }}
                  className="px-2 py-1 bg-zinc-700 hover:bg-zinc-600 text-[10px] rounded text-zinc-300">Cancel</button>
              </div>
            </div>
          ) : (
            <button onClick={() => setShowAdd(true)} className="text-[10px] text-blue-400 hover:text-blue-300">+ Add Variable</button>
          )}

          <div className="text-[9px] text-zinc-600 pt-1">Values are encrypted and never exposed to the browser. Changes take effect on restart.</div>
        </div>
      )}
    </Section>
  );
}
