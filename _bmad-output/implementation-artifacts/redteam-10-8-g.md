# Story 10-8-g: red team report

Diff: `ffd131d...56e746b` (branch `story/10-8-g-smoke-testcase-defects`). Quality bar: `quality-bar-10-8-g.md`. Known items in `review-ledger-10-8-g.md` (B-r1, L-1) are not reported again.
Method: adversarial review (`bmad-code-review` method, no sub-agents) in a detached worktree at `56e746b`. No live container run: every reproduction below uses real product code or the committed files. Worktree removed.

## Reproduced

| RT | Severity | Q | File:line | Finding |
| --- | --- | --- | --- | --- |
| RT-1 | medium | Q6 | `tests/uat/scenarios/tc-02-17.json:128` (`agent_check`) | The case Then requires the two `<FreeCAD text>` tails to be **non-empty** and equal, plus `detail.code` `INVALID_INPUT` (`TC-02-document-ingestion-and-handles.md:707`). The `agent_check` says only "start `Invalid project file <path>:` ... and their FreeCAD texts are equal". The spec triage row EC8 ("equal empty tails would pass TC-02-17", patch "`non-empty` added") patched the case only, so the gate agent that reads the runner record passes the exact defect EC8 named. |
| RT-2 | medium | Q6 | `tests/uat/scenarios/tc-09-12.json:225` (`agent_check`) | The case Then requires the exact line `INVALID_INPUT: unknown or stale document handle: fcb-doc:does-not-exist` (`TC-09-error-contract-and-fault-injection.md:504`). The `agent_check` says "the text line starts `INVALID_INPUT:` and names the handle". The unchanged `expect` regex `^INVALID_INPUT: .*fcb-doc:does-not-exist` is equally loose. A refusal with the wrong message passes the runner and the `agent_check`, and fails the case. |
| RT-3 | low | Q6 | `tests/uat/scenarios/tc-03-03.json:457` (`agent_check`) | The case row `TC-03-sketch-authoring.md:131` has a hard camera read-back (each quaternion component within 0.01 of `[0.425, 0.176, 0.34, 0.82]`, added by spec triage BH7/EC3). The `agent_check` omits it ("press Isometric ... Fit All, wait 8 s, capture"). Set-up check only; the visual Then is the same. |
| RT-4 | low | Q8 | `_bmad-output/implementation-artifacts/deferred-work.md:2089` | The TC-03-03 `resolution` cites `evidence/tc-03-03-iso-edit.png`. That file does not exist anywhere. The check run holds `tests/uat/run/2026-11-18-10-8-g-check/evidence/tc-03-03-after.png`. |
| RT-5 | low | Q8 | `deferred-work.md` resolutions of the nine fixed entries (`:2068` to `:2124`) | Each says "commit recorded by the leader after the commit"; no entry names `56e746b` yet. Q8 says "marked resolved with the commit". Leader-owned step, still open. |
| RT-6 | low | Q6 | `TC-03-sketch-authoring.md:131` vs `:31` | The new set-up row runs `mcp script_exec` (camera read) with edit mode open, "a read-only call, so edit mode may stay open". The file Preconditions say "Close edit mode before the next MCP call" with no exception. The two instructions disagree. |
| RT-7 | low | Q5 | `TC-07-verification-and-export-pairing.md:195` | The Given cites `src/freecad_buddy/contracts/envelope.py:111` for "the bridge appends [the warning] to `text` after a blank line". Line 111 is the warning sentence; the append is `envelope.py:124`: `return f"{text}\n\n{sentence}" if sentence else text`. |

### Reproduction RT-1, RT-2 (real product code)

Script `rt_regex.py` (scratchpad), run with the repo venv against the worktree `src/`:

```python
from freecad_buddy.adapters import mcp_server as m
wrong = m._invalid_input_envelope("internal error while resolving fcb-doc:does-not-exist")
res = m._to_call_result(wrong, structured=False)   # the query_tree_summary path (structured_output=False)
text = res.content[0].text
runner = re.search(r"^INVALID_INPUT: .*fcb-doc:does-not-exist", text) is not None
agent  = text.startswith("INVALID_INPUT:") and "fcb-doc:does-not-exist" in text
case   = text == "INVALID_INPUT: unknown or stale document handle: fcb-doc:does-not-exist"
# TC-02-17: msg(p) = f"document_open failed for {p!r}: Invalid project file {p}: "  (empty FreeCAD tail)
```

Output:

