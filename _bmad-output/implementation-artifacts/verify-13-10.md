# Story 13-10 verification: `feature_set_expression`

Verifier: verifier-13-10. Date: 2026-11-24.
Artifact: commit `f2a19ce86f537d71b3187001270459542ecc6b31` (branch `story/13-10-set-expression`), base `3c8efd8d`.
Own copies: detached worktrees `fcb-verify-13-10` (head) and `fcb-verify-13-10-base` (base). Both removed at the end.
Evidence: `tests/uat/run/13-10-r1/` in the main repo (`evidence/`, `scripts/`).

## Verdict

**FAIL — 2 product defects and 1 gate failure. Fix before merge.**

| Id | Severity | Finding |
| --- | --- | --- |
| V1 | high | A cycle refusal, and an equivalent-text call, leave the bracket's transaction open at application level. The next document change goes into a hidden transaction named `buddy: set expressions`. `document_undo` then refuses. The CAP-2 undo chain broke live because of this. |
| V2 | high (gate) | `pytest tests/external` has 1 failure: `test_gate_g2_exit.py::test_leg_b_is_current_for_the_committed_g2_scores`. The committed `audit_references` `validator_sha` is stale. |
| V3 | medium | The tool binds `.AttachmentOffset.*` on an object that is not attached (`MapMode` `Deactivated`). FreeCAD marks that property Hidden and ignores it. The tool reports `bound`, the value reads 4 mm, and the geometry does not move. |
| V4 | low, contract | A cycle returns `SPEC_FAILED` with code `mutation.spec_failed`. T-3 says `RECOMPUTE_ERROR`. Decision 37 says the leader aligns T-3 at merge. |
| V5 | note (R1-S1) | The TNP exemption in `audit_references` changes the result of another tool. `sketch_remove_geometry` on geometry with a bound constraint was `SPEC_FAILED` (false BROKEN) at base. At head it is `OK`. I consider this a correction, not a regression. |

All other checks pass: static gates, infc (1115 tests), 5 required mutants (plus 3 more) each turn a named test red, the G2 TNP fault suite is the same at base and head, and the CAP-2 build, edit, read-back and full undo chain pass with typed tools only. The full undo chain passes only when no cycle or equivalent-text call comes before it (run B).

## 1. Gates and counts (head copy)

