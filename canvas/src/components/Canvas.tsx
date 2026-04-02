"use client";

import { useCallback, useRef } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  useReactFlow,
  type OnNodeDrag,
  type Node,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useCanvasStore, type WorkspaceNodeData } from "@/store/canvas";
import { WorkspaceNode } from "./WorkspaceNode";
import { SidePanel } from "./SidePanel";
import { CreateWorkspaceButton } from "./CreateWorkspaceDialog";

const nodeTypes = {
  workspaceNode: WorkspaceNode,
};

export function Canvas() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}

function CanvasInner() {
  const nodes = useCanvasStore((s) => s.nodes);
  const edges = useCanvasStore((s) => s.edges);
  const onNodesChange = useCanvasStore((s) => s.onNodesChange);
  const savePosition = useCanvasStore((s) => s.savePosition);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const selectedNodeId = useCanvasStore((s) => s.selectedNodeId);
  const setDragOverNode = useCanvasStore((s) => s.setDragOverNode);
  const nestNode = useCanvasStore((s) => s.nestNode);
  const isDescendant = useCanvasStore((s) => s.isDescendant);
  const dragStartParentRef = useRef<string | null>(null);
  const { getIntersectingNodes } = useReactFlow();

  const onNodeDragStart: OnNodeDrag<Node<WorkspaceNodeData>> = useCallback(
    (_event, node) => {
      dragStartParentRef.current = (node.data as WorkspaceNodeData).parentId;
    },
    []
  );

  const onNodeDrag: OnNodeDrag<Node<WorkspaceNodeData>> = useCallback(
    (_event, node) => {
      const intersecting = getIntersectingNodes(node);
      const target = intersecting.find(
        (n) => n.id !== node.id && !isDescendant(node.id, n.id)
      );
      setDragOverNode(target?.id ?? null);
    },
    [getIntersectingNodes, isDescendant, setDragOverNode]
  );

  const onNodeDragStop: OnNodeDrag<Node<WorkspaceNodeData>> = useCallback(
    (_event, node) => {
      const { dragOverNodeId } = useCanvasStore.getState();
      setDragOverNode(null);

      if (dragOverNodeId) {
        nestNode(node.id, dragOverNodeId);
      } else {
        // Dropped on empty canvas — un-nest if previously nested
        const currentParentId = (node.data as WorkspaceNodeData).parentId;
        if (currentParentId) {
          nestNode(node.id, null);
        }
      }

      savePosition(node.id, node.position.x, node.position.y);
    },
    [savePosition, setDragOverNode, nestNode]
  );

  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  return (
    <div className="w-screen h-screen">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onNodeDragStart={onNodeDragStart}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{ animated: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#27272a"
        />
        <Controls className="!bg-zinc-800 !border-zinc-700 !text-zinc-300" />
        <MiniMap
          className="!bg-zinc-900 !border-zinc-700"
          nodeColor={(node) => {
            const status = (node.data as Record<string, unknown>)?.status;
            switch (status) {
              case "online":
                return "#22c55e";
              case "offline":
                return "#71717a";
              case "degraded":
                return "#eab308";
              case "failed":
                return "#ef4444";
              case "provisioning":
                return "#3b82f6";
              default:
                return "#52525b";
            }
          }}
        />
      </ReactFlow>

      <SidePanel />
      {!selectedNodeId && <CreateWorkspaceButton />}
    </div>
  );
}
