# Run 13-fu-r2: context

| Item | Value |
| --- | --- |
| Purpose | Story 13-fu re-verification after the red-team fixes: extended TC-17 (5 pairs, nested spheres `Ball/Shell`) |
| Branch, commit | `story/13-followups` at `04adaafa` (product code). Worktree `freecad-buddy-wt-13-fu` |
| Uncommitted change | `tests/uat/testcases/TC-17-query-interference-touching.md` only (case fix by the verifier). Diff `evidence/baseline-tracked.diff`, SHA-256 `2a9af734cc5844efc36c7494e72caa27cf7ae7c59f21016f27b23cb2d23a0bab` |
| Build | `uv run python scripts/build_addon.py --release` in the worktree |
| Container | compose run from the worktree; mounts read back: `freecad-buddy-wt-13-fu -> /repo (ro)`, `...wt-13-fu\tests\uat\run -> /repo/tests/uat/run (rw)` |
| Installed code | `queries.py` SHA-256 in container `Mod/FreeCADBuddy` = host `dist/addon` = `src` = `1c4b3729...6e730d` |
| FreeCAD | 1.1.4 in `fcb-desktop`; first `fcb-freecad start` aborted (known), second ready: healthz `freecad_pid` 663 |
| Developer `user.cfg` SHA-256 | `a8d0bb82...0468c2` before and after (unchanged) |
| Transport | MCP over HTTP `http://127.0.0.1:18765/mcp`, client `evidence/mcpcall.py`, calls `evidence/make_tc17.py` |
| GUI driver | `scripts/automation/fcb_cua.sh`; FreeCAD pid 663, window 41943133, 346 AT-SPI elements |
| Scope | TC-17-01 |
| Extra evidence | Verifier real-geometry probes under host freecadcmd: `evidence/attack.py`, `attack.log`, `gapsweep.py`, `gapsweep-head.log` (04adaafa), `gapsweep-base.log` (8049378d) |

## Result

| Scenario | Verdict | Evidence |
| --- | --- | --- |
| TC-17-01 | PASS | `evidence/tc-17-01-mcp.json`, `tc-17-01-before.png`, `tc-17-01-after.png`, `tc-17-01-after-small-pairs-zoom.png`, `tc-17-01-after-sphere-zoom.png` |

- Preconditions: installed hash equal; `document_list` 0 documents; `get_window_state` 346 elements.
- Given: build `'built'`; tree lists the eight objects; kernel fuse gaps `[0.0, 0.0, 0.0]`; `Big1/Big2` common empty `True`; `Ball/Shell` `[True, 2]`; `view_fit_viewport` OK.
- Then: status `OK`; A/Face, A/Edge, A/Vertex `common_volume 0.0`, `min_distance 0.0`, `boolean_failed false`; Big1/Big2 `common_volume null`, `boolean_failed true`; Ball/Shell `common_volume null`, `min_distance 1.7e-08`, `boolean_failed true`; text `5 pair(s), 0 overlapping, 2 boolean failed.`; tree after: same eight objects, no `!`; fresh digest `5d4f4c81...691d57` before and after.
- Visual: tree shows the eight objects. Two large cubes side by side share one face (Big1, Big2). Four small cubes in the face, edge and corner layout (A, Face, Edge, Vertex). One sphere shows behind Big2 with its seam line; `Ball` is inside `Shell`, so only one sphere is visible, as the case states. No box missing, no visible overlap. Before and after captures are byte-equal (read-only call between them); the before capture shows the fitted view of the last action, so the display was live.
- Cleanup: `document_close` OK, then `document_list` 0 documents.
- Case fix (test-case defect): the `Ball/Shell` check had raw line breaks inside its inline code; now `\n`. Expected value `[True, 2]` (Python `value_repr`), not `[true, 2]`.
