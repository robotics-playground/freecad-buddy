# Run 13-17-r1: TC-21 results

- Code: `story/13-17-part-primitive-boolean` at `deaa2b25`. Installed `features.py` in the container: sha256 `c261574f…` = `src` at `deaa2b25` = `dist/addon` after `build_addon.py --release`.
- Host: `fcb-desktop` container (`/repo` = wt-13-17, read-only; `tests/uat/run` writable). FreeCAD 1.1.4 GUI, pid 400, window 35651677. `cua-driver` element tree: 346 elements at start (File, Edit, View present).
- Driver: `evidence/tc21.py <scenario> <pid> <wid>` calls the MCP proxy at `http://127.0.0.1:18765/mcp` and captures the window with `cua-driver get_window_state`. Raw calls: `evidence/out-tc21-0N.json`. `evidence/closeall.py` closed each document after the scenario was graded.
- `addon.log`: no `ERROR` and no `Traceback`. `/tmp/freecad.log`: no `Traceback`.

| Case | Verdict | Notes |
| --- | --- | --- |
| TC-21-01 | PASS | Cut/common/fuse `OK`, volumes 500/500/1500 (envelope and `Shape.Volume`), types `Part::Cut`/`Common`/`Fuse`, inputs hidden. Visual: one solid each; x:y edge ratio 0.5, 0.5, 1.5, so the fuse is 3 times as long along x as the cut and the common. Tree shows the inputs nested under each result. Six undos (3 visibility scripts + 3 booleans) leave `[None, None, None, True, True]`; `tc-21-01-after-undo.png` shows A and B. |
| TC-21-02 | PASS | `RECOMPUTE_ERROR`, `part_boolean.empty_result`, `rolled_back` true, `rollback_proven` `rolled_back_verified`. `query_tree_summary` text: `v [BOX] A`, `v [BOX] Far` (its `structuredContent` is empty; the text block carries the tree). Before and after captures are the same: two cubes, tree A and Far. The next primitive and its undo are `OK`. |
| TC-21-03 | PASS | Reversed `Rev` → `INVALID_INPUT` `part_boolean.untrusted_shape`, message names `Rev` and "reversed". `Pad` → `part_boolean.not_top_level`, message names `Pad` and `Body`. `Body` as base → `OK`. Tree: `Rev`, `BodyCut`; no `BadCut`, no `PadCut`. |
| TC-21-04 | PASS | Five calls `OK`; volumes `[376.991, 188.496, 789.568]`; `Part::Cut` + `Part::MultiFuse` `Drilled_tools`, `Refine` false on both; cut volume 3797.76; visibility `[F, F, F, F, T]`; undo removes both objects and shows the inputs; redo `OK`; torus 2/2 → `part_primitive.dimension`, no `Bad`. Visual: plate, ring; bottom view (`tc-21-04-bottom.png`) shows the pin hole seen through and the cone hole as a conical wall around a small opening. |

## Test-case change

- TC-21-04 visual Then: the isometric top view shows two openings but cannot show that the cone hole narrows. The step now adds a bottom view (`press_key 5`) and a second capture. Cause class: test-case gap. No product finding.
