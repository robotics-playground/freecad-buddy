---
title: 'ASCII document tree for query_tree_summary'
type: 'feature'
created: '2026-10-08'
status: 'done'
baseline_commit: '4b41811f3b6e3036ca4773ff80fb45fa4a2bb13b'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/technical-agent-tree-exploration-for-mcp-2026-10-07/research.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `query_tree_summary` walks `OutList` (what an object depends on) and returns nested JSON. In run 2026-10-07-03 one call (`root: front_plate_piece, depth: 3`) followed a base feature into another body and returned 11,612 chars, the only result over the Epic 11 10K target.

**Approach:** Return the document tree as plain text in the shape of FreeCAD's Model panel: containment children, one object per line `<v|-> [CODE] <Name>`, collapsed nodes with `(+N)`, and agent-chosen `focus`/`expand`/`depth`. The type-code catalog ships in a skill reference, and a test pins it to the code.

## Boundaries & Constraints

**Always:**
- Line: `<prefix><v|-> [<CODE>] <Name>[ "<Label>"][ (+N)][ *tip][ !<status>]`. `v` = `Visibility` true. The label is shown only when it differs from the name. `(+N)` = N children not shown. `*tip` = the Tip of its Body. `!<status>` = a genuine error status.
- Connectors: `|-- ` for a middle child and `` `-- `` for the last child. Prefix `|   ` below a middle child, four spaces below the last.
- Children (containment):
  - Body: `Origin` first, then `Group`, without any member that a sibling feature claims as its `Profile`.
  - Part and group: `Group`.
  - Origin: `OriginFeatures`.
  - Sketch-based feature: `Profile` when it is a sketch.
  - `App::Link`: no children. The line ends `-> <target>`, and the tool does not descend into the target.
- Top level = objects that no other object holds as a child.
- Views:
  - No `focus`: all top-level objects are listed.
  - `focus: <Name>`: first line `path: <A> > <B> > <Name>`, then only that node's subtree.
  - `depth` (default 1, minimum 1) = levels open below the start, which is `focus` or the top level.
  - `expand: [Name…]` opens each named node one level, and opens its ancestors along the way. An ancestor opened only for a path shows just the path child, ends with `(+N more)`, and `N` excludes the shown child.
- Type code: the `TypeId` after `::` in capitals, except for a fixed override table: `PartDesign::Plane`→`DPLANE`, `App::Plane`→`PLANE`, `App::Line`/`PartDesign::Line`→`AXIS`/`DLINE`, `App::Point`/`PartDesign::Point`→`POINT`/`DPOINT`, `Sketcher::SketchObject`→`SKETCH`, `PartDesign::FeatureBase`→`BASE`, `PartDesign::Body`→`BODY`, `App::Origin`→`ORIGIN`, `App::Link`→`LINK`. A `TypeId` without `::` is used in capitals as it is.
- Cap: 200 tree lines. When the cap cuts the tree, the last line is `... <K> more lines; narrow with focus or a smaller depth`, and `structured_content.truncated` is true.
- An unknown `focus` or `expand` name gives `INVALID_INPUT` naming it.
- Reveal: `name_pattern` (regex over `Name` and `Label`) and `types` (codes such as `PAD`, or `TypeId`s) select matches.
  - Inside the start subtree, each match is shown with its path opened, the same way `expand` opens a path. The match itself is not opened, unless `expand` names it. Every other line stays collapsed.
  - With both filters given, a match must pass both.
  - `structured_content.matches` = the match count. With 0 matches, the tree shows the start level only.
  - `exclude_types`, `renderable_only` and `visible_only` are removed.
- `query_dependencies` keeps `_out_list` (OutList) unchanged.

**Decisions (human, 2026-10-08):**
- Delivery: add one generic envelope field, `text_blocks: list[str]`. The adapter sends each entry as an extra raw `TextContent` after the JSON block. `text_blocks` is never serialized into the JSON text block or `structuredContent`. The JSON carries only status and summary fields (`doc`, `total_objects`, `shown`, `truncated`, `matches`) and the one-line `text`. Amend the spine Tool-results line, `data-contracts-design.md` §ResultEnvelope, and the generated schema.
- Filters: keep `name_pattern` and `types` as reveal; remove the other three.
- One spec. Its size (about 2,500 tokens) is accepted.
- The skill catalog `skills/freecad-fundamentals/references/tree-codes.md` lists the line format and every override code with the fallback rule. A pytest fails when the catalog and the code table differ.

**Never:**
- No new MCP tool. No change to any other tool's result.
- No `FreeCADGui` import in `usecases/`. The App `Visibility` value is what the Model panel shows (FreeCAD syncs both ways, `Gui/ViewProviderDocumentObject.cpp:185-217,405-411`).
- Never open `benchmarks/*/heldout`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Top level | rebuilt drawer, no params | 5 lines, one per Body, each `(+N)` | N/A |
| Focus body | `focus: front_plate_piece` | `path:` line + body + 6 children; Pocket lines `(+1)` | N/A |
| Expand deep | `expand: [sma_boss]` | top level; `front_plate_piece (+5 more)`; `sma_boss` open with its sketch | N/A |
| Cross-body base | `focus: tray_piece, depth: 3` | no line from another body | N/A |
| Link | `App::Link` at top | `v [LINK] L -> Box`, no children | N/A |
| Cap | depth opening > 200 lines | 200 lines + `... K more lines` line; `truncated` true | N/A |
| Reveal | `name_pattern: "joint2.*"` | top level; bodies holding matches open on the path with `(+N more)`; each match line shown, not opened; `matches` = count | N/A |
| Reveal by code | `types: ["DPLANE"]`, `focus: tray_piece` | only datum planes of `tray_piece` shown on their paths | N/A |
| No match | `name_pattern: "zzz"` | start level only; `matches` 0 | N/A |
| JSON block | any call | `content[0]` JSON has no tree and no `text_blocks`; `content[1]` is the tree text | N/A |
| Bad name | `focus: nope` | — | `INVALID_INPUT` "unknown object: nope" |
| Unknown type | `TypeId` `Foo::BarBaz` | `[BARBAZ]` | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/queries.py:328` `query_tree_summary`. Rewrite it. Remove `_sparse_node`, `_prunes_subtree`, `_node_passes`, `_DATUM_EXCLUDE_DEFAULT` and `_collect_errors` if they become unused. Keep `_status_string` (`:169`, also used by `query_object :457`), `_out_list`, `_is_link`, and `summarize_tree` (`:31`, change it to a one-line summary: objects, shown, truncated).
- `src/freecad_buddy/hosts/tool_catalog.py:1172-1198`: input schema (`focus`, `expand`, `depth`) and a description with the short legend.
- `src/freecad_buddy/adapters/mcp_server.py:85` `_to_call_result` is used by both hosts (`hosts/gui_external/entry.py:140`). Pop `text_blocks` before `json.dumps` and before `structuredContent`. Append one `TextContent` for each block.
- `src/freecad_buddy/contracts/envelope.py:49` (add `text_blocks`, optional) + `scripts/gen_schemas.py:53` → regenerate `contracts/jsonschema/result-envelope.schema.json`.
- Current `name_pattern` matching: `queries.py:200` `_node_passes` (regex over `"Name Label"`). Reuse its regex rule.
- Containment precedent: `usecases/features.py:1025,1282` read `body.Group`.
- Consumers to update: `scripts/automation/run_mcp_e2e.py:118-122`, `scripts/automation/run_mcp_edge_cases.py:49-86` (both read `tree[0]["name"]`), `tests/infc/test_tree_summary.py`, `tests/infc/test_query_tools.py:71-81`, `tests/external/test_mcp_surface.py:495-507`, `tests/external/test_tool_summaries.py`, `tests/external/test_tree_helpers.py`.
- Skills that name the tool: `verification-thinking/SKILL.md:64,124`, `design-decomposition/SKILL.md:74,147`, `freecad-troubleshooting/SKILL.md:41,82`, `freecad-troubleshooting/references/symptom-cause-fix.md:66`, `freecad-fundamentals/SKILL.md:71`. Bump each `version` (`skills-structure-design.md:103`).
- Docs: `design/mcp-tools-design.md:246-278` (and `:60`, `:72`, the one-line `text` rule), the spine `ARCHITECTURE-SPINE.md:379` (Tool-results), and `data-contracts-design.md:84-94` (ResultEnvelope).
- Sample renderer used for the I/O rows: the rebuilt drawer `D:/Work/3D Printers/Ender 3V2 - Klipper/cad/kiwibox-drawer-rebuild.FCStd`, read-only. Use a copy for any infc fixture. A smaller fixture under `tests/` is preferred.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/tree_text.py` (new, pure): code table, `type_code`, line rendering and connectors. No FreeCAD import, so it can be unit-tested in `tests/external`.
- [x] `src/freecad_buddy/usecases/queries.py`: containment walk, views, cap, and errors. Call `tree_text`.
- [x] `src/freecad_buddy/hosts/tool_catalog.py`: schema and description.
- [x] `contracts/envelope.py`, `adapters/mcp_server.py` and the regenerated schema: `text_blocks`. Add a `tests/external` test asserting `content[0]` JSON and `structuredContent` hold no `text_blocks`, and that each block is its own `TextContent`.
- [x] `skills/freecad-fundamentals/references/tree-codes.md` + a link in `SKILL.md`. Update the other 4 skill files and bump versions.
- [x] `tests/external/test_tree_text.py`: rendering, codes, connectors, cap line, and the catalog drift check (parse the catalog table, compare it with the code table).
- [x] `tests/infc/test_tree_summary.py`: rewrite for the I/O matrix on a PartDesign fixture (body, origin, sketch, pad, pocket, datum plane, base feature, link).
- [x] Update the other consumers in the Code Map.
- [x] `design/mcp-tools-design.md` entry, spine Tool-results line, and `data-contracts-design.md` ResultEnvelope (`text_blocks`).

**Acceptance Criteria:**
- Given the rebuilt drawer copy, when `query_tree_summary(focus="front_plate_piece", expand=["sma_boss"])` runs, then the text equals the sample in the research file, apart from GUI visibility of sketches, and no line names an object outside `front_plate_piece`.
- Given call 128's request shape (`focus: front_plate_piece, depth: 3`), then the result is under 2,000 chars.
- Given `uv run python scripts/check_skill_shape.py`, then exit 0.

## Implementation Notes

- The research sample predates two Always rules. On the drawer copy, `focus=front_plate_piece, expand=[sma_boss]` gives the sample lines except: `Origin002 "Origin004" (+7)` (its Label differs from its Name) and `sma_boss *tip` (it is the Body Tip). Sketches read `v` (App `Visibility` true in the file). The Always rules win; the AC sample is read with these two lines amended.
- Origin first applies to every origin group, not only a Body. `App::Part` keeps its `Origin` outside `Group` too (`Gui/ViewProviderOriginGroupExtension.cpp:57-81` puts it first), so "Part: `Group`" alone would list a Part's Origin as a top-level object.
- With `filters`, `depth` opens no level: only match paths and `expand` open ("every other line stays collapsed"). With `focus` and 0 matches the start level is the focus line, collapsed.
- `filters` keeps its object shape (`filters.types`, `filters.name_pattern`). `focus` replaces `root`.
- An `expand` name that exists but lies outside the `focus` subtree is refused: `INVALID_INPUT` "<name> is outside focus <focus>".
- Containment also copies the `claimChildren` of `Part::Boolean`, `Part::MultiFuse`/`MultiCommon`, `PartDesign::Loft`, `Pipe` and `MultiTransform`, and a geometry group drops every member another member claims (`Gui/ViewProviderGeoFeatureGroupExtension.cpp:78-108`). Without them, boolean operands and transformations are listed as top-level or Body lines. `App::LinkGroup` lists its `ElementList`; only `App::Link`/`App::LinkPython` are leaf links.
- The one-line `text` ends `Errors: <Name>: <status>; ...` for every errored object in the start subtree, so an error under a collapsed line is not lost. The JSON field list is unchanged.
- `filters.types` matches a code in any case; a `TypeId` matches exactly.

## Spec Change Log

## Review Triage Log

- Pass 1: errored objects under a collapsed node vanish; the old summary listed every error (blind, verification-gap) -- medium, patch: list `name: status` of errored objects in the one-line `text`; frozen JSON field list unchanged.
- Pass 1: Part booleans (`Base`/`Tool`), MultiFuse/MultiCommon (`Shapes`), Loft/Pipe (`Sections`/`Spine`), MultiTransform (`Transformations`) not nested; their operands become top-level lines (blind) -- medium, patch: Approach says "shape of FreeCAD's Model panel"; the Always list does not say "only these"; mirror each FreeCAD `claimChildren` cited by source.
- Pass 1: `_is_link` prefix also catches `App::LinkGroup`/`App::LinkElement`; LinkGroup members become top-level (blind, edge-case) -- medium, patch.
- Pass 1: no cycle guard in `chain`/`build`; a cycle loops while holding the registry lock (blind, edge-case) -- medium, patch: visited sets.
- Pass 1: label with newline or `"` breaks one-object-per-line (blind, edge-case) -- low, patch: same whitespace rule as status, escape `"`.
- Pass 1: `filters.types` case-sensitive (edge-case) -- low, patch.
- Pass 1: `expand` name outside `focus` silently ignored (blind, edge-case) -- low, patch: refuse with `INVALID_INPUT`.
- Pass 1: code collisions (`Part::Plane`/`App::Plane` both `PLANE`, `Part::Fillet`/`PartDesign::Fillet`) (blind, edge-case) -- low, patch: document non-unique codes and exact `TypeId` match.
- Pass 1: `replay_result_sizes.py` excludes or under-counts a two-block result (verification-gap) -- medium, patch.
- Pass 1: untested: `!<status>` on a real broken object, invalid `name_pattern`, nested `path:` line, `types` as `TypeId`, `focus`+`expand`, size of the call-128 shape (blind, verification-gap) -- medium, patch.
- Pass 1: manual cases TC-02, TC-09, TC-12, TC-13 and `test-plan.md:349` assert removed fields (blind, verification-gap) -- medium, patch.
- Pass 1: SKILL.md example lines lack `v|-`; `TreeNode.hidden` clashes with "hidden" = `-`; dead clause in `_tree_names`; `depth` wording with/without `focus` and with `filters`; non-schema key in `mcp-tools-design.md` block (blind) -- low, patch.
- Pass 1: object with two containers (shared or cross-body `Profile` sketch) shows under both; path follows the first parent (blind, edge-case) -- low, rejected: rare; fix adds branching.
- Pass 1: nested `JobStatus.result` keeps `text_blocks` (blind) -- low, rejected: no job tool returns `text_blocks`.
- Pass 1: a client that reads only `structuredContent` gets no tree (blind) -- rejected: human decision (tree never in `structuredContent`).
- Pass 1: object with both `Profile` and `GroupExtension` drops its group (edge-case) -- false: no FreeCAD type combines `ProfileBased` with `GroupExtension`.
- Pass 1: path line names ancestors outside focus (edge-case, claim) -- false: the AC check is on tree lines; `path:` is the breadcrumb by design.

## Verification

**Commands:**
- `uv run pytest tests/external` -- expected: green.
- `<fcb-env> tests/run_tests.py` (in-FreeCAD suite) -- expected: green.
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift.
- `uv run ruff check .` -- expected: clean.

**Manual checks:**
- GUI: open the drawer copy, call the tool over MCP, and compare its lines with the Model panel screenshot.
