---
title: 'Part primitive and Part boolean tools'
type: 'feature'
created: '2026-11-24'
status: 'in-progress'
route: 'dispatch'
spec_checkpoint: true
review_loop_iteration: 0
baseline_commit: '0b690db152cf1541987b5dd562151d4010c40bb0'
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** No typed tool makes a `Part::` primitive, `Part::Cut`, `Part::Fuse` or `Part::Common`. An agent that builds a CSG part, or splits a print piece with a common, runs `script_exec` (CAP-9; `deferred-work.md:1654`). FreeCAD gives wrong answers on some inputs and silent empty results on others, so a raw script cannot be trusted either.

**Approach:** Two mutation tools in `usecases/features.py`, both under the AD-5 bracket, neither calls `_require_partdesign()`. `feature_part_primitive` makes one `Part::` solid at document level. `feature_part_boolean` makes a cut, fuse or common of top-level solids, refuses inputs the kernel cannot be trusted on, refuses inputs above a measured cost, and rolls back an empty result. New schema, so additive (AD-28). Same story edits `docs/intent.md` and `mcp-tools-design.md` (see Design changes).

## Boundaries & Constraints

**`feature_part_primitive`.** Input `doc`, `kind` (`box`, `cylinder`, `cone`, `sphere`, `torus`), `name`, dimensions as mm Quantities, optional `placement`, `confirm`. Fields per kind, checked against `PrimitiveFeature.cpp` and `FeaturePartBox.cpp`:

| kind | type | fields | FreeCAD property | refused (`INVALID_INPUT`) |
|---|---|---|---|---|
| box | `Part::Box` | `length`, `width`, `height` | `Length` `Width` `Height` | any value <= 0 |
| cylinder | `Part::Cylinder` | `radius`, `height` | `Radius` `Height` | any value <= 0 |
| cone | `Part::Cone` | `radius1`, `radius2`, `height` | `Radius1` `Radius2` `Height` | radius < 0, both radii 0, height <= 0 |
| sphere | `Part::Sphere` | `radius` | `Radius` | radius <= 0 |
| torus | `Part::Torus` | `radius1`, `radius2` | `Radius1` `Radius2` | radius <= 0, `radius2 >= radius1` |

A field that does not belong to the kind, a missing field, a unit other than `mm`, a non-finite number, and a bad name (existing `_name_available`) are `INVALID_INPUT`. Partial primitives (`Angle*` properties) are not exposed; they keep FreeCAD's full-turn default. The object is created at document level with `Name` = `Label` = `name` and is never added to a Body. The result is read back with `feature_state` (`body` is `""` and `is_tip` is false: existing behaviour for a non-Body feature).

**`placement`** (same value shape as `feature_set_parameters` T-4, so Stories 13-16 and 13-17 agree): `{ "base": {"x": Q, "y": Q, "z": Q}, "rotation": { "axis": [x, y, z], "angle": Q } }`. `Q` is `{value, unit: "mm"}` for `base` and `{value, unit: "deg"}` for `angle`. A key left out takes the default of a new object: base (0, 0, 0), rotation none. `axis` is three finite numbers, not all zero; the tool normalises it. Unknown keys, non-finite values and a wrong unit are `INVALID_INPUT`. One shared parser `_placement_value` in `features.py`: whichever of 13-16 and 13-17 is built second reuses it and adds no copy.

**`feature_part_boolean`.** Input `doc`, `operation` (`cut`, `fuse`, `common`), `base` (object Name), `tools` (array, 1 to 20 Names), `name`, `refine` (bool, default true), `confirm`. Objects built:

| operation | one tool | several tools |
|---|---|---|
| cut | `Part::Cut` (`Base`, `Tool`) | `Part::MultiFuse` named `<name>_tools` of the tools, then `Part::Cut` named `<name>` with that fuse as `Tool` |
| fuse | `Part::Fuse` | `Part::MultiFuse`, `Shapes` = base then tools |
| common | `Part::Common` | `Part::MultiCommon`, `Shapes` = base then tools: the intersection of the base and every tool (property `Behavior` default `CommonOfAllShapes`) |

