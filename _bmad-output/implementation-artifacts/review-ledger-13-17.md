# Story 13-17: findings ledger

Quality bar: quality-bar-13-17.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| RT-1 | Q4, Q5, Q11 | high | redteam-13-17 | fixed-proven (bec5655c; tests red first; verifier r2: p2/p3b refused, mutant killed) | p2.py: Touched upstream -> cut OK 1500 (analytic 500); p3b.py: old shapes counted 8 pairs, real 1,680, 63.2 s |
| RT-2 | Q11 | high -> accepted limit (decision 53) | redteam-13-17 | deferred | p12.py: 2-deg crossing cylinder families under the pair limit: > 130 s / > 300 s |
| RT-3 | Q4 | medium (safe-side false refusal) | redteam-13-17 | deferred (decision 53) | p9.py: 60 disjoint slanted slots refused, raw cut 0.81 s |
| RT-4, RT-5 | Q9, Q10 | low | redteam-13-17 | fixed (bec5655c) | angle 1e20 deg accepted; description omits stale refusal |
| R3-H1 | Q11 | high | r3 edge aa2772b0d0fb15625 | fixed-proven (deaa2b25; in-input pass after faces and cross-input checks, budget = limit - across; 3,000 solids worst 2.7 s) | in-input pass quadratic when solids share one x range: 77.8 s on 16,000 solids |
| R3-M | Q4, Q10 | medium x3 | r3 blind aa81b9265c8f2f74e / gap abab6819dc0b0ed1b | fixed | "at least" for exact counts; cost comment 13.4 s -> 21.9 s; weak bbox unit test pinned |
| R3-D1 | Q11 | high -> accepted limit (decision 52) | r3 edge | deferred | two single-solid combs with crossing teeth (652 faces, 1 solid pair): common > 88 s; no face-pair limit |
| R2-H1 | Q4, Q11 | high | r2 edge a01f01637f581c30e | fixed-proven (ae2b07c3; refusal test written first; mutants no_inside_count, base_only_pairs killed) | one tool compound of mutually crossing solids passes the limits and runs > 600 s (Part::Cut fuses tool solids pairwise) |
| R2-M | Q3, Q4, Q5 | medium (product) x3 | r2 blind a2ea0b9875084fad9 / edge / gap ac166d7571f6da873 | fixed-proven (r3 no repeat) (d535dc18) | non-list tools TypeError; stale Touched input measured on its old shape (Cut 1500 vs 500) -> untrusted_shape; failed boolean left Touched reported as empty_result -> invalid_result |
| R1-H1 | Q4, Q11 | high | r1 edge a2657451cf9aeb4a1 | fixed-proven (4a61330b; 606-face refusal test, 960-pair timing < 60 s) | two 100-cylinder families: guard counts 200 pairs, run 68.9 s |
| R1-M1 | Q4 | medium (pre-existing predicate) | r1 edge | deferred (deferred-work 13-fu entry + §3.7.5 limit) | overlapping solids inside one compound: fuse 3000 instead of 2500 |
| R1-P | various | mixed | r1 blind a5e487dfb0784b0e2, edge, gap ae766ab6b3b4b053c | fixed-proven (r2 no repeat) (f693e7f8) | cost before isValid, invalid_result on failed boolean, Label/Name clash, size > 3.4e38, non-string kind, docs, limit-value tests |
| R1-R | outside the bar | low x7 | r1 lenses | rejected | see builder report |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | f693e7f8 | blind a5e487dfb0784b0e2, edge a2657451cf9aeb4a1, gap ae766ab6b3b4b053c | n/a -> 1 (H1) | 0 | 1 high + patched mediums | 0 |
| r2 | f693e7f8 -> d535dc18 (+ merge 8b33e36c) | blind a2ea0b9875084fad9, edge a01f01637f581c30e, gap ac166d7571f6da873 | 1 -> 1 (H1 new) | 1 | 1 high + 3 product medium | 0 |
| r3 | 8b33e36c -> ae2b07c3 -> deaa2b25 | blind aa81b9265c8f2f74e, edge aa2772b0d0fb15625, gap abab6819dc0b0ed1b | 1 -> 0 | 4 | 1 high (fixed in round) + 1 accepted limit | 0 |

Three rounds used. Next: verifier-13-17 (container TC-21) + redteam-13-17.
| RT | deaa2b25 | redteam-13-17 | 0 -> 1 (RT-1) + 1 accepted limit | 0 | 2 high (1 fix, 1 limit), 1 medium deferred | 0 |

Fresh builder-13-17b fixes triage-13-17-rt.md T1-T3.
| v2 | 6a320fd2 | verifier-13-17 r1 (deaa2b25 PASS, container TC-21 01-04 PASS) + r2 (6a320fd2 PASS) | 1 -> 0 | 2 (RT-1, F1) | 0 | 0 |

Closed; merged into feat. Low N2 (stale object in another document: message says recompute the document) left as wording.
