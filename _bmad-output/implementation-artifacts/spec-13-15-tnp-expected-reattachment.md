---
title: 'TNP audit accepts expected re-attachment moves'
type: 'bugfix'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '538db0be3f566ebb9082d5e60ee4dc91d3ca5a0d'
context:
  - '{project-root}/docs/decisions/014-tnp-intended-target-is-what-the-op-wrote.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A datum plane attached to a Pad face gets `REPOINTED` when a driving value (Pad `Length`, sketch width) moves that face. The reference did not change. The element moved. Typed mutation rolls back (`post_verify` fails on a flagged audit). Agent then drops to `script_exec` (usage-evidence.md: 5 audit flags, agent calls it a "false positive").

**Approach:** Layer 1 accepts a witness move when FreeCAD itself says the element is the same one (equal mapped name, equal history source) AND the support object changed AND the element moved no farther than its support moved. Every other witness move stays `REPOINTED`.

## Boundaries & Constraints

**Always:** Layer 2 still runs on an excused entry. `BROKEN`, `DROPPED`, changed-mapped-name, changed-target, `ExpressionEngine` results stay as today. An entry with no mapped name, or no history on either side, keeps today's verdict (witness move = `REPOINTED`).

**Never:** No exemption keyed to the owner object or to "support unchanged name only". No new tool parameter. No change to `run_mutation` or the `op` contract. No change to `contracts/` or the JSON schemas.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Datum follows Pad | Datum on `Pad.Face6`; `Pad.Length` 10 to 15 | `PASS` (Layer 2, "descends from the same source element") | N/A |
| Datum follows sketch width | Same datum; sketch width 20 to 30 | `PASS` | N/A |
| Planted witness move | Same name, same history, snapshot witness +5, support unchanged | `REPOINTED` layer 1 "witness moved" | N/A |
| Move beyond support move | Support moved 9, element witness moved 500 | `REPOINTED` layer 1 | N/A |
| Name changed | Mapped name differs | `REPOINTED` layer 1 "maps to a different element" | N/A |
| No history | History `None` on a side | `REPOINTED` layer 1 (as today) | N/A |
| Silent drop, fillet, G2 `tnp-a/e`, coincidental | Unchanged inputs | Unchanged verdicts | N/A |

## Decisions

User answers, 2026-11-25 (epic decision 40):

1. Scope: the rule applies to every sub-element link (datum, sketch attachment, external geometry, `Fillet.Base`, `Pad.Profile`) through one mechanism.
2. Residual accepted: an element that moves farther than its whole support stays `REPOINTED`. The distance bound stays; `test_a_missing_entry_does_not_suppress_a_repoint_on_the_same_record` stays green.

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/tnp_guard.py:703` -- `_grade_entry`: `if _witness_moved(before["witness"], after["witness"], tolerance):` -- the only line that grades the false positive. Cause: `_witness` (:169) is the absolute bounding box of the element, so a legitimate move of the element reads as a re-point.
- `tnp_guard.py:232` `_capture_entry`, `:308` `snapshot_references` -- add per-record whole-support witness.
- `tnp_guard.py:719` `_grade_entries`, `:795`, `:816` -- pass the live record to `_grade_entry`.
- `tests/infc/test_tnp_guard.py:216`, `:303`, `:574` -- planted witness cases; must stay green unchanged.
- `verification-design.md:228-249` §3.2 -- Layer 1 REPOINTED bullet; add the rule.
- `benchmarks/g2/fault-injection/planted_ops.py` -- G2 `tnp-*` ops; no witness-only case there (a, b, c, d, e grade `DROPPED`, `BROKEN`, Layer 2).

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/tnp_guard.py` -- add `target_witness` to `RefRecord`; snapshot it; add `_follows_support`; guard :693 with it -- smallest change at the cause
- [x] `tests/infc/test_tnp_guard.py` -- cases for the five new matrix rows (datum on Pad length, datum on sketch width, beyond-support, no history, name changed with support moved)
- [x] `verification-design.md` -- §3.2 Layer 1 text and `RefRecord` block
- [x] `docs/decisions/` -- short note beside 014: witness move excused only when same element and support moved

**Acceptance Criteria:**
- Given a datum on a Pad face, when `Pad.Length` changes, then the audit status has no `REPOINTED` and the datum finding is `PASS`.
- Given the three planted witness tests, when run unchanged, then they pass.
- Given the full infc suite and `tests/external`, when run, then no regression.

## Implementation Notes

- `RefRecord.target_witness` holds the whole target shape's witness, read once per target per `snapshot_references` walk.
- `_axis_shifts` returns the signed per-axis face shifts, or `None` for an unreadable side, a type change or a non-finite component. `_follows_support` reads `None` as "not excused".
- `_grade_entries` takes the baseline and live records so it can compute the support travel once per record.
- The G2 scorer refreshed `validator_sha` for `audit_references` in `benchmarks/_registry/validators.yaml`; sensitivity 1.0, false alarm 0.0, n=3 are unchanged.

## Spec Change Log

## Review Triage Log

Round 1 (three lenses, opus). Verdict, route, evidence.

