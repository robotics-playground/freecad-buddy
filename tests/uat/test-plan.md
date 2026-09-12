# freecad-buddy — Manual UAT Plan (Epics 1-3 · Phases 0-2)

## 1. Overview

This suite validates the **shipped** tool surface of the FreeCAD MCP bridge: **44 tools** returned by
`tool_specs()`, plus `debug_exec` which is gated behind `FREECAD_BUDDY_ALLOW_EXEC=1`. It covers the
work of Epics 1-3 (Phases 0-2) across all three hosts: the GUI addon path, the H1 headless
single-process host, and the H2 external HTTP proxy on `http://127.0.0.1:8765/mcp`.

The suite is driven by an agent operating the real application. MCP calls go through the connected
`mcp__freecad-buddy__*` tools; GUI actions go through `cua-driver` against the live FreeCAD window.
Two existing scripts are wrapped as evidence producers, not re-derived:
`scripts/automation/run_mcp_e2e.py` (`_automation/e2e_report.json`) and
`scripts/automation/run_mcp_edge_cases.py` (`_automation/edge_report.json`).

This plan **replaces** the former `docs/tests/` plan, which was removed in commit `4cc4ee5`. That
plan covered Epic 1 / Gate G0 only and stated a tool count of "23 tools", which was already stale.
`tests/uat` is now the single home for manual UAT, per `CLAUDE.md` §9.

## 2. Scope

### In-Scope
- All 44 shipped tools: `document_*` (7), `query_*` (8), `verify_*` (6), `export_*` (3),
  `sketch_*` (8), `feature_*` (11), `preview_dry_run` (1)
- `debug_exec` behind its operator flag, including the disabled-by-default refusal
- Invariants AD-4, AD-5, AD-6, AD-7, AD-8, AD-9, AD-10, AD-17, AD-20, AD-24, AD-27, AD-28
- The GUI addon path: auto-started RPC listener plus auto-spawned MCP HTTP proxy
- H1 headless host (`serve --transport stdio --mode inline`)
- H2 HTTP proxy host (`serve --transport http --mode rpc`) on `127.0.0.1:8765`
- GUI workflows driven with `cua-driver`: menus, tree, viewport, dialogs
- Visual fidelity of MCP renders against real FreeCAD viewport screenshots

### Out-of-Scope
- Epics 4-7 work: designer loop, repair loop, `verify_visual`, TechDraw judging, Phase-4 service.
  Every deferred item and its reason is listed in `APPENDIX-A-deferred-coverage.md`.
- The three known AD conformance gaps (AD-3, AD-25, AD-26). They are recorded in TC-99 as
  expected-fail cases and are **not** part of the green gate.
- The two internal RPC-only tools `export_self_read_stl` and `export_self_read_3mf`. They are
  filtered out of `tools/list` by design; their absence is asserted in TC-01, nothing else.

## 3. Design References

| Document | Path | Covers |
| --- | --- | --- |
| MCP tools design | `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md` | tool surface, envelopes, read-only profile |
| Verification design | `.../design/verification-design.md` | fingerprint, verify_shape/export, bands, oracles |
| Data contracts | `.../design/data-contracts-design.md` | ResultEnvelope, closed status set, fingerprint |
| MCP↔FreeCAD integration | `.../design/integration-mcp-freecad.md` | offscreen render, subgraph, AA |
| Architecture spine | `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md` | AD-1..AD-28 decision records |
| Automation & verification standard | `.knowledge-base/technical/standards/testing/freecad-automation-verification.md` | H1 harness, env, invariants, traps |
| FreeCAD source-verify standard | `.knowledge-base/technical/standards/freecad/source-verify.md` | how to confirm FreeCAD behavior from source |

Design documents have drifted from the code. The installed code wins. Where a checkpoint quotes a
message string, a schema, or a tool count, that value was read from the source, not from a design
document.

## 4. Test Environment

