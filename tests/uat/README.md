# tests/uat — Manual UAT Suite

Agent-driven acceptance tests for the shipped freecad-buddy surface: the **45 typed tools** plus
`script_exec`, which is on by default, across Epics 1-3 and Epic 8. A run reads the tool count from
`tools/list` and the FreeCAD version from `query_capabilities.freecad_version`.

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
  lines in the same scenario. For a scenario the scripted runner executes, the agent reads only the
  captures of the runner's review set; the scripted pixel check grades the rest (`test-plan.md` §9).
- **A fit runs immediately before every visual `Then`** — an object outside the frame produces a
  screenshot that cannot be distinguished from a real defect. Default is
  `mcp view_fit_viewport`; where that tool is itself under test, unavailable, or returns anything
  but `OK`, fit through the GUI instead — on FreeCAD 1.1.x that is the **Fit All** toolbar button
  clicked by `element_token`, because `invoke_menu(["View","Fit All"])` is refused
  (`menu_path_unavailable`). Golden and fault models open with every object hidden: run
  the `Show All Objects` leaf of View > Visibility (pressed by `element_token`) before their fit. See `test-plan.md` §3
  rule 5.

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
3. **Run FreeCAD in the `fcb-desktop` container, never on the host.** Setup:
   `tests/close-loop/README.md`. Stop FreeCAD first and verify it: `fcb-freecad status` in the
   container shows no FreeCAD pid, and no document may be open once it is launched. Launch it with
   `docker exec -u cua fcb-desktop fcb-freecad start` so the addon auto-spawns the proxy; the host
   reaches it at `http://127.0.0.1:18765/mcp`. Starting the proxy by hand invalidates TC-01-01.
   Tool arguments use container paths (`test-plan.md` §6). The container FreeCAD shows
   its widget tree to `cua-driver` (`get_window_state`, `element_token` clicks). The driver's own
   `invoke_menu` refuses FreeCAD's menu bar, so a menu step is an
   `element_token` press of the menu leaf (`test-plan.md` §6, "Menu route"), a pixel click or a
   keyboard route; a step with no such route is `NOT RUN`. The scripted runner runs in the container (`tests/uat/runner/README.md`).
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
8. **The agent judges the visual of every scenario with no scenario file, and of every capture in
   the runner's review set.** The review set has five reasons: `fail`, `escalate`,
   `no pixel check`, `first of TC-xx` and a 20 % `sample` (`test-plan.md` §9). Each reviewed
   capture gets a complete visual comparison, recorded as one line per scenario in `report.md`.
   The scripted pixel check grades every other runner capture. When a reviewed capture contradicts
   a scripted `PASS`, the scenario is `FAIL`, the pixel-check defect goes to `bugs.md`, and the
   agent reads every remaining capture of that test case (reason `test case re-read`). When a
   reviewed capture shows a visual `Then` met although the pixel check reported a finding, the
   agent's verdict stands for that visual `Then`, other findings still stand, and the false alarm
   goes to `bugs.md`. Never accept an MCP render as the visual
   evidence. The MCP render is produced by the code under test; a `cua-driver` capture of the
   window is independent. Where the two disagree, record which is wrong as a finding.
9. **Run the watchdog between test cases.** A dead harness does not announce itself — a lapsed
   `cua-driver` session answers a plain-text refusal and the next capture silently writes nothing,
   so a run stalls rather than fails. One pass takes under a second:

   ```bash
   docker exec -u cua fcb-desktop fcb-py /repo/scripts/automation/uat_watchdog.py \
       --pid <freecad-pid> --window <window-id> --since "<run start ISO with UTC offset>"
   ```

   It checks the `cua-driver` session (reviving a lapsed one in place and saying so), the FreeCAD
   window, an `initialize` handshake against `:8765` — a LISTENING socket alone is not proof — and
   reserved-prefix temp hygiene. Exit 1 names the first failure. `--since` makes a snapshot
   directory created after that timestamp a stop-the-line condition: a surviving `FCB_TMP_snap_*`
   means a mutation bracket did not close, which voids the snapshot assertions of every scenario
   after it.

   `--since` needs a UTC offset, because the container clock zone differs from the host's. Give
   the run start with the host's offset, for example `--since "$(date +%Y-%m-%dT%H:%M:%S%z)"` in a
   host shell (`2026-11-18T09:30:00+0700`) or `+07:00`.

## Reporting

`run/<date>-<NN>/report.md` lists every scenario with its verdict and, for a failure, the exact
command, the raw output, and the `file:line` or verbatim message string that was expected. Findings
go to `bugs.md` in the same folder. The summary reports both gates separately and names any TC-99
scenario that changed state. For runner scenarios, `report.md` also holds the review line of each
reviewed capture, and its verdict is final over the runner's `results.json` (`test-plan.md` §9).

Sweep-script evidence (`run_mcp_e2e.py`, `run_mcp_edge_cases.py`) is copied into
`$RUN_DIR/evidence/` rather than left in `_automation/`, so the run folder is self-contained.
