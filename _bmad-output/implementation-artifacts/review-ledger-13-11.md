# Story 13-11: findings ledger

Quality bar: `quality-bar-13-11.md` (this folder). Lens triage: `spec-13-11-object-delete.md` (branch story/13-11-object-delete).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q10 | per builder triage | blind a7e01f6f1eb288383; edge aab97bc4cd83e74b3; gap a890bf9fa4a755ce8 | 22 findings; patched incl. Body-after-Origin crash (high), FEM vector `Origin` crash, relink-failure text, Part/LCS origin objects, design text, 9 tests | spec triage log |
| R1-U1 | Q7 | medium (unverified) | builder | open | expression relink may add an undo step or clear redo in the GUI host — verifier reads UndoCount/RedoCount after `document_undo` of a bound-pad delete in the container |
| R1-D1 | outside the bar | low | builder | deferred | cross-document links |
| R1-D2 | outside the bar | low | builder | deferred | skill text — Story 13-12 |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 4ee8c26b | blind a7e01f6f1eb288383; edge aab97bc4cd83e74b3; gap a890bf9fa4a755ce8 | ? → 1 unverified medium | ~13 | 22 | 0 |
| r2 | b83276a0, e7163db4 | blind a74611b22f08d2fa4; edge a78f48fd5e37d3364; gap a3ac4f00fa17466bc | RT-1 high + RT-2, F1 medium → 0 | RT-1, RT-2, RT-3, F1 (verifier r2 reverts red; F1 GUI screenshot S2) | lens r2 rows | 0 |

Red team FAIL at 4ee8c26b (1 high, 1 medium); verifier r1 PASS with F1 (GUI-only Tip visibility); verifier r2 PASS at e7163db4. R2-1 (low, synthetic) deferred. F2 text has no pinning test.