```
module: D:\Work\Personal\Sources\fcb-redteam-10-8-g\src\freecad_buddy\adapters\mcp_server.py
text: 'INVALID_INPUT: internal error while resolving fcb-doc:does-not-exist' isError: True structured: None
tc-09-12 expect regex passes: True
tc-09-12 agent_check (starts INVALID_INPUT:, names handle) passes: True
TC-09-12 case Then (exact line) passes: False
tc-02-17 agent_check (prefix + equal tails) passes: True
TC-02-17 case Then (prefix + equal + non-empty) passes: False
```

Severity reason: each `agent_check` says "The script does not check these Thens; check each one in the gate run: ...", so it is the Then text the gate agent reads from the ESCALATE record. It passes a wrong product that the case text fails. Not high: the case Then itself is intact, and `uat-run-practices.md` §7 grades the case "as written". Fix: copy "non-empty" and `detail.code` into `tc-02-17.json`, and the exact line into `tc-09-12.json` (also tighten its `expect` regex to the exact text, as `tc-02-15.json` does with `equals`).

### Reproduction RT-4

```
$ find tests/uat/run -name "*iso-edit*"
(no output)
$ ls tests/uat/run/2026-11-18-10-8-g-check/evidence
tc-03-03-after.png  tc-03-20-after.png  tc-03-20-before.png  tc-07-03-after.png
tc-13-04-after.png  tc-13-04-mcp.png  tc-13-10-after.png  tc-13-10-before.png
```

## Quality-bar rows checked

- Q1: `TC-02-15` line 628/630 and `TC-09-12` lines 503-506 read the text line; the eleven envelope tools keep `schema` and `detail.code`. Text form matches `mcp_server._plain_text` (status, then `detail.message`). See RT-2 for the loose `agent_check`.
- Q2: no platform literal is required; prefix and equal tails are hard. Linux text `basic_ios::clear: iostream error` confirmed in `runner/results.json`. See RT-1.
- Q3: Isometric is set before every compared capture. TC-13-04 and TC-13-10 after-captures follow `view_fit_viewport`, which calls `viewIsometric` (`usecases/view_fit.py:159`, `:331`), or keep the iso camera from the When. Render `iso` quaternion `(0.424708, 0.17592, 0.339851, 0.820473)` (`usecases/screenshot.py:89`) equals the GUI Isometric value.
- Q4: TC-07-03 enters edit mode before the capture; the visual Then wording kept.
- Q7: `git diff ffd131d...56e746b -- tests/uat/testcases | grep -c TC-02-13` = 0.
- Q9: `pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` = 186 passed; `scenario.load` on all 72 files succeeded.
- Q10: `git diff --stat` shows no file under `src/`, `tests/uat/runner/`, `tests/close-loop/`, or an earlier run folder.

## Not reproduced (low)

- TC-02-17: the new Then cannot tell FreeCAD's pass-through text from a bridge that rewrites the tail to a constant non-empty string. No such code path exists (`usecases/documents.py:496-499` passes `exc` through). An outside oracle (`FreeCAD.openDocument` in `script_exec`) would close it.
- Edit mode masking a geometry defect (TC-03-03, TC-03-20): from `evidence/tc-03-03-after.png` the axis origin sits on the top-face corner; a sketch at `z = 0` would put it at the bottom corner, about 42 px lower, which a grader can see. Not tested live with a wrong sketch.
- TC-03-20: `setEdit` runs the Sketcher solver, so the edit-mode circle could show radius 4 even if `sketch_set_datum` left the object stale. Not new: the previous `agent_check` already judged the circle in edit mode, and the scripted `expect` checks `harmless` status and a clean TNP audit.
- TC-03-20: `setEdit`/`resetEdit` in the Given open and commit a GUI transaction before the rolled-back When. The check run shows `rolled_back` true and volume `12000.0`; no interaction seen.
- TC-07-05: the fit in the Given hides no framing defect. TC-14 `:399` tests the warning; the check run shows the warning on an unfitted export and none after the fit.
- TC-07-03: the new row says "Fit All places it on the lower edge of the viewport". In `evidence/tc-07-03-after.png` the segment is at y ≈ 860 with the viewport ending at y ≈ 868. A grader who reads this as an expectation could fail a right product on another FreeCAD build. Descriptive text; not shown to fail.
- Item 3 (And lines in the Then block, TC-03-03, TC-07-03): order holds (MCP fit row, then edit mode, then capture; Cleanup closes edit mode first). The rows carry "verify:" clauses, so a grader grades them; the TC-03-03 camera check can only fail on set-up, not on product output.
- `tc-02-15.json` `tree` step has no `is_error` expect although the case says it is still a tool error. Pre-existing, not in the diff.

## Verdict

FAIL: two reproduced medium findings (RT-1, RT-2), both `agent_check` drift against Q6. No high finding.
