---
id: mem_20260401_001613_de56
type: code_change
session_id: ses_1775027710541_ydl963
agent_role: builder_agent
tags: [canvas, react, zustand, "side-panel", "workspace-creation", ux]
created_at: "2026-04-01T07:16:13.949Z"
updated_at: "2026-04-01T07:16:13.949Z"
source: mcp
status: active
related: []
---

## What was built

Added the first major Canvas UX features beyond the initial viewer:

### New components created:
- `canvas/src/components/SidePanel.tsx` — 420px right-side panel with 5 tabs (Details, Chat, Config, Memory, Events), opens on node click
- `canvas/src/components/CreateWorkspaceDialog.tsx` — FAB "New Workspace" button + modal form (name, role, tier, parent ID), sends POST /workspaces
- `canvas/src/components/StatusDot.tsx` — Shared status indicator component (extracted from 3x duplication)
- `canvas/src/components/tabs/DetailsTab.tsx` — Inline edit name/role/tier, peer discovery via /registry/:id/peers, delete with confirmation, error feedback for save/delete
- `canvas/src/components/tabs/ChatTab.tsx` — A2A message/send to workspace agent, proxied through platform API (POST /workspaces/:id/a2a) to avoid CORS/Docker network issues
- `canvas/src/components/tabs/ConfigTab.tsx` — JSON config viewer/editor with save/reset/reload, setTimeout cleanup on unmount
- `canvas/src/components/tabs/MemoryTab.tsx` — Key/value memory browser with add/TTL support, encodeURIComponent for delete keys
- `canvas/src/components/tabs/EventsTab.tsx` — Color-coded workspace event log with 10s auto-refresh

### Modified files:
- `canvas/src/store/canvas.ts` — Added selectedNodeId, panelTab, selectNode(), setPanelTab(), getSelectedNode(), updateNodeData(), removeNode() (re-parents children to grandparent). Added url and parentId to WorkspaceNodeData. PanelTab type exported.
- `canvas/src/components/Canvas.tsx` — Integrated SidePanel + CreateWorkspaceButton, added onPaneClick to deselect nodes
- `canvas/src/components/WorkspaceNode.tsx` — Click-to-select with blue ring highlight, provisioning pulse animation, uses NodeProps<Node<WorkspaceNodeData>> generic instead of unsafe double cast

### Key design decisions:
1. **ChatTab proxies through platform API** (`POST /workspaces/:id/a2a`) instead of direct fetch to agent container — browser can't reach Docker internal network
2. **removeNode re-parents children** to the deleted node's parent instead of orphaning them
3. **StatusDot extracted as shared component** to eliminate 3x duplication across WorkspaceNode, SidePanel, DetailsTab
4. **All async operations show errors to users** — no silent catch(() => {}) or console.error
