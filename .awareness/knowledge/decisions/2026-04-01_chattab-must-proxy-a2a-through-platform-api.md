---
id: kc_mnfppg0e_a4d26960
category: decision
confidence: 0.95
tags: [canvas, a2a, architecture, cors]
created_at: 2026-04-01T07:16:14.030Z
---

# ChatTab must proxy A2A through platform API

Browser cannot directly fetch agent container URLs (Docker internal network). ChatTab uses POST /workspaces/:id/a2a to proxy messages through the Go platform. This endpoint is not yet implemented on the platform side.
