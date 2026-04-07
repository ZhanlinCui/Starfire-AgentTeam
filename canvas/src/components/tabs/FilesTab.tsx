"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { api } from "@/lib/api";
import { useCanvasStore } from "@/store/canvas";
import { showToast } from "../Toaster";

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
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const successTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const editorRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    return () => clearTimeout(successTimerRef.current);
  }, []);

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
      useCanvasStore.getState().updateNodeData(workspaceId, { needsRestart: true });
      setFileContent(editContent);
      setSuccess("Saved");
      clearTimeout(successTimerRef.current);
      successTimerRef.current = setTimeout(() => setSuccess(null), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const requestDeleteFile = (path: string) => {
    setConfirmDelete(path);
  };

  const confirmDeleteFile = async () => {
    if (!confirmDelete) return;
    setError(null);
    try {
      await api.del(`/workspaces/${workspaceId}/files/${confirmDelete}`);
      if (selectedFile === confirmDelete) {
        setSelectedFile(null);
        setFileContent("");
        setEditContent("");
      }
      loadFiles();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    } finally {
      setConfirmDelete(null);
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

  const uploadRef = useRef<HTMLInputElement>(null);

  const handleDownloadFile = () => {
    if (!selectedFile || !fileContent) return;
    const blob = new Blob([editContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = selectedFile.split("/").pop() || "file";
    a.click();
    URL.revokeObjectURL(url);
    showToast("Downloaded", "success");
  };

  const handleDownloadAll = async () => {
    const fileEntries = files.filter((f) => !f.dir);
    const results = await Promise.allSettled(
      fileEntries.map((f) => api.get<{ content: string }>(`/workspaces/${workspaceId}/files/${f.path}`).then((res) => ({ path: f.path, content: res.content })))
    );
    const allFiles: Record<string, string> = {};
    for (const r of results) {
      if (r.status === "fulfilled") allFiles[r.value.path] = r.value.content;
    }
    const blob = new Blob([JSON.stringify(allFiles, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "workspace-files.json";
    a.click();
    URL.revokeObjectURL(url);
    showToast(`Downloaded ${Object.keys(allFiles).length} files`, "success");
  };

  const handleUploadFiles = async (fileList: FileList) => {
    setError(null);
    let uploaded = 0;
    for (const file of Array.from(fileList)) {
      const path = file.webkitRelativePath || file.name;
      const parts = path.split("/");
      const relPath = parts.length > 1 ? parts.slice(1).join("/") : parts[0];
      if (file.size > 1_000_000) continue;
      try {
        const content = await file.text();
        await api.put(`/workspaces/${workspaceId}/files/${relPath}`, { content });
        uploaded++;
      } catch { /* skip binary */ }
    }
    if (uploaded > 0) {
      showToast(`Uploaded ${uploaded} files`, "success");
      loadFiles();
    }
  };

  const handleDeleteAll = async () => {
    setError(null);
    let deleted = 0;
    for (const f of files) {
      if (f.dir) continue;
      try {
        await api.del(`/workspaces/${workspaceId}/files/${f.path}`);
        deleted++;
      } catch { /* skip */ }
    }
    setSelectedFile(null);
    setFileContent("");
    setEditContent("");
    showToast(`Deleted ${deleted} files`, "info");
    loadFiles();
  };

  const [showDeleteAll, setShowDeleteAll] = useState(false);

  const isDirty = editContent !== fileContent;

  const tree = useMemo(() => buildTree(files), [files]);

  if (loading) {
    return <div className="p-4 text-xs text-zinc-500">Loading files...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/40 bg-zinc-900/30">
        <span className="text-[10px] text-zinc-500">{files.filter((f) => !f.dir).length} files</span>
        <div className="flex gap-1.5">
          <button onClick={() => setShowNewFile(true)} className="text-[10px] text-blue-400 hover:text-blue-300" title="Create new file">
            + New
          </button>
          <input
            ref={uploadRef}
            type="file"
            // @ts-expect-error webkitdirectory
            webkitdirectory=""
            multiple
            className="hidden"
            onChange={(e) => e.target.files && handleUploadFiles(e.target.files)}
          />
          <button onClick={() => uploadRef.current?.click()} className="text-[10px] text-blue-400 hover:text-blue-300" title="Upload folder">
            Upload
          </button>
          <button onClick={handleDownloadAll} className="text-[10px] text-zinc-500 hover:text-zinc-300" title="Download all files">
            Export
          </button>
          <button onClick={() => setShowDeleteAll(true)} className="text-[10px] text-red-400/60 hover:text-red-400" title="Delete all files">
            Clear
          </button>
          <button onClick={loadFiles} className="text-[10px] text-zinc-500 hover:text-zinc-300" title="Refresh">
            ↻
          </button>
        </div>
      </div>

      {/* Delete all confirmation */}
      {showDeleteAll && (
        <div className="mx-3 mt-2 px-3 py-2 bg-red-950/30 border border-red-800/40 rounded space-y-1.5">
          <p className="text-xs text-red-300">Delete all {files.filter((f) => !f.dir).length} files? This cannot be undone.</p>
          <div className="flex gap-2">
            <button onClick={() => { handleDeleteAll(); setShowDeleteAll(false); }} className="px-2 py-0.5 bg-red-600 hover:bg-red-500 text-[10px] rounded text-white">
              Delete All
            </button>
            <button onClick={() => setShowDeleteAll(false)} className="px-2 py-0.5 bg-zinc-700 hover:bg-zinc-600 text-[10px] rounded text-zinc-300">
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mx-3 mt-2 px-3 py-1.5 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
          {error}
        </div>
      )}

      {confirmDelete && (
        <div className="mx-3 mt-2 px-3 py-2 bg-amber-950/30 border border-amber-800/40 rounded space-y-1.5">
          <p className="text-xs text-amber-300">Delete <span className="font-mono">{confirmDelete}</span>{files.find((f) => f.path === confirmDelete && f.dir) ? " and all its contents" : ""}?</p>
          <div className="flex gap-2">
            <button onClick={confirmDeleteFile} className="px-2 py-0.5 bg-red-600 hover:bg-red-500 text-[10px] rounded text-white">
              Delete
            </button>
            <button onClick={() => setConfirmDelete(null)} className="px-2 py-0.5 bg-zinc-700 hover:bg-zinc-600 text-[10px] rounded text-zinc-300">
              Cancel
            </button>
          </div>
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
              onDelete={requestDeleteFile}
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
                    onClick={handleDownloadFile}
                    className="text-[10px] text-zinc-500 hover:text-zinc-300"
                    title="Download file"
                  >
                    ↓
                  </button>
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
                  ref={editorRef}
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  onKeyDown={(e) => {
                    if ((e.metaKey || e.ctrlKey) && e.key === "s") {
                      e.preventDefault();
                      saveFile();
                    }
                    if (e.key === "Tab") {
                      e.preventDefault();
                      const el = editorRef.current;
                      if (!el) return;
                      const start = el.selectionStart;
                      const end = el.selectionEnd;
                      const val = editContent;
                      const updated = val.substring(0, start) + "  " + val.substring(end);
                      setEditContent(updated);
                      requestAnimationFrame(() => {
                        if (editorRef.current) {
                          editorRef.current.selectionStart = editorRef.current.selectionEnd = start + 2;
                        }
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
        <div
          className="group w-full flex items-center gap-1 px-2 py-0.5 text-left hover:bg-zinc-800/40 transition-colors cursor-pointer"
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          onClick={() => setExpanded(!expanded)}
        >
          <span className="text-[9px] text-zinc-500 w-3">{expanded ? "▼" : "▶"}</span>
          <span className="text-[10px]">📁</span>
          <span className="text-[10px] text-zinc-400 flex-1">{node.name}</span>
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
