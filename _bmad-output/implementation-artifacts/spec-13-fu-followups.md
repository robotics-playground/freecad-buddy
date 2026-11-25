---
title: 'Epic 13 follow-ups: touching solids in query_interference, 13-18 low findings'
type: 'bugfix'
created: '2026-11-25'
status: 'done'
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

- The leader authorized one edit to `tool_catalog.py` (the `query_interference` description) after plan approval; the frozen "Never" line predates that decision.
- Tolerance 1e-12 relative to the summed volume; mutants 1e-11 and 1e-9 turn two and three tests red.
- Sweep limit mutants 10,000 and 2,999 each turn the boundary tests red.

## Spec Change Log

## Review Triage Log

Round 1 (lenses review-blind-hunter-r1-s13-fu, review-edge-cases-hunter-r1-s13-fu, review-verification-gap-finder-r1-s13-fu). Verdict, route.

| Finding | Verdict | Route | Evidence |
| --- | --- | --- | --- |
| Tolerance loosened up to 3.3e-10 keeps all tests green (Blind, Edge, Gap) | medium | patch | Real; fake-volume test scaled with the constant. Added real overlap cases 3.3e-12 (100 mm, 1,000 mm) and scaled fake test; mutants 1e-11 and 1e-9 red |
| Fuse uses the same intersector as `common`, so "proves" is too strong (Blind, Edge) | low | patch | Not reproduced in 25 probes by the Edge lens; design now states the limit |
| Absolute limit follows the large part for small-against-large (Blind) | low | patch | T-2 and design state it |
| Cost comment omits the fuse (Blind, Edge) | low | patch | Comment adds 0.35 s against 19 s; fuse after the deadline check unchanged |
| Catalog sentence implies a fuse at unknown distance (Blind) | low | patch | Reworded |
| "decision 41" ambiguous (Blind) | low | patch | Now "Epic 13 decision 41" in T-2 and design |
| Setup check inside Assert, common run twice (Blind) | low | patch | Moved to Arrange |
| TC-17 hash, `Big1/Big2` empty-common setup, no-op "document unchanged" clause (Blind, Gap) | low | patch | Hash `queries.py`; setup check added; fingerprint check |
| Pronoun "It" in the loft paragraph (Blind) | low | patch | Reworded |
| SKILL.md absolute claim vs BSpline limit (Blind) | low | patch | "usually" |
| Require `fused.Solids` like the skill script (Blind) | low | reject | Non-solid fuse has a volume gap anyway; fix adds a guard |
| Volumes recomputed per touching pair (Blind) | low | reject | Runs only after `distToShape` on contact pairs; fix adds caching |
| Skip fuse after deadline (Edge) | low | reject | Deadline is checked before every pair; fuse measured at 2% of pair cost |
| Mixed timing runs; 5,000-line recompute beside 3,000-line call (Blind) | low | reject | Rows are labelled recompute and whole call |
| Compound args, untrusted pair never fuses, BSpline touch untested (Blind) | low | reject | Compound-internal overlap is a documented non-goal; structure prevents the untrusted fuse; BSpline noise is not stable to pin |
| `tool_catalog.py` edit forbidden by spec; tasks unchecked (Blind) | false | reject | Leader authorized the edit; the lens did not see the spec file, which has the tasks checked |

Round RT (leader triage T1-T7) and round 2 (lenses review-blind-hunter-r2-s13-fu, review-edge-cases-hunter-r2-s13-fu, review-verification-gap-finder-r2-s13-fu).

| Finding | Verdict | Route | Evidence |
| --- | --- | --- | --- |
| T1 nested solids pass the fuse proof | high | patch | Probe point under a face of each shape classified against the other (`_solids_interpenetrate`); nested sphere tests red first, probe-removed mutant red |
| T2 stated limit wrong by 2/3 factor | medium | patch | Stated limit is 1.5e-12 everywhere; tests below (1.2e-12) and above (2.25e-12) the limit; tolerance 3e-12 and 5e-13 mutants red |
| T3, T4, T5, T6 test doubles and gaps | medium/low | patch | Misleading fake renamed; fakes record fuse calls; above-sum case; `abs` mutant red |
| T7 distToShape 108 s on a lid and 200 boxes | medium | patch | Section shows contact and the fuse proves touching: 1.4 s; 100 boxes 0.6 s; counter test red first |
| Section shortcut returned distance 0 across a real gap inside the shape tolerance (Edge, Gap) | high | patch | Boxes 1.5e-7 mm apart and 1e-3 mm apart with tolerance 1e-2 read failed at distance 0; now the shortcut needs the fuse proof, else `distToShape`; test red first, mutant red |
| Skill recipe gives 0 for nested solids (Gap) | medium | patch | Caution added to verification-kit and measuring-clearance |
| "loses two thirds" wording, pin example, test name "twice", timing labels, min_distance wording in T-2 and design, probe limit text, constant comments, TC-17 setup and visual note, `_FakeSolid.section` (Blind, Edge, Gap) | low | patch | Fixed |
| Section pass cost on disjoint pairs unmeasured (Blind) | low | patch | 0.01 s on 360 x 360 faces against 20 s |
| 40 s promise vs one kernel call (Blind) | low | reject | Recorded as deferred work and decision 45 |
| Curved probe raising on a valid contact (Blind) | low | reject | The result is the safe `boolean_failed` true |
| subTest tearDown/setUp (Blind) | low | reject | Works; helper would add code |

Round 3 (verifier-13-fu r2 D1, leader triage T1).

| Finding | Verdict | Route | Evidence |
| --- | --- | --- | --- |
| Section shortcut read distance 0 across small real gaps at an edge, a vertex or a curved surface (D1) | medium | patch | Shortcut and `_boundaries_meet` removed; `distToShape` runs again for every trusted pair, the fuse only when it returns 1e-7 mm or less; edge 1.5e-7 mm, sphere 2e-7 mm and tolerance-1e-2 edge 1e-3 mm tests red first, shortcut-restored mutant red |
| Cost of `distToShape` on a lid over many boxes unbounded again (RT-5) | medium | defer | `deferred-work.md` entry restored; T-2 and design state the cost |

## Design Notes

Measured on FreeCAD 1.1.4, development host (scratch probes). Touch, volume sum minus fuse volume, relative: face, edge, vertex boxes 1e-16; at offset 1e5 and sizes 1 to 1,000 up to 1e-14; filleted box on box 3.5e-13; 64+64 boxes 1e-14. Noise grows with offset over size (box 0.01 at offset 1e6: 1.5e-10; BSpline loft on a plate: up to 1.1e-10). Overlap with empty `common`: 100 mm boxes at depth 1e-7 mm (1e-3 mm3) give 3.3e-10. Tolerance 1e-12: above analytic noise, below that overlap. Noisier touches stay unmeasured (safe side). Fuse cost: 0.35 s at 384 x 384 faces, against 19 s for `distToShape` on the same pair.

## Verification

**Commands:**
- `uv run ruff check .`, `check_imports`, `check_status_vocab`, `gen_schemas --check`, `check_skill_shape` -- expected: OK
- freecadcmd `tests/run_tests.py` with private cfg and `FREECAD_USER_HOME` -- expected: OK
- `uv run --extra dev pytest tests/external -q` from Git Bash -- expected: no new failure
- Mutants: sweep limit 10,000 turns the new test red; removing the fuse proof turns the touch tests red
