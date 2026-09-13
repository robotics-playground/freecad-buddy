# tests/uat — Manual UAT Suite

Agent-driven acceptance tests for the shipped freecad-buddy surface: **45 tools** plus the gated
`debug_exec`, across Epics 1-3 and Epic 8.

## Layout

```
test-plan.md                 scope, scenario format contract, gates
README.md                    this file — how to execute a run
coverage-matrix.md           tool/invariant → scenario traceability
APPENDIX-A-deferred-coverage.md   what is deliberately not tested, and why
APPENDIX-B-environment-setup.md   setup runbook; every step has a verify command
fixtures/                    fixture inventory
testcases/TC-NN-*.md         one file per test case, TC-01..TC-14 plus TC-99
run/<YYYY-MM-DD>-<NN>/       one folder per run
  report.md                  verdicts per scenario
  bugs.md                    findings raised by this run
  evidence/                  screenshots, renders, logs, json
```

## Scenario format

Test cases are written as **Given / When / Then** scenarios. There are no separate "Steps" and
"Checkpoints" blocks — the sequence and its assertions live together, so a reader never maps step 3
onto CP5. `Preconditions` (file-level) and `Cleanup` (per scenario) are kept.

The full contract, including the visual and auto-fit rules, is `test-plan.md` §3. The two rules that
change how a scenario is executed:

- **Every scenario closes with a visual `Then`, judged as a human** — a `cua-driver` pixel capture
  of the real FreeCAD window, `Read` and judged on what is actually on screen. The MCP bridge is
  the thing under test, so its statuses, envelope fields, and `query_screenshot` renders are claims
  being judged, never the evidence that judges them. Non-visual assertions stay as ordinary `Then`
  lines in the same scenario.
- **A fit runs immediately before every visual `Then`** — an object outside the frame produces a
  screenshot that cannot be distinguished from a real defect. Default is
  `mcp view_fit_viewport`; where that tool is itself under test, unavailable, or returns anything
  but `OK`, fit through the GUI instead — on FreeCAD 1.1.1 that is the **Fit All** toolbar button
  clicked by `element_token`, because `invoke_menu(["View","Fit All"])` is refused on this build
  (`menu_path_unavailable`). See `test-plan.md` §3 rule 5.

`testcases/TC-14-viewport-framing-and-auto-fit.md` is the reference example of the format.

## Two gates

| Gate | Cases | Meaning |
| --- | --- | --- |
| Green | TC-01 .. TC-14 | Must pass. P0 100 %, P1 ≥ 95 %. A failure is a regression and blocks release. |
| Conformance | TC-99 | Expected to fail. Each scenario names the AD gap and the shipped behaviour. A scenario that starts passing is a promotion signal, not a regression. |

Never merge the two into a single number.

## Execution protocol

1. **Open the run folder first.** Create `run/<YYYY-MM-DD>-<NN>/evidence/` and export
   `RUN_DIR` to it. Every evidence path in every test case is relative to `$RUN_DIR`. A run folder
   is never reused or edited by a later run.
2. **Main agent does infrastructure setup.** Work through `APPENDIX-B-environment-setup.md` end to
   end before any scenario runs. A short tool count at step 6 is a stop-the-line condition — do not
   start testing on a partial surface.
3. **Shut FreeCAD down first, and verify it.** No FreeCAD process may be running when setup starts,
   and no document may be open once it is launched. Launch it through `cua-driver launch_app` so
   the addon auto-spawns the proxy on `:8765`. Starting the proxy by hand invalidates TC-01-01.
4. **One subagent per TC file.** A subagent receives exactly one `testcases/TC-NN-*.md` and
   executes it.
5. **Strictly sequential.** One subagent at a time. The tests share a single FreeCAD process, one
   `:8765` proxy, and one document set. Parallel runs corrupt each other's state.
6. **No automatic cleanup on failure.** When a `Then` fails, stop and leave the state as it is. The
   open document, the temp snapshot under `FCB_TMP_snap_*`, the log tail, and the FreeCAD window
   are the diagnostic artifact. Run `Cleanup` only after every `Then` in that scenario passed.
7. **Record the build banner.** Step 7 of the appendix captures the FreeCAD version, element map,
   serializer tag, render ladder, `exec_enabled`, package version, and contract version. A
   fingerprint or TNP result is only interpretable against the build that produced it.
8. **The agent judges the visual, always.** Never accept an automated verdict or an MCP render as
   the visual evidence. The MCP render is produced by the code under test; a `cua-driver` capture of
   the window is independent. Where the two disagree, record which is wrong as a finding.

## Reporting

`run/<date>-<NN>/report.md` lists every scenario with its verdict and, for a failure, the exact
command, the raw output, and the `file:line` or verbatim message string that was expected. Findings
go to `bugs.md` in the same folder. The summary reports both gates separately and names any TC-99
scenario that changed state.

Sweep-script evidence (`run_mcp_e2e.py`, `run_mcp_edge_cases.py`) is copied into
`$RUN_DIR/evidence/` rather than left in `_automation/`, so the run folder is self-contained.
