# Story 13-14: findings ledger

Quality bar: `quality-bar-13-14.md` (this folder). Lens triage: `spec-13-14-typed-verify-shape-check-schema.md` (branch story/13-14-verify-shape-schema).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q1-Q8 | per builder triage | blind a67de2ccb5c37bd8e; edge a9bda85a9a5f7c037; gap a867a7ff36cb12c46 | patched: Body doc counted 10 shape objects (origin excluded); 7 schema/use-case disagreements; shape-fact checks validated in the use case; TC-12 passes object; corpus regression test | spec triage log |
| R1-D1 | Q3 | low | builder | deferred | value rules written twice (JSON Schema and Python) |
| R1-D2 | Q8 | low | builder | deferred | no tools/call-path test for a bad check |
| R1-P1 | Q6 | open | builder | open | validators.yaml hashes refreshed by running the scorers; score_g2_infc exits 1 "BARS NOT MET" (builder: pre-existing unscorable validators) — verifier checks against base |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 9a9a3e7b | blind a67de2ccb5c37bd8e; edge a9bda85a9a5f7c037; gap a867a7ff36cb12c46 | ? → 0 (claimed) | ~10 | ~13 | 0 |
| r2 | ec3282c3 | none (product change < 60 lines) | RT-1, F1/RT-2 medium → 0 | RT-1 (table edit → hash stale; list removal → 3 tests red), RT-3 (revert → 2 tests red), RT-4, F1/RT-2 (cases match live server output) | 0 | 0 |

Verifier r1 PASS at 9a9a3e7b with F1 (UAT drift); red team FAIL (2 medium); verifier r2 PASS at ec3282c3. R1-P1 closed: "BARS NOT MET" pre-existing and identical on base; scorers reproduce committed validator_sha.
