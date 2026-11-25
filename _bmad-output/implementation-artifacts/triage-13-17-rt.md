# Story 13-17 red-team round: leader triage

Base: deaa2b25 (story/13-17-part-primitive-boolean). Report: `redteam-13-17.md` (RT-1..RT-5). Probes: scratchpad `redteam-13-17\` (`p2.py`, `p3b.py`, `p9.py`, `p12.py`; read-only — copy what you need). Decision 53 records the leader calls below.
Each non-doc fix needs a test that fails first, or a mutant that the new test kills.

| # | Source | Finding | Required fix |
| --- | --- | --- | --- |
| T1 | RT-1 (high, Q4/Q5/Q11) | `features.py:4252` the stale check reads only the input's own `State`; an input whose upstream object is Touched (A = Reverse(Mid), Mid Touched, A reads Up-to-date) is measured on its old shape: cut returns OK with volume 1500 (analytic 500) (p2.py); Draft arrays behind `Part::Compound` inputs: the guard counted 8 pairs on old shapes, accepted 1,680 real pairs, OK after 63.2 s (p3b.py). | Refuse (`part_boolean.untrusted_shape`, reason "input or a dependency needs recompute") when the input or ANY object in its dependency closure (`OutListRecursive`, plus links) is Touched, Invalid or `mustExecute()`; do not recompute other objects silently. Tests red first with p2 and a reduced p3b; mutant: dependency check removed -> red. Regression risk: inputs whose dependencies are fine must still pass — neighbours: every existing accepted-boolean test. |
| T2 | RT-4 (low, Q9) | Placement angle 1e20 deg becomes an identity-like rotation (1e20 % 360 = 280) with no error (13-16 parser `_placement_value`) | Refuse angles with `abs(angle) > 1e6` deg (`parameters.out_of_range`, same code as 13-16's bound) in `_placement_value`; keep its signature; test for both the 13-17 primitive and 13-16 `feature_set_parameters` paths. |
| T3 | RT-5 (low, Q10) | Tool description omits the stale-input refusal | Add it (with T1's wording) to the `feature_part_boolean` description and §3.7.5. |

## Not fixed, with the reason
- RT-2 (high, Q11): two cylinder families crossing at 2 deg pass the 1,000-pair guard and fuse for > 130 s (20x20) / > 300 s (25x25). Same class as decision 52: OCC boolean cost on curved, near-tangent intersections is not bounded by solid or face counts. Accepted as a documented limit under decisions 45 and 52 (leader, decision 53); the deferred entry from decision 52 gains this probe; §3.7.5 states that near-tangent curved crossings can exceed the budget.
- RT-3 (medium, Q4): disjoint slanted slots refused `too_complex` ("at least 941") because their bounding boxes overlap; raw cut 0.81 s. Safe-side false refusal (no wrong result, no hang). Deferred with the probe (unblock: an exact distance or OBB pre-filter measured cheaper than the boolean); §3.7.5 states that slanted, closely packed tools can be refused and how to split the call.

## After the fixes
Gates: full infc, `tests/external` (Git Bash), ruff, check_imports, check_status_vocab, gen_schemas --check, check_skill_shape, check_provenance. No lens round. verifier-13-17 re-runs the red team's p2 / p3b probes and the gates; the container TC-21 result it is producing now stays valid unless T1 changes an accepted path.
