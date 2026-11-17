# UAT Run Practices — Lead, Phases, Grading, Fixes

How to run a full UAT gate (`tests/uat`, TC-01..TC-14, TC-99, G3) so that it ends with a gate
verdict you can defend, and so that it does not damage the developer machine. This guide covers
the **orchestration**: who does what, in which order, and how a result becomes a verdict.

Other documents cover the parts it builds on. Read them first:

| Document | Covers |
|----------|--------|
| `tests/uat/test-plan.md` | Scenario format, gates (§9), agent review of runner captures |
| `tests/uat/README.md` | Execution protocol, watchdog, reporting |
| `tests/uat/APPENDIX-B-environment-setup.md` | Setup steps with a verify command for each |
| [freecad-gui-e2e-harness](freecad-gui-e2e-harness.md) | Launch, profile, drive, capture, shut down one FreeCAD |
| [freecad-automation-verification](freecad-automation-verification.md) | H1 env, sweeps, verification bar |
| [freecad-native-validation](freecad-native-validation.md) | Prove a measured value without MCP output |

**Environment.** Every GUI phase runs FreeCAD in the `fcb-desktop` container, never on the host
(UAT environment section of [freecad-gui-e2e-harness](freecad-gui-e2e-harness.md)). Consequences
for this guide:

- The phase-agent brief points at the container: `fcb-freecad start` and `stop` instead of a host
  launch, MCP server `freecad-buddy-docker`, GUI server `cua-driver-docker`, evidence copied out
  with `docker cp`. The launch-log row still applies; the profile column reads `container`.
- The machine-hygiene rules for the developer `user.cfg` (§5) apply only to FreeCAD or FreeCADCmd
  that still runs on the host, such as the H1 env. A container FreeCAD cannot write that file.
- The foreground rules in §6 were measured on the Windows host. In the container, drive FreeCAD
  with pixel clicks and keys (FreeCAD shows no widgets to `cua-driver` there) and record any rule
  that differs.
- Runner scenarios (`tests/uat/runner/`) are `NOT RUN` until story `10-9-uat-runner-in-container`
  ports the runner. Never run them on the host instead.

## 1. Roles

A run has one **lead** agent and a sequence of **phase agents**.

| Role | Does | Does not |
|------|------|----------|
| Lead | Opens the run folder, writes `RUN-CONTEXT.md` and the phase rules, builds the H1 env, runs or spawns the runner phase, spawns one phase agent at a time, checks each phase report, re-reads key captures, records lead grades, writes `report.md` and `bugs.md`, keeps the lead log | Drive scenarios in parallel with a phase agent. Accept a phase report without a check |
| Phase agent | Runs its scenario list from each Given, captures, grades each Then, writes verdict rows and a short report | Edit product, runner, scenarios, test cases, scripts or standards. Retry a check to get a PASS |

Rules:

- **One phase agent at a time.** There is one desktop, one `:8765` and one FreeCAD. Two GUI
  agents corrupt each other's captures and state.
- **Phase agents run on the Sonnet model** (`model: "sonnet"` on the Agent call). The lead keeps
  the grading and the visual spot checks, so the evidence bar does not change. Do not switch the
  model of an agent that is already running; that wastes its work.
- **Treat a phase report as a hypothesis.** The lead re-reads at least every FAIL capture, every
  capture that a PASS on a visual Then rests on alone, and one sample per test case.
- **Shut down each agent after its report is checked** (`shutdown_request`). An idle finished
  agent holds context and can act again on a stale instruction.
- **A truncated agent report is incomplete.** Ask the agent for the rest with `SendMessage`
  before you grade.
- **Decisions cite the deciding line** in `docs/intent.md`, `_bmad-output/specs/spec-freecad-buddy/SPEC.md`
  or `ARCHITECTURE-SPINE.md`. Pass this rule to every phase agent.

## 2. Before the run

1. **Branch and baseline.** Run from a branch, never from `main`. When the code under test has
   uncommitted changes, write `evidence/baseline-tracked.diff` and its SHA-256, plus a SHA-256
   per new untracked file. A gate verdict is valid only for that exact code state.
2. **Run folder.** `tests/uat/run/<YYYY-MM-DD>-<NN>/` with `evidence/`. Never reuse or edit an
   earlier run folder. A re-run after fixes is a new folder.
3. **`RUN-CONTEXT.md`** in the run folder: commit, diff hash, FreeCAD version and path, developer
   `user.cfg` SHA-256 before the run, the scope table (phase to scenario list), evidence naming,
   and the selection rule.
