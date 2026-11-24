# Story 13-6: findings ledger

Quality bar: `quality-bar-13-6.md` (this folder). Lens triage: `spec-13-6-query-mass-properties-objects.md` (branch story/13-6-mass-properties-objects).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q8 | per builder triage | blind a1f879a019f0c3bf4; edge acde240e5b31a80cb; gap a6440f0067e4c0f3b | 6 patched, 4 rejected | spec triage log |
| R1-D1 | outside the bar | low | builder | deferred | skills say one object per call; Story 13-12 updates skills |
| R1-D2 | outside the bar | low | builder | open (leader) | tool-contracts.md T-2 still lists `solids`; leader aligns T-2 with decisions 8 and 21 at merge |
| R1-D3 | Q6/Q7 | medium (unverified) | builder | open | `isValid()` per object under the 30 s budget; verifier times a 50-object call on a large part in the container |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 61dd01f | blind a1f879a019f0c3bf4; edge acde240e5b31a80cb; gap a6440f0067e4c0f3b | ? → 1 unverified medium (R1-D3) | 6 | 13 | 0 |
| rt-fix | c513a0d | none (small) | RT-1 high (doc) → 0 | RT-1, RT-2, RT-4 (verifier r2 mutants red) | 0 | 0 |

R1-D2 closed by the leader's T-2 edit at merge; R1-D3 closed by the verifier timing (3.7 s for 50 x 172 faces). RT-3 deferred (object error state not in the record). Verifier r1 PASS at 61dd01f (live container), r2 PASS at c513a0d.
