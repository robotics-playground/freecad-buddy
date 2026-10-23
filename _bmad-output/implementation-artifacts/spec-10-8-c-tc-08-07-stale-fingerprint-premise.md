---
title: 'Story 10.8 (goal 1b): Correct the TC-08-07 Fingerprint Premise'
type: 'chore'
created: '2026-10-23'
status: 'done'
baseline_commit: '73e8c10d28564244979dc98a16653481da1285f3'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Critical scenario TC-08-07 (a preview token is single-use) assumes that creating an empty body leaves the document fingerprint unchanged, and its Then requires `mutation.fingerprint_before.digest` to equal `fingerprint_after.digest`. Since Story 10.3, `usecases/fingerprint.py` records an object with a null `Shape` as the empty-bytes hash plus zeroed mass properties, so an empty body moves the digest by design. The scenario fails on every run, and Gate 1 needs every Critical scenario to pass.

**Approach:** Remove the stale premise and its Then from `tests/uat/testcases/TC-08-preview-confirm-and-undo.md` and the digest check from `tests/uat/scenarios/tc-08-07.json`. The single-use proof stays: `verify_confirm` checks the spent set before it compares fingerprints (`usecases/confirm.py:272-287`), so the replay's message names the spent token, and the existing Then "the refusal is not a fingerprint complaint" fails if the spent check stops refusing. Prove it live: TC-08-07 runs through the runner on FreeCAD 1.1.4 with no FAIL.

</frozen-after-approval>

## Implementation Notes

- `tests/uat/testcases/TC-08-preview-confirm-and-undo.md` TC-08-07: removed the "commits without moving the digest" premise from the Given and the When, and the Then "the fingerprint did not move"; the When is now the action only. The Then "the refusal is not a fingerprint complaint" names `verify_confirm` (`usecases/confirm.py`) checking the spent set before the fingerprint, which is why it catches a spent check that stops refusing.
- `tests/uat/scenarios/tc-08-07.json`: removed the `fingerprint_after.digest equals fingerprint_before.digest` check; nothing else changed.
- Live, FreeCAD 1.1.4, runner on `tc-08-07.json`: ESCALATE on its `agent_check` only (visual before/after comparison), no finding, no run error. Agent read of the capture: tree Body, Probe, Probe2 (one Probe), the 20 x 20 sketch outline, no dialog. No FreeCAD left after the run. `test_uat_runner.py` 144 passed.

## Review Triage Log

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | the new When claims the fingerprint moves; no Then checks it | medium | the claim is not needed for the single-use proof | patch: When is the action only |
| 2 | the When states results and causes | low | expected refusal belongs in a Then | patch (with 1) |
| 3 | the ordering claim cites no source | low | `verify_confirm` in `usecases/confirm.py` | patch: named in the Then |
| 4 | the null-shape parenthetical misstates why the digest moves | low | removed with 1 | patch (with 1) |
| 5 | the Given lost the reason for `feature_body_create` | low | the last Then explains the second name; any confirmed mutation works | reject |
| 6 | no check that the replay returns no mutation; the lookahead regex is redundant beside `equals` | low | the test case checks "mutated nothing" through the tree; encoding follows the test-case text | reject |
| 7 | `agent_check` does not carry the "fingerprint moved" Then | false | that Then is not in the test case after patch 1 | reject |