### Prerequisites
- FreeCAD 1.1.1 installed at `C:\Program Files\FreeCAD 1.1\bin\freecad.exe`
- Addon linked at `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy` (a symlink to the repo
  `src/freecad_buddy`). Note `%APPDATA%\FreeCAD\Mod\` is legacy and empty.
- micromamba `fcb` env (FreeCAD + `mcp` in one interpreter) for the H1 legs
- Repo `uv` env (`.venv`, Python 3.12.12) for the client and the sweep scripts
- `cua-driver` daemon running in an interactive session (Session ID ≥ 1)
- Golden models under `benchmarks/g0/golden-models/*.FCStd`
- Fault fixtures under `benchmarks/g0/fault-injection/` and `benchmarks/g0/export-fault-injection/`

Full step-by-step setup with per-step verify commands is in `APPENDIX-B-environment-setup.md`.

### Setup Commands
```bash
# H1-capable interpreter check
"$USERPROFILE/micromamba/envs/fcb/python.exe" -c "import FreeCAD, mcp; print('H1 ok')"

# cua-driver daemon check (SessionId must be >= 1)
cua-driver status

# Proxy must be LISTENING with no manual serve command
netstat -ano | findstr :8765
```

### Environment Variables

| Variable | Purpose | Example |
| --- | --- | --- |
| `FREECAD_BUDDY_ALLOW_EXEC` | enable `debug_exec`; must be exactly `"1"` | `1` |
| `FREECAD_BUDDY_AUTO_APPROVE` | bypass the confirm gate; must be exactly `"1"` | `1` |
| `FREECAD_BUDDY_AUDIT_LOG` | audit log path; default is cwd-relative `freecad-buddy-audit.jsonl` | `_automation/audit.jsonl` |
| `FREECAD_BUDDY_LOG_FILE` | addon log path | `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log` |
| `FREECAD_BUDDY_RPC_PORT` | fix the RPC listener port; a non-int value warns and falls back to ephemeral | `47111` |
| `FREECAD_BUDDY_RPC_DIR` | directory for the RPC discovery file (mode `0o600`) | `%TEMP%\fcb-rpc` |
| `FREECAD_BUDDY_MCP_CMD` | verbatim proxy launch command; space-split, no quoting support | `C:\path\python.exe -m ...` |
| `FREECAD_BUDDY_REPO` | legacy `uv` fallback for proxy launch | `D:\Work\Personal\Sources\freecad-buddy` |
| `FREECAD_BUDDY_SRC` | source root override | `D:\...\src` |
| `FREECAD_BUDDY_NO_AUTO_MCP` | suppress proxy auto-spawn; evaluated for **truthiness**, not `"1"` | `1` |

## 5. Test Case Index

| TC-ID | Name | Priority | Category | Design Ref |
| --- | --- | --- | --- | --- |
| TC-01 | Session lifecycle & transport | Critical | Session/Core | mcp-tools-design, spine §AD-2, §AD-12 |
| TC-02 | Document ingestion & handles | Critical | Session/Core | mcp-tools-design §documents |
| TC-03 | Sketch authoring | Critical | Modelling | mcp-tools-design §sketch |
| TC-04 | Feature modelling | Critical | Modelling | mcp-tools-design §feature |
| TC-05 | Mutation protocol & rollback | Critical | Mutation | verification-design §1 (run_mutation), §2, §3 |
| TC-06 | Render & GUI visual fidelity | Critical | Quality/Output | integration-mcp-freecad |
| TC-07 | Verification & export pairing | Critical | Verification | verification-design §6 |
| TC-08 | Preview/confirm & undo | Critical | Mutation | mcp-tools-design §3.8, §4 (Confirm) |
| TC-09 | Error contract & fault injection | Critical | Error handling | data-contracts-design §status |
| TC-10 | Concurrency, timeout & quarantine | High | Resilience | spine §AD-26, §AD-27 |
| TC-11 | Security posture & artifact hygiene | High | Security | spine §AD-3, §AD-25, global/security |
| TC-12 | GUI workflows (maximal) | High | GUI | integration-mcp-freecad, cua-driver |
| TC-13 | GUI ↔ MCP parity (inspection + bidirectional mutation) | Critical | GUI/Parity | mcp-tools-design §1.1, integration-mcp-freecad |
| TC-99 | AD conformance gaps (EXPECTED-FAIL) | Informational | Conformance | spine §AD-3, §AD-25, §AD-26 |

## 6. Test Data

Golden models under `benchmarks/g0/golden-models/`, with analytic expectations:

| Model | Expected volume (mm³) | Notes |
| --- | --- | --- |
| `box-10-20-30` | 6000.0 | single solid |
| `cylinder-r5-h20` | 1570.7963 | single solid |
| `sphere-r10` | 4188.7902 | single solid |
| `box40-hole-r5` | 15214.6018 | genus-1 |
| `two-box-compound` | 2000.0 | 2 solids; **centre of mass is `null`** |

Fault fixtures:
- `benchmarks/g0/fault-injection/wrong-volume/`
- `benchmarks/g0/fault-injection/non-watertight-open-shell/`
- `benchmarks/g0/export-fault-injection/`

Each fault fixture `case.yaml` carries reference `assertions.checks`. Those checks **must** be
passed into `verify_shape`. A bare `verify_shape` with no `checks` lets a wrong-but-valid shape
pass, so a fault case that omits them proves nothing.

## 7. Pass/Fail Criteria

This suite has **two independent gates**. A run reports both. They are never merged into one number.

### Gate 1 — Green gate (TC-01 .. TC-13)

This gate must be green for the suite to pass.

| Category | Pass Criteria |
| --- | --- |
| Functional | Golden volumes within 0.1 %; STEP round-trip plus STL/3MF oracle agreement |
| Quality | P0 (Critical) checkpoints 100 % pass; P1 (High) checkpoints ≥ 95 % |
| Resilience | Every invalid input and every planted fault returns the correct closed status; zero unhandled tracebacks in stderr |
| Contract | Exact message strings match the source verbatim; unknown keys are hard-rejected (`additionalProperties: false` on every input schema) |
| **Visual (mandatory)** | Any test that touches rendering or geometry MUST include a visual check: the MCP render is `Read` and compared against a **real FreeCAD viewport screenshot** of the same object and camera. Numbers alone are not sufficient, and a self-generated render alone is not sufficient — the MCP render is a constructed scene, not a viewport capture, so visual fidelity is a separately verified checkpoint. |

A failure in TC-01 .. TC-13 is a **regression**. It blocks the release.

### Gate 2 — Conformance gate (TC-99 only)

TC-99 holds cases that are **expected to fail**. Each case names the AD it tests and the shipped
behaviour that deviates from it:

- **AD-3** — `:8765` has no authentication. `gui_external/entry.py` is a bare Starlette
  `Mount("/mcp")` with no middleware, no bearer check, no `Origin` check, no CORS. The loopback
  bind is the only control.
- **AD-25** — no per-session working directory. Snapshots use `tempfile.mkdtemp`; the audit log
  path is cwd-relative (`adapters/audit_log.py:23`). There is no `snap/ exports/ audit.log tmp/`
  layout and no start-of-session sweep.
- **AD-26** — `_accept_loop` in the RPC listener is sequential (accept → serve → close → loop). A
  second client blocks in the accept backlog instead of receiving a `-32000` busy error.

Reading the result:
- A TC-99 case that **fails** is the recorded, accepted state. It does not block the release.
- A TC-99 case that **starts passing** is a signal to **promote** that case into the green gate and
  close the gap in the spine. It is not a regression and must never be reported as one.
- A TC-99 case that fails **differently** than documented is a real finding. The documented
  deviation is part of the assertion.

## 8. Known Limitations

- **Removed predecessor.** The former `docs/tests/` suite (Epic 1 / Gate G0 only, claiming "23
  tools") was deleted in commit `4cc4ee5`. Its checkpoints are recoverable from git history, but
  several had already drifted from the code — re-verify against the source before reusing any.
- **Retired parameter.** The former `docs/tests` TC-09 CP6 exercised `query_tree_summary.max_nodes`.
  That property is retired. Passing it now is a schema reject. The live filter object is closed and
  accepts exactly `types, exclude_types, renderable_only, visible_only, name_pattern`.
- **Broken harness reader.** `_automation/live_mcp_manual.py` reads `tree["nodes"]`, but the
  response key is now `"tree"`. It returns `None` silently instead of failing. Do not treat a
  `None` from that harness as an empty tree.
- **Render needs GL.** The render leg requires a GL context. Screenshot checkpoints skip when the
  render ladder reports `none`.
- **Module caching.** A running FreeCAD caches imported modules. A render-code change needs a
  FreeCAD restart in GUI mode before it takes effect.
- **H2 diverges from inline.** The H2 proxy path `gui_external/entry.py` has its own `_call_tool`.
  It does **not** carry the suspect-document logic, the non-string `doc` guard, or the audit
  writes that the inline host in `adapters/mcp_server.py` has. Any checkpoint that asserts
  `doc handle must be a string`, `the document is now suspect: ...`, or an audit-log line must
  state which host it ran under. A pass on one host is not a pass on the other.
- **cua element tokens do not persist.** `element_token` values are keyed on `(pid, window_id)` and
  are per-snapshot. `replay_trajectory` cannot re-resolve them across sessions, so a recorded
  trajectory is regression evidence only, never a re-runnable test step.
- **`--transport http --mode inline` is refused.** The CLI exits 2 with
  `transport '{t}' is not available yet; use --transport stdio.` This is by design, not a defect.
- **Client errors are quiet.** `INVALID_INPUT` and `TIMEOUT` log one INFO line, not a traceback.
  The full traceback stays in the envelope's machine `detail.data`. Unhandled faults
  (`RECOMPUTE_ERROR`, `WORKER_CRASHED`) still write a stderr traceback.
- **Default render honours visibility.** The default render (no `include`) omits objects with
  `Visibility=false`, mirroring the viewport. An explicit `include` still renders a named hidden
  object.
- **Dirty documents still render.** `query_screenshot` renders a document with a pending or broken
  recompute instead of hard-failing. The response carries `render.dirty_document: true`, and the
  before-equals-after read-only guard is skipped for an already-unstable document.