| Command (Git Bash, from the head copy) | Result |
| --- | --- |
| `uv run --extra dev ruff check .` | pass, exit 0 |
| `ruff format --check` on the 10 changed `.py` files | 1 file would be reformatted: `tests/external/test_feature_contract.py`. This was already true at base: the same check fails on the base copy. Not caused by this commit. |
| `uv run --extra dev python scripts/check_imports.py` | `check_imports OK` |
| `scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `scripts/check_skill_shape.py` | exit 0 |
| `scripts/check_provenance.py` | `check_provenance OK` |
| `uv run --extra dev pytest tests/external -q` | **1 failed, 2096 passed, 6 skipped** (234 s). Failure: V2. At base the same test file has 71 passed. |
| infc: `freecadcmd -u <tmp>/user.cfg -s <tmp>/system.cfg tests/run_tests.py`, `FREECAD_USER_HOME=<scratch>/home` | **Ran 1115 tests, OK (skipped=1)**, exit 0 |
| Source check under freecadcmd with the same env | `freecad_buddy.usecases.features` loads from `D:\Work\Personal\Sources\fcb-verify-13-10\src\...` and has `feature_set_expression`. The installed addon junction did not shadow it. |

### V2: stale `validator_sha`

```
tests\external\test_gate_g2_exit.py:718: AssertionError
E  AssertionError: ['audit_references (stale: source hash mismatch)']
```

`benchmarks/_registry/validators.yaml:97` commits `42570d97…`. The G2 scorer (`score_g2_infc.py`) on the head copy computes `e205922f32be86924f9de6a2eebd401f5f8a6194c531fa9a05e1cbc0e8152d08`. The sources it hashes are `usecases/tnp_guard.py` and `usecases/result_projection.py`. Both files have LF line endings in the checkout (`core.autocrlf=input`), so the mismatch is not caused by line endings. The builder re-scored before the last edit to `tnp_guard.py`. Fix: re-run the scorer and commit the block.

## 2. Envelope comparison, base against head (R1-S1, L12)

Script: `scripts/envelopes.py`. It runs one sequence under freecadcmd on each copy, then the envelopes are normalized (digests, times and paths masked) and compared.

| Tool call | Base | Head | Envelope equal |
| --- | --- | --- | --- |
| `feature_pad` 20x30 profile, 10 mm | OK, audit CLEAN | OK, audit CLEAN | yes |
| `feature_fillet` r=2 on the top front edge | OK, CLEAN | OK, CLEAN | yes |
| `feature_set_parameters` Pad Length 12 (moves the filleted edge) | SPEC_FAILED, `Fillet.Base=REPOINTED`, rolled back | same | yes, except `mapped_before` hash. That hash also changes between two base runs (`H268` / `Hf11`), so it is volatile. |
| `sketch_add_constraint` (pins a 4-DoF rectangle) | OK, CLEAN | OK, CLEAN | yes |
| `sketch_remove_geometry` of a line whose `Distance` constraint `extra_len` has an expression binding | **SPEC_FAILED**, `Loose.ExpressionEngine[.Constraints.extra_len]=BROKEN`, detail "Loose is no longer present in the document" (false: Loose exists) | **OK**, CLEAN, binding removed with the constraint | no (V5) |

G2 fault suite (`benchmarks/g2/fault-injection/score_g2_infc.py`, real planted TNP breaks), same result on both copies:

| Case | Base | Head |
| --- | --- | --- |
| `g2-fault-tnp-b-attachment-support-deleted` | DETECTED, SPEC_FAILED/FLAGGED | DETECTED, SPEC_FAILED/FLAGGED |
| `g2-fault-tnp-d-expression-rename-break` | DETECTED, RECOMPUTE_ERROR/FLAGGED | DETECTED, RECOMPUTE_ERROR/FLAGGED |
| `g2-fault-coincidental-witness-match` | DETECTED | DETECTED |
| 6 controls | PASS_CLEAN | PASS_CLEAN |
| `audit_references` total | planted 3, detected 3, false alarms 0 | same |

A real broken reference still grades BROKEN. The exemption applies only when the binding is absent from the post-op `written` reading and from the live reading, and its owner still exists (`tnp_guard.py:834-850`). Every `run_mutation` call passes `refs_written` (`transaction.py:681`), so the exemption covers every mutation tool. V5 is the one behaviour change I found.

## 3. Mutants

Driver: `scripts/mutant.sh`. Each mutant edits one line in the head copy, runs `infc.test_tnp_guard.ExpressionBindingTest` + `infc.test_feature_expressions` (56 tests) under freecadcmd, then restores the file with `git checkout`. Unmutated baseline: 56 ran, 0 failures.

| Mutant | Change | Red tests |
| --- | --- | --- |
| (a) remove the exemption | `False and paired is None …` (`tnp_guard.py:834`) | 6: `ExpressionBindingTest.test_Should_pass_When_the_op_wrote_the_removal_of_a_binding`, `BindTest.test_Should_clear_the_binding_and_keep_the_value_When_the_expression_is_null`, `BindTest.test_Should_not_flag_the_audit_When_a_binding_is_added_replaced_and_cleared`, `IntegrityTest.test_Should_clear_the_binding_When_it_sits_on_a_path_that_resolves_to_nothing`, `IntegrityTest.test_Should_clear_the_binding_When_the_path_names_the_constraint_by_index`, `UndoTest.test_Should_restore_the_binding_When_a_clear_is_undone` |
| (b) widen to any removed binding | delete `and key not in written_by_key` | `ExpressionBindingTest.test_Should_flag_broken_When_a_binding_vanishes_after_the_op_wrote_it` |
| (b2) extra: drop the owner check | delete `and doc.getObject(record["owner"]) is not None` | `ExpressionBindingTest.test_Should_flag_broken_When_the_owner_of_the_binding_is_removed` |
| (b3) extra: excuse when no written reading | delete `and written is not None` | `ExpressionBindingTest.test_Should_flag_broken_When_no_written_reading_is_given` |
| (c) let a cycle through | the `setExpression` exception handler does `continue` instead of raising (`features.py:2612-2615`) | 3: `RollbackTest.test_Should_roll_back_every_item_and_prove_it_When_a_later_item_closes_a_cycle`, `…_a_self_reference_When_an_item_binds_a_property_to_itself`, `…_restore_from_the_snapshot_When_the_abort_leaves_the_binding_in_place` |
| (d) remove the 400-char cap | `_MAX_EXPRESSION_LENGTH = 10**9` | `RefusalTest.test_Should_refuse_with_the_invalid_text_code_When_the_text_cannot_be_stored` (subtest length=401). The crash test was run separately (d2): **freecadcmd ended with a segmentation fault, exit 139**, during the `+` x1000 subtest. The cap is necessary. |
| (e) no-op returns `undo_steps: 1` | `features.py:2540` | 3: `NoChangeTest.test_Should_open_no_transaction_and_report_zero_undo_steps_When_the_stored_text_is_given`, `…_When_an_unbound_path_is_cleared`, `…_revert_the_earlier_step_When_undo_follows_a_call_that_changed_nothing` |

Result files: `evidence/mut-*.out`.

## 4. CAP-2 live (container, typed tools only)

Environment: `fcb-desktop` built from the head copy (`build_addon.py --release`, `docker compose … up -d --build`, `fcb-freecad start`). FreeCAD 1.1.4, pid 720. The MCP surface lists 51 tools, including `feature_set_expression`, `feature_parameters_define` and `query_parameters`. No `script_exec` in the CAP-2 runs. I used `script_exec` once after run A only to diagnose V1. That call is not part of the CAP-2 evidence. The GUI was driven with `cua-driver` 0.28.1 through the element tree (346–661 elements, not degraded): Isometric and Fit All buttons by `element_token`, then window captures.

Model: VarSet `Params` (width 20, depth 8, height 10, lift 0, datum_z 5 mm). Body, sketch `Profile` on XY with named constraints `width` and `depth`, `Pad` 10 mm, and datum plane `Datum` on `XY_Plane`, offset 5. One `feature_set_expression` call binds 5 items: `Profile .Constraints.width`, `.Constraints.depth`, `Pad Length`, `Profile .AttachmentOffset.Base.z`, `Datum .AttachmentOffset.Base.z`.

| Step | Result (run B, `evidence/cap2b-transcript.json`) |
| --- | --- |
| bind | OK, `bound` 5 rows with values (20, 8, 10, 0, 5 mm), `undo_steps: 1`, audit CLEAN |
| `query_parameters` | 5 bindings listed as `{object, path, expression}` |
| edit VarSet (30, 12, 15, 4, 9) | OK. `mutation.changed`: Pad volume 5400, com (15, 6, 7.5); Datum com z 9; Profile com z **0**. |
| read-back | `query_parameters` gives the new values. `query_mass_properties` Pad bbox 30 x 12 x 15 (was 20 x 8 x 10). `query_placement` Datum z 5 -> 9. |
| screenshots | `01-built.png` (20x8x10 pad, datum at z 5), `05-b-edited.png` / `02-edited.png` (larger pad, datum higher). |
| undo chain, 8 calls, each with `expect_fingerprint` = that call's `fingerprint_before` | all OK, `matches_pre_op: true`: edit, bind, datum, pad, geometry, sketch, body, define |
| after undo of edit | parameters back to 20/8/10/0/5, 5 bindings remain, Pad bbox 20 x 8 x 10 (`03-undo-edit.png` matches `01-built.png`) |
| after undo of bind | 0 bindings, values the same |
| end | `query_tree_summary`: 0 objects. `06-b-undone-to-start.png`: an empty document. |

Live refusals (run A, `evidence/cap2-transcript.json`). Each is `INVALID_INPUT` before the bracket:

- `5 deg` on Length gives `expression.unit_mismatch`.
- `1 mm / 0` gives `expression.not_finite`.
- `Length.x` gives `expression.invalid_path`.
- `.AttachmentOffset` (a whole Placement) gives `expression.unsupported_property`.
- A 1999-character chain gives `expression.invalid_text`. The FreeCAD pid stayed 720.
- A same-text rebind gives `OK`, `undo_steps: 0`, and no `mutation` block.

The cycle `Pad.Length + 1 mm` gives `SPEC_FAILED`, rolled back, with the message "Length reference creates a cyclic dependency" (V4).

### V1: the bracket's transaction stays open at application level

Run A (the cycle call came before the undo chain):

```
[cycle]     feature_set_expression status=SPEC_FAILED rolled_back=True
[undo_edit] document_undo status=OK
[undo_bind] document_undo status=INVALID_INPUT msg=CAP2_Expr has an open transaction; undo would commit it and revert the transaction beneath it. Commit or abort it first.
… every later undo refused the same way (04-a-undo-blocked.png)
```

Diagnosis with `script_exec` after run A: `HasPendingTransaction True`, `App.getActiveTransaction() = ('buddy: set expressions', 9)`, redo stack empty.

Headless reproduction (`scripts/pending_probe.py`, output `evidence/pending-head.out`):

```
bind OK:            app_active=None
cycle SPEC_FAILED:  app_active=('buddy: set expressions', 3) pending=False
after raw change:   app_active=('buddy: set expressions', 3) pending=True  names=['buddy: set expressions', 'buddy: set expressions', …]
probe2 equivalent (P.a*2 over stored 'P.a * 2') OK undo_steps=0: app_active=('buddy: set expressions', 7)
probe2 after raw change: pending=True
define-after-leak OK: app_active=None   (the next bracket clears it; the user's change is then committed under the name 'buddy: set expressions')
```

Cause: `Document::openTransaction` only sets the application's active transaction (`Document.cpp:339`). The document's own undo transaction opens later, on the first change. `Document::abortTransaction` and `commitTransaction` close the application transaction only `if (d->activeUndoTransaction)` (`Document.cpp:473-475`, `519-521`). `run_mutation` calls `document.openTransaction` (`transaction.py:675`). If the op writes nothing, its `commitTransaction` (`:691`) or `abortTransaction` (`:696`, `:717`) closes nothing. `feature_set_expression` gives two ordinary inputs that reach this:

1. A cycle that `setExpression` refuses before it writes (`features.py:2611-2615`).
2. An item list that is all equivalent text. The op skips every write (`features.py:2624`) and the bracket commits.

The next document change (a GUI edit, an undo recompute, a user action) opens a hidden transaction. `document_undo` refuses while it is open, and no typed tool can close it. The defect is in shared code (`run_mutation`). Any op that raises before its first write has the same effect. This story makes it reachable with normal input. I did not check base tools for a path that reaches it.

Reproduction: `feature_set_expression` with `[{object: Pad, path: Length, expression: "Pad.Length + 1 mm"}]`, then `document_undo` twice.

### V3: binding an inert `AttachmentOffset`

`sketch_create` with `plane: "XY"` makes `Profile` with `MapMode: Deactivated` and `AttachmentSupport: []` (read with `query_object`). FreeCAD hides `AttachmentOffset` when the object is not attached (`AttachExtension.cpp:765`, `AttachmentOffset.setStatus(Hidden, !bAttached)`), and the offset then has no effect.

`feature_set_expression` checks only `ReadOnly` (`features.py:2479`). So it binds `Profile .AttachmentOffset.Base.z`, reports `bound` with value 0 mm, and after the edit the value reads 4 mm. The pad still sits at z 0 to 15 (Profile com z 0 in `changed`).

The datum (attached) moved as expected. So CAP-2's "attachment offset" criterion holds, but only for an attached object. Suggested refusal: `expression.unsupported_property` when the root property has `Hidden` status, or the attachment is deactivated.

## 5. Quality bar and acceptance criteria

| Q / AC | Verdict | Evidence |
| --- | --- | --- |
| Q1 bind/clear in one transaction, outputs | pass | infc BindTest; live bind `undo_steps: 1` |
| Q2 CAP-2 paths | pass with V3 | live: `.Constraints.width/depth`, `Length`, `Datum .AttachmentOffset.Base.z` drive geometry; whole Placement refused |
| Q3 cycle and bad-recompute rollback with proof | pass for the document; **fail for transaction state (V1)** | RollbackTest; mutant (c); live cycle rolled back, then the application transaction leaked |
| Q4 TNP exemption keyed to the written record | pass | ExpressionBindingTest; mutants a, b, b2, b3; G2 suite same as base; V5 |
| Q5 refusal codes, 400-char cap with measurement | pass | RefusalTest/IntegrityTest; mutant (d)/(d2) exit 139; live codes. `expression.not_integer` is an extra code beyond decision 37; it is in `mcp-tools-design.md` §3.7.2. |
| Q6 no-op opens no transaction, `undo_steps: 0` | pass for the pre-bracket no-op; **the in-bracket equivalent-text no-op leaks (V1)** | NoChangeTest; mutant (e); probe2 |
| Q7 one undo per call; `changed` shows moved geometry | pass when V1 is not triggered | run B undo chain, all `matches_pre_op: true`; edit `changed` lists Pad and Datum |
| Q8 `scalar_reading` public, query outputs unchanged | pass | infc 1115 OK |
| Q9 design doc agrees with code, gates | **fail (V2)**; design row, counts 50/51 and schema agree with the live tool list (51) | gates table |
| AC1 constraint and attachment offset follow a VarSet edit | pass for constraint and datum offset; V3 for a non-attached sketch | run B |
| AC2 gen_schemas, check_imports, ruff, pytest external all pass | **fail (V2)** | gates table |

## 6. Teardown

FreeCAD stopped (`fcb-freecad stop`), `docker compose … down` (container and network removed), both worktrees removed, no background process left. Image `fcb-desktop:local` now holds the build from `f2a19ce8`; the next owner rebuilds. No file outside my scratch folder, the new run folder `tests/uat/run/13-10-r1/` and this report was written.

---

# Round 2

Artifact: `55d55b24` (merge of round-2 fixes `eca29153` + `9a23aca5` with feat `78229202`, which carries 13-11 `document_object_delete`). Rules: decision 38, `triage-13-10-r2.md`.
Copies: detached worktrees at `55d55b24` (head), `78229202` (feat), `3c8efd8d` (base). All removed at the end.
Evidence: `tests/uat/run/13-10-r2/` in the main repo (`evidence/`, `scripts/`).

## Verdict

**PASS.** Every round-1 finding (V1–V4) and red-team row (RT-1, RT-2, RT-4, RT-5, RT-8) is fixed. For each row, reverting its fix turns a named test red. The run that broke in round 1 (cycle, then the undo chain) now undoes all 8 steps back to an empty document in the container. The envelopes of other tools match feat `78229202`. `sketch_remove_geometry` again grades as at base.

Open notes (none block the merge):

- N1 (low, test quality): `ClosureTest.test_Should_leave_no_transaction_open_and_keep_undo_working_When_a_cycle_is_refused` stays green when the V1 fix is reverted. A successful call between the cycle and the undo masks the leak. The shared tests in `ApplicationTransactionTest` and the live run A cover the path. A stronger test would undo directly after the cycle, then undo again.
- N2 (pre-existing, not this story): two timing tests fail at random under load. `test_marshal_self_submit.py::test_submitting_to_a_loop_this_thread_must_pump_deadlocks` failed in one full run. `test_mcp_cache_proxy.py::test_should_answer_both_calls_when_two_parallel_calls_meet_a_lost_session` failed in another full run and in 1 of 3 runs alone. This story does not change either file or its subject.

## Gates and counts (head `55d55b24`)

| Command | Result |
| --- | --- |
| `ruff check .`, `check_imports`, `check_status_vocab`, `gen_schemas --check`, `check_skill_shape`, `check_provenance` | all exit 0 |
| `ruff format --check` on the 10 Python files changed in round 2 | all formatted |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | 2106 passed, 6 skipped, 1 failed (N2, a different flaky test in each of 2 runs). `test_gate_g2_exit.py` passes, so V2 is closed. |
| infc `tests/run_tests.py`, `FREECAD_USER_HOME` temp | **Ran 1186 tests, OK (skipped=1)** |
| G2 scorer `score_g2_infc.py` | `audit_references` planted 3, detected 3, false alarm 0, same as base. Committed `validator_sha` is current. |

## Fix proof: revert each fix, named test turns red

Driver `scripts/mutant2.sh`, scope `test_feature_expressions` + `ExpressionBindingTest` + `ApplicationTransactionTest` (82 tests). Unmutated: 82 ran, 0 failures. Results: `evidence/mut-*.out`.

| Row | Revert | Red tests |
| --- | --- | --- |
| V1 | `shim.close_pending_transaction` closes nothing | `ApplicationTransactionTest.…_When_the_op_writes_nothing_and_commits`, `…_When_the_op_raises_before_its_first_write`, `…_close_the_transaction_of_the_bracket_name_When_it_is_left_open`, `ClosureTest.…_When_every_item_is_equivalent_text` (4) |
| RT-8 cell target | drop the `Spreadsheet::Sheet` refusal | `RoundTwoRefusalTest.…_unsupported_code_When_the_target_is_a_spreadsheet_cell` |
| RT-8 range | drop the `_CELL_RANGE` refusal | `RoundTwoRefusalTest.…_range_code_When_the_text_holds_a_cell_range` (6 subtests) |
| V3 | drop the Hidden `AttachmentOffset` refusal | `RoundTwoRefusalTest.…_unsupported_code_When_the_object_is_not_attached` |
| RT-4 / RT-2 precheck | `_range_problem` returns None | `…_When_a_pad_length_is_negative`, `…_When_a_revolution_angle_exceeds_a_full_turn`, `…_When_an_integer_leaves_the_int32_range` (2 subtests), `…_When_a_percent_parameter_exceeds_100` |
| RT-4 in-bracket | `recompute_check` raises nothing | `IntegrityTest.…_not_finite_code_When_a_sibling_item_makes_a_value_infinite`, `…_range_code_When_a_new_binding_drives_another_out_of_range` |
| RT-1 | `undo_steps` from `applied and UndoMode` again | `ClosureTest.test_Should_report_the_recorded_step_When_a_no_change_call_runs_on_touched_objects` |
| RT-5 | exemption without the `removed_bindings` key | `OtherToolTest.…_When_another_tool_removes_its_constraint`, `ExpressionBindingTest.…_When_the_op_removed_a_binding_without_reporting_it` |
| V4 | cycle raises `RuntimeError` again | `ClosureTest.…_When_a_cycle_is_refused`, `RollbackTest.…_When_a_later_item_closes_a_cycle` |

## L12 envelopes

`scripts/envelopes2.py` (head vs feat `78229202`, `evidence/env2-*.json`). The application transaction was `None` and `HasPendingTransaction` was false after every call:

| Call | Head vs feat |
| --- | --- |
| `feature_parameters_define` new, then the same values again (no-op) | equal |
| `feature_pad` | equal |
| `document_object_delete`: refused with dependents (`delete.has_dependents`), plain delete, delete with dependents (an expression holder), unknown object | equal |
| `document_undo` | equal except the random document handle |

`scripts/envelopes.py` (head vs base `3c8efd8d`, `evidence/env-*.json`). `feature_pad`, `feature_fillet`, `sketch_add_constraint` and `feature_set_parameters` are equal (the last differs only in the per-run mapped-name hash). `sketch_remove_geometry` of a bound constraint gives `SPEC_FAILED` with `ExpressionEngine[.Constraints.extra_len]=BROKEN` at head and at base, 0 diffs. RT-5 behaves as at base.

## Container (rebuilt from `55d55b24`; FreeCAD 1.1.4, 52 tools; typed tools only)

**Run A replay** (`evidence/runA-transcript.json`, `runA.log`; the round-1 order that broke). Steps: build, bind, VarSet edit, read-back. Then, before any undo:

- same-text no-op: `undo_steps 0`
- equivalent text `" Params.height"`: OK, `unchanged`, `undo_steps 0`, with a mutation block
- `feature_parameters_define` no-op
- refusals: `expression.unsupported_property` for the unattached `Profile .AttachmentOffset.Base.z` (V3); `expression.range_unsupported` for `sum(A1:ZZ16384) + 1 mm` in 0.014 s (RT-8); `expression.value_out_of_range` for `-5 mm` on Length (RT-4); `expression.unsupported_property` for `.Shape.Volume` (RT-7); and the round-1 unit, inf, dead-path, whole-Placement and 1999-char refusals
- cycle: `RECOMPUTE_ERROR` with code `expression.cycle`, rolled back (V4)

Then the undo chain: **all 8 `document_undo` calls OK, `matches_pre_op: true`**. Undo names were `define parameters on Params` / `set expressions 1` / datum / pad / geometry / sketch / body / define. After the undo of the edit: 20/8/10/0/5 and 4 bindings. After the undo of the bind: 0 bindings. End: 0 objects.

Screenshots: `01-A-built`, `02-A-edited` (larger pad, datum higher), `03-A-undo-edit` (back to the built state), `04-A-undone-to-start` (empty document; the tree shows only the document). No scratch probe document appeared in the GUI.

**CAP-2 run B** (`evidence/cap2b-transcript.json`; build, bind, edit, read-back, 8 undos). Bind OK, `undo_steps 1`. Edit: Pad 30 x 12 x 15, Datum z 9. All 8 undos OK with `matches_pre_op: true`. End: 0 objects (`05-B-edited`, `06-B-undone-to-start`). The script's post-chain calls address objects that the undo had already removed. They return `unknown object`, as in round 1, and grade nothing.

## Teardown

FreeCAD stopped, `docker compose … down`, three worktrees removed, nothing running. Image `fcb-desktop:local` holds the build from `55d55b24`.
