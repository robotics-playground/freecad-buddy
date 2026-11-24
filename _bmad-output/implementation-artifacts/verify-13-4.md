# Story 13-4: verification report

Artifact: commit `1bc4795` on `story/13-4-skill-routing-gap-list` (base `905e038`), worktree `freecad-buddy-wt-13-4`, read only.
Quality bar: `quality-bar-13-4.md`. Ledger row R1-U1 snippets: run in real FreeCAD (section "Snippet runs").

**Verdict: FAIL.** Q1 and Q5 fail on 4 wrong statements in the new skill text (D1-D4). One minor wording defect (D5). Q2, Q3, Q4, Q6, Q7, Q8 pass.

## Results per Q row

| Q | Result | Evidence |
| --- | --- | --- |
| Q1 | FAIL | Snippets no longer measure a document object's own volume, validity or solid count (6 hits → 0). New prose at `verification-kit.md:91-92` routes the volume and validity of an `App::Link` to `script_exec` because "a typed tool reads `obj.Shape`, which an `App::Link` lacks". That is false: both typed tools measure a link (D3). |
| Q2 | PASS | Every class in `usage-evidence.md` "What `script_exec` does" (17 rows), plus C-4 (multi-object export, ellipse/B-spline, linked copy), has a row in `gap-list.md` "Covered" or "Gaps". The traced-outline route (`gap-list.md:64-69`) and STEP import (`gap-list.md:40`, `:44-58`) are present. No class missing. Row accuracy: see Q5. |
| Q3 | PASS | `freecad-scripting-idioms/SKILL.md:78-79`: "Before each `script_exec` call, state the missing typed tool in one sentence." Also `gap-list.md:5-6`. |
| Q4 | PASS | `part-sourcing` has no "document/import path", "through the bridge" or "Phase-5" text: 9 hits at `905e038`, 0 at `1bc4795`. Import is a stated gap: `part-sourcing/SKILL.md:41-43`, `:73`. |
| Q5 | FAIL | 4 wrong claims about tools: D1, D2, D3, D4. Tool names and arguments: table below. |
| Q6 | PASS | `check_skill_shape.py` exit 0. Body words (checker method, after front matter): table below. |
| Q7 | PASS | `freecad-scripting-idioms/SKILL.md:54-65` is byte-equal at `905e038` and `1bc4795` (own-transaction rule). |
| Q8 | PASS | Old checks map to new checks: `valid` → `is_valid_solid`; `solids` → `expect_solid_count`; `diff_pct` → `expect_volume` with `tol.rel` 1e-6; `overlap_pct` kept in the script; per-case `Invalid` scan → `verify_recompute`; restore → separate restore script plus default equality re-run. Run in FreeCAD: each check still goes red on a bad part (section "Snippet runs"). |

## Defects

**D1 (Q5, high): `gap-list.md:28` says no typed tool sets a VarSet value.**
Quote: "Create a VarSet property, set a VarSet value, bind an expression | none (`feature_set_parameters` targets features)".
Code: `features.py:1815-1818` `_resolve_object(document, feature, "feature")` takes any object; `_parameter_value` (`features.py:1752`) writes any quantity, float, integer, boolean or enum property.
Run: `feature_set_parameters(feature="Params", parameters={"PLATE_T": {"value": 4.0, "unit": "mm"}})` on an `App::VarSet` → status `OK`, `PLATE_T` 5 → 4 mm, dependent box height 5 → 4.
What breaks: the agent scripts a VarSet value write that a typed tool does, and skips the transaction, audit and verify. The row also contradicts `freecad-scripting-idioms/SKILL.md:74-75` ("on any object") and `parametric-patterns/SKILL.md:88` (`plate_len` with `feature_set_parameters`).
Fix wording: "Create a VarSet property, bind an expression | none (`feature_set_parameters` sets the value of an existing VarSet property) | `addProperty`, `setExpression`". Add to "Covered": "Set an existing VarSet property value | `feature_set_parameters`".

