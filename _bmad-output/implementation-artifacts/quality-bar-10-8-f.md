# Story 10-8-f: quality bar

Base: `9aee2bf`. Plan: `plan-10-8.md` §3.2; spec `spec-10-8-f-uat-testcase-defects.md`; decisions 30, 34, 38.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | TC-02-02 `:106`, TC-02-05 and TC-02-14 read `query_tree_summary` counts from the first text line `OK: <N> objects, <S> shown, <M> matches.`, not from `structured_content` | `mcp-tools-design.md:60`; `usecases/queries.py:46-48` | live container call recorded in `tests/uat/run/2026-11-18-10-8-f-check/` |
| Q2 | TC-11-18 brings the golden view to the front before its closing fit; visual Then stays "identical" | lead log R2-F1; spine AD-31; TC-09-09 `:403` route | container capture with golden view in front, read by the builder |
| Q3 | TC-12-05 compares tree object lines only; header lines are excluded | `mcp-tools-design.md:60`, `:282` | live container call |
| Q4 | `tc-08-04.json` regex is `\\bFillet\\b`; no other control character in the 72 scenario files | lead log R0-F1 | runner run of tc-08-04 in the container; scan of all scenario files |
| Q5 | TC-06-01 Cleanup uses `RemInt` | `docs/references/FreeCAD/src/Base/ParameterPy.cpp:242` | live `ParamGet(...).RemInt` in container |
| Q6 | TC-08-17 restores the Visibility value read before the toggle | lead log R2-F2 | text review |
| Q7 | TC-09-01 Given checks no H1 process; the GUI proxy is not counted | `hosts/gui_addon/bootstrap.py:240` | `pgrep` in container prints 0 with the proxy running |
| Q8 | No Then is weakened to hide a product defect; Then observables change only on the listed lines | decision 23; `uat-run-practices.md` §8 | diff review |
| Q9 | Runner tests and lint stay green; all 72 scenario files load | CLAUDE.md §9 | `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q`; `uv run ruff check .`; runner validate |
| Q10 | No edit to `src/`, runner code, container files or an earlier run folder | plan §3.2 boundaries | `git diff --stat 9aee2bf` |

Levels marked RUN: Unit (runner tests), UAT (container check of changed readers and tc-08-04). Integration and E2E: BLOCKED (test-case text only; no product code change).
