---
id: kc_mnlmi4j9_39e8b7af
category: pitfall
confidence: 1
tags: [github, permissions, branch-protection]
created_at: 2026-04-05T10:33:10.773Z
---

# Branch protection requires repo admin access

gh api branches/main/protection returns 404 when the authenticated user (HongmingWang-Rabbit) is not an admin on the repo (owned by ZhanlinCui). Need admin collaborator access or repo owner to configure.
