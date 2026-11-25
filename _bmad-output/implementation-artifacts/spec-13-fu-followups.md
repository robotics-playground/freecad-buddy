---
title: 'Epic 13 follow-ups: touching solids in query_interference, 13-18 low findings'
type: 'bugfix'
created: '2026-11-25'
status: 'in-progress'
route: 'dispatch'
baseline_commit: '3df33fbdb1d4749d4e76caef9c4d813a141a3a96'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-13-decisions.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-13-lessons.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** (A) `query_interference` reads two valid solids that only touch as `boolean_failed` true, because `Shape.common` returns an empty shape at distance 0 (FreeCAD 1.1.4). The caller cannot tell touching from a broken boolean. (B) Three low findings from Story 13-18 round 2: no test pins the sweep cost limit; the design doc says every closed loft builds invalid; two code comments quote shorter timings than measured.

**Approach:** (A) Decision 41, option (b): when `common` raises or is empty and `min_distance` is at most the contact distance for two trusted solids, fuse the pair. A valid fuse whose volume equals the sum of the two volumes within a measured tolerance proves touching: `common_volume` 0, `boolean_failed` false. Any other result keeps `boolean_failed` true and `common_volume` null. (B) Add a boundary test, correct the design sentence and the comments.

## Boundaries & Constraints

**Always:** An empty or failed boolean never reads as no overlap unless the fuse proves it. The fuse runs only inside the existing bounds (face product 150,000 checked before any pair; 40 s between pairs). Booleans run on the copies. Tolerance and costs are written beside the constant with the measurement.

**Never:** No edit of `script_exec.py`, `transaction.py`, `tool_catalog.py`, `rpc_listener.py`, `mcp_server.py`, `tnp_guard.py`. No change to T-2 outside the one paragraph at `tool-contracts.md:83-86`. No new tool input or output field.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Face, edge, vertex touch | Valid boxes; `common` empty; distance 0 | `common_volume` 0, `min_distance` 0, `boolean_failed` false | N/A |
| Overlap with empty `common` | Boxes overlapping by about 1e-3 mm3 at depth 1e-7 mm; `common` empty | `boolean_failed` true, `common_volume` null | fuse volume gap above tolerance |
| Fuse invalid, raises, or empty | Fuse not valid, raises, or volume not finite | `boolean_failed` true | N/A |
| `common` raises, distance unknown | Distance null | `boolean_failed` true; no fuse | N/A |
| Untrusted shape or pair above face limit | As today | As today | As today |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/queries.py:811` `_measure_interference` -- add the fuse cross-check on the empty-at-contact branch (line 843); new constant beside `_CONTACT_DISTANCE_MM` (line 689) with the measurement.
- `tests/infc/test_query_tools.py:481` `QueryInterferenceTest`; line 607 `test_Should_flag_a_failed_boolean_When_two_solids_only_touch_at_a_face` is inverted; `_FakeSolid` (line 470) lacks `fuse` and stays a failed-fuse stand-in.
- `_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md:83-86` T-2 paragraph; `mcp-tools-design.md` line 344 (§3.2.3) and line 132 (§2 row).
- Skills text on touching pairs: `skills/freecad-scripting-idioms/references/gap-list.md:36`, `skills/verification-thinking/SKILL.md:64`, `skills/verification-thinking/references/measuring-clearance-and-sections.md:14-35`, `skills/code-cad-conversion/references/verification-kit.md:182-192`.
- `src/freecad_buddy/hosts/tool_catalog.py:1673-1676` says "solids that only touch also give this": stale after A. Not edited here; leader decides.
- `src/freecad_buddy/usecases/features.py:845,855` timing comments; `:857` `_SWEEP_MAX_COST`; `tests/infc/test_feature_tools.py:3062` `SweepTest`; `mcp-tools-design.md:734,738` closed-loft sentence and timings.
- UAT: new `tests/uat/testcases/TC-17-query-interference-touching.md` (fixture built with `script_exec`, as the 13-7 replay did).

## Tasks & Acceptance

**Execution:**
- [x] `queries.py` -- fuse cross-check with relative tolerance 1e-12 of the volume sum -- decision 41
- [x] `test_query_tools.py` -- touch (face, edge, vertex), 1e-3 mm3 overlap with empty `common`, fuse invalid, fuse raises, common raises with distance 0 and valid fuse, read-only fingerprint kept
- [ ] T-2, design §3.2.3 and §2 row, four skill files -- new touching reading
- [x] `test_feature_tools.py` -- 3001-line spine refused `sweep.too_complex` with the real limit; 3000-line cost not above the limit
- [x] `features.py` comments; `mcp-tools-design.md:734,738` -- measured timings, closed-loft sentence
- [x] `deferred-work.md` -- mark the 13-18 low entry resolved; TC-17 UAT fixture

**Acceptance Criteria:**
- Given two valid boxes touching at a face, edge or vertex, when measured, then `boolean_failed` is false and `common_volume` is 0.
- Given the sweep limit set to 10,000, when `SweepTest` runs, then the new test fails.
- Given all gates, when run, then they pass.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

Measured on FreeCAD 1.1.4, development host (scratch probes). Touch, volume sum minus fuse volume, relative: face, edge, vertex boxes 1e-16; at offset 1e5 and sizes 1 to 1,000 up to 1e-14; filleted box on box 3.5e-13; 64+64 boxes 1e-14. Noise grows with offset over size (box 0.01 at offset 1e6: 1.5e-10; BSpline loft on a plate: up to 1.1e-10). Overlap with empty `common`: 100 mm boxes at depth 1e-7 mm (1e-3 mm3) give 3.3e-10. Tolerance 1e-12: above analytic noise, below that overlap. Noisier touches stay unmeasured (safe side). Fuse cost: 0.35 s at 384 x 384 faces, against 19 s for `distToShape` on the same pair.

## Verification

**Commands:**
- `uv run ruff check .`, `check_imports`, `check_status_vocab`, `gen_schemas --check`, `check_skill_shape` -- expected: OK
- freecadcmd `tests/run_tests.py` with private cfg and `FREECAD_USER_HOME` -- expected: OK
- `uv run --extra dev pytest tests/external -q` from Git Bash -- expected: no new failure
- Mutants: sweep limit 10,000 turns the new test red; removing the fuse proof turns the touch tests red
