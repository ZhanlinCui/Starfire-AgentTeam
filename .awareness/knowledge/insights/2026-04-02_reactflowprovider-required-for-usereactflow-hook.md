---
id: kc_mngus0z9_5a7470b9
category: pitfall
confidence: 0.95
tags: [react-flow, canvas]
created_at: 2026-04-02T02:25:58.773Z
---

# ReactFlowProvider required for useReactFlow hook

useReactFlow() (for getIntersectingNodes, etc.) requires the component to be inside a ReactFlowProvider. Canvas component needed to be split into outer Canvas (with provider) and inner CanvasInner (with hooks).
