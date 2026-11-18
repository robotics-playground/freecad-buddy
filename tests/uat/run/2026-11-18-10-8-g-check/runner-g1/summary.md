# Scripted UAT run

2 scenarios: 0 PASS, 0 FAIL, 2 ESCALATE.

| Scenario | Title | Launch | Verdict | Capture |
|----------|-------|--------|---------|---------|
| TC-02-17 | Bad open paths are refused, and a missing file is distinguishable | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-g-check/runner-g1/captures/TC-02-17.png |
| TC-09-12 | An unknown doc handle returns INVALID_INPUT | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-g-check/runner-g1/captures/TC-09-12.png |

## Escalation queue

### TC-02-17: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button, which the runner cannot press; click Fit All, capture the window and judge its visual Then. The script does not check these Thens; check each one in the gate run: Given: not-fcstd.txt and corrupt.FCStd prepared with printf (README.md stands in for the first) (file check); corrupt zip refused with 'document_open failed for ...corrupt.FCStd' (file check); non-FCStd file and corrupt zip: `status` and `detail.code` are `INVALID_INPUT`, each message reads `document_open failed for '<path>': Invalid project file <path>: <FreeCAD text>`, the two FreeCAD texts are non-empty and equal once each path is replaced, and both differ from the missing-file text (`does not exist`); platform text recorded, not required (file check); addon log records no unhandled traceback (log or audit read); Given: baseline framed with GUI Fit All and a before capture (GUI action).

### TC-09-12: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: untouched window captured after the fit (tc-09-12-before.png) (GUI action); query_tree_summary unknown handle: the text equals exactly `INVALID_INPUT: unknown or stale document handle: fcb-doc:does-not-exist`, with no status or detail field (mcp-tools-design.md:60) (raw RPC or second client).

## Agent review

Sample seed 345996517 (drawn). The agent reads these captures (tests/uat/test-plan.md §9); the scripted pixel check grades the rest.

- TC-02-17 (escalate): /repo/tests/uat/run/2026-11-18-10-8-g-check/runner-g1/captures/TC-02-17.png
- TC-09-12 (escalate): /repo/tests/uat/run/2026-11-18-10-8-g-check/runner-g1/captures/TC-09-12.png
