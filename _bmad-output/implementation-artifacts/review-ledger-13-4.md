# Story 13-4: findings ledger

Quality bar: `_bmad-output/implementation-artifacts/quality-bar-13-4.md`. Full lens triage: spec `spec-13-4-skill-routing-gap-list.md` (worktree wt-13-4) and `report-13-4-build.md`.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q8 | per builder triage | blind adde9f60f12d90587 (9), edge a4a5f8f3b1cb416a1 (14), gap a03bf1cac40ec12c5 (0) | 13 groups patched, 2 rejected, 0 deferred | spec Review Triage Log |
| R1-U1 | Q5 | open | builder | open | unverified: `feature_set_parameters` on a VarSet; `Import.insert` snippet; `Groove`/`AdditiveBox` type names — verifier runs them in FreeCAD |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 1bc4795 | blind adde9f60f12d90587; edge a4a5f8f3b1cb416a1; gap a03bf1cac40ec12c5 | n/a (skill text) → 0 | 13 | 23 | 0 |

Round 2 findings (verifier D1-D5, red team RT1-RT3 + lows): see `triage-13-4-r2.md`. Open: D3=RT1 high; D1, D2=RT2, D4=RT3 medium; D5, RT-L1..L3 low. RT-L4 (urdf/sdf name non-existent tools) deferred: Phase 5 scope; leader adds the deferred-work entry after 13-2 merges (13-2 edits deferred-work.md).
| r2 | 5782fee (+409c1b8 wording) | blind a5b7b74ceff167b25 (8); edge a46291ebf16e62109 (14); gap abd787c4709a4b5ec (0) | 1 high + 3 medium → 0 (verifier r2 PASS) | D1-D5, RT1-RT3, RT-L1..L3 (FreeCAD runs + shape-checker mutants) | 22 lens findings (2 medium patched) | 0 |
