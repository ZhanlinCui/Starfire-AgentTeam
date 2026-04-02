import { create } from "zustand";
import {
  type Node,
  type Edge,
  applyNodeChanges,
  type NodeChange,
} from "@xyflow/react";
import { api } from "@/lib/api";
import type { WorkspaceData, WSMessage } from "./socket";

export interface WorkspaceNodeData extends Record<string, unknown> {
  name: string;
  status: string;
  tier: number;
  agentCard: Record<string, unknown> | null;
  activeTasks: number;
  collapsed: boolean;
  role: string;
  lastErrorRate: number;
  lastSampleError: string;
  url: string;
  parentId: string | null;
}

export type PanelTab = "details" | "chat" | "config" | "settings" | "terminal" | "memory" | "events";

interface CanvasState {
  nodes: Node<WorkspaceNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  panelTab: PanelTab;
  dragOverNodeId: string | null;
  hydrate: (workspaces: WorkspaceData[]) => void;
  applyEvent: (msg: WSMessage) => void;
  onNodesChange: (changes: NodeChange<Node<WorkspaceNodeData>>[]) => void;
  savePosition: (nodeId: string, x: number, y: number) => void;
  selectNode: (id: string | null) => void;
  setPanelTab: (tab: PanelTab) => void;
  getSelectedNode: () => Node<WorkspaceNodeData> | null;
  updateNodeData: (id: string, data: Partial<WorkspaceNodeData>) => void;
  removeNode: (id: string) => void;
  setDragOverNode: (id: string | null) => void;
  nestNode: (draggedId: string, targetId: string | null) => Promise<void>;
  isDescendant: (ancestorId: string, nodeId: string) => boolean;
}

