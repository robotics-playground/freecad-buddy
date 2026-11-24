# Story 13-1: findings ledger

Quality bar: `_bmad-output/implementation-artifacts/quality-bar-13-1.md`.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-1 | Q2 | low | edge-cases, r1, a095ca7c121083085 | fixed-proven | bare `\r` line break now elided; unit test in `test_envelope_summary.py` |
| R1-2 | Q4 | low | verification-gap, r1, ae4dec70edfb954c5 | fixed-proven | script_exec test uses the real result key set |
| R1-3 | Q6 | low | verification-gap, r1, ae4dec70edfb954c5 | fixed-proven | rounding-path test with a long string in `test_mcp_surface.py` |
| R1-4 | outside the bar | low | blind-hunter, r1, abe375c3f095947aa | fixed-proven | constant comment and docstring reworded (no unmeasured claim) |
| RT-1 | Q4 | low | redteam-13-1 | rejected | short value inline follows T-13 table (tool-contracts.md:23); Q4 reworded to long values |
| RT-2 | Q2 | low | redteam-13-1 | fixed-proven | verifier r2: dropping each of 10 _LINE_BREAK chars turns its parametrised case red |
| RT-3 | outside the bar | low | redteam-13-1 | rejected | addon/proxy version skew outside Story; release ships one wheel |
| RT-4 | Q1 | low | redteam-13-1 | fixed-proven | verifier r2: len(value.encode()) mutant red |
| RT-5 | outside the bar | low | redteam-13-1 | fixed-proven | rename in test_envelope_summary.py |
| R1-5 | Q8 | low | builder | deferred | text share ≤5% depends on bespoke summaries; measured by Story 13-20 |
| R1-6 | outside the bar | low | builder | deferred | design text lacks the `<N chars>` rule; leader adds it to Story 13-2 scope (`mcp-tools-design.md:60`) |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| rt-fix | uncommitted, patch-13-1-r2.diff sha256 899bd67ed468 | none (red-team fix, ~8 product lines) | 0 → 0 | RT-2, RT-4, RT-5 (proven by verifier r2) | 0 | 0 |
| r1 | uncommitted, patch-13-1-r1.diff sha256 904e6edad4b3 | blind abe375c3f095947aa; edge a095ca7c121083085; gap ae4dec70edfb954c5 | 0 → 0 | 4 | 4 low | 0 |

r1 passes (no high, no product medium). Fix batch is small (well under 60 lines): no lens round 2; verifier gates + red team next. Lens subagents could not carry names (teammates cannot spawn named agents); ids recorded instead.
