"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { useCanvasStore } from "@/store/canvas";

interface Props {
  workspaceId: string;
}

interface ConfigData {
  name: string;
  description: string;
  version: string;
  tier: number;
  model: string;
  runtime: string;
  runtime_config?: {
    model?: string;
    auth_token_file?: string;
    timeout?: number;
  };
  prompt_files: string[];
  shared_context: string[];
  skills: string[];
  tools: string[];
  a2a: { port: number; streaming: boolean; push_notifications: boolean };
  delegation: { retry_attempts: number; retry_delay: number; timeout: number; escalate: boolean };
  sandbox: { backend: string; memory_limit: string; timeout: number };
  env: { required: string[]; optional: string[] };
}

const DEFAULT_CONFIG: ConfigData = {
  name: "",
  description: "",
  version: "1.0.0",
  tier: 1,
  model: "",
  runtime: "",
  prompt_files: [],
  shared_context: [],
  skills: [],
  tools: [],
  a2a: { port: 8000, streaming: true, push_notifications: true },
  delegation: { retry_attempts: 3, retry_delay: 5, timeout: 120, escalate: true },
  sandbox: { backend: "docker", memory_limit: "256m", timeout: 30 },
  env: { required: [], optional: [] },
};

// Simple YAML parser for config.yaml — handles flat keys, 1-level objects,
// lists, and 2-level nesting (e.g., env.required: [...]).
function parseYaml(text: string): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  const lines = text.split("\n");

  function parseValue(v: string): unknown {
    if (v === "true") return true;
    if (v === "false") return false;
    if (/^\d+$/.test(v)) return parseInt(v, 10);
    return v;
  }

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // Skip blanks and comments
    if (line.trim() === "" || line.trim().startsWith("#")) { i++; continue; }

    // Top-level key
    const topMatch = line.match(/^(\w[\w_]*):\s*(.*)/);
    if (!topMatch) { i++; continue; }

    const key = topMatch[1];
    const val = topMatch[2].trim();
    i++;

    if (val !== "" && val !== "[]") {
      result[key] = parseValue(val);
      continue;
    }

    // Peek ahead to determine structure
    const nextLine = lines[i] || "";
    if (val === "[]" || (!nextLine.match(/^\s/) || nextLine.trim() === "" || nextLine.trim().startsWith("#"))) {
      result[key] = val === "[]" ? [] : "";
      continue;
    }

    // Indented content follows — is it a list or object?
    if (nextLine.match(/^\s+-\s+/)) {
      // List
      const items: string[] = [];
      while (i < lines.length && lines[i].match(/^\s+-\s+/)) {
        items.push(lines[i].replace(/^\s+-\s+/, "").trim());
        i++;
      }
      result[key] = items;
    } else if (nextLine.match(/^\s+\w+:/)) {
      // Object (1 or 2 levels)
      const obj: Record<string, unknown> = {};
      while (i < lines.length) {
        const sub = lines[i];
        if (sub.trim() === "" || sub.trim().startsWith("#")) { i++; continue; }
        // 2-space indented key: value
        const subMatch = sub.match(/^  (\w[\w_]*):\s*(.*)/);
        if (!subMatch) break;
        const subKey = subMatch[1];
        const subVal = subMatch[2].trim();
        i++;

        if (subVal !== "" && subVal !== "[]") {
          obj[subKey] = parseValue(subVal);
        } else {
          // Check for nested list (2-level: env.required: [...])
          const subNext = lines[i] || "";
          if (subNext.match(/^\s{4,}-\s+/)) {
            const subItems: string[] = [];
            while (i < lines.length && lines[i].match(/^\s{4,}-\s+/)) {
              subItems.push(lines[i].replace(/^\s+-\s+/, "").trim());
              i++;
            }
            obj[subKey] = subItems;
          } else {
            obj[subKey] = subVal === "[]" ? [] : "";
          }
        }
      }
      result[key] = obj;
    }
  }
  return result;
}

