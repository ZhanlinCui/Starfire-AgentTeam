---
id: kc_mnlg5d7s_b967a7e9
category: problem_solution
confidence: 0.95
tags: [code-review, canvas, react, performance, bug-fix]
created_at: 2026-04-05T07:35:17.800Z
---

# Code review round 18 fixes

Fixed 2 critical (unbounded recursion in countDescendants, orphaned children on WORKSPACE_REMOVED), 4 warnings (full nodes array subscription perf, unsafe type cast, stale getState in render, multiple filter passes), 2 suggestions (wrapper div, empty span spacer). All in canvas components.