**D2 (Q5, medium): `gap-list.md:29` says `query_object` cannot read a bound expression.**
Quote: "Read the expression bound to a property | none (`query_object` returns values only) | read `obj.ExpressionEngine`".
Code: `queries.py:554-557` reads every name in `PropertiesList`; `ExpressionEngine` is in that list.
Run: `query_object(object="Box")` → `properties.ExpressionEngine` = `[["Height", "Params.PLATE_T"]]`.
Fix wording: move the row to "Covered": "Read the expression bound to a property | `query_object` (`properties.ExpressionEngine`, pairs of property and expression)".

**D3 (Q1 and Q5, medium): `verification-kit.md:91-92` says typed tools cannot measure an `App::Link`.**
Quote: "A typed tool reads `obj.Shape`, which an `App::Link` lacks: for a link, take the shape with `Part.getShape(obj)` in the script and measure its volume and validity there."
Run (FreeCAD 1.1.4): `getattr(link, "Shape")` returns the linked solid with the link placement applied (`XMin` 100 for a link placed at x=100). `query_mass_properties(object="Lnk")` → `OK`, volume 1000 mm^3, `xmin` 100. `verify_shape(object="Lnk", checks=[is_valid_solid, expect_bbox])` → `OK`, passed. Overlap through `link.Shape` equals overlap through `Part.getShape(link)`.
What breaks: the text sends link volume and validity to `script_exec`, against Q1.
Fix wording: delete the sentence. If a link note is wanted: "A typed tool measures an `App::Link` like any object: `query_mass_properties` and `verify_shape` read the linked shape with the link placement."

**D4 (Q5, low): `gap-list.md:33` names `Lock` as a constraint type.**
Quote: "Sketch constraint outside the `sketch_add_constraint` types (for example `Lock`) | none | `sketch.addConstraint`".
Run: `Sketcher.Constraint("Lock", 0, 1, 0.0, 0.0)` and `Sketcher.Constraint("Lock", 0, 1)` → `TypeError: Invalid parameters`. `Lock` is a GUI command that adds `DistanceX` and `DistanceY` on one point; `sketch_add_constraint` takes both (single-point form).
What breaks: an agent scripts a constraint that does not exist, and scripts what the typed tool covers.
Fix wording: "(for example `InternalAlignment`, `AngleViaPoint`, `SnellsLaw`; a GUI Lock is `DistanceX` plus `DistanceY`, which `sketch_add_constraint` takes)".

**D5 (low, wording): `gap-list.md:60-61` says a container carries no shape.**
Quote: "A multi-body STEP creates a container: measure each leaf solid with `query_mass_properties`, because a container carries no shape."
Run: the multi-body import made an `App::Part` container with a shape (volume 238.097 = sum of both leaves); `query_mass_properties` on it returned `OK`. `result` also lists the container's `Origin`, 3 axes, 3 planes and a point; `query_mass_properties` on `Origin` raises `object has no queryable shape`.
Fix wording: "A multi-body STEP creates an `App::Part` container with its origin objects: measure each leaf `Part::Feature`, because the container shape is the sum of all leaves and the origin objects carry no solid."

## Commands and counts

| Check | Command | Result |
| --- | --- | --- |
| Shape | `uv run python scripts/check_skill_shape.py` (worktree) | exit 0, no output |
| Q1 API grep | `git grep -n -E 'isValid\(\|\.Volume\|BoundBox\|len\([a-zA-Z_.]*Solids\)\|\.Solids' <rev> -- skills/` | `905e038`: 11 hits; `1bc4795`: 7 hits |
| Q1 hits on a document object's own measure | same grep, minus reference-STEP volume (`ref.Volume`) and cross-object `common(...).Volume` | `905e038`: 6 (`verification-kit.md:74,75,76,78,140,141`); `1bc4795`: 0 |
| Q1 prose | `git grep -n -i -E 'bounding box\|bbox\|solid count\|validity\|isValid'` + `script_exec` lines, each read | one route to script: `verification-kit.md:91-92` (D3) |
| Q4 grep | `git grep -n -i 'import path\|document/import\|through the bridge\|Phase-5' <rev> -- skills/part-sourcing` | `905e038`: 9; `1bc4795`: 0 |
| `script_exec` mentions | `git grep -n script_exec <rev> -- skills/` | 14 → 24 (new gap list and routing text) |

