# Story 10-10: triage, verifier round 2

Base: `355690e`. Verifier: re-run FAIL (D1-D5, D7 proven fixed; 2 new medium, 3 new low). Report: `verify-10-10.md`, "Re-run at 355690e".

Pattern: each round finds a GUI step whose element route works on the Windows tree but not on the container AT-SPI tree (token click on a tree row, an editor with no element, a `selected` field that does not exist). One class fix, not more single fixes.

| Id | Q | Required fix | Proof required |
| --- | --- | --- | --- |
| N1 | Q4 | TC-13:797-802 (TC-13-15): the F2 rename editor has no element, so `set_value` and `enter` by editor token have no target. Use the measured route: window-level `type_text` plus `enter`; `ctrl+z` restores | Run as written; label before, after, after undo |
| N2 | Q1/Q4 | TC-12:89, :272, :307: tree items have no `selected` field in the container. Read the selection with `script_exec` (as the D1 route does). If the text before ` — verify:` names `selected: true`, change only the verify clause when the head still holds ("Box is selected"); if the head itself must change, list it as a third observable change with the reason | Run as written; `then-check.py` result |
| N3 | Q2 | TC-99:205, :223, :318, :333: expected values use the Windows `\freecad-buddy\workdir` form. Use the container path the log prints | grep, and one log line from the container |
| N4 | Q2 | `test-plan.md:332`, `APPENDIX-B:261`, `TC-12:47`: Recompute leaf is listed only while the document needs recompute; Toggle Visibility is listed while an object is selected. State the measured condition | text |
| N5 | Q4 | TC-02:240: say that Body must be expanded to show the Pad row, and how | run once |
| C1 | Q4 | Class sweep. List every distinct `cua-driver` tool, `action`, and tree field a test case relies on (for example `click` by token on a tree row, `set_value`, `select`, `selected`, `expanded`, `checked`, editor tokens, `scroll`, menu leaves, dialog buttons). Mark each one measured (cite the proof file) or not. Measure every unmeasured one once in the container on FreeCAD; fix each test-case site whose route fails, with the route that works | `C1-action-census.txt`: one row per tool/action/field, measured result, sites fixed. 0 rows left unmeasured |

## After the fixes

One commit (leader). The verifier re-runs N1-N5 and reads `C1-action-census.txt` and runs at least 3 of its rows. Then the red team attacks the whole Story diff.

Stop rule: if the next verifier run still finds a new medium of this class, the leader records the remaining GUI-route risk for Story 10-8 (which runs every scenario end to end, and fixes a test-case route found broken during the run as a test-case defect), instead of a fourth fix round.
