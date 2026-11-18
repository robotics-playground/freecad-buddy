# Story 10-9: quality bar

Base: `9c214a9`. Plan: `_bmad-output/implementation-artifacts/spec-10-9-uat-runner-in-container.md`.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | The `cua-driver mcp` process started by `fcb-cua-mcp` holds the desktop session's `DBUS_SESSION_BUS_ADDRESS` whatever the start order; a check fails when it is absent | AC1 | `/proc/<pid>/environ` before and after; check script or test, shown red |
| Q2 | `get_window_state` on a GTK app returns more than 1 element and no `atspi_walk_failed`, through `cua-driver serve` and MCP; registry `ChildCount` answers | AC2 | element counts before and after; `dbus-send` output |
| Q3 | Container FreeCAD 1.1.4 main window tree has more than 1 element and holds File, Edit, View | AC3, decision D4 | element counts before and after; FreeCAD version in the evidence |
| Q4 | `invoke_menu` and one `element_index` click change FreeCAD visibly | AC4 | screenshots read by the builder, then one decoded by the leader |
| Q5 | Runner starts FreeCAD only in the container with `-M` probe and temp `-u`/`-s`; no `tasklist`, `%APPDATA%`, `FREECAD_EXE`, host FreeCAD | AC5, D2, CLAUDE.md section 9 | pytest on command building; grep of `tests/uat/runner/`; smoke run `results.json` `run` block |
| Q6 | Preflight exit 2 and launch exit 3 name the pid or port; teardown frees `:8765` and removes the discovery file | AC6 | pytest with faked process and port output; one live preflight refusal |
| Q7 | Capture, frame and allow-listed menu steps use the container `cua-driver`; Show All retry and probe confirmation kept | AC7 | smoke run captures read |
| Q8 | Smoke run of 4 named scenarios, one with a pixel check and one with a menu step, into `tests/uat/run/2026-11-17-10-9-smoke/`; no group error | AC8 | `summary.md`, `results.json`, captures |
| Q9 | Watchdog checks in the container; FreeCAD stopped exits 1, planted `FCB_TMP_snap_x` exits 1, clean exits 0 | AC9 | three live runs with output pasted |
| Q10 | Both sweeps run H1 and its worker in the container from the host `uv` env; edge sweep all checks (14 of 14 at round 2; the spec's "13 of 13" was the 2026-10-23-02 count); no `FCB_ENV` or `micromamba` in `scripts/automation/`; wrong golden path exits non-zero | AC10 | sweep reports under `_automation/`; grep; planted-path run |
| Q11 | New pure tests pass and each reads red on a broken input; ruff, `check_imports`, format on changed files clean | AC11 | `uv run pytest tests/external -q` counts; gate output |
| Q12 | Documents state the new truth; CLAUDE.md and AGENTS.md stay identical | AC12 | `diff CLAUDE.md AGENTS.md`; reading of each named file |
| Q13 | Unblocked deferred entries resolved with an evidence pointer; others keep a reason | AC13 | `deferred-work.md` diff |
| Q14 | No masked failure: no `\|\| true`, no retry to get a pass, no `continue-on-error` | spec Never list; memory rule "CI must not hide failures" | review lenses; grep of the diff |
| Q15 | Every pinned download in the image keeps its SHA-256 check; any new package is pinned | spec Always list | Dockerfile diff |
| Q16 | Developer `user.cfg` unchanged (baseline SHA-256 in decision 8) | CLAUDE.md section 9; lead log decision 2026-10-24 12:52 | SHA-256 before and after the Story |

Levels marked RUN: Unit (`uv run pytest tests/external -q`), Integration (`freecadcmd -u/-s tests/run_tests.py`), E2E (`journey_box.py`, both sweeps in the container), UAT (smoke run and element demo in the container).
