# Story 13-16: findings ledger

Quality bar: quality-bar-13-16.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-M | Q1, Q2, Q7 | medium (product) x3 | r1 blind a91118f7dae0452aa / edge ae707f991cc5f9719 / gap a33ff8044dd65939f | fixed-unproven until r2 | failed calls lost feature/feature_state; axis lengths beyond 1e100/1e-100 or huge ints became Z or raised OverflowError; axis-only with zero angle dropped |
| R1-L | various | low x10 | r1 lenses | fixed | 20-row triage in wt-13-16 spec |
| R1-R | outside the bar | low x5 | r1 lenses | rejected | empty Label, MapMode+offset same call, Visibility abort escalation, repeat unique Label, preview of Label |
| R1-D | outside the bar | x2 | r1 lenses | deferred / leader review | gap-list rows 33/42 -> Story 13-19; expression-bound numeric write still reverts (pre-existing) -> leader asked to fix if small |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 3b7242f4 (patches squashed) | blind a91118f7dae0452aa, edge ae707f991cc5f9719, gap a33ff8044dd65939f | n/a -> 3 (fixes unreviewed) | 0 | 3 | 0 |

Deviation accepted (leader): read-only placements are refused before the bracket (INVALID_INPUT), not rolled back; Q4 updated. Round 2 required (product mediums).
