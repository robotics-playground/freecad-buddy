# Run 13-fu-r1: context

| Item | Value |
| --- | --- |
| Purpose | Story 13-fu verification: TC-17 (`query_interference` reads touching solids as zero overlap, Epic 13 decision 41) |
| Branch, commit | `story/13-followups` at `8049378d` (product code). Worktree `freecad-buddy-wt-13-fu` |
| Uncommitted change | `tests/uat/testcases/TC-17-query-interference-touching.md` only (case fix by the verifier). Diff `evidence/baseline-tracked.diff`, SHA-256 `4e289a5d14e90fa0db298eebf670ca622bc5e30849d5f848acab562efe314f38` |
| Build | `uv run python scripts/build_addon.py --release` in the worktree |
| Container | `docker compose -f tests/close-loop/docker/compose.yaml up -d --build` run from the worktree. Mounts read back: `freecad-buddy-wt-13-fu -> /repo (ro)`, `freecad-buddy-wt-13-fu/tests/uat/run -> /repo/tests/uat/run (rw)` |
| Installed code | `queries.py` SHA-256 in the container `Mod/FreeCADBuddy` = host `dist/addon` = `src` = `f1ffb5ee...bc5f95` |
| FreeCAD | 1.1.4 AppImage in `fcb-desktop`; first `fcb-freecad start` aborted (known Qt xcb plugin abort), second start ready: healthz `freecad_pid` 1202 |
| Developer `user.cfg` SHA-256 | `a8d0bb82...0468c2` before and after the run (unchanged) |
| Transport | MCP over HTTP `http://127.0.0.1:18765/mcp`, client `evidence/mcpcall.py` (host `uv` env), call list built by `evidence/make_tc17.py` |
| GUI driver | `scripts/automation/fcb_cua.sh` (container `cua-driver` 0.28.1); FreeCAD window pid 1202, window 41943133, 346 AT-SPI elements |
| Scope | TC-17-01 only |
| Evidence naming | `evidence/tc-17-01-*`; attempt 1 files carry `-attempt1` |
