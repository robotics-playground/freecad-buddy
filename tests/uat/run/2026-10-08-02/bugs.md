# Findings: UAT run 2026-10-08-02

## Product defects

### B1 — GUI abort on the drawer restores the snapshot instead of proving the rollback

Open item from run `2026-10-07-03` (deferred-work, Story 11.6), now seen on the normal MCP path too.

- TC-16-04: `feature_set_parameters duct_pilot.Length = 0 mm` → `RECOMPUTE_ERROR`, `rollback_proven: "rolled_back_via_snapshot"`, `snapshot_path` set, 38.4 s (`evidence/tc16-calls.jsonl`, label `16-04-setlen0`; `evidence/audit.jsonl` line 81).
- TC-16-05: macro abort check `rolled_back_via_snapshot`, `same_document: false`, `close_document_calls: ["drawer_timing"]`, 32.5 s and 32.9 s (`evidence/gui-timing.json`, `evidence/gui-timing-repeat.json`).
- After the abort, neither the digest nor `massprops_equal` matched, so `usecases/transaction.py` `_prove_rollback` fell back to `_restore_from_snapshot` (close and reopen). The user sees the same model afterwards, but each failed mutation on this document costs about 32 to 38 s and reopens the document.
- Headless on the same file proves `rolled_back_verified` (run `2026-10-07-03`). Root cause unknown: the audit record does not name the objects that did not match.

### B2 — A pocket that removes all material commits, and the result text says it failed

TC-05-06 reproducer 1 on `tc05_06` (Pad 20x20x30, Fillet, Sketch001 on a flat face of the fillet result): `feature_pocket` Length 900 mm.

- Result: `SPEC_FAILED`, `rolled_back: false`, `rollback_proven: null`, `fingerprint_after: null`, snapshot kept, explanation `OverflowError: cannot convert float infinity to integer`, text `Mutation failed and its rollback could not be proven: <snapshot path>.` (`evidence/phaseB-calls.jsonl`, label `05-06-r1-pocket`).
- Live state after the call: `Pocket` is the Body tip, Length 900 mm, `Shape` an empty `Compound`; the window shows no solid (`evidence/tc-05-06-after-pocket.png`).
- Path: `post_verify` passed (the empty shape was not graded), the transaction committed, then `fingerprint(document)` raised (`usecases/transaction.py:672-680` → `_unhashable_commit_envelope`).
- Cause 1: `usecases/fingerprint.py` `_quantize` checks `math.isfinite(number)` before the division. An empty shape's bounding box is ±1.797e308, finite, and `number / step` is `inf`, so `round()` raises. Present since story 1-6 (`round(number / Q)`), not introduced by Epic 11.
- Cause 2: `post_verify` accepts a feature whose result has no volume.
- Cause 3: the summary text of the committed-but-unhashable path says "failed … rollback could not be proven", but the change is committed. An agent reading the text would assume nothing changed.
- The preview of the same call reported `diff.validity.status: "SPEC_FAILED"` with the same explanation, while its text said `valid=True`.

### B3 — Preview run leaves a snapshot folder behind

The preview of B2's pocket left `FCB_TMP_snap_0_k8j4t4` in the session temp folder. The session-start sweep removes it on the next launch.

### B4 — Error results carry a full traceback with local paths

Every `INVALID_INPUT` result includes `detail.data.traceback` (about 1.7K to 2.8K chars) with absolute local paths (`adapters/rpc_dispatch.py:87`). Size cost on every refusal; also a disclosure question for the security review.

## Test-case defects (not fixed in this run)

| Id | Where | Problem |
|---|---|---|
| T1 | TC-05 (many), TC-08-01 | `query_sketch_info` returns no `dof` or `fully_constrained` (`usecases/queries.py:706`); fixtures were proven from `sketch_state` / `post_verify` instead |
| T2 | TC-05-01 | "three times as tall as it is wide": 20x20x30 is 1.5:1 |
| T3 | TC-05-01 (line edited in this run) | says the audit `mutation` line keeps `transaction_id`; it has none |
| T4 | TC-05 preconditions, -02, -05, -06, -10, -12 | snapshot checks look in `$TEMP`; snapshots live in `%LOCALAPPDATA%\freecad-buddy-workdir\tmp\FCB_TMP_session_<pid>_<token>\` (`usecases/documents.py:72`, `usecases/transaction.py:107`). `$TEMP` also holds 10 unreadable stale folders from 2026-09-22 |
| T5 | TC-05-05 | "not an MCP isError response": every non-OK result sets `isError` by design (`adapters/mcp_server.py:100`) |
| T6 | TC-05-06 | `feature_pattern` arguments `base` and `direction: "X"` are not valid; a sketch cannot attach to the curved fillet face |
| T7 | TC-05-13 | the same file cannot be opened twice (second open returns the same handle); the golden box file is saved with `Box` hidden |
| T8 | TC-11-08 | starts H1 with `uv run` (no FreeCAD in that env); cites old line numbers (`mcp_server.py:176-177`, `audit_log.py:88-103` now); does not say the fixture must be built outside the audited process; cleanup deletes the evidence |
| T9 | TC-16-05 | the closing visual cannot run: the macro blocks the GUI while it runs and calls `sys.exit(1)` when the abort check fails (`scripts/automation/time_mutation_overhead.py:178-179`) |
