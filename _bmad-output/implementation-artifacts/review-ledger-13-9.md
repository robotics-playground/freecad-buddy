# Story 13-9: findings ledger

Quality bar: `quality-bar-13-9.md` (this folder). Lens triage: `spec-13-9-varset-parameters.md` (branch story/13-9-varset-parameters).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q8 | per builder triage | blind a9139ba6fdd856c99; edge ab08a795c3fe82313; gap a82fabc13f0aed9ae | 27 findings: 17 patched (incl. highs: silent clamp of out-of-range length/angle, dimensionless quantity read as 1e308, lexer-list check skipped without docs/references), 1 false, 2 rejected, 7 deferred/noted | spec triage log |
| R1-D1 | outside the bar | medium (architecture) | builder | deferred | AD-6 fingerprint blind to VarSet/spreadsheet changes (decision 32) |
| R1-D2 | Q2 | low | builder | deferred | no G2 fault case measures the new rollback proof |
| R1-D3 | outside the bar | low | builder | deferred | a VarSet already holding a `TypeId` property breaks both tools |
| R1-D4 | outside the bar | low | builder | deferred | parametric-patterns skill text — Story 13-12 |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | feac4bfd | blind a9139ba6fdd856c99; edge ab08a795c3fe82313; gap a82fabc13f0aed9ae | ? → 0 (claimed) | 17 | 27 | 0 |
