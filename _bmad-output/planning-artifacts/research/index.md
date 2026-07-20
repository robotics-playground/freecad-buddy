# Research Documents Index

Technical research reports resolving unclear areas in [docs/intent.md](../../../docs/intent.md). Each verified against local FreeCAD source (`docs/references/FreeCAD`, 1.1-dev) and web sources. Generated 2026-07-20.

## Phase 0 Blockers — Bridge & CI Foundation

- **[technical-freecad-mcp-servers-survey-research-2026-07-20.md](./technical-freecad-mcp-servers-survey-research-2026-07-20.md)** - Survey of 8 community FreeCAD MCP servers; partial-reuse recommendation
- **[technical-headless-freecad-ci-research-2026-07-20.md](./technical-headless-freecad-ci-research-2026-07-20.md)** - conda-forge + FreeCADCmd CI setup, version pinning strategy
- **[technical-mcp-embedding-freecad-gui-process-research-2026-07-20.md](./technical-mcp-embedding-freecad-gui-process-research-2026-07-20.md)** - Qt main-thread rules, transport choice, GUI vs headless embedding
- **[technical-offscreen-screenshot-freecadcmd-research-2026-07-20.md](./technical-offscreen-screenshot-freecadcmd-research-2026-07-20.md)** - Headless screenshots feasible natively via SoQtOffscreenRenderer
- **[technical-python-execution-sandbox-policy-research-2026-07-20.md](./technical-python-execution-sandbox-policy-research-2026-07-20.md)** - Typed-tools-only mutation path; debug.exec policy; resolves intent contradiction

## Phase 2 Blockers — Copilot Verification & Rollback

- **[technical-freecad-version-matrix-research-2026-07-20.md](./technical-freecad-version-matrix-research-2026-07-20.md)** - Drop 0.21; pin 1.0 floor, 1.1 primary
- **[technical-headless-preview-diff-channel-research-2026-07-20.md](./technical-headless-preview-diff-channel-research-2026-07-20.md)** - Dry-run-on-copy structured diff plus MCP elicitation gate
- **[technical-sketch-dof-programmatic-query-research-2026-07-20.md](./technical-sketch-dof-programmatic-query-research-2026-07-20.md)** - FullyConstrained property is the pass signal; headless-safe
- **[technical-tnp-post-mutation-reference-audit-research-2026-07-20.md](./technical-tnp-post-mutation-reference-audit-research-2026-07-20.md)** - TNP guard feasible; ~200-line audit layer, no C++ changes
- **[technical-undo-transaction-geometry-hashing-research-2026-07-20.md](./technical-undo-transaction-geometry-hashing-research-2026-07-20.md)** - Bridge-owned transactions; BRep-bytes SHA-256 rollback verification

## Phase 1/3 Blockers — Assistant, Skills & Benchmarks

- **[technical-benchmark-statistics-small-n-research-2026-07-20.md](./technical-benchmark-statistics-small-n-research-2026-07-20.md)** - Wilson CI, McNemar, repeats; 15pp criterion needs n≥40
- **[technical-cad-dataset-licenses-convertibility-research-2026-07-20.md](./technical-cad-dataset-licenses-convertibility-research-2026-07-20.md)** - Dataset license traps; use FreeCAD-native CC-BY sources
- **[technical-geometry-to-spec-assertions-research-2026-07-20.md](./technical-geometry-to-spec-assertions-research-2026-07-20.md)** - Geometry-first assertion vocabulary for machine-checkable specs
- **[technical-local-llm-mcp-tool-use-research-2026-07-20.md](./technical-local-llm-mcp-tool-use-research-2026-07-20.md)** - llama.cpp + Qwen3-30B as second backend
- **[technical-skill-token-budget-context-limits-research-2026-07-20.md](./technical-skill-token-budget-context-limits-research-2026-07-20.md)** - Selective skill loading; context-rot limits all-12 loading

## Phase 4 Blockers — Autonomous Service

- **[technical-freecad-3mf-export-fidelity-research-2026-07-20.md](./technical-freecad-3mf-export-fidelity-research-2026-07-20.md)** - 3MF writer immature; paired re-import verify tools required
- **[technical-os-level-sandboxing-service-research-2026-07-20.md](./technical-os-level-sandboxing-service-research-2026-07-20.md)** - nsjail/bubblewrap Linux, AppContainer/WSL2 Windows, egress deny-by-default
- **[technical-process-per-job-isolation-research-2026-07-20.md](./technical-process-per-job-isolation-research-2026-07-20.md)** - Warm worker pool, recycle per job, whole-tree kill
