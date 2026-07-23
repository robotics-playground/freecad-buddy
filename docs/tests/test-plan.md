# freecad-buddy — Manual Test Plan (Epic 1 · Gate G0)

## 1. Overview

The Epic-1 tool surface (the verifiable FreeCAD MCP bridge, 23 tools) is validated end-to-end
over the **real MCP stdio protocol** against a headless H1 server (FreeCAD + MCP in one
interpreter), driving real golden-model geometry. Two executable sweeps back this plan:

- `scripts/automation/run_mcp_e2e.py` — happy-path golden-model sweep (29 checks)
- `scripts/automation/run_mcp_edge_cases.py` — edge/corner/error + fault-injection sweep (13 checks)

Each test case below maps to a sweep check; the sweep is the reproducible executor and its JSON
report (`_automation/e2e_report.json`, `_automation/edge_report.json`) is the evidence artifact.

## 2. Scope

### In-Scope
- Document lifecycle (create/open/save/close/list/recompute)
- Read-only queries (tree, object, mass-properties, dependencies, sketch, placement)
- Verification (verify_shape, verify_export_*, fault detection)
- Exports with paired verification (STEP/STL/3MF)
- View-controlled screenshots (offscreen render, read-only invariance)
- Error contract: the closed terminal-status set over MCP

### Out-of-Scope
- Phase 1+ tools (mutation, copilot, designer) — later epics
- GUI-host RPC path (covered by `tests/infc` under `FreeCADCmd`; H1 is the automation target)

## 3. Design References

| Document | Path | Covers |
| --- | --- | --- |
| Verification design | `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md` | fingerprint, verify_shape/export, bands, oracles |
| MCP tools design | `.../design/mcp-tools-design.md` | tool surface, envelopes, read-only profile |
| MCP↔FreeCAD integration | `.../design/integration-mcp-freecad.md` | offscreen render, subgraph, AA |
| Data contracts | `.../design/data-contracts-design.md` | ResultEnvelope, closed status set, fingerprint |
| Automation & verification standard | `.knowledge-base/technical/standards/testing/freecad-automation-verification.md` | H1 harness, env, invariants, traps |

## 4. Test Environment

### Prerequisites
- micromamba `fcb` env (FreeCAD 1.1 + mcp + oracles) — see the automation standard
- `uv` env (MCP client) at repo root
- Golden models present under `benchmarks/g0/golden-models/*.FCStd`
- Fault fixtures under `benchmarks/g0/fault-injection/` and `benchmarks/g0/export-fault-injection/`

### Setup Commands
```bash
# H1-capable interpreter check
"$USERPROFILE/micromamba/envs/fcb/python.exe" -c "import FreeCAD, mcp; print('H1 ok')"
```

### Environment Variables
| Variable | Purpose | Example |
| --- | --- | --- |
| `FREECAD_BUDDY_AUDIT_LOG` | route the H1 audit log | `_automation/audit.jsonl` |
| `FREECAD_BUDDY_LOG_FILE` | GUI-mode addon log path | `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log` |

## 5. Test Case Index

| TC-ID | Name | Priority | Category | Design Ref |
| --- | --- | --- | --- | --- |
| TC-01 | Bridge lifecycle & happy-path tool sweep | Critical | Session/Core | mcp-tools-design |
| TC-06 | Render visual fidelity vs. real FreeCAD viewport | Critical | Quality/Output | integration-mcp-freecad |
| TC-09 | Error contract, edge/boundary & fault detection | Critical | Error handling | verification-design, data-contracts §status |

## 6. Test Data

Golden models (analytic expectations): `box-10-20-30` (6000 mm³), `cylinder-r5-h20`
(1570.796 mm³), `sphere-r10` (4188.790 mm³), `box40-hole-r5` (genus-1, 15214.602 mm³),
`two-box-compound` (2 solids, 2000 mm³). Planted-fault fixtures carry their reference `checks` in
each `case.yaml`.

## 7. Pass/Fail Criteria

| Category | Pass Criteria |
| --- | --- |
| Functional | Golden volumes within 0.1 %; STEP round-trip + STL/3MF oracle agreement |
| Quality | P0 checks 100 % pass; P1 ≥ 95 % |
| Resilience | Every invalid/fault input returns the correct closed status; zero crashes in stderr |
| **Visual (mandatory)** | Any test touching rendering/geometry MUST include a visual check: the MCP render is `Read` and compared against a **real FreeCAD viewport screenshot** of the same object/angle. Numbers and a self-generated render alone are NOT sufficient — the MCP render is a constructed scene, not a viewport capture, so visual fidelity is a separately-verified checkpoint. |

## 8. Known Limitations
- Render leg requires a GL context; screenshot checks skip when the render ladder reports `none`.
- A running FreeCAD caches imported modules — a render-code change needs a FreeCAD restart in GUI mode.
- `INVALID_INPUT` currently logs a full traceback (deferred-work ledger) — expected noise, not a crash.