function toYaml(config: ConfigData): string {
  const lines: string[] = [];
  const simple = (k: string, v: unknown) => {
    if (v === undefined || v === null || v === "") return;
    lines.push(`${k}: ${v}`);
  };
  const list = (k: string, arr: string[]) => {
    if (!arr || arr.length === 0) { lines.push(`${k}: []`); return; }
    lines.push(`${k}:`);
    arr.forEach((v) => lines.push(`  - ${v}`));
  };
  const obj = (k: string, o: Record<string, unknown>) => {
    if (!o) return;
    lines.push(`${k}:`);
    Object.entries(o).forEach(([sk, sv]) => {
      if (sv !== undefined && sv !== null && sv !== "") lines.push(`  ${sk}: ${sv}`);
    });
  };

  simple("name", config.name);
  simple("description", config.description);
  simple("version", config.version);
  simple("tier", config.tier);
  if (config.runtime) {
    lines.push("");
    simple("runtime", config.runtime);
    if (config.runtime_config && Object.keys(config.runtime_config).length > 0) {
      obj("runtime_config", config.runtime_config as Record<string, unknown>);
    }
  }
  if (config.model) { lines.push(""); simple("model", config.model); }
  if (config.prompt_files?.length) { lines.push(""); list("prompt_files", config.prompt_files); }
  if (config.shared_context?.length) { lines.push(""); list("shared_context", config.shared_context); }
  lines.push(""); list("skills", config.skills);
  if (config.tools?.length) { list("tools", config.tools); }
  lines.push(""); obj("a2a", config.a2a as unknown as Record<string, unknown>);
  lines.push(""); obj("delegation", config.delegation as unknown as Record<string, unknown>);
  if (config.sandbox?.backend) { lines.push(""); obj("sandbox", config.sandbox as unknown as Record<string, unknown>); }
  if (config.env?.required?.length || config.env?.optional?.length) {
    lines.push(""); lines.push("env:");
    if (config.env.required?.length) {
      lines.push("  required:");
      config.env.required.forEach((v) => lines.push(`    - ${v}`));
    }
    if (config.env.optional?.length) {
      lines.push("  optional:");
      config.env.optional.forEach((v) => lines.push(`    - ${v}`));
    }
  }

  return lines.join("\n") + "\n";
}

function TextInput({ label, value, onChange, placeholder, mono }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; mono?: boolean }) {
  return (
    <div>
      <label className="text-[10px] text-zinc-500 block mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 ${mono ? "font-mono" : ""}`}
      />
    </div>
  );
}

function NumberInput({ label, value, onChange, min, max }: { label: string; value: number; onChange: (v: number) => void; min?: number; max?: number }) {
  return (
    <div>
      <label className="text-[10px] text-zinc-500 block mb-1">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value, 10) || 0)}
        min={min}
        max={max}
        className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 font-mono"
      />
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="accent-blue-500" />
      <span className="text-[10px] text-zinc-400">{label}</span>
    </label>
  );
}

function TagList({ label, values, onChange, placeholder }: { label: string; values: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [input, setInput] = useState("");
  return (
    <div>
      <label className="text-[10px] text-zinc-500 block mb-1">{label}</label>
      <div className="flex flex-wrap gap-1 mb-1">
        {values.map((v, i) => (
          <span key={i} className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-zinc-800 border border-zinc-700 rounded text-[10px] text-zinc-300 font-mono">
            {v}
            <button onClick={() => onChange(values.filter((_, j) => j !== i))} className="text-zinc-500 hover:text-red-400">×</button>
          </span>
        ))}
      </div>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && input.trim()) {
            onChange([...values, input.trim()]);
            setInput("");
          }
        }}
        placeholder={placeholder || "Type and press Enter"}
        className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-[10px] text-zinc-200 focus:outline-none focus:border-blue-500 font-mono"
      />
    </div>
  );
}

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-zinc-800 rounded mb-2">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-3 py-1.5 text-[10px] text-zinc-400 hover:text-zinc-200 bg-zinc-900/50">
        <span className="font-medium uppercase tracking-wider">{title}</span>
        <span>{open ? "▾" : "▸"}</span>
      </button>
      {open && <div className="p-3 space-y-3">{children}</div>}
    </div>
  );
}

// --- Secrets Section (merged from SettingsTab) ---

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

