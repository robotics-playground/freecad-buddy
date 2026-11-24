# Story 13-9 triage: round 2 (red team; verifier pending — may add an addendum)

Base: feac4bfd on `story/13-9-varset-parameters`. Source: `redteam-13-9.md` (this folder). Use its reproductions as failing tests first. Leader decision 34.

| Id | Source | Required fix |
| --- | --- | --- |
| RT1 (high) | red team | A define whose values all equal the current values records no FreeCAD undo step but returns OK; the next `document_undo` reverts the step before it (deleted a user Box in the probe). Detect a no-op before the bracket: do not open a transaction; return OK with the parameters listed as `unchanged` and `undo_steps: 0` (same field name as Story 13-13), and say in the tool description that `undo_steps: 0` means `document_undo` would revert an earlier step. A partly changed call records one step and lists `unchanged` too. Test with a user Box made before the no-op call. |
| RT2 (high) | red team | FreeCAD does not record property group or description changes in undo, so `document_undo` reports `matches_pre_op` true but leaves them changed. Set group and description only when a property is created; a call that would change them on an existing property is refused before the bracket with `detail.code` `parameters.metadata_immutable`. Test: undo after a create restores everything; a metadata change on an existing property is refused. |
| RT3 (high) | red team | A NUL in a string value is cut ('rev A\x00…' stored as 'rev A') with status OK. Refuse strings containing NUL (and other characters FreeCAD cannot store, verified by a FreeCAD round trip) with `parameters.invalid_string`; never store a silently changed value. Test. |
| RT4 (medium, shared code) | red team | `rpc_dispatch` reads `exc.code` from any exception, so `script_exec` errors give an int `detail.code` (5, 404) that breaks the envelope schema, or a method object that `json.dumps` cannot encode. Read `code` only from the project's own refusal type(s) and only when it is a non-empty `str`; test with a script raising `OSError(5, ...)` and an exception with a `code` method. |
| RT5 (medium) | red team | A VarSet object named `W`, `mm` or `e` is created, but no expression can reference it. Apply the unit-symbol / reserved-name check to the VarSet name too. Test. |
| RT6 (medium) | red team | A parameter named `Shape` is not refused and always ends `SPEC_FAILED`. Add it (and any other property name that the AD-5 post-verify reads, verified in code) to the reserved names. Test. |
| RT7, RT8 (low) | red team | Fix if each is a small change in this Story's files; otherwise list with the reason in the spec. |

## After the fixes

1. Commit on your branch yourself (no trailer).
2. Three fresh lenses (round 2) on feac4bfd..HEAD with `quality-bar-13-9.md`; patch high/medium; commit.
3. `uv run --extra dev pytest tests/external -q` from Git Bash and the infc suite (FREECAD_USER_HOME temp); reply with SHA, lens ids, counts in at most 10 lines.
