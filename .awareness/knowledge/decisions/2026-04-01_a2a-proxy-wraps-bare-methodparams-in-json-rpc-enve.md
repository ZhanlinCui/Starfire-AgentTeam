---
id: kc_mngo5i2c_d57cfb0b
category: decision
confidence: 0.95
tags: [a2a, platform, api]
created_at: 2026-04-01T23:20:30.132Z
---

# A2A proxy wraps bare method+params in JSON-RPC envelope

The POST /workspaces/:id/a2a endpoint checks if the request body already has a 'jsonrpc' field. If not, it wraps method+params into a full JSON-RPC 2.0 envelope with a generated UUID id. This lets the ChatTab send a simpler payload while the agent receives spec-compliant JSON-RPC.
