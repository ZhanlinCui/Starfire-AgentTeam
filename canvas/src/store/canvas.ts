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
}

interface CanvasState {
  nodes: Node<WorkspaceNodeData>[];
  edges: Edge[];
  hydrate: (workspaces: WorkspaceData[]) => void;
  applyEvent: (msg: WSMessage) => void;
  onNodesChange: (changes: NodeChange<Node<WorkspaceNodeData>>[]) => void;
  savePosition: (nodeId: string, x: number, y: number) => void;
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
