# Story 13-13: findings ledger

Quality bar: quality-bar-13-13.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| RT-1 | Q3 | high | redteam-13-13 | open (triage-13-13-rt.md T1) | probe_c C1: SystemExit from a script __repr__/__str__ after commit ends the listener; WORKER_CRASHED then TIMEOUT |
| RT-2 | Q1, Q2 | medium (product) | redteam-13-13 | open (T2) | 20 identical names: undo_steps 0 + false note, document_undo reverts it |
| RT-3 | Q1 | medium (product/contract) | redteam-13-13 | open (T3) | script doc.undo(): undo_steps 1, no note, document_undo does not restore pre-op |
| RT-4, RT-6 | outside the bar | low | redteam-13-13 | open (T4, T5) | stdout closed by script; zero-step note after clearUndos/UndoMode 0 |
| RT-5 | outside the bar | low | redteam-13-13 | comment only | proxy defeats enable_undo read-back, no false pass |
| R3-B1 | Q11 | medium (product) | r3 blind review-blind-r3-s13-13 | fixed-proven (fba56e57; tests red first) | deleted-object repr after commit -> RECOMPUTE_ERROR, no fingerprints; probe in scratchpad review-blind-r3-s13-13 |
| G1 | Q2 | low | r3 gap review-gap-r3-s13-13 | open (T2) | UndoNames-failure mutant survives 50 tests |
| E3-1..E3-4, R3-L1, R3-L2 | outside the bar / Q12 | low | r3 edge review-edge-r3-s13-13, blind | open (T3-T7) | edge/blind chat reports |
| R2-1 | Q2, Q6 | medium (product) | r2 blind ac63858f9075cceee / edge a3d35b8def0d6ba58 / gap a57eeae352a00d1da (all three) | fixed-proven (r3 probes + mutants) | failing document.commitTransaction skipped the app-level close (transaction left open), second failure lost; both commits in own try (2c925827) |
| R2-2 | Q1, Q2 | medium (product) | r2 lenses | fixed-proven (r3 probes + mutants) | undo_steps overcount after doc.undo() on a deeper stack ([C,B,A] -> [S,B,A] gave 3); smaller of prefix/suffix alignment |
| R2-3 | Q1, Q2 | medium (product) | r2 lenses | fixed-proven (r3 probes + mutants) | one failed observe read reset undo_steps to 0 with a false note; each read guarded, null when unreadable |
| R2-L | various | low x5 | r2 lenses | fixed | observe_before phase, closed-doc commit guard, 4000-char traceback test, SyntaxError frame, observe phase doc |
| R2-D | outside the bar | low x2 | r2 lenses | deferred | close ignored under a GUI command guard (UAT probe); openTransaction by the script commits another caller's transaction / UndoMode 0 by the script |
| R2-R | outside the bar | low x3 | r2 lenses | rejected | commit-then-write note (spec case 5), nested call, hostile repr |
| R1-1 | Q2, Q6 | medium (product) | r1 blind a9f5fa9a96c918734 / edge a17955ea4efab105b / gap ab6a30dde35796e38 (all three) | fixed-proven (r2: recompute path closed; commit path was a separate gap, R2-1) | transaction left open after a failed recompute; patched 296f11f9 |
| R1-L | various | low/medium mix (23-row triage log in wt-13-13 spec) | r1 lenses | fixed | unguarded reads, traceback tail, undo-count removal, schema/wiring/remember tests, 4 stale runner scenarios, doc gaps |
| R1-R | outside the bar | low x4 | r1 lenses | rejected | AD-27 release wording, hostile repr, weak-test nits, AC3 via real listener (builder evidence in spec) |
| R1-D | outside the bar | low x2 | r1 lenses | deferred | Visibility framing gap on non-OK; usage_report.py class for the new status |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 7fb24f1d -> fix 296f11f9 | blind a9f5fa9a96c918734, edge a17955ea4efab105b, gap ab6a30dde35796e38 | n/a -> 1 (fix unproven) | 0 | 1+ | 0 |

Builder report: wt-13-13 `_bmad-output/implementation-artifacts/report-13-13-build.md`. Gates at 296f11f9: external 2117 passed / 6 skipped; infc 1295 OK (1 skipped); AC5 30x406 faces 4.08 s. Deviation accepted (leader): `_invalid_objects` not renamed (G2 validator hash pins transaction.py), imported under an alias. Fix batch 69 product lines with a product medium -> round 2, all three lenses.
| r2 | 296f11f9 -> fix 2c925827 | blind ac63858f9075cceee, edge a3d35b8def0d6ba58, gap a57eeae352a00d1da | 1 -> 3 | 1 | 3 | 0 |

r2 is a STALL (open product medium 1 -> 3). The new findings are all bracket exit/observe-path robustness (one family: exit paths not enumerated in round 1); the builder now pins an exit-path matrix by tests. builder-13-13 has run two fix rounds -> any further fix goes to a fresh builder. Round 3 (last) is dispatched by the leader: three fresh reviewers on 296f11f9..2c925827.
| r3 | 2c925827 | blind review-blind-r3-s13-13, edge review-edge-r3-s13-13, gap review-gap-r3-s13-13 (leader-dispatched) | 3 -> 1 | 3 | 1 | 0 |

r3 does not pass (R3-B1). Three rounds used: fresh builder-13-13b fixes triage-13-13-r3.md; then red team (attacks the batch first) and verifier; no fourth lens round.
| RT | fba56e57 | redteam-13-13 | 0 -> 3 (RT-1 high, RT-2, RT-3) | 1 (R3-B1) | 3 | 0 |
