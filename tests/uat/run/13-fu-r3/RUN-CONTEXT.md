# Run 13-fu-r3: context

| Item | Value |
| --- | --- |
| Purpose | Story 13-fu third verification after the section shortcut was removed: TC-17 (5 pairs) |
| Branch, commit | `story/13-followups` at `1c21724b`, clean tree (no uncommitted change). Worktree `freecad-buddy-wt-13-fu` |
| Build | `uv run python scripts/build_addon.py --release` in the worktree |
| Container | compose run from the worktree; mounts read back: `freecad-buddy-wt-13-fu -> /repo (ro)`, `...wt-13-fu\tests\uat\run -> /repo/tests/uat/run (rw)` |
| Installed code | `queries.py` SHA-256 in container `Mod/FreeCADBuddy` = host `dist/addon` = `src` = `d59c6a6e...29c66aa` |
| FreeCAD | 1.1.4 in `fcb-desktop`; first `fcb-freecad start` aborted (known), second ready: healthz `freecad_pid` 580 |
| Developer `user.cfg` SHA-256 | `a8d0bb82...0468c2` unchanged |
| Transport | MCP over HTTP `http://127.0.0.1:18765/mcp`, client `evidence/mcpcall.py`, calls `evidence/make_tc17.py` |
| GUI driver | `scripts/automation/fcb_cua.sh`; FreeCAD pid 580, window 41943133, 346 AT-SPI elements |
| Extra evidence | Host freecadcmd real-geometry probes `evidence/probe_r3.py`, `probe_r3.log` (29 cases); mutant log `mutants.log` |

## Result

| Scenario | Verdict | Evidence |
| --- | --- | --- |
| TC-17-01 | PASS | `evidence/tc-17-01-mcp.json`, `tc-17-01-before.png`, `tc-17-01-after.png`, `tc-17-01-after-small-pairs-zoom.png`, `tc-17-01-after-sphere-zoom.png` |

- Preconditions: installed hash equal; `document_list` 0 documents; `get_window_state` 346 elements.
- Given: `'built'`; tree lists the eight objects; kernel fuse gaps `[0.0, 0.0, 0.0]`; `Big1/Big2` common empty `True`; `Ball/Shell` `[True, 2]`; `view_fit_viewport` OK.
- Then: status `OK`; A/Face, A/Edge, A/Vertex `common_volume 0.0`, `min_distance 0.0`, `boolean_failed false`; Big1/Big2 `common_volume null`, `boolean_failed true`; Ball/Shell `common_volume null`, `min_distance 1.7e-08`, `boolean_failed true`; text `5 pair(s), 0 overlapping, 2 boolean failed.`; tree after: same eight objects, no `!`; fresh digest `5d4f4c81...691d57` before and after.
- Visual: the tree shows the eight objects of this run's document. Two large cubes sit side by side and share one face (Big1, Big2). Four small cubes in the face, edge and corner layout (A, Face, Edge, Vertex). One sphere shows behind Big2 with its seam line: `Ball` is inside `Shell`. No box is missing and no overlap is visible. Before and after captures are byte-equal (read-only call), and byte-equal to run 13-fu-r2 (same scene, deterministic software rendering). The display was live: FreeCAD started with no document, and the capture shows the document this run built and fitted.
- Cleanup: `document_close` OK, then `document_list` 0 documents.
