# Coverage Matrix

Generated from the finished test-case files and from `tool_specs()`, not authored by hand. Regenerate
this file whenever the tool surface changes or a TC file gains scenarios — a matrix that drifts from
the suite is worse than no matrix.

**Verification command** (this is the check, not an eyeball):

```bash
.venv/Scripts/python.exe -c "
import re,sys,pathlib
sys.path.insert(0,'src')
from freecad_buddy.hosts.tool_catalog import tool_specs
corpus=''.join(p.read_text(encoding='utf-8') for p in pathlib.Path('tests/uat/testcases').glob('TC-*.md'))
missing=[t.name for t in tool_specs() if t.name not in corpus]
print('shipped:',len(tool_specs()),'missing:',missing or 'none')
"
```

Expected output: `shipped: 45 missing: none`.

## 1. Suite totals

| Metric | Value |
| --- | --- |
| Test-case files | 15 (TC-01..TC-14 green gate, TC-99 conformance gate) |
| Scenarios | 259 |
| Checkpoints | 1637 |
| Shipped tools covered | 45 / 45 |
| Green-gate scenarios | 251 |
| Conformance-gate scenarios (expected-fail) | 8 |

## 2. Scenario allocation by file

`Primary` names the file that owns each tool's dedicated scenarios. `Driver` is how the scenarios
are executed: **GUI** = `cua-driver` against the live FreeCAD window, **MCP** = the connected
`mcp__freecad-buddy__*` tools, **H1** = the headless stdio host.

| TC | Title | Gate | Pri | Driver | Scenarios | CPs |
| --- | --- | --- | --- | --- | --- | --- |
| TC-01 | Session lifecycle & transport | green | Critical | GUI+MCP+H1 | 14 | 94 |
| TC-02 | Document ingestion & handles | green | Critical | GUI+MCP | 18 | 139 |
| TC-03 | Sketch authoring | green | Critical | MCP+GUI | 21 | 145 |
| TC-04 | Feature modelling | green | Critical | MCP+GUI | 24 | 181 |
| TC-05 | Mutation protocol & rollback | green | Critical | MCP+H1 | 18 | 112 |
| TC-06 | Render & GUI visual fidelity | green | Critical | **GUI** | 12 | 75 |
| TC-07 | Verification & export pairing | green | Critical | MCP+H1 | 21 | 137 |
| TC-08 | Preview, confirm & undo | green | Critical | MCP+GUI | 21 | 138 |
| TC-09 | Error contract & fault injection | green | Critical | MCP+H1 | 23 | 153 |
| TC-10 | Concurrency, timeout & quarantine | green | High | MCP×2+H1 | 14 | 86 |
| TC-11 | Security posture & artifact hygiene | green | High | MCP+GUI | 16 | 109 |
| TC-12 | GUI workflows (maximal) | green | High | **GUI** | 15 | 98 |
| TC-13 | GUI ↔ MCP parity | green | Critical | **GUI+MCP** | 18 | 123 |
| TC-14 | Viewport framing & auto-fit | green | Critical | **GUI+MCP+H1** | 16 | 88 |
| TC-99 | AD conformance gaps | conformance | — | MCP×2 | 8 | 47 |

## 3. Tool → TC coverage

Every one of the 45 shipped tools has an owning file. `Also in` lists files that exercise the tool
as a supporting step.

### `document_` (7)

| Tool | Mut | TO (s) | Primary | Also in |
| --- | --- | --- | --- | --- |
| `document_create` | yes | 30 | TC-02 | 01, 03, 04, 07, 08, 09, 10 |
| `document_open` | yes | 60 | TC-02 | 01, 04, 05, 06, 07, 09, 10, 11, 12 |
| `document_save` | yes | 120 | TC-02 | 08, 11 |
| `document_close` | yes | 30 | TC-02 | 01, 03, 04, 05, 06, 07, 08, 09, 11, 12 |
| `document_recompute` | yes | 120 | TC-02 | 03, 06, 12 |
| `document_undo` | yes | 120 | TC-08 | 02, 05, 12 |
| `document_list` | no | 30 | TC-02 | 01, 05, 06, 07, 08, 09, 10, 11, 12 |

### `query_` (8, all read-only)

