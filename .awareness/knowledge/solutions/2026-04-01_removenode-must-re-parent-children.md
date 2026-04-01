---
id: kc_mnfppg0e_2156aab2
category: problem_solution
confidence: 0.95
tags: [canvas, zustand, hierarchy]
created_at: 2026-04-01T07:16:14.030Z
---

# removeNode must re-parent children

When deleting a workspace node, its children must be re-parented to the deleted node's parent (or become root-level). Without this, children become orphaned with dangling parentId references and missing edges.