4. **Phase rules file** (`RULES.md`) in the lead scratchpad. Every phase agent reads it first.
   Template in [§4](#4-phase-agent-brief).
5. **H1 env** (`FCB_ENV`). Build it from the code under test, then prove it before any phase:
   - The APPENDIX-B Step 3 command prints `H1 ok <version>`.
   - `run_mcp_e2e.py` and `run_mcp_edge_cases.py` both exit 0.
   - `diff -r --exclude=__pycache__ src/freecad_buddy <env>/Lib/site-packages/freecad_buddy`
     shows no difference.
   - **No pip numpy in the env.** Use FreeCAD's bundled numpy. A pip numpy 2.x makes
     `import trimesh` hang in the H1 stdio front while its reader thread blocks on stdin, so
     `verify_export_stl` never returns.
   - When no conda `fcb` env exists, an fcb-shaped venv works:
     `uv venv --system-site-packages --python "<FreeCAD>\bin\python.exe"`, then
     `uv pip install <repo> pyyaml`, then `uv pip uninstall numpy`. Give it the `fcb` layout:
     `<env>\fcb\python.exe` plus junctions `<env>\fcb\Library\{bin,lib,...}` to the FreeCAD
     install folders.
6. **Record the developer profile hash** (`%APPDATA%\FreeCAD\v1-1\user.cfg`, SHA-256).

## 3. Phase plan

- **Runner phase first (R0).** Run every scenario file of `tests/uat/scenarios/` with a drawn
  seed (`run.py` without `--seed`), then the §9 agent review. It is fast and it shows harness
  defects before the long agent-driven phases start.
- **Size each agent phase to one or two test case files, about 12 to 22 scenarios.** A larger
  phase reaches the agent session limit, and a stop in the middle of a scenario leaves state that
  the next scenario inherits.
- **Phase order follows the test case order.** Later test cases use features that earlier ones
  prove.
- **A gate rests on one code state.** After a fix, re-run every scenario of the gate, not only
  the failed ones: the runner runs all scenario files, and the agent phases run all agent-driven
  scenarios, including a regression phase for the scenarios that passed before. If the owner
  chooses a selective re-run, record that choice in `RUN-CONTEXT.md` and in `report.md`.
- **Gate denominators.** Gate 1 counts TC-01..TC-14 only. TC-99 is Gate 2 and never enters the
  Gate 1 numbers.
- **When the agent session limit stops a phase**, keep the rows already written, record the stop
  time, and resume the same phase from the first scenario with no row.

## 4. Phase agent brief

Keep the brief in one file. Each phase prompt names the file, the phase id, the scenario list,
the watch items from earlier phases, and the output file. Minimum content:

```markdown
## Never
- git commit, reset, checkout, stash, switch, restore, clean, rebase, push.
- Edit src/, tests/uat/runner/, tests/uat/scenarios/, tests/uat/testcases/, scripts/,
  benchmarks/, .knowledge-base/. A wrong test case is a finding, not an edit.
- Open benchmarks/*/heldout.
- Move, truncate or delete files outside the run folder and your temp dirs.
  Read addon.log by byte offset only.
- End a FreeCAD you did not start.

## Always
- FreeCAD and FreeCADCmd: -u <temp>\user.cfg -s <temp>\system.cfg.
  In-process `import FreeCAD`: FREECAD_USER_HOME=<temp>.
- Hash the developer user.cfg at phase start, at phase end, and after every launch.
- One FreeCAD at a time. Before a launch: no freecad.exe, :8765 free.
  One row per launch in evidence/launch-log.tsv (phase, start, pid, profile, env, end).
- One scenario at a time, each from its own Given.
- Watchdog between test cases and before File > Exit.
- Every agent-driven scenario ends with a fit and a cua-driver capture you read and describe.
- Grade every Then as written. Not met literally = FAIL (cause class).

## Output
- Evidence: evidence/tc-xx-yy-<what>.<ext>
- Rows: TC-xx-yy | <Priority> | <PASS|FAIL (cause)|BLOCKED (reason)> | <evidence> | <note with file:line>
- FINDINGS: and LAUNCHES: lines. user.cfg hash at start and end. Nothing of yours left running.
```

## 5. Machine hygiene

- **Temporary profile for every FreeCAD.** FreeCAD and FreeCADCmd write `user.cfg` and
  `system.cfg` on exit. One launch without `-u` and `-s` overwrites the developer files, and no
  copy is kept. The rule applies to fix work between runs too, not only to phases.
- **A changed `user.cfg` hash is a finding at once.** Find the writer from file mtime and the
  launch log. If it cannot be restored, record a new baseline in the lead log with the reason.
- **`addon.log` is shared.** A temporary profile does not move the user app data folder, so every
  FreeCAD of the run appends to the developer `addon.log`. Read it by byte offset. Do not rotate
  or edit it during a run. If a phase must separate it, merge the parts in time order at run end
  with no FreeCAD running, and check that no line is out of order.
- **A FreeCAD that blocks the run** (the owner's own instance holding `:8765`) is closed
  gracefully by the lead, with no question to the owner. Phase agents never end a FreeCAD they
  did not start.
- **GUI lock for parallel fix work.** When non-GUI agents work in parallel (fix workstreams), a
  lock directory (`mkdir <scratchpad>/gui.lock`) gives the GUI to one agent at a time. Take it by
  `mkdir` just before the launch and remove it just after the exit. A background loop that takes
  the lock and then waits holds it from every other agent.

## 6. Driving the GUI

The harness standard has the action table. These rules come from FreeCAD 1.1.4 with `cua-driver`:

- **Foreground delivery is required** for three actions: select a model-tree row, click a
  `ListItem` in a combo-box popup, and scroll. In the background they do nothing and still report
  success. Use `delivery_mode: "foreground"` for these actions only.
- **Move the real pointer off the window after a foreground action.** Then wait 1 s before a
  capture. A pointer over the tree or the 3D view paints a hover or preselection highlight, and
  that highlight fails a visual Then.
- **Close open popups with `press_key escape`**, one key per open level, and confirm with
  `list_windows` that only the main window is left.
- **`invoke_menu` degrades late in a long session**: paths stop resolving and popups stay open.
  Relaunch FreeCAD. Do not count it as a product defect.
- **Live display check before judging a capture.** Two captures a few seconds apart must differ
  somewhere (title, clock, tree), or the window must show your last action. A stale capture is
  never judged. Wait up to 5 min, then mark the visual Then `BLOCKED (display stale)`.
- **Known display freeze.** After some minutes with no physical input, GPU-drawn windows can stop
  painting on screen and in captures while the taskbar clock still updates. A physical mouse move
  ends it; `cua-driver` input does not. Its cause is not proven. Report it as `BLOCKED`, never as
  a product result, and do not ask the owner to stay idle to reproduce it.

## 7. Grading

- **A Then is graded as written.** A Then not met literally is FAIL, even when the product
  behaves as designed. Give one cause class:

  | Cause class | Meaning | Next step |
  |-------------|---------|-----------|
  | product defect | product breaks intent, SPEC or design | fix the product |
  | test-case defect | the Then contradicts the design | rewrite the Then, cite the design line |
  | harness limit | the tool cannot drive or observe the step | change the step, or record the gap |
  | agent execution fault | the agent's own mistake | re-run once from the Given, keep both runs |

- **A failed check is a finding**, with the request, the raw output and a `file:line`. Never retry
  a check to get a PASS.
- **Read the design before you blame the product.** Example: `query_tree_summary` is text-only by
  design (`mcp-tools-design.md`: no `outputSchema`, no `structuredContent`). A Then or a sweep
  that reads its `structuredContent` is a test-case or harness defect.
- **Lead grades override phase grades** only with a reason. Keep them in one file (one row per
  scenario: id, phase verdict, lead verdict, reason, evidence) and carry them into `report.md`.
- **Runner verdicts.** A runner FAIL caused by a scenario file defect (for example a JSON string
  `"\bword\b"`, which is a backspace character, not a regex word boundary) is graded on the
  capture and the defect goes to `bugs.md`. The `report.md` verdict is final over `results.json`.
- **Counts come from the tables.** Recompute the gate numbers from the verdict rows and check that
  every scenario appears once.

## 8. From findings to fixes

- **No fix during a run phase.** Fixes are separate changes on the branch, between runs. Then
  re-run into a new run folder.
- **Rewrite a Then only when the design or SPEC proves the product behaviour is the designed
  one.** Otherwise it is a product defect.
- **One workstream per cause, each owning its files.** Two agents never edit the same file. A
  product fix gets a test that fails without it.
- **Find the cause before the fix.** For an odd runtime behaviour, follow `ultrathink-protocol`:
  a verified cause with direct evidence, then the fix. A probe that runs unattended is better than a
  request to the owner to watch the screen.
- **Owner decisions** (scope, accepting a visual result, a design question) are asked once, with
  the evidence and a recommendation, and recorded in the lead log with the answer or "no answer".
- **Commits need the owner's approval.** Ask at the end, with the file list and both run folders.

## 9. Records

| Record | Location | Holds |
|--------|----------|-------|
| Lead log | `_bmad-output/implementation-artifacts/lead-log-<date>-<topic>.md` | plan, actions, findings, decisions with reasons, results per phase and workstream |
| Run context | `run/<id>/RUN-CONTEXT.md` | code state, scope, phases, selection rule |
| Report | `run/<id>/report.md` | one row per scenario, §9 review lines, both gates, runner seeds |
| Bugs | `run/<id>/bugs.md` | each finding with request, output, `file:line`, cause class |
| Deferred work | `_bmad-output/implementation-artifacts/deferred-work.md` | findings not fixed in this story |
| Resume file | lead scratchpad `LEAD-CONTEXT.md` | state, invariants, open decisions, next steps |

Update the lead log after each phase and each decision, not at the end. Before a context
compaction, write the resume file: it lets the lead continue with no loss.

## 10. End-of-run checklist

- [ ] Every scenario of the gate has one row, and the counts are recomputed from the rows.
- [ ] Every FAIL has a cause class and a `bugs.md` entry.
- [ ] Lead re-read every FAIL capture and the sample set.
- [ ] Developer `user.cfg` hash equals the baseline, or the change is recorded with its writer.
- [ ] No FreeCAD of the run is running, `:8765` is free, no `FCB_TMP_snap_*` is left.
- [ ] `addon.log` merged in time order if it was split.
- [ ] `git status` shows only the run folder and the approved fixes.
- [ ] Every phase agent is shut down.
- [ ] Owner asked for commit approval.
