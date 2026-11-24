# Epic 13 status

Goal: Build SPEC-mcp-usage-improvement (`_bmad-output/specs/spec-mcp-usage-improvement/SPEC.md`): typed tools cover the frequent operations so `script_exec` becomes an escape route for rare work (CAP-1 .. CAP-9).
Done: 13-1, 13-2, 13-3, 13-4, 13-6, 13-7 (merge c6492d77, records 90303e36)
In progress: 13-5 (PASS at 9af2ac8; done_checkpoint waits for user acceptance before merge); 13-8 (main tree, builder); 13-15 (spec waits for the user)
Remaining: 13-9 .. 13-14, 13-16 .. 13-20
Branch / head: integration feat/epic-13-mcp-usage-improvement @ 116377e, checked out in worktree D:/Work/Personal/Sources/freecad-buddy-int (leader merges there)
Blockers: none
Open decisions (user): accept 13-5; 13-15 TNP rule (3 questions); 13-7 touching solids option b
Open for the user to confirm: decisions 15-17 (leader)
Agents alive: builder-13-5, verifier-13-5 (13-5 checkpoint); builder-13-7 (option b if user chooses); builder-13-8; builder-13-15
Next: 13-7 in the main tree. Leader records live in this integration worktree.
Plan: epic-13-plan.md. Context: epic-13-context.md. Decisions: epic-13-decisions.md.
Updated: 2026-11-24 at 90303e36

## Environment
Skill version: bmad-leader SKILL.md sha256 `936e3e227d5e`.
Host: Windows 11 Pro; user timezone SE Asia Standard Time (UTC+7).
Shell and tools: Git Bash (POSIX) and PowerShell 7. `uv` for Python (`C:\Users\thuan\.local\bin\uv`). Docker 29.6.2 and `docker compose` present. No `package.json`: CLAUDE.md `npm run` gates do not apply; the gates are below. Host FreeCAD 1.1 at `C:\Program Files\FreeCAD 1.1\bin\` — never for UAT; `freecadcmd.exe` only with `-u <tmp>\user.cfg -s <tmp>\system.cfg` (private temp cfg files) for the in-FreeCAD test suite.
Gates: `uv run ruff check .` · `uv run python scripts/check_imports.py` · `uv run python scripts/check_status_vocab.py` · `uv run python scripts/gen_schemas.py --check` · `uv run python scripts/check_skill_shape.py` · `uv run pytest tests/external -q` · `"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py`. `uv run ruff format --check .` fails on pre-existing files: check only the files you change.
Known unstable test: `tests/external/test_managed_venv.py::test_Should_start_an_external_interpreter_When_freecad_set_pythonhome` fails in the full run and passes alone (pre-existing).
Installed addon shadow: importing FreeCAD puts the installed `Mod/FreeCADBuddy` copy on `sys.path` ahead of editable `src` (see memory `installed-addon-shadows-src`); check which copy a test imports.
UAT: container `fcb-desktop` only (image `fcb-desktop:local`, currently stopped). Start: `uv run python scripts/build_addon.py --release`, then `docker compose -f tests/close-loop/docker/compose.yaml up -d --build`, then `docker exec -u cua fcb-desktop fcb-freecad start`; ready when `http://127.0.0.1:18765/healthz` shows a number in `freecad_pid`. Rebuild after any change under `src/`. Runner: `docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/runner/run.py ... --out /repo/tests/uat/run/<run>/runner`. Read `tests/close-loop/README.md` and `.knowledge-base/technical/standards/testing/uat-run-practices.md` first.
MCP servers in the leader session: `freecad-buddy-docker` and `cua-driver-docker` failed to connect at session start (container was down). Subagents use the `cua-driver` CLI through `docker exec` and the runner; do not depend on those MCP tools.
Credentials: none needed. `gh` is logged in; do not push.
In use: container `fcb-desktop` publishes `127.0.0.1:6901` (noVNC) and `127.0.0.1:18765` (MCP proxy relay). Host `:8765` is the host FreeCAD bridge port; leave it free.
Missing tools: conda env `fcb` is gone; the headless H1 sweeps (`scripts/automation/run_mcp_e2e.py`, `run_mcp_edge_cases.py`) run from the host `uv` env against the container.
Shared resources: container `fcb-desktop`, image `fcb-desktop:local`, ports 6901/18765 — owner: the current Story's verifier (one Story at a time); `tests/uat/run/` — new run folders only, never edit an existing run folder; developer `%APPDATA%\FreeCAD\v1-1\user.cfg` — nobody writes it; `dist/addon/` — written only by `build_addon.py`, by the agent that owns the container at that time.
