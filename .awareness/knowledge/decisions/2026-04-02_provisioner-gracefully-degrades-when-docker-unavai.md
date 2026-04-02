---
id: kc_mngwryvm_79a13032
category: decision
confidence: 0.95
tags: [provisioner, docker, platform]
created_at: 2026-04-02T03:21:55.282Z
---

# Provisioner gracefully degrades when Docker unavailable

provisioner.New() is called in main.go and if it fails (Docker not available), prov is set to nil and handlers check for nil before provisioning. This allows the platform to run without Docker for development/testing.
