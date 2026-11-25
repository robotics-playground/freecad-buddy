# Story 13-13: findings ledger

Quality bar: quality-bar-13-13.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-1 | Q2, Q6 | medium (product) | r1 blind a9f5fa9a96c918734 / edge a17955ea4efab105b / gap ab6a30dde35796e38 (all three) | fixed-unproven until r2 | transaction left open after a failed recompute; patched 296f11f9 |
| R1-L | various | low/medium mix (23-row triage log in wt-13-13 spec) | r1 lenses | fixed | unguarded reads, traceback tail, undo-count removal, schema/wiring/remember tests, 4 stale runner scenarios, doc gaps |
| R1-R | outside the bar | low x4 | r1 lenses | rejected | AD-27 release wording, hostile repr, weak-test nits, AC3 via real listener (builder evidence in spec) |
| R1-D | outside the bar | low x2 | r1 lenses | deferred | Visibility framing gap on non-OK; usage_report.py class for the new status |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 7fb24f1d -> fix 296f11f9 | blind a9f5fa9a96c918734, edge a17955ea4efab105b, gap ab6a30dde35796e38 | n/a -> 1 (fix unproven) | 0 | 1+ | 0 |

Builder report: wt-13-13 `_bmad-output/implementation-artifacts/report-13-13-build.md`. Gates at 296f11f9: external 2117 passed / 6 skipped; infc 1295 OK (1 skipped); AC5 30x406 faces 4.08 s. Deviation accepted (leader): `_invalid_objects` not renamed (G2 validator hash pins transaction.py), imported under an alias. Fix batch 69 product lines with a product medium -> round 2, all three lenses.
