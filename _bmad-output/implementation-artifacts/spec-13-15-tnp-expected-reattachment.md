---
title: 'TNP audit accepts expected re-attachment moves'
type: 'bugfix'
created: '2026-11-24'
status: 'draft'
route: 'dispatch'
review_loop_iteration: 0
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

</frozen-after-approval>

## Open Questions

1. Scope of the rule. Options: all subelement-link references (datum, sketch attachment, external geometry, `Fillet.Base`, `Pad.Profile`) — one mechanism, recommended; or only `AttachmentSupport` — matches T-8 wording, needs a property-name list, `Fillet.Base` keeps its false positive. Measured with the rule on all references: `Fillet.Base` Edge4 moves with Pad length and passes; Edge1/Edge2 stay `BROKEN` (FreeCAD renumbers them) so a real break still reports.
2. Accepted residual. An element that moves farther than its whole support moved (a pocket floor moves, support box unchanged) stays `REPOINTED`. Options: accept (conservative, strictly fewer false positives than today, recommended) or drop the distance bound (passes more, but then a witness tamper on a really changed support also passes; test `test_a_missing_entry_does_not_suppress_a_repoint_on_the_same_record` fails).

## Code Map

- `src/freecad_buddy/usecases/tnp_guard.py:693` -- `_grade_entry`: `if _witness_moved(before["witness"], after["witness"], tolerance):` -- the only line that grades the false positive. Cause: `_witness` (:168) is the absolute bounding box of the element, so a legitimate move of the element reads as a re-point.
- `tnp_guard.py:231` `_capture_entry`, `:307` `snapshot_references` -- add per-record whole-support witness.
- `tnp_guard.py:709` `_grade_entries`, `:785`, `:806` -- pass the live record to `_grade_entry`.
- `tests/infc/test_tnp_guard.py:216`, `:303`, `:574` -- planted witness cases; must stay green unchanged.
- `verification-design.md:228-249` §3.2 -- Layer 1 REPOINTED bullet; add the rule.
- `benchmarks/g2/fault-injection/planted_ops.py` -- G2 `tnp-*` ops; no witness-only case there (a, b, c, d, e grade `DROPPED`, `BROKEN`, Layer 2).

## Tasks & Acceptance

**Execution:**
- [ ] `src/freecad_buddy/usecases/tnp_guard.py` -- add `target_witness` to `RefRecord`; snapshot it; add `_follows_support`; guard :693 with it -- smallest change at the cause
- [ ] `tests/infc/test_tnp_guard.py` -- cases for the five new matrix rows (datum on Pad length, datum on sketch width, beyond-support, no history, name changed with support moved)
- [ ] `verification-design.md` -- §3.2 Layer 1 text and `RefRecord` block
- [ ] `docs/decisions/` -- short note beside 014: witness move excused only when same element and support moved

**Acceptance Criteria:**
- Given a datum on a Pad face, when `Pad.Length` changes, then the audit status has no `REPOINTED` and the datum finding is `PASS`.
- Given the three planted witness tests, when run unchanged, then they pass.
- Given the full infc suite and `tests/external`, when run, then no regression.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

Why the support-movement bound (not only "support changed"): measured on the prototype, "support changed" alone passed `test_a_missing_entry_does_not_suppress_a_repoint_on_the_same_record` (witness +500 beside a real pad shrink). Bound check: `max |element delta| <= max |support delta|`, over the 6 bounding-box components, same `ShapeType`, NaN reads as not bounded.

## Verification

**Commands:**
- `uv run ruff check .` -- expected: clean
- `uv run python scripts/check_imports.py` -- expected: OK
- `uv run pytest tests/external -q` -- expected: pass
- `freecadcmd -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` -- expected: all pass
