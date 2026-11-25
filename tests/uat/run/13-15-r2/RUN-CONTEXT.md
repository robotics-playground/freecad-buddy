# Run 13-15-r2: context

| Item | Value |
| --- | --- |
| Purpose | Story 13-15 re-verification after the fix batch (positional-counter detector, lineage walk, exact-geometry witness, element-count guard): TC-18-01 .. 04 and the 04b probe of defect D-1 (run 13-15-r1) |
| Commit tested | `6d6bdc60`. Worktree head was `1c459a8a` (docs only: `deferred-work.md`, decision 017); `git diff --stat 6d6bdc60 -- src addon scripts tests/close-loop` is empty |
| Uncommitted change by the verifier | this run folder; TC-18-04b `Then` lines in `tests/uat/testcases/TC-18-tnp-support-follow.md` |
| Build | `uv run python scripts/build_addon.py --release` in the worktree |
| Container | `docker compose -f tests/close-loop/docker/compose.yaml up -d --build` from the worktree. Mounts: `freecad-buddy-wt-13-15 -> /repo (ro)`, `.../tests/uat/run -> /repo/tests/uat/run (rw)` |
| Installed code | `tnp_guard.py` SHA-256 in the container = `dist/addon` = `git show 6d6bdc60:` = `2c87d5a78a624399ed5a256a3fd53ac7aff0dff330e0ff88910251490e32c867` |
| FreeCAD | 1.1.4; started after `fcb-session-env` answered (desktop ready): pid 364, window 23068765, 346 AT-SPI elements |
| Developer `user.cfg` SHA-256 | starts `a8d0bb82aa39569` (unchanged) |
| Transport | MCP over HTTP `http://127.0.0.1:18765/mcp`; `evidence/tc18.py` and `evidence/closeall.py` copied unchanged from run 13-15-r1; `evidence/probe04b_reason.py` runs the installed guard in FreeCAD around the 04b edit |
| GUI driver | `scripts/automation/fcb_cua.sh` (container `cua-driver` 0.28.1) |
| Scenario id map | as in run 13-15-r1: 03a `tc-18-03a`, 03b `tc-18-03a2`, 03c `tc-18-03b`, 03d `tc-18-03c`, 04a `tc-18-04`, 04b `tc-18-04b` (+ `-repeat`) |

## Results

| Case | Verdict | Evidence |
| --- | --- | --- |
| TC-18-01 | PASS | `OK`, `rolled_back` false, `CLEAN` `{PASS: 2}`, datum z 10.0 -> 15.0, support `('Face6',)`; audit log 16:39:50 UTC `verify_verdict` `OK`, `rolled_back` false; `tc-18-01-after-front.png`: datum line (yellow) on the top edge of the 20 x 15 outline |
| TC-18-02 | PASS | `sketch_set_datum` `OK`, `CLEAN` `{PASS: 3}`, `(10.0, 30.0, 30.0, [])` |
| TC-18-03 | PASS | 03a `REPOINTED` L1 "now maps to a different element"; 03b `REPOINTED` L1 "witness moved"; 03c `SPEC_FAILED`, rolled back, z 10 -> -10, restored; 03d `SPEC_FAILED`, rolled back, mapped name `#10:4;:G;XTR;:H3ce:7,E -> #10;:G;XTR;:H3ce:7,E` |
| TC-18-04 | PASS (04a `CLEAN`); 04b safe-side `REPOINTED`, reason recorded | 04a `CLEAN` `{PASS: 2}`, point z 7.5. 04b twice: `SPEC_FAILED`, rolled back, witness `(7.0, 2.0, 10.0, 13.0, 8.0, 15.0) -> (7.0, 2.0, 10.0, 13.0, 8.0, 20.0)` (y exact now; r1 read 2.0164). `tc-18-04b-reason.txt`: mapped `#23:1;:M;FUS;:H-85b:7,F`, `counter True`, `lineage True`, counts `{Face: 8, Edge: 15, Vertex: 10}`; shipped `REPOINTED` L1, detector and lineage off `PASS` L2 |

`addon.log`: no `ERROR`, no `Traceback`. Teardown: `fcb-freecad stop`, `compose down`; no `fcb` container left.
