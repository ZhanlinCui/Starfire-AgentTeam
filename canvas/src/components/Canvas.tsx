"use client";

import { useCallback, useRef, useMemo } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  useReactFlow,
  type OnNodeDrag,
  type Node,
  type Edge,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useCanvasStore, type WorkspaceNodeData } from "@/store/canvas";
import { WorkspaceNode } from "./WorkspaceNode";
import { SidePanel } from "./SidePanel";
import { CreateWorkspaceButton } from "./CreateWorkspaceDialog";
import { ContextMenu } from "./ContextMenu";
import { TemplatePalette } from "./TemplatePalette";
import { BundleDropZone } from "./BundleDropZone";
import { Toolbar } from "./Toolbar";

const nodeTypes = {
  workspaceNode: WorkspaceNode,
};

const defaultEdgeOptions: Partial<Edge> = {
  animated: true,
  style: {
    stroke: "#3f3f46",
    strokeWidth: 1.5,
  },
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

  const saveViewport = useCanvasStore((s) => s.saveViewport);
  const viewport = useCanvasStore((s) => s.viewport);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const onMoveEnd = useCallback(
    (_event: unknown, vp: { x: number; y: number; zoom: number }) => {
      // Debounce viewport saves to avoid spamming the API
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        saveViewport(vp.x, vp.y, vp.zoom);
      }, 1000);
    },
    [saveViewport]
  );

  const defaultViewport = useMemo(
    () => ({ x: viewport.x, y: viewport.y, zoom: viewport.zoom }),
    // Only use the initial viewport — don't re-render on every save
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  return (
    <div className="w-screen h-screen bg-zinc-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onNodeDragStart={onNodeDragStart}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onPaneClick={onPaneClick}
        onMoveEnd={onMoveEnd}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        defaultViewport={defaultViewport}
        fitView={viewport.x === 0 && viewport.y === 0 && viewport.zoom === 1}
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
          color="#27272a"
        />
        <Controls
          className="!bg-zinc-900/90 !border-zinc-700/50 !rounded-lg !shadow-xl !shadow-black/20 [&>button]:!bg-zinc-800 [&>button]:!border-zinc-700/50 [&>button]:!text-zinc-400 [&>button:hover]:!bg-zinc-700 [&>button:hover]:!text-zinc-200"
          showInteractive={false}
        />
        <MiniMap
          className="!bg-zinc-900/90 !border-zinc-700/50 !rounded-lg !shadow-xl !shadow-black/20"
          maskColor="rgba(0, 0, 0, 0.7)"
          nodeColor={(node) => {
            const status = (node.data as Record<string, unknown>)?.status;
            switch (status) {
              case "online":
                return "#34d399";
              case "offline":
                return "#52525b";
              case "degraded":
                return "#fbbf24";
              case "failed":
                return "#f87171";
              case "provisioning":
                return "#38bdf8";
              default:
                return "#3f3f46";
            }
          }}
          nodeStrokeWidth={0}
          nodeBorderRadius={4}
        />
      </ReactFlow>

      <Toolbar />
      <BundleDropZone />
      <TemplatePalette />
      <SidePanel />
      <ContextMenu />
      {!selectedNodeId && <CreateWorkspaceButton />}
    </div>
  );
}
