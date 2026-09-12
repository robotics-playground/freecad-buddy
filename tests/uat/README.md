# tests/uat — Manual UAT Suite

Agent-driven acceptance tests for the shipped freecad-buddy surface: **44 tools** plus the gated
`debug_exec`, across Epics 1-3. This suite replaces the former `docs/tests/` suite (removed in
commit `4cc4ee5`), which covered Epic 1 only and
states a stale tool count.

## Files

- `test-plan.md` — the plan. Scope, environment, test-case index, pass/fail gates.
- `APPENDIX-A-deferred-coverage.md` — what is deliberately not tested, and why.
- `APPENDIX-B-environment-setup.md` — the setup runbook. Every step has a verify command.
- `TC-NN-*.md` — one file per test case, TC-01 through TC-13, plus TC-99.

## Two gates

| Gate | Cases | Meaning |
| --- | --- | --- |
| Green | TC-01 .. TC-13 | Must pass. P0 100 %, P1 ≥ 95 %. A failure is a regression and blocks release. |
| Conformance | TC-99 | Expected to fail. Each case names the AD gap and the shipped behaviour. A case that starts passing is a promotion signal, not a regression. |

Never merge the two into a single number.

## Execution protocol

1. **Main agent does infrastructure setup first.** Work through
   `APPENDIX-B-environment-setup.md` end to end before any test case runs. A short tool count at
   step 6 is a stop-the-line condition — do not start testing on a partial surface.
2. **One subagent per TC file.** A subagent receives exactly one `TC-NN-*.md` and executes it.
3. **Strictly sequential.** One subagent at a time. The tests share a single FreeCAD process, one
   `:8765` proxy, and one document set. Parallel runs corrupt each other's state and produce
   results that cannot be trusted.
4. **No automatic cleanup on failure.** When a checkpoint fails, stop and leave the state as it is.
   The open document, the temp snapshot under `FCB_TMP_snap_*`, the log tail, and the FreeCAD
   window are the diagnostic artifact. Run the `Cleanup` block only after all checkpoints in that
   case pass.
5. **Record the build banner.** Step 7 of the appendix captures the FreeCAD version, element map,
   serializer tag, render ladder, `exec_enabled`, package version, and contract version. A
   fingerprint or TNP result is only interpretable against the build that produced it.
6. **Visual checks are mandatory.** Any case touching rendering or geometry must compare the MCP
   render against a real FreeCAD viewport screenshot. Numbers and a self-render are not enough.

## Reports

Per-case evidence goes under `_automation/`:
- `_automation/e2e_report.json` and `_automation/edge_report.json` — the wrapped sweep scripts
- `_automation/server.stderr.log`, `_automation/edge.stderr.log` — server stderr
- `_automation/sample_render.png` — render evidence
- Screenshots taken through `cua-driver` use `screenshot_out_file` so image bytes stay out of the
  agent's context.

The run summary reports both gates separately, names every failed checkpoint with its `file:line`
or exact message string, and lists any TC-99 case that changed state.

## Setup

See `APPENDIX-B-environment-setup.md`. Short version: the cua-driver daemon must be in an
interactive session, the addon must be linked into `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\`, and
FreeCAD must be launched through `cua-driver launch_app` so the addon auto-spawns the proxy on
`:8765`. Starting the proxy by hand invalidates TC-01-01.
