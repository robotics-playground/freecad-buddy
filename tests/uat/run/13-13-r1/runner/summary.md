# Scripted UAT run

4 scenarios: 0 PASS, 0 FAIL, 4 ESCALATE.

| Scenario | Title | Launch | Verdict | Capture |
|----------|-------|--------|---------|---------|
| TC-02-06 | query_object returns properties and error state for a Pad | default | ESCALATE | /repo/tests/uat/run/13-13-r1/runner/captures/TC-02-06.png |
| TC-09-17 | A broken recompute returns RECOMPUTE_ERROR, not a false OK | default | ESCALATE | /repo/tests/uat/run/13-13-r1/runner/captures/TC-09-17.png |
| TC-09-18 | A broken reference surfaces the failing object and its status string | default | ESCALATE | /repo/tests/uat/run/13-13-r1/runner/captures/TC-09-18.png |
| TC-12-07 | A GUI-side recompute agrees with the bridge | default | ESCALATE | /repo/tests/uat/run/13-13-r1/runner/captures/TC-12-07.png |

## Escalation queue

### TC-02-06: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: healthy state captured before the break (tc-02-06-before.png) (GUI action).

### TC-09-17: ESCALATE

- agent check: Read the capture: the FreeCAD tree marks the failing object (Pad) with an error icon, and the 3D view still shows the last valid 20 x 20 x 10 block (FreeCAD keeps it on a failed recompute). If the fit step did not return OK (the test case expects the MCP fit may refuse a faulted document), the capture is unframed: click the GUI Fit All toolbar button, capture the window and judge that. A tree with no error marker on Pad is a finding. The script does not check these Thens; check each one in the gate run: at least one check recompute.object with passed false (checked at checks.0 only) (comparison op); _RECOMPUTE_ERROR_STATES in usecases/verify.py includes Touched (encoded as measured equals Touched) (file check).

### TC-09-18: ESCALATE

- agent check: Read the capture: the object named in subject.failing_objects (Pad) has an error icon in the tree and its Sketch is gone from the tree; the 3D view still shows the last valid 20 x 20 x 10 block (FreeCAD keeps it on a failed recompute). If the fit step did not return OK (the test case expects the MCP fit may refuse a faulted document), the capture is unframed: click the GUI Fit All toolbar button, capture the window and judge that. A tree with no error marker on Pad is a finding. The script does not check these Thens; check each one in the gate run: Pad's recompute.object check picked by index checks.1 (comparison op).

### TC-12-07: ESCALATE

- agent check: The runner takes no capture between steps: the clean-state Given (toolbar Recompute button disabled) and the dirty-state Then (tc-12-07-props.png: old 5 mm pad still drawn, touched marker on the Pad row where Body is expanded, Recompute button enabled) are not captured; the Edit > Recompute step succeeding is the only scripted sign the command was enabled. Re-run those two GUI reads by hand, then judge the capture: no touched or error marker on any tree row, Recompute button disabled again, a solid visibly taller than the 5 mm plate (20 x 10 x 8). The script does not check these Thens; check each one in the gate run: Given: toolbar Recompute button reads disabled (GUI action); GUI dirty state: Recompute enabled and the touched marker in the tree (GUI action).

## Agent review

Sample seed 408164812 (drawn). The agent reads these captures (tests/uat/test-plan.md §9); the scripted pixel check grades the rest.

- TC-02-06 (escalate): /repo/tests/uat/run/13-13-r1/runner/captures/TC-02-06.png
- TC-09-17 (escalate): /repo/tests/uat/run/13-13-r1/runner/captures/TC-09-17.png
- TC-09-18 (escalate): /repo/tests/uat/run/13-13-r1/runner/captures/TC-09-18.png
- TC-12-07 (escalate): /repo/tests/uat/run/13-13-r1/runner/captures/TC-12-07.png
