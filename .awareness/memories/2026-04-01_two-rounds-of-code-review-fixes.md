---
id: mem_20260401_001613_3921
type: code_review
session_id: ses_1775027710541_ydl963
agent_role: builder_agent
tags: ["code-review", canvas, "bug-fix", "error-handling"]
created_at: "2026-04-01T07:16:13.973Z"
updated_at: "2026-04-01T07:16:13.973Z"
source: mcp
status: active
related: []
---

## Round 1 fixes (9 issues)
1. Extracted shared StatusDot component + STATUS_COLORS constant — removed 3x duplication
2. ChatTab: changed from direct fetch to agent URL → platform API proxy (POST /workspaces/:id/a2a) — critical fix for CORS/network
3. ConfigTab: fixed double JSON.parse — parse once, reuse result
4. Added error states to replace silent catch(() => {}) in DetailsTab loadPeers, MemoryTab loadMemory, EventsTab loadEvents
5. WorkspaceNode: used NodeProps<Node<WorkspaceNodeData>> generic instead of `data as unknown as WorkspaceNodeData`
6. removeNode: re-parents children to deleted node's parent instead of orphaning them
7. ChatTab: added crypto.randomUUID() id to ChatMessage for stable React keys (was using array index)
8. MemoryTab: handleDelete shows error to user instead of console.error
9. Removed redundant `as PanelTab` type assertion in canvas store

## Round 2 fixes (6 issues)
1. DetailsTab: renamed shadowed `data` variable in loadPeers to `peerList`
2. DetailsTab: replaced console.error in handleSave/handleDelete with saveError/deleteError state + UI banners
3. ConfigTab: added useRef + cleanup effect for success setTimeout (prevents state update on unmounted component)
4. MemoryTab: added encodeURIComponent(key) in delete URL to handle keys with special chars
5. DetailsTab: replaced useCanvasStore.getState().selectNode(p.id) with existing selectNode binding
6. EventsTab: moved error state declaration adjacent to other state hooks (cosmetic)
