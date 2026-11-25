# Epic 13 lessons for builders

Defects the red teams and container runs found in Stories 13-1 .. 13-9. Plan for each one up front, with a test. Decisions are in `epic-13-decisions.md`.

| # | Lesson | Source |
| --- | --- | --- |
| L1 | FreeCAD booleans, `distToShape` and `section` give wrong answers on invalid, reversed or non-solid shapes. Refuse untrusted input with a `detail.code`; never report a number you cannot trust. | 13-7 RT-1/2, 13-8, decisions 26, 29 |
| L2 | One long OCC call holds the Python GIL; the bridge timeout cannot fire and the bridge stays busy for minutes. Measure the cost of the operation on large and on curved (BSpline, swept) inputs and refuse above a measured limit. Face count alone is a poor proxy. Write the measurement beside the constant. | 13-7 F2, 13-8 RT-1, decisions 27, 28, 31 |
| L3 | A read-only tool must not change the document: run on `shape.copy()` and test that a fresh fingerprint is equal before and after. | 13-7 F1 |
| L4 | Never a made-up value: a measurement that failed or was skipped is `null` with a reason, never 0. | 13-6, 13-7, 13-8 |
| L5 | The AD-6 fingerprint sees shapes only. A mutation that changes only properties (VarSet, spreadsheet, expression, label, visibility) leaves the digest equal, so the AD-5 rollback proof is trivially true. Prove rollback by reading the changed state back against a snapshot (`run_mutation` `state_probe`). | 13-9, decision 32 |
| L6 | A call that changes nothing records no FreeCAD undo step; the next `document_undo` then reverts an earlier step. Detect a no-op before the bracket and return `undo_steps: 0`. | 13-9 RT1, decision 34 |
| L7 | FreeCAD does not record every property change in undo (property group and description). Check that `document_undo` really restores what the tool changed. | 13-9 RT2 |
| L8 | FreeCAD silently changes some values (string NUL truncation, clamped length/angle). Refuse what FreeCAD cannot store; never store a silently changed value. | 13-9 RT3, decision 33 |
| L9 | New failure kinds: `detail.code` from the project's `CodedValidationError` (string code). AD-17 status set is closed. | 13-9 RT4, decision 34 |
| L10 | GUI and headless differ (thumbnails in 3MF, boolean input visibility). Container UAT in the GUI catches what headless tests cannot. | 13-5 D-1, 13-17 probe |
| L11 | Update every UAT case and scenario whose expected text or behaviour your change alters (grep `tests/uat/`). | 13-14 F1/RT-2, 13-20 |
| L12 | Shared code (`run_mutation`, `rpc_dispatch`, `tnp_guard`) changes reach every tool: compare a few other tools' envelopes against base. | 13-9 |
| L13 | Environment: `uv run --extra dev pytest` from Git Bash; under freecadcmd set `FREECAD_USER_HOME` to a temp folder (the dev addon junction points to the main tree); worktrees have no `docs/references/FreeCAD` — read it from the main tree; never run an unscoped `ruff format`; scratch only under your own scratchpad subfolder; do not go idle while a background command runs. | Environment block |
| L14 | A FreeCAD transaction that records no change stays open at application level; the next change by any tool joins it and `document_undo` refuses. Close the active transaction after every commit or abort (`run_mutation` does this after Story 13-10). | 13-10 V1, 13-13 spec, decision 38 |
| L15 | A length cap bounds parsing, not evaluation: one short expression over a spreadsheet range ran 1,087 s. Bound evaluation cost too (refuse ranges, cap work). | 13-10 RT-8 |