Falsification (task 6): at `905e038` the Q1 grep shows 6 own-measure hits, for example `verification-kit.md:74` `"valid": shape.isValid(),` and `:140` `"valid": s.isValid(), "solids": len(s.Solids),`. The grep can go red.

Remaining `1bc4795` API hits, judged:

| Hit | Measures | Judgment |
| --- | --- | --- |
| `verification-kit.md:75-76`, `:155-156` | `ref.Volume` (reference STEP, not a document object), `common(ref).Volume` overlap | allowed: no typed tool reads a file or overlap |
| `verification-kit.md:187` | `a.common(b).Volume` interference | allowed: cross-object (gap row 36) |
| `verification-kit.md:198` | hole-probe `common(c).Volume` | unchanged text; out of Q1 scope. Note: `verify_shape` `hole_diameter` may cover part of it; not judged here |
| `gap-list.md:36` | gap row for cross-object measure | allowed |

Body word counts (checker method):

| Skill | `905e038` | `1bc4795` | Cap |
| --- | --- | --- | --- |
| `code-cad-conversion` | 1,416 | 1,424 | 1,500 |
| `freecad-scripting-idioms` | 1,292 | 1,310 | 1,500 |
| `part-sourcing` | 845 | 862 | 1,500 |

## Q5: tool names and arguments in changed text

Checked against `tool_specs()` input schemas (`hosts/tool_catalog.py`) and usecase code.

| Text | Claim | Result |
| --- | --- | --- |
| `query_mass_properties` (one `object` per call) | schema `doc`, `object` (required) | PASS |
| `query_mass_properties`: bbox, volume, area, centre of mass, solid count | `queries.py:584-610`; `counts.solids` | PASS |
| `verify_shape` `checks` items `{"fn", "expect"}`, `object` | schema `object`, `checks`; `verify.py:248-252` | PASS |
| `is_valid_solid` `expect: true` | `assertions.py:67`, `:196` (bool) | PASS |
| `expect_solid_count` `expect: 1` | `verify.py:185`, `:142` | PASS |
| `expect_volume` `tol: {"rel": 1e-6}`; default 0.01 | `assertions.py:77`, `:33` `_DEFAULT_VOLUME_REL = 0.01`, `_band` | PASS |
| Covered row: watertight, bbox, extent, hole count, diameter, position, spacing, distance, angle | `expect_watertight`, `expect_bbox`, `expect_extent`, `count_cylindrical_holes`, `hole_diameter`, `hole_position`, `hole_spacing`, `distance_between`, `angle_between` | PASS |
| `verify_recompute` for failing objects | schema `doc`; run returns `failing_objects` | PASS |
| `query_object`, `query_placement`, `query_sketch_info`, `query_dependencies` | in `tool_specs()` | PASS |
| `sketch_*`, `feature_*` covered operations (body, pad, pocket, hole, fillet, chamfer, revolve, pattern, mirror, datum) | all present | PASS |
| `feature_set_parameters` refuses `App::PropertyPlacement` | `features.py:1767`; usage-evidence failure row | PASS |
| `feature_set_parameters` cannot set a VarSet value (`gap-list.md:28`) | run: it can | FAIL (D1) |
| `query_object` returns values only (`gap-list.md:29`) | returns `ExpressionEngine` | FAIL (D2) |
| `sketch_add_geometry` takes line, circle, arc, point | enum `line_segment`, `circle`, `arc_of_circle`, `point` | PASS |
| `sketch_add_constraint` types; `Lock` outside them | `Lock` is not a Sketcher type | FAIL (D4) |
| `export_*` take one object | `exports.py:83-105` raises on more than one | PASS |
| Groove has no typed tool | no `Groove` in `src/`; `feature_revolve` is additive | PASS |
| `query_capabilities` `exec_enabled` | `contracts/capabilities.py:17` | PASS |
| `verify_sketch`, `document_save`, `query_screenshot` | in `tool_specs()` | PASS |
| Typed tools cannot measure `App::Link` (`verification-kit.md:91`) | run: they can | FAIL (D3) |

