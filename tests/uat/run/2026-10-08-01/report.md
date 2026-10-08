# UAT run 2026-10-08-01: ASCII document tree (`query_tree_summary`)

FreeCAD 1.1.4 GUI, freecad-buddy working tree on `4b41811` with the spec `spec-ascii-document-tree.md` changes, junction install (`Mod/FreeCADBuddy/freecad_buddy` → `src/freecad_buddy`). Auto-approve on (`addon.log`: `SECURITY: mutation auto-approve ENABLED`). Document: a copy of `kiwibox-drawer-rebuild.FCStd` (178 objects) in the session scratchpad; the original is unchanged. Driven with `cua-driver`; tool calls over the live MCP HTTP bridge (`evidence/tree_calls.py`, `evidence/gui-tree-calls.json`).

## Matrix cases over MCP

Every OK result has 2 content blocks: a JSON envelope and the tree text. No JSON block and no `structuredContent` contains the tree or `text_blocks` (checked for `text_blocks`, `[BODY]` and `|--`). `structuredContent` keys: `schema, status, detail, structured_content, text, framing`.

| Case | Arguments | Result | Total chars |
|---|---|---|---|
| Top level | — | 5 Body lines, each `(+N)`; `178 objects, 5 shown.` | 471 |
| Focus body | `focus: front_plate_piece` | `path:` line + body + 6 children | 604 |
| Expand deep | `expand: [sma_boss]` | `front_plate_piece (+5 more)`, `sma_boss *tip` open with its sketch | 537 |
| Focus + expand | `focus: front_plate_piece, expand: [sma_boss]` | 8 tree lines (below) | 634 |
| Call 128 shape | `focus: front_plate_piece, depth: 3` | 17 lines, no line from another body | **985** (was 11,612) |
| Cross-body base | `focus: tray_piece, depth: 3` | 22 lines, none from `drawer` | 1,154 |
| Reveal by name | `filters.name_pattern: "joint2.*"` | `matches: 24`, 29 lines | 1,471 |
| Reveal by code | `focus: tray_piece, filters.types: [DPLANE]` | `matches: 3`, `tray_piece (+7 more)` + 3 datum planes | 504 |
| No match | `filters.name_pattern: "zzz"` | start level only, `matches: 0` | 483 |
| All open | `depth: 6` | 178 lines, `truncated: false` | 6,665 |
| Bad name | `focus: nope` | `INVALID_INPUT`, `unknown object: nope` | 1,648 |

Focus + expand output:

```
path: front_plate_piece
v [BODY] front_plate_piece
|-- - [ORIGIN] Origin002 "Origin004" (+7)
|-- - [BASE] BaseFeature
|-- v [DPLANE] front_plate_piece_back_plane
|-- - [POCKET] front_plate_region_cut (+1)
|-- - [POCKET] locating_groove (+1)
`-- v [PAD] sma_boss *tip
    `-- v [SKETCH] sma_boss_sketch
```

The research sample differs only where the spec's later rules apply: `Origin002 "Origin004"` (the Label differs from the Name) and `*tip`.

## Model panel comparison

The same document open in the GUI, `front_plate_piece` and its children expanded in the Model panel (`evidence/gui-model-panel-front-plate.png`), compared by the developer agent against the `depth: 3` output:

- Children and order are the same: `Origin004` (its 3 axes, 3 planes and `Origin003`), `BaseFeature`, `front_plate_piece_back_plane`, `front_plate_region_cut` (with its sketch), `locating_groove` (with its sketch), `sma_boss`. The status bar names the `Origin004` row `Internal name: Origin002`, as the tool line does.
- The eye icon matches `v`/`-` on all 15 rows. Hidden: `drawer`, `Origin004`, `BaseFeature`, `front_plate_region_cut`, `locating_groove`. Visible: `front_plate_piece`, the 7 origin features, the back plane, both pocket sketches, `sma_boss`.

## Visibility parity, GUI to tool

| GUI action (Space on the tree row) | Model panel | Tool line |
|---|---|---|
| Hide `sma_boss` | crossed eye (`gui-model-panel-sma-boss-hidden.png`) | `` `-- - [PAD] sma_boss (+1) *tip `` (`gui-after-hide-sma_boss.txt`) |
| Hide `sma_boss_sketch` | crossed eye (`gui-model-panel-sketch-hidden.png`) | `` `-- - [SKETCH] sma_boss_sketch `` (`gui-after-hide-sketch.txt`) |

The second Space press was meant to show `sma_boss` again; the tree had scrolled, so it hid the sketch instead. Both hide transitions reached the tool. The show transition (`-` to `v`) was not driven in the GUI; the unit and in-FreeCAD tests cover both values.

## Automated checks (same tree)

- `uv run pytest tests/external`: 1,330 passed.
- In-FreeCAD suite (`tests/run_tests.py`, fcb env): 809 tests, OK (1 skipped).
- `ruff check .`, `gen_schemas.py --check`, `check_skill_shape.py`, `check_imports.py`: clean.

## Operator note

The operator's own FreeCAD (`* kiwibox-drawer`, unsaved) held port 8765 with the old code. Before the restart the developer agent saved that session through the bridge as `D:/Work/3D Printers/Ender 3V2 - Klipper/cad/kiwibox-drawer.unsaved-2026-10-08.FCStd` (save-as, then Save on exit). `cad/kiwibox-drawer.FCStd` kept its SHA-256 (`9a4bb13a…`).

## Verdict

PASS: line format, containment, views, reveal, cap state, error refusal, delivery in a separate text block, Model panel structure and visibility parity. Not covered in the GUI: a real error-state object (`!<status>` is tested in-FreeCAD), and the `-` to `v` transition.
