# Story 10-8-f check run (not a gate run)

This folder records the check of the Story 10-8-f test-case fixes. It is not a UAT gate run and grades no scenario for Gate 1.

- `runner/`: `tc-08-04.json` once, in `fcb-desktop`, after the `"\\bFillet\\b"` fix. Result: ESCALATE on its `agent_check` only, 0 FAIL, 0 findings, 0 run errors. The explanation `recompute left 1 object(s) invalid: Fillet: BRep_API: command not done` matches the regex. Agent read of `runner/captures/TC-08-04.png`: body `TC0804` with one pad, sharp edges, no rounded edge, no error colouring.
- `readers-check.md`: request and output of each new reader (TC-02 on the golden, two-box, Body/Pad and `App::Part` fixtures, TC-06, TC-08-17, TC-09, TC-11-18, TC-12-05).
- The runner's `agent_check` for TC-08-04 (compare a before capture with the runner capture) is outside this check; the check proves only that the regex no longer fails.
- `evidence/tc-11-18-before.png`, `evidence/tc-11-18-after.png`: golden view in front before and after the new `Next` step.
