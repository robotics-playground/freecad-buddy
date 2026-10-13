# Appendix A — Deferred Coverage

What this suite deliberately does **not** test, and why. A reader comparing coverage against the
design documents can use this table to tell "untested" from "broken".

Every row was checked against the installed source. "Module absent" means the file does not exist
in `src/freecad_buddy/`. "Not in `tool_specs()`" means the tool name never reaches `tools/list`.

## Deferred items

| Item | Epic | Status | Re-enable when |
| --- | --- | --- | --- |
| Designer loop | Epic 4 | Not implemented. No designer host, no loop driver. | The designer host ships and appears in `tool_specs()` or as a documented entry point. |
| Repair loop | Epic 4 | Not implemented. | The repair loop ships with a defined success criterion for a failed recompute. |
| `verify_visual` | Epic 4 | Module absent; also one of the 6 planned-but-unshipped tool names. | The tool appears in `tool_specs()` with a schema. |
| `techdraw_for_judge` | Epic 4 | Module absent. No TechDraw tool of any kind exists. | A TechDraw tool ships and is reachable over MCP. |
| `hosts/phase4/` service | Epic 5 | Directory absent. | The directory exists and the service has an entry point. |
| `skills_loader.py` | Epic 5 | Module absent. | The loader ships and skills are loaded at runtime, not only read by agents. |
| `robot_export.py` | Epic 6 | Module absent. | The export path ships and produces a verifiable artifact. |
| `part_import.py` | Epic 6 | Module absent. | The import path ships and has an oracle to verify against. |
| `document_object_delete` | Epic 2 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-02. |
| `query_tree_children` | Epic 2 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-02. |
| `query_parameters` | Epic 2 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-04. |
| `verify_fingerprint` | Epic 3 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-07. |
| `verify_references` | Epic 3 | Planned, not shipped. Not in `tool_specs()`. | The tool appears in `tools/list`; add to TC-07. |
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

Two architecture decisions are recorded in the spine but are not met by the shipped code. They
are **not** deferred — the surface exists and is testable, it just behaves differently than the
decision says. Each has a case in **TC-99**, which is an expected-fail gate, separate from the
green gate.

| AD | Decision | Shipped behaviour |
| --- | --- | --- |
| AD-3 | The MCP endpoint is authenticated | `:8765` has no auth. `gui_external/entry.py` is a bare Starlette `Mount("/mcp")` — no middleware, no bearer token, no `Origin` check, no CORS. The loopback bind is the only control. A source search for `Bearer`, `Authorization`, or `Origin` hits only FreeCAD's own `App::Origin`. |
| AD-25 | Each session gets a working directory (`snap/ exports/ audit.log tmp/`) swept at start | No session workdir. Snapshots go to `tempfile.mkdtemp` with prefix `FCB_TMP_snap_`; the audit log path is cwd-relative (`adapters/audit_log.py:23`). There is no start-of-session sweep. |

See `test-plan.md` §7 Gate 2 for how to read a TC-99 result. A TC-99 case that starts passing is a
signal to promote it into the green gate, not a regression.
