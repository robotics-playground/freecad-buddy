---
title: 'technical research: top-down document-tree exploration for an MCP agent'
type: 'technical'
topic: 'Top-down tree exploration tool for an MCP agent over a FreeCAD document'
decision: 'Shape of a level-by-level document tree tool replacing the one-call query_tree_summary dump'
source: 'native run, inline, 4 sources + FreeCAD source'
status: final
preset: 'quick-inline'
validation: 'normal'
created: '2026-10-07'
updated: '2026-10-07'
---

# Top-down document-tree exploration for an MCP agent

## Decision

How should freecad-buddy let an agent look at a large document (about 180 objects) one level at a time, like a person who opens folders, so that one look never fills the context?

## What the current tool does

This section holds codebase facts. They set the questions; they are not research evidence.

- `query_tree_summary` (`src/freecad_buddy/usecases/queries.py:328`) already defaults to `depth: 1`, takes `root`, and gives `children_count` at the depth edge. The folder-browse model already exists in part.
- A node's children are its `OutList`, the objects it **depends on**, not the objects it **contains**. A sketch-based feature lists its sketch, its base feature and its support planes. A piece body lists `BaseFeature`, which leads into another body.
- Story 11.6, call 128 (`root: front_plate_piece`, `depth: 3`, `exclude_types: []`) returned 92 nodes and 11,612 chars. 88 of them were at level 3: the walk crossed from `front_plate_piece` through its base feature into the `drawer` body and listed its 80 features. For 85 of the 92 nodes, `label` equals `name`.
- Measured on the same file: the containment children of `front_plate_piece` are 9 rows, 541 chars of compact JSON. The `drawer` body has 80 rows, 4,696 chars.

## Findings

- **Containment is what a person sees.** FreeCAD's tree view shows a group's `Group` values as its children [6], and a sketch-based feature shows only its `Profile` sketch, not its base or previous feature [7]. Both are App-level properties, so a headless host can read them too.
- **One level, then a separate search.** The MCP reference filesystem server splits a one-level `list_directory` (`[FILE]`/`[DIR]` entries) from a recursive `directory_tree` and a recursive `search_files` that returns paths [2]. Browsing and finding are separate tools there.
- **Bounded output with defaults and steering.** Anthropic recommends pagination, range selection, filtering and truncation with sensible defaults for any tool that can return a lot. When the tool truncates, it should tell the agent what narrower call to make [3][5]. Claude Code caps a tool response at 25,000 tokens by default [3].
- **Detail on demand.** A `response_format` enum (`concise`/`detailed`) lets the agent choose detail. The source's example is 72 tokens concise against 206 detailed [4]. High-signal fields beat low-level identifiers [3].
- **Pagination convention.** MCP's own list operations use an opaque `cursor`/`nextCursor`, with page size set by the server [1]. The spec defines this for protocol list methods only, not for tool results. A tool that pages its own output may copy the shape, but that is a choice, not a requirement.

## Options (brainstorm)

1. **Containment edges.** Children = `Group` (Body, Part, group), `OriginFeatures` (Origin), and `Profile` for a sketch-based feature. Dependencies stay in `query_dependencies`. This alone turns call 128 into about 540 chars.
2. **Collapsed clutter rows.** Show `Origin` and datum planes as rows with a count, closed by default, instead of hiding them with `exclude_types`. The agent overrode the default exclusion with `exclude_types: []` because it needed the datums.
3. **Compact rows.** Drop `label` when it equals `name`, emit `visibility` only when false, and use one `columns` + `rows` table per level. On the drawer body: 4,696 to 3,763 chars.
4. **Per-level cap with a cursor.** For example, 50 rows per listing, an opaque `cursor`, and a truncation line that names the narrower call (`name_pattern`, `types`, or the next `cursor`).
5. **Breadcrumb.** Each listing carries the path from the document root to the parent (`drawer-rebuild / front_plate_piece`), like the current directory in a shell.
6. **Row flags that decide whether to open.** Give `children_count`, `error`, `is_tip` and `hidden`, and nothing that needs a separate query to read.
7. **Separate find tool.** A flat `name_pattern`/`types` search that returns paths and no tree, like `search_files` [2]. The current filters do part of this, inside the tree tool.
8. **Type summary when a level is large.** For example, "drawer: 25 Pocket, 22 Pad, 28 datum, 5 Sketch…". The agent asks for one type next.
9. **`response_format` concise/detailed** [4]. Detailed adds `label`, `placement` and `shape_summary` per row.
10. **Keep `depth > 1` but cap total nodes**, with the same truncation steering. This keeps one-call views of small documents.
11. **New tool name** (`query_tree_children`), keeping `query_tree_summary`. This is extra surface; the current tool already has the one-level default.

