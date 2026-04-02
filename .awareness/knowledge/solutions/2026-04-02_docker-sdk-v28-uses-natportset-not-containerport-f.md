---
id: kc_mngus0z9_e7f0b33d
category: problem_solution
confidence: 1
tags: [docker, go, provisioner]
created_at: 2026-04-02T02:25:58.773Z
---

# Docker SDK v28 uses nat.PortSet not container.Port for ExposedPorts

github.com/docker/docker@v28.2.2+incompatible changed ExposedPorts from map[container.Port]struct{} to nat.PortSet. Need to import github.com/docker/go-connections/nat and use nat.Port(). Also requires many transitive deps (go-units, errdefs, otelhttp, etc.).