## Snippet runs

Host `freecadcmd.exe` 1.1.4, private temp `user.cfg`/`system.cfg`. Usecases imported from the worktree `src` (confirmed `freecad_buddy.__file__`). Snippets extracted verbatim from the committed files; only placeholder paths replaced. Each snippet ran through the real `script_exec` usecase. Fixture: `App::VarSet` `Params.PLATE_T` = 5 mm; `Part::Box` labelled `bracket`, 60 × 40, `Height` bound to `Params.PLATE_T`; reference STEPs written by `Part.makeBox`.

| Snippet | Result |
| --- | --- |
| `verification-kit.md` part-equality (block 2) + `verify_shape` JSON (block 3), default ref | ran. `overlap_pct` 100.0, `ref_vol` 12000; checks `is_valid_solid` true, `solid_count` 1, `expect_volume` pass |
| same, reference shifted 1 mm | ran. `overlap_pct` 98.3333; `verify_shape` still passes, so only overlap catches the shift (matches text) |
| `expect_volume` with ref volume +0.01 % | `rel` 1e-6: fail (correct); default tol: pass (matches "too wide") |
| case script (block 5), T3 | ran. `{'case': 'T3', 'old': {'PLATE_T': 5.0 mm}, 'parts': [{'name': 'Box', 'ref_vol': 7200.0, 'overlap_pct': 100.0}]}`; part left at 3 mm |
| then `verify_recompute` + `verify_shape` (T3 `ref_vol`) | `OK`, `failing_objects` []; all 3 checks pass |
| restore script (block 6) | ran. `PLATE_T` back to 5 mm; default equality re-run: overlap 100.0, checks pass |
| case script, missing reference file | raised `File to load not existing or not readable`; values restored (`PLATE_T` 5 mm, height 5) |
| `gap-list.md` STEP import script, single body | ran. 1 new `Part::Feature`, volume 339.292; `query_mass_properties` `OK` |
| same, two-body STEP | ran. 2 leaf `Part::Feature` + `App::Part` container (has a shape) + `Origin` and 7 origin objects (D5) |
| `body.newObject("PartDesign::AdditiveBox")` | ran, `TypeId` `PartDesign::AdditiveBox`, volume 1000 |
| `body.newObject("PartDesign::Groove")` | ran, `TypeId` `PartDesign::Groove` (recompute error "No profile linked" is expected without a profile) |
| delete route `body.removeObject(f)` then `doc.removeObject(f.Name)` | ran. Next feature `BaseFeature` relinked `Grv` → `ABox`; object gone |
| `Sketcher.Constraint("Lock", ...)` | failed: `TypeError: Invalid parameters` (D4). `Block` accepted |
| `shape.slice(Vector(0,0,1), 2.0)` | ran, 1 wire |
| `Import.export([a, b], path)` (multi-object export row) | ran, 10,284-byte STEP |
| `feature_set_parameters` on a VarSet (R1-U1) | `OK`, value written (D1) |
| `query_object` on an expression-bound object | `ExpressionEngine` returned (D2) |
| `App::Link`: `query_mass_properties`, `verify_shape`, `link.Shape` with link placement | all work (D3) |

Not run: `verification-kit.md` block 1 (re-export, runs outside FreeCAD, unchanged), block 4 (coverage, unchanged), blocks 7-8 (interference, hole probe, unchanged). Snippets ran under `freecadcmd`, not under the GUI bridge; the GUI path calls the same usecases.

