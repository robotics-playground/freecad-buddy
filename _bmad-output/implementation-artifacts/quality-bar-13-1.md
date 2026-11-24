# Story 13-1: quality bar

Base: bd122f2. Plan: builder-13-1 plan (approved 2026-11-23), `epic-13-plan.md` section 13-1.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | A `str` value with length ≤ 80 and no newline renders `key: value` exactly as before | tool-contracts.md:23 | unit test, 80-char boundary |
| Q2 | A `str` value longer than 80, or containing a newline, renders `key: <N chars>` where N is `len(value)` | tool-contracts.md:24 | unit tests, 81-char and short-with-newline |
| Q3 | `dict` and `list` values render unchanged (`{N fields}`, `[N items]`); non-str scalars unchanged | tool-contracts.md:25 | unit test |
| Q4 | A `script_exec`-shaped result holds a long (>80 chars or multi-line) `value_repr` and `stdout` once (no copy in `text`); a short value stays inline per Q1 | tool-contracts.md:30, CAP-8 SPEC.md:54 | unit test on summary; verifier checks one live `script_exec` result in the container |
| Q5 | Tools with a bespoke `summary` are unchanged | tool-contracts.md:27 | existing tests; grep of callers |
| Q6 | `mcp_server.py:106-109` regeneration after rounding still regenerates correct text | epic-13-plan.md 13-1 risk | existing rounding tests in tests/external |
| Q7 | `contracts/` stays stdlib only | AD-1 | `scripts/check_imports.py` |
| Q8 | `text` share ≤5% of result characters over a test session | tool-contracts.md:30-31 | NOT RUN in this Story: measured by Story 13-20 `usage_report.py` |

Levels marked RUN: Unit (`uv run pytest tests/external -q`). Integration infc: only if a test depends on long text. E2E/UAT: verifier spot check of one live `script_exec` result in the container (batched with done checkpoint 13-5 if the container is not up).
