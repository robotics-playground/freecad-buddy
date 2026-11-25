# Story 13-18: findings ledger

Quality bar: `quality-bar-13-18.md` (this folder). Lens triage: `spec-13-18-loft-sweep.md` (branch story/13-18-loft-sweep).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q8 | per builder triage | blind ac866481e169b08a1; edge afc3620d14122415a; gap a195efefcdce32b94 | patched: tangent check order/caps, coded refusals, sweep cost counts profile BSpline poles, loft capped at 500 sections, Body spine refused, more tests | spec triage log |
| R1-N1 | Q6 | high (found by builder) | builder | fixed (claimed) | a BSpline spine that doubles back held the interpreter >280 s; refused as `sweep.degenerate_spine` |
| R1-D1 | Q6 | low | builder | deferred | a spine with a zero-velocity point and no tangent reversal is not detected |
| R1-N2 | outside the bar | note | builder | documented | every sketch the call names must be fully constrained (AD-5 post-verify runs verify_sketch on all) |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | d8968a1e (merge of feat over 8a3cf206) | blind ac866481e169b08a1; edge afc3620d14122415a; gap a195efefcdce32b94 | ? → 0 (claimed) | per spec | per spec | 0 |
