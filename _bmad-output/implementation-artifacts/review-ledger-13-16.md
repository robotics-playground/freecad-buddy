# Story 13-16: findings ledger

Quality bar: quality-bar-13-16.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| RT-1 | Q6 | high | redteam-13-16 | fixed-proven (195868c5; verifier r2 PASS, mutants red) | rt2 P8b/P8c, rt3 P10: 1/3000 or 0.5 deg pre-value -> SPEC_FAILED rolled_back false while the document is restored |
| RT-2 | Q2 | medium (product) | redteam-13-16 | fixed-proven (195868c5; verifier r2 PASS, mutants red) | rt1 P7: 10**400 -> RECOMPUTE_ERROR via OverflowError |
| RT-3 | Q2, Q6 | medium (product) | redteam-13-16 | fixed-proven (195868c5; verifier r2 PASS, mutants red) | rt6: base x 1e150 commits, after-fingerprint raises, SPEC_FAILED with the change kept |
| RT-4 | Q4 | medium (test double) | redteam-13-16 | fixed-proven (195868c5; verifier r2 PASS, mutants red) | stub clamp FreeCAD never does; real 2**31 -> SPEC_FAILED SystemError |
| L-1, L-2 | Q1 | low | redteam-13-16 | fixed (195868c5) | stored placement not reported; stub hidden-offset test |
| R3-M1 | Q5 | medium (product) | r3 blind a6bfb8fa3172353c2 / edge a1d2efbdedff6878a | fixed-proven (15a097d6; mutant red) | `not_attached` tested the Hidden status; an object attached before its support had a shape keeps the offset Hidden yet applies it -> a valid write refused; now tests MapMode |
| R3-M2 | Q4 | medium (product) | r3 lenses | fixed-proven (15a097d6; mutant red) | isclose 1e-9 accepted a clamped integer (2**31 vs 2**31-1); integers compare exactly |
| R3-L | various | low | r3 lenses | fixed | probe rounding to 15 significant digits, NaN equality, limit message, clamp test, hints, doc fixes |
| R2-H1 | Q6 | high | r2 edge a34a89c4e42a1344f | fixed-proven (r3 no repeat) | 17-digit float reopens as 16 digits after a snapshot restore: rollback probe mismatch -> SPEC_FAILED, rolled_back false; `_comparable` rounds floats; mutant red |
| R2-M1 | Q4, Q6 | medium (test) | r2 gap a1943a2149033081f | fixed | no OK-path read-back test for angle / unitless float; quantity probe branch untested |
| R2-L | various | low | r2 blind a81d9eb183201e75f + others | fixed / 8 rejected | spec rows 21-37 in wt-13-16 |
| R1-M | Q1, Q2, Q7 | medium (product) x3 | r1 blind a91118f7dae0452aa / edge ae707f991cc5f9719 / gap a33ff8044dd65939f | fixed-proven (r2 lenses found no repeat) | failed calls lost feature/feature_state; axis lengths beyond 1e100/1e-100 or huge ints became Z or raised OverflowError; axis-only with zero angle dropped |
| R1-L | various | low x10 | r1 lenses | fixed | 20-row triage in wt-13-16 spec |
| R1-R | outside the bar | low x5 | r1 lenses | rejected | empty Label, MapMode+offset same call, Visibility abort escalation, repeat unique Label, preview of Label |
| R1-D | outside the bar | x2 | r1 lenses | numeric revert fixed (76946913, test red first); gap-list rows 33/42 deferred to 13-19 | |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 3b7242f4 (patches squashed) | blind a91118f7dae0452aa, edge ae707f991cc5f9719, gap a33ff8044dd65939f | n/a -> 3 (fixes unreviewed) | 0 | 3 | 0 |

Deviation accepted (leader): read-only placements are refused before the bracket (INVALID_INPUT), not rolled back; Q4 updated. Round 2 required (product mediums).
| r2 | 3b7242f4 -> 76946913 -> 5af36b75 | blind a81d9eb183201e75f, edge a34a89c4e42a1344f, gap a1943a2149033081f | 3 -> 1 | 3 | 2 (H1, M1) | 0 |

r2 found a high -> round 3 (last) after the builder merges the integration branch (13-13 and 13-15 now merged).
| r3 | 5af36b75 -> merge 0253cdd7 -> 15a097d6 | blind a6bfb8fa3172353c2, edge a1d2efbdedff6878a, gap a39c40cbf481743d3 | 1 -> 0 | 1 (H1) | 2 (fixed in round with mutants) | 0 |

Three rounds used; no open high or product medium. As for 13-fu and 13-13: verifier + red team attack the last batch instead of a fourth lens round.
| RT | 15a097d6 | redteam-13-16 | 0 -> 4 (RT-1 high, RT-2, RT-3, RT-4) | 2 (R3) | 4 | 0 |

Fresh builder-13-16b fixes triage-13-16-rt.md; verifier-13-16 re-runs.
| v2 | 195868c5 (+ doc fix) | verifier-13-16 r1 (15a097d6 PASS, container TC-20) + r2 (195868c5 PASS) | 4 -> 0 | 4 | 0 | 0 |

Closed; merged into feat.
