---
id: kc_mnfppg0e_e7acb4ee
category: insight
confidence: 0.9
tags: [canvas, react, dry]
created_at: 2026-04-01T07:16:14.030Z
---

# StatusDot shared component pattern

Status color maps were duplicated 3x across WorkspaceNode, SidePanel, and DetailsTab. Extracted to shared StatusDot.tsx with exported STATUS_COLORS constant and size prop ('sm'|'md'). WorkspaceNode uses STATUS_COLORS directly for its inline dot, SidePanel/DetailsTab use the StatusDot component.