| Tool | TO (s) | Primary | Also in |
| --- | --- | --- | --- |
| `query_capabilities` | 30 | TC-01 | 02, 03, 04, 05, 06, 07, 08, 09, 11, 12 |
| `query_screenshot` | 60 | TC-06 | 01, 02, 08, 10, 11, 12 |
| `query_tree_summary` | 30 | TC-02 | 01, 03, 04, 05, 06, 07, 08, 09, 10, 12 |
| `query_object` | 30 | TC-02 | 01, 03, 04, 05, 09, 10 |
| `query_mass_properties` | 30 | TC-04 | 01, 02, 03, 05, 06, 07, 08, 09, 12 |
| `query_dependencies` | 30 | TC-02 | 01, 03, 05, 09 |
| `query_sketch_info` | 30 | TC-03 | 01, 02, 05, 08, 09, 12 |
| `query_placement` | 30 | TC-02 | 01, 03, 04, 09, 12 |

### `verify_` (6, all read-only)

| Tool | TO (s) | Primary | Also in |
| --- | --- | --- | --- |
| `verify_shape` | 60 | TC-07 | 01, 02, 03, 04, 05, 06, 09, 10, 12 |
| `verify_sketch` | 60 | TC-03 | 01, 04, 05, 07, 09, 10 |
| `verify_recompute` | 120 | TC-07 | 01, 03, 04, 06, 09, 10, 12 |
| `verify_export_step` | 120 | TC-07 | 01, 09, 11 |
| `verify_export_stl` | 120 | TC-07 | 01, 09 |
| `verify_export_3mf` | 120 | TC-07 | — |

### `export_` (3, all mutating, 120 s)

| Tool | Primary | Also in |
| --- | --- | --- |
| `export_step` | TC-07 | 09 |
| `export_stl` | TC-07 | 08, 09, 11 |
| `export_3mf` | TC-07 | — |

`export_3mf` and `verify_export_3mf` are covered **only** in TC-07. That is deliberate: the existing
`run_mcp_e2e.py` sweep claims STL/3MF but checks STL only, so TC-07 is the sole 3MF coverage in the
repository. Do not trim those scenarios.

### `sketch_` (8, all mutating, 120 s)

| Tool | Primary | Also in |
| --- | --- | --- |
| `sketch_create` | TC-03 | 07, 08 |
| `sketch_add_geometry` | TC-03 | 07, 08, 09 |
| `sketch_remove_geometry` | TC-03 | 05, 08 |
| `sketch_add_constraint` | TC-03 | 08 |
| `sketch_remove_constraint` | TC-03 | 08 |
| `sketch_set_datum` | TC-03 | 08 |
| `sketch_toggle_construction` | TC-03 | 08 |
| `sketch_add_external_geometry` | TC-03 | 08 |

### `feature_` (11, all mutating, 120 s)

| Tool | Primary | Also in |
| --- | --- | --- |
| `feature_pad` | TC-04 | 05, 08 |
| `feature_pocket` | TC-04 | 05, 08 |
| `feature_revolve` | TC-04 | 08 |
| `feature_hole` | TC-04 | 08 |
| `feature_fillet` | TC-04 | 05, 08, 12 |
| `feature_chamfer` | TC-04 | 05, 08 |
| `feature_pattern` | TC-04 | 05, 08, 09 |
| `feature_mirror` | TC-04 | 08 |
| `feature_datum` | TC-04 | 08 |
| `feature_body_create` | TC-04 | 03, 05, 08 |
| `feature_set_parameters` | TC-04 | 02, 03, 05, 06, 08, 09 |

### `preview_` (1) and the operator tool

| Tool | Mut | TO (s) | Primary | Also in |
| --- | --- | --- | --- | --- |
| `preview_dry_run` | no | 180 | TC-08 | 01, 05, 06, 07, 10, 11, 12 |
| `debug_exec` (gated) | yes | 30 | TC-11 | 01 |

### Not MCP tools — asserted absent

| Name | Where asserted |
| --- | --- |
| `export_self_read_stl` | TC-01-03 (`internal=True`, filtered from `tools/list`) |
| `export_self_read_3mf` | TC-01-03 (same) |
| `debug_exec` when the flag is unset | TC-01-03, TC-11-01 (unregistered, not merely erroring) |

## 3a. GUI ↔ MCP parity (TC-13)

TC-13 is the only file that asserts the two views of a document agree. It is organised by
direction, because a one-way check cannot catch a stale view on the other side.

| Direction | Scenarios | What it proves |
| --- | --- | --- |
| A — inspection parity | TC-13-01 … 07 | What MCP reports equals what FreeCAD shows: tree node set, object name and type, visibility in **both** states, mass properties, placement, render, error state |
| B — MCP mutation reaches the GUI | TC-13-08 … 13 | `document_create`, `document_open`, `feature_pad`, `feature_set_parameters`, `document_undo` and `document_close` each appear in the GUI tree, tab bar, property panel or viewport |
| C — GUI mutation reaches MCP | TC-13-14 … 18 | A GUI visibility toggle, label rename, file open, recompute and close are each observed by the bridge |

