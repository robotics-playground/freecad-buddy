# Story 13-fu: findings ledger

Quality bar: quality-bar-13-fu.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| V2-D1 | Q2, Q3 | medium (product regression) | verifier-13-fu r2 | fixed-proven (1c21724b; small-gap test red at 04adaafa; shortcut-restored mutant 3 red; verifier r3 29/29 probes) | gap sweep: edge 1.5e-7 reads 0 (true 2.12e-7); tol 1e-2 sphere gaps up to 0.02 mm read 0; base returns true distance |
| R3-1 | Q1, Q2 | high | r3 lens blind ad7d1acd8d44c87e3 (builder-run) | fixed-proven (04adaafa; test red first; section-without-proof mutant 8 red) | first T7 version set distance 0 across a real gap inside tolerance |
| RT-1 | Q2 | high | redteam-13-fu | fixed-proven (6aa611dd; nested r10/r100 red->green; probe-removed mutant 3 red) | probes/rt1_nested_sphere_e2e.py: nested spheres read overlap 0, real 4188.79 mm3 |
| RT-2 | Q2, Q5 | medium (product) | redteam-13-fu | fixed-proven (limit stated 1.5e-12; tol 3e-12 and 5e-13 mutants red) | probes/rt2_tolerance_factor.py: limit 1.45x stated |
| RT-3 | Q2 | medium (test) | redteam-13-fu | fixed | fake fuse contradicts kernel |
| RT-4 | Q2 | medium (test double) | redteam-13-fu | fixed | RaisingShape has no fuse() |
| RT-5 | Q3 | medium (pre-existing 13-7) | redteam-13-fu | regressed (verifier r2 D1: shortcut reads distance 0 across small edge/vertex/curved gaps) -> shortcut removed, RT-5 deferred (triage-13-fu-v2.md) | probes/rt5_pair_cost.py: one pair 108 s |
| F1 | Q3 | low | verifier-13-fu | fixed (fakes record calls) | test_query_tools.py:768 assertion swallowed |
| F2, RT-6 | Q2 | low | verifier-13-fu, redteam-13-fu | fixed (fuse-above-sum case, abs mutant red) | abs mutant and 3e-12 mutant survive |
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
| r3 | 447806fb -> 6aa611dd -> 04adaafa | blind ad7d1acd8d44c87e3, edge ae1da2bd490b4bb7f, gap aeb5b4621abe2182b | 3 -> 0 | 4 (RT-1, RT-2, RT-5, R3-1) | 1 (R3-1, fixed in round) | 0 |

Three rounds used. No open high or product medium at 04adaafa. Leader decision: no fourth lens round (rule: stop after three); the final batch 6aa611dd..04adaafa is covered by verifier-13-fu's re-run with adversarial probes on the section shortcut and nested-solid probe (it already ran once; no second red team). Deferred: concentric nested pair at distance > 1e-7 reads disjoint (pre-existing 13-7); distToShape cost when boundaries do not meet (decision 45).
| v2 | 04adaafa | verifier-13-fu r2 (gates, mutants, probes, UAT TC-17 PASS) | 0 -> 1 | 0 | 0 | 1 (RT-5 fix regressed distance) |
| v3 | 1c21724b | verifier-13-fu r3 (gates, 29 probes, mutant, UAT TC-17 PASS) | 1 -> 0 | 1 | 0 | 0 |

Closed: verifier r3 PASS at 1c21724b; merged into feat/epic-13-mcp-usage-improvement as 2b6fbe2d. Deferred: RT-5 (distToShape cost with many contacts; lid x200 96.9 s), concentric nested pair at distance > 1e-7.
