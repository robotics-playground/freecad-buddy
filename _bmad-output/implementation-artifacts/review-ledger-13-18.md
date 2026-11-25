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
| r2 | eaf97e18, af61cc66 | blind a2ea51fca45284212; edge aaa624b060e455a28; gap a12cf48afbb4cbba6 | RT-1, RT-2 high + RT-3, RT-4, F1 medium → 0 | RT-1, RT-2/RT-6, RT-3, RT-4, RT-5, N1 (verifier r2 reverts red; red team's lofts refused in ≤0.31 s) | lens r2 rows | 0 |

Red team FAIL at d8968a1e (2 high, 2 medium); verifier r1 PASS with F1 (sweep up to 32 s) and N1; verifier r2 PASS at af61cc66. Deferred: R2-F1 (no test pins the sweep limit), R2-F2 (closed-loft doc wording), timing comments, R2-R1 BSpline self-intersection residual.
