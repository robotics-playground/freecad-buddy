# Story 10-8-d (preparation): quality bar

Base: `c66b80e`. Plan: `plan-10-8.md` §3.3, §6; spec `spec-10-8-d-uat-gate-1-run.md`; decisions 5, 8, 31, 34, 35, 36.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | Frozen block changes only `:26` (D1 G3 GUI script in container form) and `:34` (profile line) with the decision-36 wording; the G3 "unchanged" pass rule is word for word the same | decision 36; spec frozen marker | `git diff c66b80e -- spec-10-8-d-uat-gate-1-run.md` |
| Q2 | `baseline_commit` stays `3025e7c`; a body line names the run baseline as the integration head at run start | bmad-build step-03 | diff review |
| Q3 | Code Map and Tasks use only container forms (CLAUDE.md §9; plan §6.4); no host runner or `launch_env.sh` line remains | CLAUDE.md §9 | grep + diff review |
| Q4 | Spec states phases, run folder layout, records (image id, wheel SHA-256, user.cfg hashes), re-run rule (decision 35), TC-02-08 as written (decision 34) | plan §6.2, §6.3; decisions 34, 35 | diff review |
| Q5 | Ported `tests/uat/g3-gui/g3_gui_replay.py` and `gui.py` differ from the 2026-10-03-04 source only in repo root, MCP URL `:18765`, `cua-driver` call route and capture path; replay, `verify_shape` grading and classification unchanged | decision 36 | diff against source in the report |
| Q6 | Ported GUI replay runs one control case in the container and produces a capture the builder read | spec D1 | prep folder record + capture |
| Q7 | Headless scorer runs in the container from a temp copy with `--check --frames-check`, and its H1 child starts under `fcb-py`; no scorer edit | spec D1; plan §6.4 risk | prep folder record, case counts |
| Q8 | S0 preflight runs once: build, recreate, image id, H1 import `1.1.4`, `run_mcp_e2e.py` and `run_mcp_edge_cases.py` counts, probe faults 5/5 detected and 0/2 false alarms, pixel faults, user.cfg SHA-256 equal to decision 8 | plan §6.4; decision 8 | prep folder record |
| Q9 | No edit to `src/`, runner code, test cases, scenarios, container files, earlier run folders; `benchmarks/*/heldout` never opened | spec boundaries | `git diff --stat c66b80e` |
| Q10 | Gates green | CLAUDE.md §9 | `uv run ruff check .`; `uv run python scripts/check_imports.py`; `uv run pytest tests/external -q` |

Levels marked RUN: Unit (pytest external), E2E (sweeps against the container), UAT (G3 one case per form and preflight in the container). Integration: not changed by this slice (no product code).
