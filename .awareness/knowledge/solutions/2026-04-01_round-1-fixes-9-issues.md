---
id: kc_mnfppfzz_e1d9827d
category: problem_solution
confidence: 0.7
tags: [code-review, canvas, bug-fix, error-handling]
created_at: 2026-04-01T07:16:14.015Z
---

# Round 1 fixes (9 issues)

1. Extracted shared StatusDot component + STATUS_COLORS constant — removed 3x duplication 2. ChatTab: changed from direct fetch to agent URL → platform API proxy (POST /workspaces/:id/a2a) — critical fix for CORS/network 3. ConfigTab: fixed double JSON.parse — parse once, reuse result 4. Added error states to replace silent catch(() => {}) in DetailsTab loadPeers, MemoryTab loadMemory, EventsTab loadEvents 5. WorkspaceNode: used NodeProps<Node<WorkspaceNodeData>> generic instead of `data as unknown as WorkspaceNodeData` 6. removeNode: re-parents children to deleted node's parent instead of orphaning them 7. ChatTab: added crypto.randomUUID() id to ChatMessage for stable React keys (was using array index) 8. MemoryTab: handleDelete shows error to user instead of console.error 9. Removed redundant `as PanelTab` type assertion in canvas store
