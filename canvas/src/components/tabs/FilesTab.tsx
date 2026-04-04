"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

interface Props {
  workspaceId: string;
}

interface FileEntry {
  path: string;
  size: number;
  dir: boolean;
}

const FILE_ICONS: Record<string, string> = {
  ".md": "📄",
  ".yaml": "⚙",
  ".yml": "⚙",
  ".py": "🐍",
  ".ts": "💠",
  ".tsx": "💠",
  ".js": "📜",
  ".json": "{}",
  ".html": "🌐",
  ".css": "🎨",
  ".sh": "▸",
};

function getIcon(path: string, isDir: boolean): string {
  if (isDir) return "📁";
  const ext = "." + path.split(".").pop();
  return FILE_ICONS[ext] || "📄";
}

function getLang(path: string): string {
  const ext = path.split(".").pop() || "";
  const map: Record<string, string> = {
    py: "python",
    ts: "typescript",
    tsx: "typescript",
    js: "javascript",
    json: "json",
    yaml: "yaml",
    yml: "yaml",
    md: "markdown",
    html: "html",
    css: "css",
    sh: "shell",
  };
  return map[ext] || "text";
}

export function FilesTab({ workspaceId }: Props) {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");
  const [editContent, setEditContent] = useState("");
  const [loadingFile, setLoadingFile] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showNewFile, setShowNewFile] = useState(false);
  const [newFileName, setNewFileName] = useState("");

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<FileEntry[]>(`/workspaces/${workspaceId}/files`);
      setFiles(data);
    } catch {
      setFiles([]);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const openFile = async (path: string) => {
    setLoadingFile(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await api.get<{ content: string }>(`/workspaces/${workspaceId}/files/${path}`);
      setSelectedFile(path);
      setFileContent(res.content);
      setEditContent(res.content);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to read file");
    } finally {
      setLoadingFile(false);
    }
  };

  const saveFile = async () => {
    if (!selectedFile) return;
    setSaving(true);
    setError(null);
    try {
      await api.put(`/workspaces/${workspaceId}/files/${selectedFile}`, { content: editContent });
      setFileContent(editContent);
      setSuccess("Saved");
      setTimeout(() => setSuccess(null), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const deleteFile = async (path: string) => {
    setError(null);
    try {
      await api.del(`/workspaces/${workspaceId}/files/${path}`);
      if (selectedFile === path) {
        setSelectedFile(null);
        setFileContent("");
        setEditContent("");
      }
      loadFiles();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const createFile = async () => {
    if (!newFileName.trim()) return;
    setError(null);
    try {
      await api.put(`/workspaces/${workspaceId}/files/${newFileName.trim()}`, { content: "" });
      setShowNewFile(false);
      setNewFileName("");
      loadFiles();
      openFile(newFileName.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create");
    }
  };

  const isDirty = editContent !== fileContent;

  // Build tree structure
  const tree = buildTree(files);

  if (loading) {
    return <div className="p-4 text-xs text-zinc-500">Loading files...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/40 bg-zinc-900/30">
        <span className="text-[10px] text-zinc-500">{files.filter((f) => !f.dir).length} files</span>
        <div className="flex gap-1.5">
          <button onClick={() => setShowNewFile(true)} className="text-[10px] text-blue-400 hover:text-blue-300">
            + New
          </button>
          <button onClick={loadFiles} className="text-[10px] text-zinc-500 hover:text-zinc-300">
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-3 mt-2 px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        {/* File tree */}
        <div className="w-[180px] border-r border-zinc-800/40 overflow-y-auto shrink-0">
          {/* New file input */}
          {showNewFile && (
            <div className="px-2 py-1 border-b border-zinc-800/40">
              <input
                value={newFileName}
                onChange={(e) => setNewFileName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createFile()}
                placeholder="path/file.md"
                autoFocus
                className="w-full bg-zinc-800 border border-zinc-600 rounded px-1.5 py-0.5 text-[10px] text-zinc-100 font-mono focus:outline-none focus:border-blue-500"
              />
            </div>
          )}

          {files.length === 0 ? (
            <div className="px-3 py-4 text-[10px] text-zinc-600 text-center">
              No config files yet
            </div>
          ) : (
            <TreeView
              nodes={tree}
              selectedPath={selectedFile}
              onSelect={openFile}
              onDelete={deleteFile}
            />
          )}
        </div>

        {/* Editor */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedFile ? (
            <>
              {/* File header */}
              <div className="flex items-center justify-between px-3 py-1.5 border-b border-zinc-800/40 bg-zinc-900/20">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="text-[10px] opacity-50">{getIcon(selectedFile, false)}</span>
                  <span className="text-[10px] font-mono text-zinc-300 truncate">{selectedFile}</span>
                  {isDirty && <span className="text-[9px] text-amber-400">modified</span>}
                </div>
                <div className="flex items-center gap-2">
                  {success && <span className="text-[9px] text-emerald-400">{success}</span>}
                  <button
                    onClick={saveFile}
                    disabled={!isDirty || saving}
                    className="text-[10px] text-blue-400 hover:text-blue-300 disabled:opacity-30"
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                </div>
              </div>

              {/* Editor area */}
              {loadingFile ? (
                <div className="p-4 text-xs text-zinc-500">Loading...</div>
              ) : (
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  onKeyDown={(e) => {
                    // Ctrl/Cmd+S to save
                    if ((e.metaKey || e.ctrlKey) && e.key === "s") {
                      e.preventDefault();
                      saveFile();
                    }
                    // Tab inserts spaces
                    if (e.key === "Tab") {
                      e.preventDefault();
                      const start = e.currentTarget.selectionStart;
                      const end = e.currentTarget.selectionEnd;
                      const val = editContent;
                      setEditContent(val.substring(0, start) + "  " + val.substring(end));
                      requestAnimationFrame(() => {
                        e.currentTarget.selectionStart = e.currentTarget.selectionEnd = start + 2;
                      });
                    }
                  }}
                  spellCheck={false}
                  className="flex-1 w-full bg-zinc-950 p-3 text-[11px] font-mono text-zinc-200 leading-relaxed resize-none focus:outline-none"
                  style={{ tabSize: 2 }}
                />
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="text-2xl opacity-20 mb-2">📄</div>
                <p className="text-[10px] text-zinc-600">Select a file to edit</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Tree building utilities
interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children: TreeNode[];
  size: number;
}

function buildTree(files: FileEntry[]): TreeNode[] {
  const root: TreeNode[] = [];
  const dirMap = new Map<string, TreeNode>();

  // Sort: dirs first, then alphabetical
  const sorted = [...files].sort((a, b) => {
    if (a.dir !== b.dir) return a.dir ? -1 : 1;
    return a.path.localeCompare(b.path);
  });

  for (const file of sorted) {
    const parts = file.path.split("/");
    if (parts.length === 1) {
      root.push({ name: parts[0], path: file.path, isDir: file.dir, children: [], size: file.size });
    } else {
      // Find or create parent dirs
      let parentChildren = root;
      for (let i = 0; i < parts.length - 1; i++) {
        const dirPath = parts.slice(0, i + 1).join("/");
        let dirNode = dirMap.get(dirPath);
        if (!dirNode) {
          dirNode = { name: parts[i], path: dirPath, isDir: true, children: [], size: 0 };
          parentChildren.push(dirNode);
          dirMap.set(dirPath, dirNode);
        }
        parentChildren = dirNode.children;
      }
      if (!file.dir) {
        parentChildren.push({
          name: parts[parts.length - 1],
          path: file.path,
          isDir: false,
          children: [],
          size: file.size,
        });
      }
    }
  }

  return root;
}

function TreeView({
  nodes,
  selectedPath,
  onSelect,
  onDelete,
  depth = 0,
}: {
  nodes: TreeNode[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onDelete: (path: string) => void;
  depth?: number;
}) {
  return (
    <div>
      {nodes.map((node) => (
        <TreeItem
          key={node.path}
          node={node}
          selectedPath={selectedPath}
          onSelect={onSelect}
          onDelete={onDelete}
          depth={depth}
        />
      ))}
    </div>
  );
}

function TreeItem({
  node,
  selectedPath,
  onSelect,
  onDelete,
  depth,
}: {
  node: TreeNode;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onDelete: (path: string) => void;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const isSelected = selectedPath === node.path;

  if (node.isDir) {
    return (
      <div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-1 px-2 py-0.5 text-left hover:bg-zinc-800/40 transition-colors"
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
        >
          <span className="text-[9px] text-zinc-500 w-3">{expanded ? "▼" : "▶"}</span>
          <span className="text-[10px]">📁</span>
          <span className="text-[10px] text-zinc-400">{node.name}</span>
        </button>
        {expanded && (
          <TreeView
            nodes={node.children}
            selectedPath={selectedPath}
            onSelect={onSelect}
            onDelete={onDelete}
            depth={depth + 1}
          />
        )}
      </div>
    );
  }

  return (
    <div
      className={`group flex items-center gap-1 px-2 py-0.5 cursor-pointer transition-colors ${
        isSelected ? "bg-blue-900/30 text-zinc-100" : "hover:bg-zinc-800/40 text-zinc-400"
      }`}
      style={{ paddingLeft: `${depth * 12 + 20}px` }}
      onClick={() => onSelect(node.path)}
    >
      <span className="text-[9px]">{getIcon(node.name, false)}</span>
      <span className="text-[10px] flex-1 truncate font-mono">{node.name}</span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete(node.path);
        }}
        className="text-[9px] text-red-400/0 group-hover:text-red-400/60 hover:!text-red-400 transition-colors"
      >
        ✕
      </button>
    </div>
  );
}
