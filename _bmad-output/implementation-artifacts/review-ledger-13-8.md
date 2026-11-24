# Story 13-8: findings ledger

Quality bar: `quality-bar-13-8.md` (this folder). Lens triage: `spec-13-8-query-section.md` (branch story/13-8-query-section), 16 rows.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q10 | per builder triage | blind ac765520a554447e9; edge a38cb940b3153dc6b; gap acab03bbc43f14a88 | patched incl. open-shell area 0 → null, 9,000-hole plate 103 s → area cap 1,500 wires, face limit read before copy, near-float-limit normal abort | spec triage log |
| R1-D1 | outside the bar | low | builder | deferred | gap-list.md:38 still advises `shape.slice`; Story 13-12 owns skills |
| R1-D2 | Q2 | low | builder | deferred | touching/overlapping solids inside one compound not detected (documented) |
| R1-D3 | outside the bar | low | builder | deferred | third copy of the Quantity parser (`_mm_quantity`) |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | d4a258e4 | blind ac765520a554447e9; edge a38cb940b3153dc6b; gap acab03bbc43f14a88 | ? → 0 (claimed) | 16 rows | 16 | 0 |