| # | Finding | Verdict | Route | Evidence |
| --- | --- | --- | --- | --- |
| 1 | Support bound ignores direction (blind, edge) | medium | patch | Element 5 in X beside support 5 in Z passed `max <= max`. Per-axis bound added; `test_Should_not_excuse_the_move_When_it_runs_along_an_axis_the_support_did_not_move_on`. |
| 2 | No test on the `written` baseline branch (blind, edge, gap) | medium | patch | Production `run_mutation` passes `written`. Added `test_Should_pass_the_datum_When_the_written_reading_is_taken_before_recompute` and a `feature_set_parameters` test. |
| 3 | NaN support test never moves the support (blind, gap) | low | patch | Test now grows the pad before planting NaN. |
| 4 | History-equality mutant survives; no both-None history or mapped test (blind, gap) | medium | patch | Layer assertion added; `FollowsSupportTest` cases for no history, no mapped name, different source. |
| 5 | Layer 2 adds no detection for an excused entry (blind) | false | rejected | The spec Always clause requires Layer 2 to run on an excused entry. It is a guard against a future change to the excuse rule, not a duplicate detector. |
| 6 | Curved element tolerance under GUI mesh deflection (blind) | maybe-false | defer | Not measurable headless. Entry in `deferred-work.md` names what settles it. |
| 7 | Fillet test expects FLAGGED without showing a real break (blind) | low | patch | Test now asserts `fillet.isValid()` is false: FreeCAD itself marks the fillet invalid (Layer 0). |
| 8 | `validator_sha` refreshed with no scoring run (blind) | false | rejected | `score_g2_infc.py` ran under freecadcmd and wrote the block: audit_references planted 3, controls 6, sensitivity 1.0, false alarm 0.0, same as the committed `last_run`. |
| 9 | Design `RefRecord` block drift (blind) | low | defer | Pre-existing drift; the spec allows only the new field. Entry in `deferred-work.md`. |
| 10 | Docstrings not updated (blind) | low | patch | Module, `snapshot_references`, `audit_references` and `_grade_entry` docstrings updated. |
| 11 | Sketch width test fragile and weak (blind) | low | patch | Index from `addConstraint`; layer asserted; datum placement asserted. |
| 12 | Decision 017 lacks alternatives and links (blind) | low | patch | Sections added. |
| 13 | Unreadable target shape drops the whole record (edge) | low | patch | `_support_witness` returns `None` on an exception, as `_witness` does. |
| 14 | Support `ShapeType` change keeps `REPOINTED` (edge) | low | rejected | Safe direction; the excuse needs a readable, same-type support. A type change is not a reachable edit of a Pad. |

Round 2 (three lenses, opus, on the round-1 fix batch).

| # | Finding | Verdict | Route | Evidence |
| --- | --- | --- | --- | --- |
| R2-1 | Per-axis bound ignores sign: an element moving -5 beside a support growing +5 is excused (blind, edge) | medium | patch | `test_Should_flag_repointed_When_the_element_moved_against_the_direction_of_its_support` was red; signed shifts and an interval test now. |
| R2-2 | Written-baseline test cannot fail if the baseline is swapped (blind) | medium | patch | New `test_Should_grade_against_the_written_support_When_the_op_wrote_the_reference` plants NaN in the written support only; red under the swap mutant. |
| R2-3 | NaN test does not kill the dropped `isfinite` guard (blind, gap) | low | patch | NaN moved to a maximum-face position; red under the mutant. |
| R2-4 | Per-axis rule never exercised on real geometry (blind) | low | patch | New cross-axis audit test. |
| R2-5 | `_support_witness` exception guard untested (blind, gap) | low | patch | Stub with a raising `Shape`; red under the mutant. |
| R2-6 | Minimum-face half of the travel never checked (gap) | low | patch | Unit cases plus a reversed-pad audit test. The shipped code was already correct. |
| R2-7 | End-to-end test passes if the datum is never recorded (blind) | low | patch | Asserts the datum record exists in the snapshot. |
| R2-8 | Decision 017: "two independent identity signals" is wrong (blind) | low | patch | History source is decoded from the mapped name; text corrected in 017 and the design. |
| R2-9 | Decision 017 names the snapshot, production uses the written reading (blind) | low | patch | Baseline sentence corrected. |
| R2-10 | Second residual missing from the design; "decision 40" ambiguous; alias placement (blind) | low | patch | Design text, `epic-13-decisions.md` pointer, alias moved beside `Witness`. |
| R2-11 | Rotated support moves an element beyond its bounding-box faces (edge) | low | rejected | A false positive on the safe side; documented as a residual in 017, a fix needs the support frame and adds complexity. |

## Design Notes

Why the support-movement bound (not only "support changed"): measured on the prototype, "support changed" alone passed `test_a_missing_entry_does_not_suppress_a_repoint_on_the_same_record` (witness +500 beside a real pad shrink). Bound check: per axis, each signed shift of the element's two bounding-box faces lies between zero and the support's own two face shifts; same `ShapeType`; a non-finite value reads as not bounded.

## Verification

**Commands:**
- `uv run ruff check .` -- expected: clean
- `uv run python scripts/check_imports.py` -- expected: OK
- `uv run pytest tests/external -q` -- expected: pass
- `freecadcmd -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` -- expected: all pass