function buildNodesAndEdges(workspaces: WorkspaceData[]) {
  const nodes: Node<WorkspaceNodeData>[] = workspaces.map((ws) => ({
    id: ws.id,
    type: "workspaceNode",
    position: { x: ws.x, y: ws.y },
    parentId: ws.parent_id ?? undefined,
    data: {
      name: ws.name,
      status: ws.status,
      tier: ws.tier,
      agentCard: ws.agent_card,
      activeTasks: ws.active_tasks,
      collapsed: ws.collapsed,
      role: ws.role,
      lastErrorRate: ws.last_error_rate,
      lastSampleError: ws.last_sample_error,
      url: ws.url,
      parentId: ws.parent_id,
    },
  }));

  // Edges from parent/child hierarchy
  const edges: Edge[] = workspaces
    .filter((ws) => ws.parent_id)
    .map((ws) => ({
      id: `edge-${ws.parent_id}-${ws.id}`,
      source: ws.parent_id!,
      target: ws.id,
      animated: true,
      style: { stroke: "#525252" },
    }));

  return { nodes, edges };
}

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  panelTab: "details",
  dragOverNodeId: null,

  selectNode: (id) => set({ selectedNodeId: id }),
  setPanelTab: (tab) => set({ panelTab: tab }),
  setDragOverNode: (id) => set({ dragOverNodeId: id }),

  isDescendant: (ancestorId, nodeId) => {
    const { nodes } = get();
    let current = nodes.find((n) => n.id === nodeId);
    while (current?.data.parentId) {
      if (current.data.parentId === ancestorId) return true;
      current = nodes.find((n) => n.id === current?.data.parentId);
    }
    return false;
  },

  nestNode: async (draggedId, targetId) => {
    const { nodes, edges } = get();
    const currentParentId = nodes.find((n) => n.id === draggedId)?.data.parentId ?? null;

    // No change needed
    if (currentParentId === targetId) return;

    // Optimistic update: move edges and parentId
    const newEdges = edges.filter(
      (e) => !(e.target === draggedId && e.source === currentParentId)
    );
    if (targetId) {
      newEdges.push({
        id: `edge-${targetId}-${draggedId}`,
        source: targetId,
        target: draggedId,
        animated: true,
        style: { stroke: "#525252" },
      });
    }

    set({
      nodes: nodes.map((n) =>
        n.id === draggedId
          ? { ...n, data: { ...n.data, parentId: targetId } }
          : n
      ),
      edges: newEdges,
    });

    // Persist to API
    try {
      await api.patch(`/workspaces/${draggedId}`, { parent_id: targetId });
    } catch {
      // Revert on failure
      set({
        nodes: get().nodes.map((n) =>
          n.id === draggedId
            ? { ...n, data: { ...n.data, parentId: currentParentId } }
            : n
        ),
        edges,
      });
    }
  },

  getSelectedNode: () => {
    const { nodes, selectedNodeId } = get();
    if (!selectedNodeId) return null;
    return nodes.find((n) => n.id === selectedNodeId) ?? null;
  },

  updateNodeData: (id, data) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, ...data } } : n
      ),
    });
  },

  removeNode: (id) => {
    const { nodes, edges, selectedNodeId } = get();
    // Re-parent children to the deleted node's parent (or root)
    const deletedNode = nodes.find((n) => n.id === id);
    const parentOfDeleted = deletedNode?.parentId;
    set({
      nodes: nodes
        .filter((n) => n.id !== id)
        .map((n) =>
          n.parentId === id
            ? { ...n, parentId: parentOfDeleted, data: { ...n.data, parentId: parentOfDeleted ?? null } }
            : n
        ),
      edges: edges
        .filter((e) => e.source !== id && e.target !== id)
        .concat(
          // Re-create edges from the grandparent to orphaned children
          edges
            .filter((e) => e.source === id)
            .filter((e) => parentOfDeleted)
            .map((e) => ({
              ...e,
              id: `edge-${parentOfDeleted}-${e.target}`,
              source: parentOfDeleted!,
            }))
        ),
      selectedNodeId: selectedNodeId === id ? null : selectedNodeId,
    });
  },

  hydrate: (workspaces: WorkspaceData[]) => {
    const { nodes, edges } = buildNodesAndEdges(workspaces);
    set({ nodes, edges });
  },

  applyEvent: (msg: WSMessage) => {
    const { nodes, edges } = get();

    switch (msg.event) {
      case "WORKSPACE_ONLINE": {
        const existing = nodes.find((n) => n.id === msg.workspace_id);
        if (existing) {
          set({
            nodes: nodes.map((n) =>
              n.id === msg.workspace_id
                ? { ...n, data: { ...n.data, status: "online" } }
                : n
            ),
          });
        }
        break;
      }

      case "WORKSPACE_OFFLINE": {
        set({
          nodes: nodes.map((n) =>
            n.id === msg.workspace_id
              ? { ...n, data: { ...n.data, status: "offline" } }
              : n
          ),
        });
        break;
      }

      case "WORKSPACE_DEGRADED": {
        set({
          nodes: nodes.map((n) =>
            n.id === msg.workspace_id
              ? {
                  ...n,
                  data: {
                    ...n.data,
                    status: "degraded",
                    lastErrorRate: (msg.payload.error_rate as number) ?? 0,
                    lastSampleError:
                      (msg.payload.sample_error as string) ?? "",
                  },
                }
              : n
          ),
        });
        break;
      }

      case "WORKSPACE_PROVISIONING": {
        const exists = nodes.find((n) => n.id === msg.workspace_id);
        if (!exists) {
          set({
            nodes: [
              ...nodes,
              {
                id: msg.workspace_id,
                type: "workspaceNode",
                position: { x: 0, y: 0 },
                data: {
                  name: (msg.payload.name as string) ?? "New Workspace",
                  status: "provisioning",
                  tier: (msg.payload.tier as number) ?? 1,
                  agentCard: null,
                  activeTasks: 0,
                  collapsed: false,
                  role: "",
                  lastErrorRate: 0,
                  lastSampleError: "",
                  url: "",
                  parentId: null,
                },
              },
            ],
          });
        }
        break;
      }

      case "WORKSPACE_REMOVED": {
        set({
          nodes: nodes.filter((n) => n.id !== msg.workspace_id),
          edges: edges.filter(
            (e) =>
              e.source !== msg.workspace_id && e.target !== msg.workspace_id
          ),
        });
        break;
      }

      case "AGENT_CARD_UPDATED": {
        set({
          nodes: nodes.map((n) =>
            n.id === msg.workspace_id
              ? {
                  ...n,
                  data: {
                    ...n.data,
                    agentCard: msg.payload.agent_card as Record<
                      string,
                      unknown
                    >,
                  },
                }
              : n
          ),
        });
        break;
      }

      default:
        break;
    }
  },

  onNodesChange: (changes) => {
    set({
      nodes: applyNodeChanges(changes, get().nodes),
    });
  },

  savePosition: async (nodeId: string, x: number, y: number) => {
    try {
      await api.patch(`/workspaces/${nodeId}`, { x, y });
    } catch (e) {
      console.error("Failed to save position:", e);
    }
  },
}));
