# Appendix A — Deferred Coverage

What this suite deliberately does **not** test, and why. A reader comparing coverage against the
design documents can use this table to tell "untested" from "broken".

Every row was checked against the installed source. "Module absent" means the file does not exist
in `src/freecad_buddy/`. "Not in `tool_specs()`" means the tool name never reaches `tools/list`.

## Deferred items

| Item | Epic | Status | Re-enable when |
| --- | --- | --- | --- |
| Designer loop | Epic 4 | **Module ships, no tool.** `usecases/designer_loop.py` (story 4.5) implements plan → execute → measure → repair with convergence defined as geometry ∧ visual and a hard 3-repair cap; `CAP_EXHAUSTED` is a terminal status that is never `CONVERGED`. It is **not** in `tool_specs()` — the loop is driven by the benchmark harness, not over MCP. Story 4.1 landed the measures it is graded against. | A designer tool appears in `tool_specs()`, or the loop gains a documented MCP entry point. |
| Repair loop | Epic 4 | **Ships inside the designer loop** (story 4.5), driven by the discrepancy vector plus judge findings. Its corrupted-plan taxonomy scores **sensitivity 1.000 / false-alarm 0.000** over 8 driveable planted cases + 4 controls; 2 further cases are excluded with the measurement attached (DW-122 — the dev spec cannot decide them). No MCP surface. | The loop gains a tool surface, or DW-122's two specs gain the position checks that would make those cases decidable. |
| `verify_visual` | Epic 4 | **Module ships, no tool, and unmeasured.** `usecases/verify_visual.py` + `adapters/visual_judge_client.py` (story 4.4) implement the conjunctive visual leg with schema-validated verdicts, preflight model-independence, the ≥2048 px legibility gate and a fail-closed `visual.unavailable`. **No vision credential exists on this machine**, so no image has ever reached a model and the judge's sensitivity is honestly `not_scored` (decision 017). Not in `tool_specs()`. | The tool appears in `tool_specs()`, AND an operator run measures the judge's sensitivity over its planted-fault suite. |
| `techdraw_for_judge` | Epic 4 | **Module ships, no tool.** `usecases/techdraw.py` (story 4.3) builds the three-view dimensioned sheet on a TempDoc copy — part fingerprint asserted byte-identical — composes one SVG canvas and rasterizes it at ≥2048 px through `QtSvgRasterPort` in `adapters/`. It **composes** the sheet rather than exporting a page, because `docs/decisions/016-headless-techdraw-export.md` established page export is GUI-only; that verdict is proven executably by `tests/infc/test_techdraw_probe.py` and confirmed against the running application by **TC-16** (run `2026-09-14-01`, no divergence). Not in `tool_specs()`. | A TechDraw tool ships and is reachable over MCP. |
| Parameter façade / editability | Epic 4 | **Module ships, no tool.** `usecases/parameters.py` (story 4.6) exposes driving dimensions as intent-bearing named parameters over a VarSet backend (Spreadsheet fallback written but **unexercised** — VarSet is available on both legs here, so nothing on this machine tests the fallback). `benchmarks/harness/editability.py` implements the G3.3 test per `docs/decisions/018-editability-test-definition.md`, requiring both a clean recompute **and** a proven dimension change. Not in `tool_specs()`. | A parameter tool appears in `tool_specs()`, or an environment without VarSet exercises the fallback. |
| `hosts/phase4/` service | Epic 5 | Directory absent. | The directory exists and the service has an entry point. |
| `skills_loader.py` | Epic 5 | Module absent. | The loader ships and skills are loaded at runtime, not only read by agents. |
| `robot_export.py` | Epic 6 | Module absent. | The export path ships and produces a verifiable artifact. |
| `part_import.py` | Epic 6 | Module absent. | The import path ships and has an oracle to verify against. |
| `document_object_delete` | Epic 2 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-02. |
| `query_tree_children` | Epic 2 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-02. |
| `query_parameters` | Epic 2 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-04. |
| `verify_fingerprint` | Epic 3 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-07. |
| `verify_references` | Epic 3 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-07. |
| `/healthz` endpoint | Epic 3 | Absent. A source search for `healthz` returns zero hits. The HTTP host mounts only `/mcp`. | An endpoint is added to `gui_external/entry.py`; add to TC-01. |
| Job tools | Epic 5 | No job tool of any kind in `tool_specs()`. | A job tool ships with a defined lifecycle and terminal states. |
| Assembly tools | Epic 6 | No assembly tool in `tool_specs()`. | An assembly tool ships. |
| Measurement tools | Epic 6 | No measurement tool in `tool_specs()`. | A measurement tool ships with an analytic expectation to check against. |
| `--transport http --mode inline` | n/a | **Explicitly refused by design.** The CLI exits **2** with `transport '{t}' is not available yet; use --transport stdio.` | Never, unless the CLI adds the combination. This is correct behaviour, not a gap. TC-01 asserts the refusal. |

## Notes on the CLI surface

`hosts/main.py` has one subcommand and two flags: `serve --transport {stdio,http} --mode
{inline,rpc}`. There is no `--host`, `--port`, `--version`, or `--log-level`. The two rejected
combinations both exit 2:

- `--mode rpc` with a transport other than `http` → `--mode rpc requires --transport http.`
- `--mode inline` with a transport other than `stdio` → `transport '{t}' is not available yet; use
  --transport stdio.`

The HTTP host and port are hard-coded in `gui_external/entry.py` as `_HOST="127.0.0.1"` and
`_PORT=8765`. Any test that assumes a configurable port is testing something that does not exist.

## Known deviations

Three architecture decisions are recorded in the spine but are not met by the shipped code. They
are **not** deferred — the surface exists and is testable, it just behaves differently than the
decision says. Each has a case in **TC-99**, which is an expected-fail gate, separate from the
green gate.

| AD | Decision | Shipped behaviour |
| --- | --- | --- |
| AD-3 | The MCP endpoint is authenticated | `:8765` has no auth. `gui_external/entry.py` is a bare Starlette `Mount("/mcp")` — no middleware, no bearer token, no `Origin` check, no CORS. The loopback bind is the only control. A source search for `Bearer`, `Authorization`, or `Origin` hits only FreeCAD's own `App::Origin`. |
| AD-25 | Each session gets a working directory (`snap/ exports/ audit.log tmp/`) swept at start | No session workdir. Snapshots go to `tempfile.mkdtemp` with prefix `FCB_TMP_snap_`; the audit log path is cwd-relative (`adapters/audit_log.py:23`). There is no start-of-session sweep. |
| AD-26 | A second RPC client is refused with a `-32000` busy error | `_accept_loop` is sequential: accept → serve → close → loop. A second client blocks in the accept backlog and never receives `-32000`. |

See `test-plan.md` §7 Gate 2 for how to read a TC-99 result. A TC-99 case that starts passing is a
signal to promote it into the green gate, not a regression.
