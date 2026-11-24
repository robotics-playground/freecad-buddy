# Story 13-10: findings ledger

Quality bar: `quality-bar-13-10.md` (this folder). Lens triage: `spec-13-10-set-expression.md` (branch story/13-10-set-expression).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q9 | per builder triage | blind aa27ed9c6e117ea3a; edge a1e6daed23b7deb99; gap a8f1916c11f603145 | 23 rows fixed incl. high: op recompute hid TNP edge drops; wrong undo_steps on equivalent text / full undo stack; constraint index/name aliases; int rounding, unit on float, .Value path, read-only property | spec triage log |
| R1-S1 | Q4 | note | builder | open | TNP exemption placed in `audit_references`, so it applies to every tool (op's own removal of a binding) — shared-code check (L12) by verifier and red team |
| R1-D1 | outside the bar | medium | builder | deferred | a non-finite value from a sibling item commits and poisons the fingerprint (reported SPEC_FAILED, not silent); needs a shared post_verify check |
| R1-D2 | Q4 | low | builder | deferred | no G2 fault case for the new audit_references rule |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | f2a19ce8 | blind aa27ed9c6e117ea3a; edge a1e6daed23b7deb99; gap a8f1916c11f603145 | ? → 0 (claimed) | 23 | 23 | 0 |
