# Story 10-8-f: findings ledger

Quality bar: `quality-bar-10-8-f.md`.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R2-B'1 | Q4 | high | Blind, r2, aabd4f32da2b1096b | fixed-proven | raw scan replaced by decoded-string pytest case; baseline offends, fixed passes; 182 passed |
| R1-B1 | Q7 | medium | Blind/Edge, r1 | fixed-proven | fake `exec -a` process: pgrep printed 2, then 0 (`readers-check.md`) |
| R1-B3 | Q1 | medium | Blind/Edge, r1 | fixed-proven | header lines excluded; live `framing:` variance recorded |
| R1-B5 | Q2 | medium | Blind/Edge, r1-r2 | fixed-proven | `tc-11-18-before/after.png`, step bounded, title states tab |
| R1-B6 | Q6 | medium | Blind/Edge, r1-r2 | fixed-proven | read first, opposite-value write; live run recorded |
| R1-B10 | Q4 | medium | Blind, r1 | fixed-proven | scan in Verification, then pytest case (R2-B'1) |
| RT-1 | Q6 | medium | redteam-10-8-f | fixed-proven | TC-08-17 `:680` restore leaves Pad and Fillet hidden (PartDesign `ViewProvider.cpp:279-296`); reproduced live; fix F2-1 |
| R2-B'3 | Q1 | medium | Blind, r2 | fixed-proven | F1 `19473e4`: builder records + verifier-10-8-f live `OK:` reader PASS (8 calls) |
| V-1 / RT-low | Q1 | low | verifier-10-8-f, redteam-10-8-f | open | TC-12 `:659`, TC-09 `:313` "ends `, truncated.`" vs `Errors:` suffix; fix F2-2 |
| RT-low2 | Q4 | low | redteam-10-8-f | open | pytest guard skips DEL, C1, keys; fix F2-3 |
| V-2 | outside the bar | low | verifier-10-8-f | open | DW entries state blocker by implication; triage row B'3 stale; fix F2-4 |
| RT-low3 | outside the bar | low | redteam-10-8-f | rejected | pre-existing wordings (TC-09 H1 port check, tree-line count, 201 lines capped, filter vs depth); not changed by this Story |
| R1-B11 | outside the bar | low | Blind, r1 | deferred | `mcp-tools-design.md:249` vs §1.3; epic-close correct-course batch (decision 40) |
| R1-G1 | outside the bar | low | Gap, r1 | deferred | runner `scenario.py` reject; runner code out of slice; pytest guards committed files |
| R*-low | — | low | r1-r3, many | fixed / rejected | spec `## Review Triage Log` |

Severity in the builder's log is for test text; no finding is in product code (Q10: no `src/` change).

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | pre-8790ad4 | Blind a293b15c6e2011c61, Edge a4c57c00e6a4f8622, Gap af9d379c3ee552c35 | 0 → 0 (product); test-text medium 7 | 5 | 9 | 0 |
| 2 | pre-8790ad4 | Blind aabd4f32da2b1096b, Edge a7e488e97ba4894aa, Gap ad9a3af54cefa8095 | 0 → 0; test-text high 1, medium 8 | 7 | 8 | 0 |
| 3 | 8790ad4 | Blind a0bcb60459e202f32, Edge a4a3cbea7402f7b26, Gap ad6e1dfad12f8a37f | 0 → 0; patched lows | all patched or rejected | 0 high/medium | 0 |
| F1 | 19473e4 | none (test text < 60 lines); verifier-10-8-f PASS; redteam-10-8-f FAIL (RT-1) | 0 → 0 (product); test-text medium 1 → 1 (B'3 closed, RT-1 new) | 1 | 1 | 0 |
| F2 | a61c315 | verifier-10-8-f re-run PASS | test-text medium 1 → 0 (RT-1 proven: 12 tree lines equal, captures pixel-identical) | 4 | 1 low (order wording, false fail) | 0 |
| F3 | f3d1909 | verifier-10-8-f (case owner) fix + proof | 0 → 0 | 1 (`tc-08-17-after.png` equals before; old order `tc-08-17-listed-order.png` differs) | 0 | 0 |

Closed: merged into `fix/uat-gate-1-failures` at `d676505` (2026-11-18). Post-merge: runner pytest 186 passed, ruff clean.
