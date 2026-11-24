# Story 13-10 triage: round 2 (verifier + red team)

Base: f2a19ce8 on `story/13-10-set-expression`. Sources (this folder): `verify-13-10.md` (V1 .. V5), `redteam-13-10.md` (RT-1 .. RT-8). Use their reproductions as failing tests first. Leader decision 38.

| Id | Source | Required fix |
| --- | --- | --- |
| V1 (high, shared code) | verifier | A call that writes nothing (cycle refusal, equivalent text) leaves the bracket's application-level transaction open ("buddy: set expressions"); the next change lands in a hidden transaction and `document_undo` refuses. Fix in `run_mutation`: after commit or abort, close the application-level active transaction (`App.closeActiveTransaction()`, verified in FreeCAD source; same rule the Story 13-13 spec measured). Test for every exit path (commit with changes, commit with no change, abort, refusal inside the op) that no active transaction remains and the next tool call's undo works. Compare other tools' envelopes against base (L12). |
| RT-8 (high) | red team | A spreadsheet cell target (`Sheet.B1`) with a 31-char `sum(C1:ZZ16384)+…` held one call for 1,087 s (L2: the char cap bounds parsing, not evaluation). Refuse spreadsheet cells as targets (`expression.unsupported_property`), and refuse range references (`A1:B2` syntax) in expression text anywhere (`expression.range_unsupported`), because a range in a Pad.Length expression costs the same. Test both. |
| RT-3 (medium) | red team | Spreadsheet cell bindings are ignored by dependent cells and lost on save/reopen — closed by the RT-8 refusal; test that a cell target is refused. |
| V3 (medium) | verifier | `.AttachmentOffset.*` on an object whose `MapMode` is `Deactivated` (offset hidden and unused) reports bound but moves nothing. Refuse with `expression.unsupported_property` naming the reason (verify which properties FreeCAD ignores when not attached). |
| RT-4 (medium) | red team | Range-constrained properties are clamped silently (Revolution angle 400 → 40 deg solid reported as 400; Pad.Length −5 flips the pad). After recompute, read each bound property and compare with the evaluated expression; a mismatch rolls back with `expression.value_out_of_range` (L8). Test both cases. |
| RT-1 (medium) | red team | `undo_steps: 0` while FreeCAD recorded a step (in-bracket no-op on a touched document). Derive `undo_steps` from the measured UndoCount change, not from the tool's own guess. Test. |
| RT-2 (medium) | red team | int32 overflow stored as −2147483648 with status OK. Refuse integer results outside the property's range (`expression.not_finite` or a new `expression.value_out_of_range`). Test. |
| RT-5 (low) | red team | The `audit_references` exemption lets `sketch_remove_geometry` drop a bound constraint's binding with PASS (base rolled back). Key the exemption to the expression paths THIS op wrote (decision 014 style), so another tool that removes a binding still grades as before. Test the `sketch_remove_geometry` case against base behaviour. |
| V4 (low) | verifier | A cycle returns `SPEC_FAILED`; T-3 says `RECOMPUTE_ERROR`. Return `RECOMPUTE_ERROR` with `detail.code` `expression.cycle`. If this needs a hook in `transaction.py`, keep it minimal and named so Story 13-17 can reuse it (13-17 spec proposes `RecomputeFailure(code, message)`). |
| RT-6, RT-7 (low) | red team | Rounding/overflow through R1-D1, and `.Shape.Volume` reaching the bracket: refuse before the bracket. |
| V2 (gate) | verifier | `validators.yaml:97` `audit_references` `validator_sha` is stale. Re-score by running the scorers after all fixes. |

## After the fixes

1. Commit on your branch yourself (no trailer).
2. Shared code and core rules changed: run three fresh lenses (round 2) on f2a19ce8..HEAD with `quality-bar-13-10.md`. Patch high/medium; commit.
3. External (Git Bash, `uv run --extra dev`), infc (FREECAD_USER_HOME temp), check_provenance; reply with SHA, lens ids, counts in at most 10 lines.
