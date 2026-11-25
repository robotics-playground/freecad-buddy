# Run 13-15-r1: context

| Item | Value |
| --- | --- |
| Purpose | Story 13-15 verification: TC-18 (TNP audit accepts a reference that rides its moved support; epic decision 40, decision note 017) |
| Branch, commit | `story/13-15-tnp-expected-reattachment` at `5115b2ac`. Worktree `freecad-buddy-wt-13-15` |
| Uncommitted change by the verifier | `tests/uat/testcases/TC-18-tnp-support-follow.md` (new), one index row in `tests/uat/test-plan.md`, this run folder |
| Build | `uv run python scripts/build_addon.py --release` in the worktree |
| Container | `docker compose -f tests/close-loop/docker/compose.yaml up -d --build` run from the worktree. Mounts read back: `freecad-buddy-wt-13-15 -> /repo (ro)`, `freecad-buddy-wt-13-15/tests/uat/run -> /repo/tests/uat/run (rw)` |
| Installed code | `tnp_guard.py` SHA-256 in the container `Mod/FreeCADBuddy` = host `dist/addon` = `src` = `git show 5115b2ac:...` = `bec0a8c66ae1f51bcb648e987efb2baf90031ad1da8e5039a3df7b84fb92e275` |
| FreeCAD | 1.1.4 AppImage in `fcb-desktop`. First `fcb-freecad start` ran before the XFCE session (`fcb-session-env: no xfce4-session is running`), so the window had no AT-SPI tree (`element_count` 1); stopped and started again: pid 795, window 23068770, 349 elements |
| Developer `user.cfg` SHA-256 | starts `a8d0bb82aa39569`, the same as run 13-fu-r1 records (unchanged; host FreeCADCmd ran with private cfg files only) |
| Transport | MCP over HTTP `http://127.0.0.1:18765/mcp`, client `evidence/tc18.py <scenario> <out.json>` (host `uv` env); `evidence/closeall.py` closes every document between scenarios; `evidence/probe04.py` reads the support box of 04a |
| GUI driver | `scripts/automation/fcb_cua.sh` (container `cua-driver` 0.28.1) |
| Scope | TC-18-01 .. TC-18-04 (04b is a probe added for review ledger R1-D1) |
| Evidence naming | `evidence/tc-18-<scenario>-mcp.json` (every call, args and full structured result); `-attempt1` = a run with a driver error, kept; `audit-final.jsonl`, `addon.log` copied from the container at the end |
| Scenario id map | case 03a = `tc-18-03a`, 03b = `tc-18-03a2`, 03c = `tc-18-03b`, 03d = `tc-18-03c`, 04a = `tc-18-04`, 04b = `tc-18-04b` (+ `-repeat`) |

## Results

| Case | Verdict | Evidence |
| --- | --- | --- |
| TC-18-01 | PASS | `tc-18-01-mcp.json`: edit `OK`, `rolled_back` false, `tnp_audit` `CLEAN` counts `{PASS: 2}`, datum z 10.0 -> 15.0; audit log `verify_verdict` `OK`, `rolled_back` false (14:58:42 UTC); `tc-18-01-after-front.png`: datum line on the top edge, status bar "Preselected ... TopDatum (17.05 mm, -2.78 mm, 15.00 mm)" |
| TC-18-02 | PASS | `tc-18-02-mcp.json`: `sketch_set_datum` `OK`, `CLEAN` `{PASS: 3}`; `(10.0, 30.0, 30.0, [])` |
| TC-18-03 | PASS | 03a `REPOINTED` L1 "now maps to a different element"; 03b `REPOINTED` L1 "witness moved"; 03c `SPEC_FAILED`, rolled back, `REPOINTED` witness z 10 -> -10, state restored; 03d `SPEC_FAILED`, rolled back, `REPOINTED` L1 mapped name `#10:4;:G;XTR;:H1205:7,E -> #10;:G;XTR;:H1205:7,E` |
| TC-18-04 | PASS (04a `CLEAN`); 04b recorded safe-side `REPOINTED` (defect D-1 in the verify report) | 04a: face and support box both y -4.990133642 -> -4.988343846 (mesh-based), `CLEAN` `{PASS: 2}`, point z 7.5. 04b (twice): `SPEC_FAILED`, rolled back, `BossPoint` witness `(7.0, 2.0, 10.0, 13.0, 8.0, 15.0) -> (7.0, 2.01643431389518, 10.0, 13.0, 7.98356568610482, 20.0)`, support y unchanged |

`addon.log`: no `ERROR` and no `Traceback`. Teardown: `fcb-freecad stop`, `compose down`; no `fcb` container left.