`Refine` is set explicitly from `refine` on every boolean object the tool creates, because FreeCAD reads its default from the user preference `Mod/Part/Boolean/RefineModel`. `<name>_tools` must also be a free, usable name. The result and the intermediate fuse (if any) are the `touched` objects; `feature` is the result `Name`.

**Inputs.** Each of `base` and `tools` must exist, be distinct from every other input, and be top-level: `getParentGeoFeatureGroup()` is `None` (a Body itself is allowed; a Body feature, a sketch inside a Body and a member of an `App::Part` are not) → `INVALID_INPUT` `detail.code` `part_boolean.not_top_level`, naming the object. Each input shape must be trusted: valid, made only of solids, every solid with positive volume (the rule of `_is_measurable_solid`, `queries.py:777`) → else `INVALID_INPUT` `part_boolean.untrusted_shape`, naming the object and the reason. A sketch, wire, face or shell is untrusted. Probe (FreeCAD 1.1.4): a reversed solid made `Part::Cut` return 1500 where 500 is right and `Part::Fuse` return 500 where 1500 is right, with status `Valid`; a self-intersecting solid made `Part::Common` return an empty compound with status `Valid`. Cost: total faces of all inputs above 3,000, or `base` solids times total tool solids above 1,000 → `INVALID_INPUT` `part_boolean.too_complex`, before any write, naming both numbers and the limit (limits and measurements in Implementation Notes).

**Visibility.** The tool sets `Visibility` to false on `base`, every tool, and the intermediate fuse, inside the transaction, so undo restores it. Reason: `ViewProviderBoolean.cpp:212` (`Base`, `Tool`) and `:330`, `:474` (`Shapes`) hide the inputs when a link property changes, but only in a GUI session; a headless session leaves them visible. Headless and GUI must read the same.

**Result check.** FreeCAD does not flag an empty result: a common of disjoint solids, a cut that removes everything and a common of touching solids gave a `Compound` with 0 solids and status `Valid` (probe), and `post_verify` passes it. After the recompute the tool checks that the result has at least one solid and positive volume; if not, the call ends `RECOMPUTE_ERROR` with `detail.code` `part_boolean.empty_result`, the message names the operation and inputs, and the AD-5 rollback runs (proven). The result is never reported as a made-up number.

**Always.** AD-5 bracket for both tools; both appear in `preview_op_table` (they are `feature_` specs with a function of the same name in `features`); `timeout_s` is the existing feature value (120 s). Quantities in mm and deg only. Every new failure kind carries a `detail.code` (AD-17).

