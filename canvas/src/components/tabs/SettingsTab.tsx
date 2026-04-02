"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

interface Props {
  workspaceId: string;
}

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

export function SettingsTab({ workspaceId }: Props) {
  const [secrets, setSecrets] = useState<SecretEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [customSaving, setCustomSaving] = useState(false);

  const loadSecrets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<SecretEntry[]>(`/workspaces/${workspaceId}/secrets`);
      setSecrets(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load secrets");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    loadSecrets();
  }, [loadSecrets]);

  const handleSave = async (key: string, value: string) => {
    setError(null);
    try {
      await api.post(`/workspaces/${workspaceId}/secrets`, { key, value });
      setNewKey("");
      setNewValue("");
      setShowAdd(false);
      loadSecrets();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  };

  const handleDelete = async (key: string) => {
    setError(null);
    try {
      await api.del(`/workspaces/${workspaceId}/secrets/${encodeURIComponent(key)}`);
      setSecrets((prev) => prev.filter((s) => s.key !== key));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  if (loading) {
    return <div className="p-4 text-xs text-zinc-500">Loading settings...</div>;
  }

  const configuredKeys = new Set(secrets.map((s) => s.key));

  return (
    <div className="p-4 space-y-4">
      {error && (
        <div className="px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Quick-set common keys */}
      <Section title="LLM & API Keys">
        <div className="space-y-2">
          {COMMON_KEYS.map(({ key, label }) => (
            <QuickSetRow
              key={key}
              label={label}
              secretKey={key}
              isSet={configuredKeys.has(key)}
              onSave={(value) => handleSave(key, value)}
              onDelete={() => handleDelete(key)}
            />
          ))}
        </div>
      </Section>

      {/* Custom env vars */}
      <Section title="Custom Environment Variables">
        {secrets
          .filter((s) => !COMMON_KEYS.some((c) => c.key === s.key))
          .map((s) => (
            <div key={s.key} className="flex items-center justify-between py-1">
              <span className="text-xs font-mono text-blue-400">{s.key}</span>
              <div className="flex items-center gap-2">
                <span className="text-[9px] text-green-500">Set</span>
                <button
                  onClick={() => handleDelete(s.key)}
                  className="text-[10px] text-red-400 hover:text-red-300"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}

        {showAdd ? (
          <div className="bg-zinc-800 rounded p-3 space-y-2 border border-zinc-700 mt-2">
            <input
              value={newKey}
              onChange={(e) => setNewKey(e.target.value.toUpperCase())}
              placeholder="KEY_NAME"
              className="w-full bg-zinc-900 border border-zinc-600 rounded px-2 py-1 text-xs font-mono text-zinc-100 focus:outline-none focus:border-blue-500"
            />
            <input
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              placeholder="Value"
              type="password"
              className="w-full bg-zinc-900 border border-zinc-600 rounded px-2 py-1 text-xs text-zinc-100 focus:outline-none focus:border-blue-500"
            />
            <div className="flex gap-2">
              <button
                onClick={async () => {
                  if (!newKey || !newValue) return;
                  setCustomSaving(true);
                  await handleSave(newKey, newValue);
                  setCustomSaving(false);
                }}
                disabled={!newKey || !newValue || customSaving}
                className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-xs rounded text-white disabled:opacity-30"
              >
                Save
              </button>
              <button
                onClick={() => { setShowAdd(false); setNewKey(""); setNewValue(""); }}
                className="px-3 py-1 bg-zinc-700 hover:bg-zinc-600 text-xs rounded text-zinc-300"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowAdd(true)}
            className="mt-2 px-3 py-1 bg-zinc-700 hover:bg-zinc-600 text-xs rounded text-zinc-300"
          >
            + Add Variable
          </button>
        )}
      </Section>

      <div className="text-[10px] text-zinc-600 pt-2">
        Changes take effect on next workspace restart. Values are stored securely and never exposed to the browser.
      </div>
    </div>
  );
}

function QuickSetRow({
  label,
  secretKey,
  isSet,
  onSave,
  onDelete,
}: {
  label: string;
  secretKey: string;
  isSet: boolean;
  onSave: (value: string) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  return (
    <div className="bg-zinc-800 rounded px-3 py-2 border border-zinc-700">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-zinc-200">{label}</div>
          <div className="text-[10px] font-mono text-zinc-500">{secretKey}</div>
        </div>
        <div className="flex items-center gap-2">
          {isSet && <span className="text-[9px] text-green-500 bg-green-900/30 px-1.5 py-0.5 rounded">Set</span>}
          {editing ? null : isSet ? (
            <button
              onClick={onDelete}
              className="text-[10px] text-red-400 hover:text-red-300"
            >
              Remove
            </button>
          ) : null}
          <button
            onClick={() => setEditing(!editing)}
            className="text-[10px] text-blue-400 hover:text-blue-300"
          >
            {editing ? "Cancel" : isSet ? "Update" : "Set"}
          </button>
        </div>
      </div>

      {editing && (
        <div className="flex gap-2 mt-2">
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={secretKey === "MODEL_PROVIDER" ? "anthropic:claude-sonnet-4-6" : "sk-..."}
            type={secretKey === "MODEL_PROVIDER" ? "text" : "password"}
            autoFocus
            className="flex-1 bg-zinc-900 border border-zinc-600 rounded px-2 py-1 text-xs text-zinc-100 font-mono focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={async () => {
              setSaving(true);
              onSave(value);
              setEditing(false);
              setValue("");
              setSaving(false);
            }}
            disabled={!value || saving}
            className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-xs rounded text-white disabled:opacity-30"
          >
            Save
          </button>
        </div>
      )}
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
