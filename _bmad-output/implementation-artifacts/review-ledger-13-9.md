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
| r2 | 03b4fbf7, 57bba0eb | blind a01f9257f02b8c76a; edge aae529cfbf3db840a; gap a83adadd230e8d5f7 | RT1-RT3 high + RT4-RT6 medium → 0 | RT1-RT6 (verifier r2: each revert red; RT4 through real dispatch; container no-op undo_steps 0) | 14 lens rows | 0 |

Red team FAIL at feac4bfd (3 high, 3 medium); verifier r1 PASS at feac4bfd (CAP-2 live); verifier r2 PASS at 57bba0eb. R2-1 (brief said undo after a no-op must not delete the earlier step) closed by the leader: the brief misstated decision 34; `document_undo` is a separate call; the tool reports `undo_steps: 0` and a warning. R2-4 (`SystemExit` escapes dispatch) is in the Story 13-13 spec.
