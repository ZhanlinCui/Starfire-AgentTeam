---
id: kc_mnlhwg7t_c0c6152d
category: problem_solution
confidence: 1
tags: [provisioner, docker, a2a, proxy, networking]
created_at: 2026-04-05T08:24:21.018Z
---

# A2A proxy requires host port mapping for local dev

When platform runs on host and agents in Docker, the A2A proxy can't reach Docker-internal URLs. Fix: bind ephemeral host port (127.0.0.1:0->8000/tcp), resolve via ContainerInspect, pre-store in DB, and preserve during agent registration.