## Unverified

- Live agent behaviour (CAP-6) is batched with Story 13-12 / 13-19, per the quality bar.
- `Import.insert` under the GUI can differ from `freecadcmd` in container naming; not run in the GUI.

## Round 2

Head: `5782fee` (commits `14c2e7b`, `0f1d1f6`, `e9cf5bd`, `bb335fd`, `5782fee` on top of `1bc4795`). Worktree clean. Triage: `triage-13-4-r2.md`.

**Verdict round 2: PASS.** All 8 triage rows closed. Q1-Q8 pass. One low wording note (N1), not blocking.

### Triage rows

| Id | Status | Evidence at `5782fee` |
| --- | --- | --- |
| D3 = RT1 | closed | `verification-kit.md:79-81`: `verify_shape` on the link Name, "the placement is applied". Script route and false reason removed (no `Part.getShape` left in `skills/`). Run: with `LinkTransform` false and true, `query_mass_properties` `xmin` = `link.Shape` = `Part.getShape` (100 and 110); `verify_shape` `is_valid_solid` and `expect_volume` (rel 1e-6) pass. |
| D1 | closed | `gap-list.md:20` covered row: `feature_set_parameters` on any object (feature, VarSet, `Visibility`). `gap-list.md:29` gap keeps only create VarSet, add property, bind expression. Run: VarSet `PLATE_T` 5 → 4 → 6 mm, `OK`; `Visibility` false, `OK`. |
| D2 = RT2 | closed | `gap-list.md:16`: `query_object` reads bound expressions (`ExpressionEngine`). Round-1 run: `[["Height", "Params.PLATE_T"]]`. |
| D4 = RT3 | closed | `gap-list.md:18` covered: fixed point by `DistanceX` plus `DistanceY`. Run: `sketch_add_constraint` single-point `DistanceX` 2 + `DistanceY` 3 on a point → `OK`, point at (2, 3), DoF 0. `gap-list.md:33` examples `InternalAlignment`, `TangentViaPoint`: typed tool rejects both (`type must be one of [...]`); `Sketcher.Constraint("TangentViaPoint", 0, 1, 2, 1)` builds (`Type` `Tangent`, `Third` 2). |
| D5 | closed | `gap-list.md:61-64`: `App::Part` container by default, its shape is the sum of the leaves, measure each leaf. Round-1 run: container volume 238.097 = 125 + 113.097. Import options `merge` and `useLinkGroup` exist (`ImportOCAF2.h:88-91`). See N1. |
| RT-L1 | closed | `gap-list.md:7`, `part-sourcing/SKILL.md:45-46`, `code-cad-conversion/SKILL.md:31-32` all send `exec_enabled: false` to the headless route of `freecad-scripting-idioms/SKILL.md:85-92`. Same action in every place. |
| RT-L2 | closed | `git grep references/ 5782fee -- skills/part-sourcing`: 0 hits. Text names the skill: "a gap in `freecad-scripting-idioms`, whose gap list holds the import script" (`part-sourcing/SKILL.md:42-43`). |
| RT-L3 | closed | `check_skill_shape.py:36-58` skips lines inside a backtick or tilde fence; closes only on the same character, at least as long, no info string. Tests below. |

### Quality bar again

