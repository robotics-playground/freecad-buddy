# Story 13-3: findings ledger

Quality bar: `_bmad-output/implementation-artifacts/quality-bar-13-3.md`. Full lens triage: `spec-13-3-server-instructions.md` (Review Triage Log). Builder report given in chat (the harness refused the report file); summary below.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-* | Q3-Q7 | per builder triage | blind a5c482911e3d99623; edge a7cb1a1b4a61d5a0a; gap aa166d6d381bef025 | 8 patched (atomic cache write, failed write does not block tool cache, dropped/empty upstream text clears cache, family parse test, T-10 sentence tests, pinned script_exec pointer, 3 relay tests, README) | tests in test_mcp_surface.py, test_mcp_cache_proxy.py |
| R1-R1 | Q4 | low | builder | rejected | text names script_exec when the tool is off; T-10 fixes one text, ScriptExec on by default |
| R1-R2 | Q3 | low | builder | rejected | relay sends the previous run's text on its first start (cache-first design); documented in tests/close-loop/README.md |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 010a92b | blind a5c482911e3d99623; edge a7cb1a1b4a61d5a0a; gap aa166d6d381bef025 | ? → 0 | 8 | 10 | 0 |
| rt-fix | f4782e7 | none (relay change < 60 lines) | RT-1 medium → 0 (verifier r2: mutation red) | RT-1..RT-4 (each fix revert turns its test red) | 0 | 0 |

Red team (redteam-13-3.md): PASS with RT-1 medium (false-pass test), RT-2..4 low — all fixed-proven at f4782e7. Verifier r1 PASS at 010a92b (live initialize, relay, claude -p first tool load = 18 typed tools); r2 PASS at f4782e7.