Two checkpoints in this file are worth protecting from future trimming:

- **TC-13-15 CP7** — the pass must come from `query_tree_summary` after the commit, never from the
  inline editor echoing its own value. An editor showing new text while MCP still reports the old
  label is exactly the parity defect the file exists to catch.
- **TC-13-03** — visibility is checked in **both** states. The golden models ship hidden, so a
  single-state check passes trivially and proves nothing.

## 4. AD → TC coverage

| AD | Rule | Primary | Also in |
| --- | --- | --- | --- |
| AD-2 | Process topology, addon auto-spawn, main-thread marshal | TC-01 | 10, 12 |
| AD-3 | Transport, loopback bind, per-session RPC token | TC-11 | 01 · **gap in TC-99-01/02** |
| AD-4 | Typed tools are the only mutation path; `debug_exec` gating | TC-11 | 01 |
| AD-5 | Mutation transaction protocol, proven rollback | TC-05 | 03, 04, 08 |
| AD-6 | Fingerprint, serializer tag, cross-tag comparison banned | TC-05 | 08 |
| AD-7 | TNP reference audit, `UNSUPPORTED` never clean | TC-05 | 03, 04 |
| AD-8 | Sketch PASS ⇔ `FullyConstrained` | TC-03 | 07 |
| AD-9 | Export completes only via paired verify; failed export leaves no file | TC-07 | 09 |
| AD-10 | Preview diff, confirm token, headless fail-closed | TC-08 | 05, 11 |
| AD-17 | Closed terminal status set, append-only audit log | TC-09 | 05, 10, 11 |
| AD-20 | Explicit doc handle, never `ActiveDocument`, TempDoc lifecycle | TC-02 | 08, 11, 12 |
| AD-24 | Latency budget | TC-10 | 01 · **`/healthz` gap in TC-99-08** |
| AD-25 | Session workdir, snapshot deletion on every exit path | TC-11 | 05 · **gap in TC-99-04/05/06/07** |
| AD-26 | Single client session | — | **gap in TC-99-03**; shipped serialization pinned in TC-10-03 |
| AD-27 | Post-timeout quarantine, no automatic mutation retry | TC-10 | 09 |
| AD-28 | Schema evolution, `contract_version` handshake | TC-01 | 11 |

## 5. Test-class distribution

| TC | Happy | Edge | Abnormal |
| --- | --- | --- | --- |
| TC-01 | 5 | 4 | 5 |
| TC-02 | 7 | 6 | 5 |
| TC-03 | 8 | 7 | 6 |
| TC-04 | 11 | 8 | 5 |
| TC-05 | 4 | 5 | 9 |
| TC-06 | 5 | 4 | 3 |
| TC-07 | 9 | 6 | 6 |
| TC-08 | 6 | 7 | 8 |
| TC-09 | 2 | 9 | 12 |
| TC-10 | 2 | 4 | 8 |
| TC-11 | 4 | 5 | 7 |
| TC-12 | 8 | 4 | 3 |
| TC-99 | 0 | 0 | 8 |
| **Total** | **71** | **69** | **85** |

Abnormal cases outnumber happy-path cases. That is intended: the suite exists to prove the bridge
fails correctly, not only that it succeeds. The five resilience-heavy files (TC-05, TC-08, TC-09,
TC-10, TC-11) carry 44 of the 85 abnormal scenarios.

## 6. Known coverage boundaries

These are not gaps in the matrix; they are the documented edge of the suite.

| Area | Why it is not covered | Recorded in |
| --- | --- | --- |
| Epics 4–7 (designer loop, visual judge, TechDraw, Phase-4 service, skills loader, URDF/SDF) | No source exists | `APPENDIX-A-deferred-coverage.md` |
| 6 planned-but-unshipped tools | Not in `tool_specs()` | `APPENDIX-A-deferred-coverage.md` |
| `OOM_KILLED` status | Not reachable on the GUI or H1 host; TC-09-02 asserts the status **set** is closed, not that every member is reachable | TC-09-02 |
| AD-6 cross-tag fingerprint comparison | Producing two serializer tags needs two FreeCAD builds; conditional-skip | TC-05 |
| AD-7 `UNSUPPORTED` verdict | Needs `element_map_available()` false; true on FreeCAD 1.1; conditional-skip | TC-05 |
| Snapshot-restore escalation (FreeCAD #6031) | Build- and operation-dependent; a `rolled_back_verified` result is an accepted conditional pass | TC-05 |
