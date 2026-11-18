# Story 10-8-e: quality bar

Base: `9aee2bf`. Plan: `plan-10-8.md` §3.1, §5; spec `spec-10-8-e-canary-dev-freecad.md` (worktree `fcb-10-8-e`); decisions 19, 28, 32, 33, 37, 39.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | The canary solve asks `freecad>=2026` from `conda-forge` label `main` only, and resolves `+ freecad 2026.*` | decision 32; AD-11 | local job run in `fcb-canary-10-8-e`, solve log line |
| Q2 | The old spec (`freecad=1.2`, `freecad_dev` label) fails the solve in the same harness (check can go red) | plan §5 | local run, `does not exist` line |
| Q3 | The install line equals the `ci.yml:106` dependency line, so the External suite imports `mcp`, `trimesh`, `lib3mf`, `jsonschema`, `yaml` | decision 32 | local run, no import error |
| Q4 | Both suites run on the dev build: In-FreeCAD `Ran N tests` line and External pytest summary line | decision 32 done bar | local run log |
| Q5 | Each failing dev-line test is a `deferred-work.md` entry; `canary.yml` has no `continue-on-error` and no `\|\| true` | AD-11 allowed-to-fail; memory "CI must not hide failures" | grep + diff review |
| Q6 | Triggers stay `schedule` and `workflow_dispatch` only | AD-11; `project-structure.md` canary row | new `canary.yml` test (decision 41, E1); `actionlint` |
| Q7 | "1.2-dev" is replaced by "the next FreeCAD development line (weekly builds)" in AD-11, `project-structure.md` and `epics.md:114,276`; `project-structure.md:321` names label `main`; no other wording change; `docs/decisions/016` unchanged | decisions 37, 39 | `git diff` of the doc files; proposal pair rows |
| Q8 | Proposal pair `sprint-change-proposal-2026-11-18-ad11-dev-line.md` + `.html` records tier, citation and approval for each changed clause | `bmad-leader` correct-course rule | file review |
| Q9 | Gates green | CLAUDE.md §9 | `uv run ruff check .`; `uv run python scripts/check_imports.py`; `uv run pytest tests/external/test_ci_workflow.py -q` |
| Q10 | GitHub `workflow_dispatch` run reported `NOT RUN` (needs a push) | decision 28, 33 | report text |

Levels marked RUN: Unit (`test_ci_workflow.py`), E2E (canary job steps in a local Linux micromamba container). Integration: covered inside the E2E job (In-FreeCAD suite). UAT: BLOCKED (CI workflow, no user-visible GUI). GitHub canary run: NOT RUN (needs a push).
