# R0 review brief — §9 agent review of the runner run (R0a, R0b)

Read `lead-notes/RULES.md` first: every rule there applies. Then `tests/uat/test-plan.md` §9 ("Agent
review of runner captures") and `tests/uat/runner/README.md` ("Scenario file", "Checks and verdicts").

## Inputs

- R0 output (read only; never write into `runner/`): `$RUN_DIR/runner/summary.md`,
  `$RUN_DIR/runner/results.json` (per scenario: `steps` with args and results, `findings`, `pixel`,
  `verdict`, `reasons`, `review`), captures `$RUN_DIR/runner/captures/<id>.png`, keep-step renders
  `$RUN_DIR/runner/tc-06-*.png`, audit logs `$RUN_DIR/runner/audit-group-<n>.jsonl`.
- R0 facts: exit 0, seed `423616651` (`drawn`), 72 scenarios: 5 PASS, 0 FAIL, 67 ESCALATE, no
  `not_run` group. Launch groups: group 0 no variables; group 1 `FREECAD_BUDDY_AUTO_APPROVE=0`
  (TC-05-03, -08, -14, -15, TC-08-03, -04, -07, -08, -09, -10, -11, -13, -14, -15, -16); group 2
  `FREECAD_BUDDY_SCRIPT_EXEC=0` (TC-11-17).
- The scenario file `tests/uat/scenarios/<id>.json` and the test case scenario in
  `tests/uat/testcases/TC-xx-*.md` (the human source).

## What to do for each scenario of your list

1. Read the runner capture `runner/captures/<id>.png` and apply test-plan §3 rule 4 to every visual
   Then of the test case scenario: say what is on screen (part present, whole, not clipped, right
   shape, dialog), compare with the expected visual.
2. Read `results.json` for the scenario: its `findings`, `reasons`, the `pixel` measurement, and
   each step result. A scripted `PASS` check stands for the Thens it encodes; say which.
3. Work every item of the `agent_check` text (its reason in `results.json`), one by one:
   - "click Fit All, capture" / "open in Sketcher edit mode" / a before capture / a capture between
     steps / a capture right after a refused call: the runner hands over only after the last step,
     so re-run that scenario's steps by MCP from its Given, on a FreeCAD you start with
     `fcb-freecad start` (with the group's variable, `-e NAME=value`, for group 1 or 2), up to the
     named step, take the capture there with `cua-driver` (`screenshot_out_file`
     `$RUN_DIR_C/evidence/<phase>-<id>-<what>.png`), `Read` it and judge it. Then go on to the end
     of the steps when a later capture is also named.
   - "(comparison op)", "(file check)", "(log or audit read)", "(H1 host)", "(raw RPC or second
     client)", "(GUI action)", "(timing bound)": do the check the test case states, on the R0 data
     when that data holds it (step results, the run folder files, `audit-group-<n>.jsonl`), else
     in your re-run. Record the request and the raw value.
   - Sketcher edit mode: use the route the test case Preconditions give (`script_exec` with
     `setEdit`), leave edit mode after the capture.
   - GUI Fit All: the toolbar button by `element_token` from a fresh `get_window_state`.
4. Grade the scenario: PASS only when every Then (scripted checks plus every agent_check item plus
   every visual Then) is met and every capture it rests on was read. Otherwise FAIL with a cause
   class, or NOT RUN with the reason for an item no route serves (then the scenario is not PASS).
   The window wins both ways (§9): a capture that contradicts a scripted PASS makes the scenario
   FAIL and a pixel-check finding; a capture that meets a visual Then the pixel check flagged makes
   a pixel-check false-alarm finding.
5. Close every document you opened before the next scenario. Run the watchdog between test cases.

## Output

Your report file `$RUN_DIR/lead-notes/phase-<id>-report.md` holds, in addition to RULES.md Output:

- One review line per scenario, in the §9 form:
  `TC-xx-yy (<review reason>): <what is on screen>. <verdict>`
  The review reason is the `review` value in `results.json` (`escalate`, `first of TC-xx`,
  `sample`, `no pixel check`).
- The row table: `| Scenario | Priority | Verdict | Evidence | Note |`; the note lists each
  agent_check item with its result and the raw value.
