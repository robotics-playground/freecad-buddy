# Scripted UAT run

4 scenarios: 0 PASS, 0 FAIL, 4 ESCALATE.

| Scenario | Title | Launch | Verdict | Capture |
|----------|-------|--------|---------|---------|
| TC-02-02 | Open a golden model and read its tree | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-9-verify/runner/captures/TC-02-02.png |
| TC-02-04 | Two open documents stay isolated | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-9-verify/runner/captures/TC-02-04.png |
| TC-11-17 | A script_exec call while it is off is refused and never runs (GUI proxy part) | FREECAD_BUDDY_SCRIPT_EXEC=0 | ESCALATE | /repo/tests/uat/run/2026-11-18-10-9-verify/runner/captures/TC-11-17.png |
| TC-05-03 | post_verify runs its four checks in order | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | /repo/tests/uat/run/2026-11-18-10-9-verify/runner/captures/TC-05-03.png |

## Escalation queue

### TC-02-02: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: every property value is JSON-safe, no repr of a live FreeCAD pointer (comparison op).

### TC-02-04: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: query on A returns Box while B is active after a sphere tree-item click (GUI action); handle A and handle B are different strings (comparison op).

### TC-11-17: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: H1 refuses with INVALID_INPUT and the exact 'script_exec is off: ...' message (H1 host); H1 audit has two exec lines, the second verify_verdict INVALID_INPUT (H1 host); H1 query_tree_summary has no Leak line (H1 host); GUI audit log line count unchanged (log or audit read); Given: addon.log has FREECAD_BUDDY_SCRIPT_EXEC='0' and no SECURITY ENABLED line (log or audit read); Given: GUI audit.jsonl line count recorded (log or audit read); Given: framed baseline captured (tc-11-17-before.png) (GUI action).

### TC-05-03: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: pre-mutation window framed and captured (tc-05-03-before.png) (GUI action).

## Agent review

Sample seed 685223104 (drawn). The agent reads these captures (tests/uat/test-plan.md §9); the scripted pixel check grades the rest.

- TC-02-02 (escalate): /repo/tests/uat/run/2026-11-18-10-9-verify/runner/captures/TC-02-02.png
- TC-02-04 (escalate): /repo/tests/uat/run/2026-11-18-10-9-verify/runner/captures/TC-02-04.png
- TC-11-17 (escalate): /repo/tests/uat/run/2026-11-18-10-9-verify/runner/captures/TC-11-17.png
- TC-05-03 (escalate): /repo/tests/uat/run/2026-11-18-10-9-verify/runner/captures/TC-05-03.png