**Never.** Call `_require_partdesign()`. Change a PartDesign tool's behaviour. Add a status value. Expose `Angle*` properties, `Behavior`, `Part::Reverse`, `Part::Compound` or any other `Part::` type. Return a pass or verdict. Import FreeCAD outside the AD-1 whitelist.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Box | box 10x20x30 | `Part::Box`, volume 6000, solid_count 1 | N/A |
| Cone, point apex | radius1 5, radius2 0, height 10 | volume 261.799 (pi r^2 h / 3) | N/A |
| Torus | radius1 10, radius2 2 | volume 789.568 | N/A |
| Placed | box + base (1,2,3) + rotation z 90 deg | bbox (-19, 2, 3) to (1, 12, 33) | N/A |
| Bad dimension | box length 0, cone both radii 0, torus radius2 >= radius1 | none | `INVALID_INPUT` |
| Wrong field | box with `radius` | none | `INVALID_INPUT` |
| Cut | 10 cube minus cube shifted 5 mm | volume 500 | N/A |
| Common | same inputs | volume 500 | N/A |
| Fuse | same inputs | volume 1500, one solid | N/A |
| Multi cut | box minus two bars | volume 920, `<name>_tools` made, inputs hidden | N/A |
| Multi common | three solids, all overlap | intersection volume | N/A |
| Disjoint common | tool far away | rolled back, no object left | `RECOMPUTE_ERROR` `part_boolean.empty_result` |
| Cut removes all | tool larger than base | rolled back | `RECOMPUTE_ERROR` `part_boolean.empty_result` |
| Touching common | solids share a face | rolled back | `RECOMPUTE_ERROR` `part_boolean.empty_result` |
| Reversed input | solid with negative volume | none | `INVALID_INPUT` `part_boolean.untrusted_shape` |
| Invalid input | self-intersecting solid | none | `INVALID_INPUT` `part_boolean.untrusted_shape` |
| Sketch or shell input | sketch Name | none | `INVALID_INPUT` `part_boolean.untrusted_shape` |
| Body feature input | pad inside a Body | none | `INVALID_INPUT` `part_boolean.not_top_level` |
| Body as input | the Body Name | accepted | N/A |
| Too complex | inputs above a limit | none | `INVALID_INPUT` `part_boolean.too_complex` |
| Duplicate or unknown input | base in `tools`, bad Name, empty `tools`, 21 tools | none | `INVALID_INPUT` |
| Refine false | `refine` false | `Refine` false on every object made | N/A |
| Undo | `document_undo` after a boolean | result, `<name>_tools` and Visibility restored | N/A |
| Preview | `preview_dry_run` of each tool | geometry delta, live document unchanged | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/features.py:83` `_require_partdesign` (not called); `:226` `_name_available`; `:175` `_resolve_object`; `:343` `_feature_mutation` (add both tools after `feature_datum` `:1564` or after `feature_body_create` `:1653`); `:89`-`:125` quantity helpers.
- `src/freecad_buddy/usecases/queries.py:760` `_solid_volumes`, `:777` `_is_measurable_solid`: move both to a new `usecases/shape_trust.py` (two callers: `queries.py`, `features.py`); `queries.py` imports them.
- `src/freecad_buddy/usecases/documents.py` `CodedValidationError` and `adapters/rpc_dispatch.py` `_refusal_code` come from Story 13-9 (branch `story/13-9-varset-parameters`, not yet on `feat/epic-13-mcp-usage-improvement`): raise `CodedValidationError` from the prechecks. 13-9 must merge first.
- `src/freecad_buddy/usecases/transaction.py:610` `_bracket`, `:467` `_envelope`: new `RecomputeFailure(code, message)`; an op raising it ends `RECOMPUTE_ERROR` (`recompute_clean` false) and `_envelope` writes the op's `code` in `detail.code` instead of `mutation.recompute_error`.
- `src/freecad_buddy/hosts/tool_catalog.py:624`-`:790` `_feature_method`, `_feature_schema(…, conditional=("kind", {...}))` (as `feature_pattern`); `_LENGTH_QUANTITY_SCHEMA` (`:242`), `_ANGLE_QUANTITY_SCHEMA` (`:243`). `preview_op_table` (`:994`) picks the tools up with no edit.
- `docs/intent.md:254`; `mcp-tools-design.md` §2 `feature_` table (`:176-190`), counts (`:204-221`), §3.7 refusal list (`:549`) and a new §3.7.1.
- FreeCAD source (read): `Part/App/FeaturePartBoolean.cpp` (`Boolean::execute`, `Refine` default from `RefineModel`, `throwIfInvalidIfCheckModel`), `FeaturePartCommon.cpp` (`MultiCommon`, `BehaviorEnums`), `FeaturePartFuse.cpp` (`MultiFuse`, needs two shapes), `FeaturePartCut.cpp`, `PrimitiveFeature.cpp`, `FeaturePartBox.cpp`, `Part/Gui/ViewProviderBoolean.cpp`.
- Tests: `tests/infc/test_feature_part.py` (new, one test per matrix row), `tests/external/test_feature_contract.py:35` and `test_mcp_surface.py:102` add the names.
- Do not change: PartDesign tools, `shape_metrics`, skill files (Story 19 routes them).

## Tasks & Acceptance

**Execution:**
- [x] `shape_trust.py` -- move the two functions; `queries.py` imports them
- [x] `transaction.py` -- `RecomputeFailure` and the `detail.code` pass-through
- [x] `features.py` -- `_placement_value` (if 13-16 has not added it), `feature_part_primitive`, `feature_part_boolean`, trust, top-level and cost prechecks, empty-result check, visibility
- [x] `tool_catalog.py` -- two specs, schemas, descriptions
- [x] `docs/intent.md`, `mcp-tools-design.md` -- the edits listed under Design changes
- [x] tests -- infc per matrix row, fingerprint changes on create and returns on undo, dispatch test, catalog lists

**Acceptance Criteria:**
- Given a 10 cube and a cube shifted 5 mm, when cut, fused and common run, then volumes are 500, 1500 and 500 (analytic).
- Given disjoint solids, when common runs, then `RECOMPUTE_ERROR` `part_boolean.empty_result` and the document fingerprint equals the one before.
- Given a reversed or invalid solid, when any boolean runs, then `part_boolean.untrusted_shape`, never a number.
- Given the boolean is undone, when `document_undo` runs, then the result, the intermediate fuse and the input Visibility values are back.
- Given the gates of `epic-13-status.md`, when they run, then all pass.

## Design changes

**`docs/intent.md:254`, before:**
`**Specific.** Expose mutation tools (`sketch.*`, `feature.*`: create sketch, add geometry + constraints, pad, pocket, fillet, chamfer, hole, mirror, pattern). The AI maps …`
**after:**
`**Specific.** Expose mutation tools (`sketch.*`, `feature.*`: create sketch, add geometry + constraints, pad, pocket, fillet, chamfer, hole, mirror, pattern; and, for parts built by solid combination, Part primitives (box, cylinder, cone, sphere, torus) and Part booleans (cut, fuse, common)). The AI maps …`
The sentence after it, the exit criteria and the "8 operation types" benchmark stay unchanged.

**`mcp-tools-design.md` §2 `feature_` table, two rows after `feature_set_parameters`:**
`| `feature_part_primitive` | 2 | Part box/cylinder/cone/sphere/torus at document level, outside any Body; optional placement | yes |`
`| `feature_part_boolean` | 2 | Part cut/fuse/common of top-level solids; refuses untrusted or too-complex inputs, rolls back an empty result | yes |`

**Counts:** `feature_` P2 and Specified 11 → 13; Shipped 11 → 13; AI-visible total Specified 52 → 54, Shipped 47 → 49; "`tool_specs()` returns **47**; … that is 48" → "**49** … 50". Other Stories of Epic 13 change the same cells; the leader aligns the final numbers at merge.

**§3.7** refusal list gains a line for each tool; new §3.7.1 holds both input schemas, the limits with their measurements, and the visibility rule.

## Implementation Notes

Probes (FreeCAD 1.1.4 freecadcmd, private cfg, scratch `builder-13-17\p1.py`-`p7.py`):

- Primitives: box 10x20x30 volume 6000; cylinder r5 h10 785.398; cone 5/0/10 261.799; cone 5/2/10 408.407; sphere r5 523.599; torus 10/2 789.568; all analytic, `Valid`. Torus `radius2 > radius1` gives a null shape (`BRep_API: command not done`). Torus `radius1 == radius2` is valid (horn torus, volume 532.959): refused too, boundary cases are not measured for booleans. Cone 0/0 gives volume 0 and `isValid()` false. Zero or negative sizes fail the recompute with FreeCAD's own message ("Length of box too small"). Placement (1,2,3) + z 90 deg moves a 10x20x30 box to bbox (-19,2,3)-(1,12,33).
- Booleans: every result is a `Compound` (one solid inside it for one-solid results). `Refine` reads `True` by default here (preference default). `MultiFuse` with one shape fails ("Not enough shape objects linked"), so one tool uses `Part::Fuse`. `MultiCommon` of (b, c, far) is empty although `b common c` is 500, so `Behavior` `CommonOfAllShapes` is the intersection of all. Cut of a `MultiFuse` of two bars: 920 (analytic 920). Inputs stay `Visibility` true after a headless boolean.
- `post_verify` of an empty common returns `passed` true (`transaction.post_verify` run on `Part::Common` of disjoint boxes).
- Cost (whole call: recompute with refine + `post_verify` + two fingerprints + `saveCopy`; shared host, other processes running): box minus 1,000 disjoint cylinders (3,006 faces) 8.9 s; 2,000 cylinders (6,006 faces) 34 s, of which `post_verify` 20 s; common of a box and 1,000 overlapping spheres in one compound (1,006 faces) 7.3 s, 1,728 spheres 16.3 s, 2,744 spheres 31.9 s; common of two families of crossing cylinders, 30 x 30 (180 faces, 900 solid pairs) 13.4 s, 36 x 36 (216 faces, 1,296 pairs) 37.7 s, 45 x 45 (270 faces) 39 s (result 8,100 faces). Face count alone does not bound the cost (270 faces took 39 s), so the guard has two terms. Interleaved box compounds (two grids shifted 1.5 mm, each box overlaps four): cut 768 faces 2.4 s, 1,728 faces 8.3 s, 3,072 faces 22.4 s; common and fuse of the same inputs 1.2 to 5.7 s. Cut of the 36 x 36 crossing families 16.8 s. A `MultiFuse` of 20 separate cylinders and the cut of it by a plate: 0.04 s. A Body (Pad of a 10 cube) is a valid boolean input: cut by a bar gave 840 (analytic 840); a Body's sketch and pad report `getParentGeoFeatureGroup()` = the Body, a member of an `App::Part` reports the Part, a document-level box reports `None`; `Visibility = False` on a document-level object reads back False.
- Limits chosen: total input faces 3,000 (the `query_section` value, 3,006 faces took 8.9 s) and solid-pair product 1,000. Worst measured under both limits: about 22 s (interleaved box cut at 3,072 faces, just above the face limit), under the 120 s feature timeout. The bridge cannot interrupt a long OCC call (decisions 28 and 31), so the limit is on the input, not on time. `tools` at most 20.

## Open Questions

Each has a recommendation; answer only the ones you want to change.

1. **Empty result status.** `tool-contracts.md` T-9 says `RECOMPUTE_ERROR`, but an op that raises ends `SPEC_FAILED` today (`transaction.py:_bracket`). Recommend: keep the contract; add `RecomputeFailure(code, message)` to `transaction.py` (about 15 lines, also usable by 13-18 loft and sweep). Alternative: accept `SPEC_FAILED` and change T-9.
2. **Hide inputs.** Recommend yes (GUI does it; headless does not). Alternative: leave `Visibility` alone and document the GUI/headless difference.
3. **Torus `radius2 >= radius1`.** Recommend refuse (null shape or horn torus). Alternative: refuse only `>`.
4. **Several-tool cut makes an extra object `<name>_tools`.** Recommend yes (T-9 wording "cuts their fuse"; FreeCAD `Part::Cut` takes one tool). Alternative: refuse several tools for cut.
5. **Shared trust helper.** Recommend moving `_is_measurable_solid` to `usecases/shape_trust.py` (two callers). Alternative: import it from `queries.py` (private name across modules).
6. **Placement parser owner.** 13-16 is first in the plan; recommend it owns `_placement_value`, 13-17 reuses it. If 13-17 builds first, 13-17 adds it.
7. **Cost limits** (3,000 faces, 1,000 pairs, 20 tools) are measured above; recommend accept. Bridge recovery after a long OCC call stays deferred (AD-27).
8. **Merge order.** `CodedValidationError` is in 13-9. Recommend merge 13-9 before the 13-17 build starts.
