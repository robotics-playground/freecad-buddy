# Story 13-3: quality bar

Base: 905e038. Plan: builder-13-3 plan (approved 2026-11-24), `epic-13-plan.md` section 13-3.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | The `initialize` result of the headless server (`adapters/mcp_server.py`) carries `instructions` | tool-contracts.md:35 | unit test on initialization options |
| Q2 | The GUI proxy server (`hosts/gui_external/entry.py:55`) carries the same `instructions` | M-4, epic-13-plan.md 13-3 | unit test; verifier live `initialize` against the container proxy |
| Q3 | The UAT relay `scripts/automation/mcp_cache_proxy.py` passes the upstream `instructions` to its client, so a Claude Code session through the relay sees them | CAP-6 live check path (CLAUDE.md section 9 UAT tools) | unit test of the relay; verifier live `initialize` through the relay |
| Q4 | Text holds one line per family `document_`, `query_`, `verify_`, `export_` + `verify_export_`, `sketch_`, `feature_`, `preview_`, `view_`; each prefix has ≥1 real tool in `tool_specs()`; no tool name that does not exist | tool-contracts.md:38-39 | unit test |
| Q5 | Text holds the two quoted sentences of T-10 and the four skill names | tool-contracts.md:40-44 | unit test |
| Q6 | ≤250 words; client-neutral (no `ToolSearch`, `select:`, client product names) | tool-contracts.md:36, SPEC.md:68, decision 10 | unit test |
| Q7 | `script_exec` description adds exactly "Before using it, check the typed tool families in the server instructions." and changes nothing else | tool-contracts.md:46-47 | unit test; `gen_schemas.py --check` if descriptions feed schemas |
| Q8 | AD-1 ring rules hold | AD-1 | `scripts/check_imports.py` |
| Q9 | A Claude Code session sees the instructions before its first tool load (`SPEC.md:93` assumption) | CAP-6 | verifier: headless `claude -p` through the relay against the container, or NOT RUN with the reason |

Levels marked RUN: Unit (`uv run pytest tests/external -q`). E2E: verifier live `initialize` on the container proxy and the relay. UAT: Q9 headless Claude Code session, or NOT RUN.
