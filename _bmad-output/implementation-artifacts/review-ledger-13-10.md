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
| r2 | eca29153, 9a23aca5, merge 55d55b24 | blind a196bc6602c80f3ce; edge adff17f15a8cf2ba4; gap aaf3ec8e6d09a8775 | V1 + RT-8 high, V3, RT-1..RT-4 medium → 0 | V1..V4, RT-1, RT-2, RT-4, RT-5, RT-8 (verifier r2: each revert red; run A undo chain 8/8; CAP-2 typed run) | lens r2 rows | 0 |

Verifier r1 FAIL at f2a19ce8 (V1 app transaction left open; V2 stale hash; V3); red team FAIL (RT-8 high: spreadsheet range held a call 1,087 s); verifier r2 PASS at 55d55b24 (combined with 13-11). Decisions 37, 38. N1 (low): the feature-level cycle test does not pin V1; shared transaction tests and the live run do.
