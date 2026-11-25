# Story 13-16: findings ledger

Quality bar: quality-bar-13-16.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R2-H1 | Q6 | high | r2 edge a34a89c4e42a1344f | fixed-unproven until r3 | 17-digit float reopens as 16 digits after a snapshot restore: rollback probe mismatch -> SPEC_FAILED, rolled_back false; `_comparable` rounds floats; mutant red |
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
