# Story 13-17: findings ledger

Quality bar: quality-bar-13-17.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-H1 | Q4, Q11 | high | r1 edge a2657451cf9aeb4a1 | open (decision 51: count all cross-input pairs) | two 100-cylinder families: guard counts 200 pairs, run 68.9 s |
| R1-M1 | Q4 | medium (pre-existing predicate) | r1 edge | deferred (deferred-work 13-fu entry + §3.7.5 limit) | overlapping solids inside one compound: fuse 3000 instead of 2500 |
| R1-P | various | mixed | r1 blind a5e487dfb0784b0e2, edge, gap ae766ab6b3b4b053c | fixed-unproven until r2 (f693e7f8) | cost before isValid, invalid_result on failed boolean, Label/Name clash, size > 3.4e38, non-string kind, docs, limit-value tests |
| R1-R | outside the bar | low x7 | r1 lenses | rejected | see builder report |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | f693e7f8 | blind a5e487dfb0784b0e2, edge a2657451cf9aeb4a1, gap ae766ab6b3b4b053c | n/a -> 1 (H1) | 0 | 1 high + patched mediums | 0 |
