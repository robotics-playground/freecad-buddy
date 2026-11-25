# Story 13-7: findings ledger

Quality bar: `quality-bar-13-7.md` (this folder). Lens triage: `spec-13-7-query-interference.md` and `report-13-7-build.md` (branch story/13-7-query-interference).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q12 | per builder triage | blind a47020905ae6d8459; edge a5f4117b508fefa6d; gap a41661ce8d89645be | 10 patched, 4 rejected, 3 deferred | spec triage log |
| R1-D1 | outside the bar | low | builder | deferred | global frame / App::Link placement (same as 13-5 R1-D1) |
| R1-D2 | Q9 | medium (unverified) | builder | open | no deadline check: a disjoint pair of large compounds can take 45 s; 190 such pairs exceed the 60 s budget. Verifier measures; leader decides |
| R1-D3 | Q2 | low | builder | decided | `min_distance` null when `distToShape` fails: decision 25 |

Probe (decision 24): touching solids give an empty common at distance 0 → `boolean_failed` true; bowtie solid planted as a real failed boolean. User question open: fuse cross-check for touching solids (option b).
Timing: 190 pairs of 81-hole plates 8.1 s disjoint / 25.8 s overlapping.

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 8e381d9 | blind a47020905ae6d8459; edge a5f4117b508fefa6d; gap a41661ce8d89645be | ? → 1 unverified medium (R1-D2) | 10 | 18 | 0 |
| r2 | 0c691e0, 718c802, b7c9d75, 7037fd6 | blind a866f60ec91ef3dd1; edge a14e218be6e9c7384; gap a4625d5a04ed67a59 | RT-1, RT-2 high + RT-3, F2 medium → 0 | RT-1..RT-5, F1, F2, e1 (verifier r2: each revert red) | 15 lens rows | 0 |

Red team (redteam-13-7.md) FAIL at 8e381d9 (2 high, 1 medium); verifier r1 PASS with F2 medium (900-box hang) and F1 low; verifier r2 PASS at 7037fd6: CAP-1 replay 52 records 0 mismatches; 900-box pair refused in 1.6 s and the next call OK; 190 plates 5.6 s / 3.4 s. Decisions 25-28. Open user question: touching solids fuse cross-check (option b).