function SecretsSection({ workspaceId }: { workspaceId: string }) {
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
      useCanvasStore.getState().updateNodeData(workspaceId, { needsRestart: true });
      setNewKey(""); setNewValue(""); setShowAdd(false);
      loadSecrets();
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to save"); }
  };

  const handleDelete = async (key: string) => {
    setError(null);
    try {
      await api.del(`/workspaces/${workspaceId}/secrets/${encodeURIComponent(key)}`);
      useCanvasStore.getState().updateNodeData(workspaceId, { needsRestart: true });
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

// --- Main ConfigTab ---

export function ConfigTab({ workspaceId }: Props) {
  const [config, setConfig] = useState<ConfigData>({ ...DEFAULT_CONFIG });
  const [originalYaml, setOriginalYaml] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [rawMode, setRawMode] = useState(false);
  const [rawDraft, setRawDraft] = useState("");
  const successTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    return () => clearTimeout(successTimerRef.current);
  }, []);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ content: string }>(`/workspaces/${workspaceId}/files/config.yaml`);
      const parsed = parseYaml(res.content);
      setOriginalYaml(res.content);
      setRawDraft(res.content);
      setConfig({ ...DEFAULT_CONFIG, ...parsed } as ConfigData);
    } catch {
      setError("No config.yaml found");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const update = <K extends keyof ConfigData>(key: K, value: ConfigData[K]) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const updateNested = <K extends keyof ConfigData>(key: K, subKey: string, value: unknown) => {
    setConfig((prev) => ({
      ...prev,
      [key]: { ...(prev[key] as Record<string, unknown>), [subKey]: value },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const content = rawMode ? rawDraft : toYaml(config);
      await api.put(`/workspaces/${workspaceId}/files/config.yaml`, { content });
      useCanvasStore.getState().updateNodeData(workspaceId, { needsRestart: true });
      setOriginalYaml(content);
      if (rawMode) {
        const parsed = parseYaml(content);
        setConfig({ ...DEFAULT_CONFIG, ...parsed } as ConfigData);
      } else {
        setRawDraft(content);
      }
      setSuccess(true);
      clearTimeout(successTimerRef.current);
      successTimerRef.current = setTimeout(() => setSuccess(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const isDirty = rawMode ? rawDraft !== originalYaml : toYaml(config) !== originalYaml;

  if (loading) {
    return <div className="p-4 text-xs text-zinc-500">Loading config...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Mode toggle */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-zinc-800/40 bg-zinc-900/30">
        <span className="text-[10px] text-zinc-500">config.yaml</span>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <span className="text-[9px] text-zinc-500">Raw YAML</span>
          <input
            type="checkbox"
            checked={rawMode}
            onChange={(e) => {
              if (e.target.checked) {
                setRawDraft(toYaml(config));
              } else {
                const parsed = parseYaml(rawDraft);
                setConfig({ ...DEFAULT_CONFIG, ...parsed } as ConfigData);
              }
              setRawMode(e.target.checked);
            }}
            className="accent-blue-500"
          />
        </label>
      </div>

      {rawMode ? (
        <div className="flex-1 p-3">
          <textarea
            value={rawDraft}
            onChange={(e) => setRawDraft(e.target.value)}
            spellCheck={false}
            className="w-full h-full min-h-[300px] bg-zinc-800 border border-zinc-700 rounded p-3 text-xs font-mono text-zinc-200 focus:outline-none focus:border-blue-500 resize-none"
          />
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <Section title="General">
            <TextInput label="Name" value={config.name} onChange={(v) => update("name", v)} />
            <TextInput label="Description" value={config.description} onChange={(v) => update("description", v)} />
            <div className="grid grid-cols-2 gap-3">
              <TextInput label="Version" value={config.version} onChange={(v) => update("version", v)} mono />
              <div>
                <label className="text-[10px] text-zinc-500 block mb-1">Tier</label>
                <select
                  value={config.tier}
                  onChange={(e) => update("tier", parseInt(e.target.value, 10))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                >
                  <option value={1}>T1 — Sandboxed</option>
                  <option value={2}>T2 — Standard</option>
                  <option value={3}>T3 — Full Access</option>
                </select>
              </div>
            </div>
          </Section>

          <Section title="Runtime">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] text-zinc-500 block mb-1">Runtime</label>
                <select
                  value={config.runtime || ""}
                  onChange={(e) => update("runtime", e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                >
                  <option value="">LangGraph (default)</option>
                  <option value="claude-code">Claude Code</option>
                  <option value="codex">Codex</option>
                  <option value="ollama">Ollama</option>
                </select>
              </div>
              <TextInput label="Model" value={config.runtime_config?.model || config.model || ""} onChange={(v) => {
                if (config.runtime) {
                  update("runtime_config", { ...config.runtime_config, model: v });
                } else {
                  update("model", v);
                }
              }} placeholder="e.g. anthropic:claude-sonnet-4-6" mono />
            </div>
            {config.runtime === "claude-code" && (
              <TextInput label="Auth Token File" value={config.runtime_config?.auth_token_file || ""} onChange={(v) => updateNested("runtime_config" as keyof ConfigData, "auth_token_file", v)} placeholder=".auth-token" mono />
            )}
          </Section>

          <Section title="Skills & Tools" defaultOpen={false}>
            <TagList label="Skills" values={config.skills || []} onChange={(v) => update("skills", v)} placeholder="e.g. code-review" />
            <TagList label="Tools" values={config.tools || []} onChange={(v) => update("tools", v)} placeholder="e.g. web_search, filesystem" />
            <TagList label="Prompt Files" values={config.prompt_files || []} onChange={(v) => update("prompt_files", v)} placeholder="e.g. system-prompt.md" />
            <TagList label="Shared Context" values={config.shared_context || []} onChange={(v) => update("shared_context", v)} placeholder="e.g. architecture.md" />
          </Section>

          <Section title="A2A Protocol" defaultOpen={false}>
            <NumberInput label="Port" value={config.a2a?.port ?? 8000} onChange={(v) => updateNested("a2a" as keyof ConfigData, "port", v)} />
            <Toggle label="Streaming" checked={config.a2a?.streaming ?? true} onChange={(v) => updateNested("a2a" as keyof ConfigData, "streaming", v)} />
            <Toggle label="Push Notifications" checked={config.a2a?.push_notifications ?? true} onChange={(v) => updateNested("a2a" as keyof ConfigData, "push_notifications", v)} />
          </Section>

          <Section title="Delegation" defaultOpen={false}>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput label="Retry Attempts" value={config.delegation?.retry_attempts ?? 3} onChange={(v) => updateNested("delegation" as keyof ConfigData, "retry_attempts", v)} min={0} max={10} />
              <NumberInput label="Retry Delay (s)" value={config.delegation?.retry_delay ?? 5} onChange={(v) => updateNested("delegation" as keyof ConfigData, "retry_delay", v)} min={1} />
            </div>
            <NumberInput label="Timeout (s)" value={config.delegation?.timeout ?? 120} onChange={(v) => updateNested("delegation" as keyof ConfigData, "timeout", v)} min={10} />
            <Toggle label="Escalate on failure" checked={config.delegation?.escalate ?? true} onChange={(v) => updateNested("delegation" as keyof ConfigData, "escalate", v)} />
          </Section>

          <Section title="Sandbox" defaultOpen={false}>
            <div>
              <label className="text-[10px] text-zinc-500 block mb-1">Backend</label>
              <select
                value={config.sandbox?.backend || "docker"}
                onChange={(e) => updateNested("sandbox" as keyof ConfigData, "backend", e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
              >
                <option value="subprocess">subprocess</option>
                <option value="docker">docker</option>
                <option value="e2b">e2b</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <TextInput label="Memory Limit" value={config.sandbox?.memory_limit || "256m"} onChange={(v) => updateNested("sandbox" as keyof ConfigData, "memory_limit", v)} mono />
              <NumberInput label="Timeout (s)" value={config.sandbox?.timeout ?? 30} onChange={(v) => updateNested("sandbox" as keyof ConfigData, "timeout", v)} min={5} />
            </div>
          </Section>

          <Section title="Environment" defaultOpen={false}>
            <TagList label="Required" values={config.env?.required || []} onChange={(v) => updateNested("env" as keyof ConfigData, "required", v)} placeholder="e.g. ANTHROPIC_API_KEY" />
            <TagList label="Optional" values={config.env?.optional || []} onChange={(v) => updateNested("env" as keyof ConfigData, "optional", v)} placeholder="e.g. GITHUB_TOKEN" />
          </Section>

          <SecretsSection workspaceId={workspaceId} />
        </div>
      )}

      {error && (
        <div className="mx-3 mb-2 px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">{error}</div>
      )}
      {success && (
        <div className="mx-3 mb-2 px-3 py-1.5 bg-green-900/30 border border-green-800 rounded text-xs text-green-400">Saved</div>
      )}

      <div className="p-3 border-t border-zinc-800 flex gap-2">
        <button
          onClick={handleSave}
          disabled={!isDirty || saving}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-xs rounded text-white disabled:opacity-30 transition-colors"
        >
          {saving ? "Saving..." : "Save"}
        </button>
        <button
          onClick={loadConfig}
          className="px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-xs rounded text-zinc-300 ml-auto"
        >
          Reload
        </button>
      </div>
    </div>
  );
}
