# Story 13-5: findings ledger

Quality bar: `quality-bar-13-5.md` (main tree copy; same text here once committed). Lens triage: `spec-13-5-multi-object-export.md` (branch story/13-5-multi-object-export).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-H1 | Q5/Q6 | high | lens r1 | fixed (claimed) | touching boxes failed all five STL oracle checks as one welded mesh; writer records facet count per object, oracles weld per object |
| R1-M* | Q2, Q4, Q7 | medium | lens r1 | fixed (claimed) | expression/attachment ref removed a solid from default selection; Mod/Import prefs changed STEP structure; one hidden object refused (K-1); failed 3MF rename left a file; 3MF handler wiring untested |
| R1-D1 | outside the bar | low | builder | deferred | App::Part placement not applied to exported shapes (pre-existing); blocker: global vs local coordinates product decision |
| R1-D2 | outside the bar | low | builder | deferred | default selection ignores App::Link and solids in a hidden App::Part (not reproduced); blocker: assemblies out of scope |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 3527cc2 | blind a04acfda514f282a5; edge a44d449d801e1aea6; gap ac6b4727dd7c46902 | ? → 0 (claimed) | 1 high + 5 medium (claimed) | 6+ | 0 |
| r2 | 80e0b00, 9af2ac84 | blind ab25971a900789028; edge aa71fe06eaf454d5b; gap a0669763dbe56b3c4 | D-1 + RT-1 high, RT-2..RT-5 medium → 0 | D-1, RT-1..RT-7, L-1 + 3 lens fixes (verifier r2: 12 reverts red); K-1 single-object output unchanged | lens r2 rows | 0 |

Verifier r1 FAIL at 3527cc2 (D-1 GUI 3MF duplicate content types, found only in the container); red team FAIL (1 high, 4 medium); verifier r2 PASS at 9af2ac84 incl. container UAT TC-07-11/12. Merged on decision 35.
