# Story 13-fu: findings ledger

Quality bar: quality-bar-13-fu.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| RT-1 | Q2 | high | redteam-13-fu | open (T1) | probes/rt1_nested_sphere_e2e.py: nested spheres read overlap 0, real 4188.79 mm3 |
| RT-2 | Q2, Q5 | medium (product) | redteam-13-fu | open (T2) | probes/rt2_tolerance_factor.py: limit 1.45x stated |
| RT-3 | Q2 | medium (test) | redteam-13-fu | open (T3) | fake fuse contradicts kernel |
| RT-4 | Q2 | medium (test double) | redteam-13-fu | open (T4) | RaisingShape has no fuse() |
| RT-5 | Q3 | medium (pre-existing 13-7) | redteam-13-fu | open (T7: fix if measured small, else defer) | probes/rt5_pair_cost.py: one pair 108 s |
| F1 | Q3 | low | verifier-13-fu | open (T5) | test_query_tools.py:768 assertion swallowed |
| F2, RT-6 | Q2 | low | verifier-13-fu, redteam-13-fu | open (T6) | abs mutant and 3e-12 mutant survive |
| RT-7 | Q9 | low | redteam-13-fu | fixed (447806fb, verifier) | TC-17 code string |
| R1-1..R1-10 | Q1, Q2, Q5, Q9 | low-medium (builder triage; tolerance not pinned by real geometry found by all three lenses) | lenses r1: blind aae5596adec329663, edge af6950519014e9413, gap ac7f15d3daf10165c | fixed (8049378d) | builder mutants: tolerance 1e-9 -> 3 red, 1e-11 -> 2 red, fuse always-true -> 7 red, never -> 6 red; details in wt-13-fu spec-13-fu-followups.md triage table |
| R1-11..R1-16 | outside the bar / Q3 | low | same | rejected | evidence in spec-13-fu-followups.md (fused.Solids, volume recompute, deadline skip, timing runs, compound/BSpline, authorization claim) |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 65acb437 -> fix 8049378d | blind aae5596adec329663, edge af6950519014e9413, gap ac7f15d3daf10165c | n/a -> 0 (builder) | 10 | 0 | 0 |

Builder report: chat message 2026-11-25 (report file write refused by the platform for the subagent). Gates at 8049378d: infc 1266 OK (1 skipped); external 2109 passed / 6 skipped before patches, 593 subset after. Fix batch 8049378d: 2 product lines in queries.py, 8 in tool_catalog.py -> no new lens round; red team attacks it first.
| RT | 8049378d | redteam-13-fu (red team), verifier-13-fu | 0 -> 3 (RT-1 high, RT-2, RT-5) | 0 | 7 | 0 |

Red team FAIL reopens the loop as counted round 2: triage-13-fu-rt.md; after fixes, review r2 with three new lenses.
