# Story 13-20: findings ledger

Quality bar: `quality-bar-13-20.md` (this folder). Lens triage: `spec-13-20-usage-report.md` (branch story/13-20-usage-report).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q8 | per builder triage | blind a8ecc4bd8aa7737a6 (16); edge aa76abcfde1254f06 (11); gap af83c2fd28cfe2a1c (2) | 12 patched, 5 rejected, 2 deferred | spec triage log |
| R1-D1 | outside the bar | low | builder | deferred | stat race in `rpc_client._live_records` |
| R1-D2 | outside the bar | low | builder | deferred | spill paths with a space not matched by `_SPILL`/`_PERSISTED` |
| R1-A1 | Q2 | open (user) | builder | open | evidence transcripts partly deleted (oldest 2026-10-25; 2026-10-18 Ender session gone); report on range: 897 calls / 8 sessions / 36% script_exec vs evidence 1,221 / 10 / 34%; raw independent scan: 1,069 unique ids over all dates = report all-date total; script-class counts lower (isValid 122 vs 163; loft/sweep 0 vs 14 unexplained). User question 4: replace the AC |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 27d75a93 | blind a8ecc4bd8aa7737a6; edge aa76abcfde1254f06; gap af83c2fd28cfe2a1c | ? → 0 | 12 | 29 | 0 |
| r2 | 8392d7f5, 3864c166 | blind a744a79b3af10f7c5; edge ac14355a21fd06f64; gap a7bb6b77aec3aaddf | RT-1..RT-4 medium → 0 | RT-1..RT-6, G-1 (verifier r2 reverts red); independent recount equals report on every count | lens r2 rows | 0 |

R1-A1: the evidence transcripts are partly deleted; the report equals an independent recount on the transcripts on disk. Merged on decision 35 (the user's "auto merge"); the acceptance wording question (decision batch item 4) was not answered separately.
