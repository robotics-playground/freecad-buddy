# Scripted UAT run

1 scenarios: 0 PASS, 0 FAIL, 1 ESCALATE.

| Scenario | Title | Launch | Verdict | Capture |
|----------|-------|--------|---------|---------|
| TC-08-04 | A preview of a failing operation is still a successful preview | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-f-check/runner/captures/TC-08-04.png |

## Escalation queue

### TC-08-04: ESCALATE

- agent check: The runner takes no before capture: capture the framed pad before the preview and compare it with the runner's capture; the two must be identical by eye, sharp edges, no rounded edge, no error-state colouring.

## Agent review

Sample seed 3671377492 (drawn). The agent reads these captures (tests/uat/test-plan.md §9); the scripted pixel check grades the rest.

- TC-08-04 (escalate): /repo/tests/uat/run/2026-11-18-10-8-f-check/runner/captures/TC-08-04.png