| Q | Result | Evidence |
| --- | --- | --- |
| Q1 | PASS | API grep at `5782fee`: 7 hits, all reference-STEP volume, overlap or cross-object (`verification-kit.md:75-76,154-155,186,197`; `gap-list.md:37`). Own-measure hits: 0. No prose route of bbox, volume, validity or solid count to `script_exec` (link route removed). |
| Q2 | PASS | All usage-evidence classes still have a row; VarSet value and expression read moved to covered, which matches the code. |
| Q3 | PASS | `freecad-scripting-idioms/SKILL.md:78-79`, `gap-list.md:5-6` unchanged in meaning. |
| Q4 | PASS | Import-path grep: 0 hits. Import stated as a gap. |
| Q5 | PASS | New claims run in FreeCAD (table below). |
| Q6 | PASS | `check_skill_shape.py` exit 0. Body words: `code-cad-conversion` 1,423; `freecad-scripting-idioms` 1,310; `part-sourcing` 872. |
| Q7 | PASS | `freecad-scripting-idioms/SKILL.md:54-65` byte-equal to `905e038`; file not changed in round 2. |
| Q8 | PASS | Snippet code blocks not changed in round 2; only prose at `verification-kit.md:79-81, 89-93`. |

### Q5: new claims, run in host `freecadcmd` 1.1.4 (private temp cfg, worktree `src` imported)

| Claim | Location | Run | Result |
| --- | --- | --- | --- |
| `feature_set_parameters` writes a VarSet property | `gap-list.md:20` | `PLATE_T` → 6 mm, `OK` | PASS |
| writes `Visibility` | `gap-list.md:20` | `{"Visibility": false}` → `OK`, value false | PASS |
| expression-driven property reset on recompute | `gap-list.md:20` | `Box.Height` (bound to `Params.PLATE_T`) set 8 mm → `OK`; after recompute 5 mm | PASS |
| lengths in mm, angles in degrees | `gap-list.md:20` | code: `_length_mm`, `_angle_degrees` (`features.py:1770-1772`) | PASS (code) |
| refuses string and link properties | `gap-list.md:34` | `Label` → `App::PropertyString ... cannot write`; `LinkedObject` → `App::PropertyXLink ... cannot write` | PASS |
| `query_object` returns `ExpressionEngine` | `gap-list.md:16` | round-1 run | PASS |
| fixed point by `DistanceX` + `DistanceY` | `gap-list.md:18` | `OK`, DoF 0 | PASS |
| `InternalAlignment`, `TangentViaPoint` outside typed types | `gap-list.md:33` | typed tool rejects both; Python constructor accepts `TangentViaPoint` | PASS |
| `App::Link` through `query_mass_properties` / `verify_shape`, placement applied | `verification-kit.md:79-81` | `LinkTransform` false and true | PASS |
| no typed tool creates a VarSet property or binds an expression | `code-cad-conversion/SKILL.md:31-32` | `tool_specs()`: no such tool | PASS |

Product note, outside this Story (skill text not affected): `sketch_add_constraint` rolls back any call that leaves the sketch with DoF > 0 (`SPEC_FAILED`, `verify_sketch failed ... sketch.fully_constrained`), so a lock on one point of a line with free DoF is refused. `_THIRD_TYPES` (`sketches.py:55`) admits `third` on `Tangent`/`Perpendicular`, but `_constraint_args` (`sketches.py:357-375`) returns without it; not run.

### RT-L3: `check_skill_shape.py`

| Step | Result |
| --- | --- |
| `uv run pytest tests/external/test_check_skill_shape.py -q` | 15 passed |
| Mutation 1 (scratch copy): remove `and fence is None` from the heading test | 3 failed (backtick fence, tilde fence, longer fence) |
| Mutation 2 (scratch copy): `_closes_fence` ignores fence length | 1 failed (`test_should_keep_a_fence_open_when_a_shorter_fence_line_appears_inside_it`) |
| Checker at `1bc4795` and at `5782fee` over all 16 skills | both exit 0, no output: no skill changed from pass to fail |
| `## ` lines inside fences in any `SKILL.md` | 0 |

### Note

**N1 (low, not blocking):** `gap-list.md:62` "`result` also lists `Origin` objects, which carry no shape". Round-1 run: `Origin` (`App::Origin`) has no shape (`query_mass_properties` raises), but its axes, planes and point carry a non-null shape with no solid (`query_mass_properties` `OK`, volume null). Possible wording: "which carry no solid".
