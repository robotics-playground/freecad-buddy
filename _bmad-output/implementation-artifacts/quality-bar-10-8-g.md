# Story 10-8-g: quality bar

Base: `ffd131d`. Source: run `tests/uat/run/2026-11-18-01/` (`report.md`, `bugs.md` B-11..B-18); spec `spec-10-8-g-smoke-testcase-defects.md`; decisions 23, 38, 49.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | TC-02-15 and TC-09-12 read the `query_tree_summary` refusal from its text line; other tools keep their envelope Thens | `mcp-tools-design.md:60`; decision 38 | live container call |
| Q2 | TC-02-17 has no platform literal; `Invalid project file <path>:` prefix and equal-after-path-replace stay hard checks; differs from the missing-file tail | `documents.py:496-499`; `data-contracts-design.md` §9 | live container call |
| Q3 | TC-03-03, TC-03-20, TC-13-04, TC-13-10 set the camera (Isometric by token) in their own steps, before each capture they compare | run 2026-11-18-01 lead grades | one live run each, captures read |
| Q4 | TC-07-03 enters Sketch edit mode in its own steps before the capture; the Then is unchanged | run 2026-11-18-01 TC-07-03 row | one live run, capture read |
| Q5 | TC-07-05 export `text` Then is met: exact STEP line after a fit in the Given, or the exact documented suffix | `contracts/envelope.py:111`; AD-32; TC-14:399 | one live run |
| Q6 | No Then weakened; added steps are When/Given steps only; scenario `agent_check` strings mirror the case text | decision 23; `uat-run-practices.md` §8 | diff review |
| Q7 | TC-02-13 unchanged (harness limit); its deferred entry stays open | run report | diff review |
| Q8 | Each fixed `deferred-work.md` entry marked resolved with the commit | CLAUDE.md fix-before-defer | diff review |
| Q9 | Runner tests and lint green; 72 scenario files load | CLAUDE.md §9 | `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q`; `uv run ruff check .`; runner validate |
| Q10 | No edit to `src/`, runner code, container files, earlier run folders | slice boundary | `git diff --stat ffd131d` |

Levels marked RUN: Unit (runner tests), UAT (one live run per changed case in the container). Integration and E2E: not changed (test text only).