## Recommendation

Keep one tool and change what it lists. The user's top-down model is already the tool's default (`depth: 1` + `root`). The 11.6 failure came from the edges and the missing bound, not from a missing tool.

- **Do:** option 1 (containment edges), option 4 (per-level cap, cursor and steering text), option 3 (compact rows), and option 5 (breadcrumb).
- **Consider:** option 2 (collapsed clutter rows), so that `exclude_types` stops being the way to see datums.
- **Defer:** options 7, 8 and 9 until a measured session shows a need.

This keeps the AD-15 surface stable and needs a story in the Epic 11 follow-up. Open question for the design: whether a containment listing must still show an `App::Link`'s target, which can live in another document. Today's `links` partition handles that.

## Design agreed with the user (2026-10-08)

- The tree is plain text, one object per line, in the form `<vis> [<CODE>] <Name>`. `v` means visible and `-` means hidden. `(+N)` follows a collapsed node with N children.
- ASCII connectors `|--` and `` `-- ``, with `|   ` and four spaces as the prefix for deeper levels.
- The tree tool returns two content blocks: a small JSON envelope (status, doc, counts) and the tree as raw multi-line text. `structuredContent` keeps the data for schema checks.
- The agent names nodes to expand. Expanding a deep node opens its path: each ancestor shows only the line on the path plus a count of its other children.
- Two views. **Whole tree** (no `focus`): every top-level object is listed, and only the `expand` nodes and their paths are open. **Focus** (`focus: <name>`): only that node and its subtree are shown, under a `path:` line that gives its place in the tree. `expand` works in both views. `depth` (default 1) sets how many levels open below the starting point (`focus`, or the top level). `focus` replaces today's `root`.
- Type-code catalog. The code table is defined once in code. `skills/freecad-fundamentals/references/tree-codes.md` lists every code and the line format (`v`/`-`, `(+N)`, `!<status>`, `*tip`), and `freecad-fundamentals/SKILL.md` links to it. A pytest fails when the skill table and the code table differ. The tool description carries only a short legend. The five skill files that mention `query_tree_summary` change to the new output. Both ship in the same story as the tool.
- Children are containment, as in FreeCAD's Model panel: `Origin` and `Group` for a Body (without sketches that a feature claims), `OriginFeatures` for an Origin, and `Profile` for a sketch-based feature.

Sample, rendered from `kiwibox-drawer-rebuild.FCStd` (`front_plate_piece` and `sma_boss` expanded; 12 lines, 407 chars against 11,612 for call 128):

```
- [BODY] drawer (+49)
v [BODY] front_plate_piece
|-- - [ORIGIN] Origin002 (+7)
|-- - [BASE] BaseFeature
|-- v [DPLANE] front_plate_piece_back_plane
|-- - [POCKET] front_plate_region_cut (+1)
|-- - [POCKET] locating_groove (+1)
`-- v [PAD] sma_boss
    `-- - [SKETCH] sma_boss_sketch
v [BODY] tray_piece (+10)
v [BODY] rear_module_piece (+13)
v [BODY] duct_cover (+10)
```

All five bodies expanded: 93 lines, 3,375 chars.

## Sources

| [n] | Source | Publisher | Published | Accessed |
|---|---|---|---|---|
| 1 | https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/pagination | MCP project | 2025-06-18 | 2026-10-07 |
| 2 | https://github.com/modelcontextprotocol/servers/blob/main/src/filesystem/README.md | MCP project | main | 2026-10-07 |
| 3 | https://www.anthropic.com/engineering/writing-tools-for-agents | Anthropic | 2025-09-11 | 2026-10-07 |
| 4 | same as [3] | Anthropic | 2025-09-11 | 2026-10-07 |
| 5 | same as [3] | Anthropic | 2025-09-11 | 2026-10-07 |
| 6 | FreeCAD `src/Gui/ViewProviderGroupExtension.cpp:174-184` (commit 4fd3bf3) | FreeCAD project | 2026-09-28 | 2026-10-07 |
| 7 | FreeCAD `src/Mod/PartDesign/Gui/ViewProviderSketchBased.cpp:75-84` (commit 4fd3bf3) | FreeCAD project | 2026-09-28 | 2026-10-07 |
