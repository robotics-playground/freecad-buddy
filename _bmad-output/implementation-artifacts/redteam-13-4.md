# Story 13-4: red team report

Diff: `905e038...1bc4795` (branch `story/13-4-skill-routing-gap-list`, worktree `freecad-buddy-wt-13-4`), read only.
Quality bar: `quality-bar-13-4.md`. Ledger items R1-* and R1-U1 are not re-reported.

Reproduction setup. FreeCAD runs: host `"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -u <scratch>\user.cfg -s <scratch>\system.cfg <script>` (FreeCAD 1.1.4). Each script puts the worktree `src` first on `sys.path`, drops cached `freecad_buddy` modules, and prints `freecad_buddy.__file__` = `D:\Work\Personal\Sources\freecad-buddy-wt-13-4\src\freecad_buddy\__init__.py`. The scripts call the usecases the MCP tools dispatch to (`queries.query_object`, `queries.query_mass_properties`, `verify.verify_shape`, `verify.verify_recompute`) through a `DocumentRegistry`. Scratch files are deleted.

## Reproduced

### RT1 (high, Q1): the kit routes the validity and volume of an `App::Link` to `script_exec`, but the typed tools measure a link

- File: `skills/code-cad-conversion/references/verification-kit.md:91-92` (added by this Story):
  > A typed tool reads `obj.Shape`, which an `App::Link` lacks: for a link, take the shape
  > with `Part.getShape(obj)` in the script and measure its volume and validity there.
- Q1 forbids skill text that routes volume or validity of a document object to `script_exec`. The claim behind the route is false in FreeCAD 1.1.4.
- Reproduction: Body with `PartDesign::AdditiveBox` 20×10×5, `App::Link` `Link` to the Body, link placement x=100, `doc.recompute()`, then:
  ```python
  queries.query_mass_properties(reg, doc=h, object="Link")
  verify.verify_shape(reg, doc=h, object="Link", checks=[
      {"fn": "is_valid_solid", "expect": True}, {"fn": "expect_solid_count", "expect": 1},
      {"fn": "expect_volume", "expect": 1000.0, "tol": {"rel": 1e-6}}])
  ```
- Output:
  ```
  "Shape_in_PropertiesList": false, "link_Shape_vol": 999.9999999999998,
  "getShape_vol": 999.9999999999998, "link_Shape_bbox_xmin": 100.0,
  "qmp_status": "OK", "qmp_volume": {"value": 999.9999999999998, "unit": "mm^3"},
  "verify_shape": ["OK", ["assert.is_valid_solid", true, true],
                   ["shape.solid_count", true, 1], ["assert.expect_volume", true, 999.9999999999998]]
  ```
  `Shape` is not in the link's `PropertiesList`, but `getattr(link, "Shape")` returns the placed shape. `verify_shape` and `query_mass_properties` both measure it. A link to a `Part::Box` gave the same result (`link_verify: "OK"`).
- Proposed fix: delete the link sentence (lines 91-92 from "A typed tool reads" to "validity there."). Links go through the same `verify_shape` call as any part. Keep `Part.getShape` only inside the overlap script, if the script must handle a link at all; `link.Shape.common(ref)` also works.

### RT2 (medium, Q2/Q5): gap-list row says no typed tool reads a bound expression; `query_object` returns it

- File: `skills/freecad-scripting-idioms/references/gap-list.md:29`:
  > `| Read the expression bound to a property | none (`query_object` returns values only) | read `obj.ExpressionEngine` |`
- `usage-evidence.md` classes table also says "Property or expression read | `query_object` (partly)".
- Reproduction: VarSet `Params` with `PLATE_T` 5.0, `Part::Box` with `setExpression("Height", "Params.PLATE_T")`, recompute, then `queries.query_object(reg, doc=h, object="Box")`.
- Output:
  ```
  "A_status": "OK",
  "A_ExpressionEngine": [["Height", "Params.PLATE_T"]]
  ```
  `query_object` reads every name in `PropertiesList` (`usecases/queries.py:553-557`), and `ExpressionEngine` is in it. The row sends the agent to `script_exec` for a covered read. The SKILL anti-pattern "`script_exec` where a typed tool exists" (`SKILL.md:120`) then applies to the agent that follows the gap list.
- Proposed fix: delete the row. Add to the covered table: "Read property values and bound expressions | `query_object` (`properties.ExpressionEngine` lists `[path, expression]` pairs)".

### RT3 (medium, Q2/Q5): gap-list example `Lock` is not a FreeCAD constraint type; the shown script fails

- File: `skills/freecad-scripting-idioms/references/gap-list.md:33`:
  > `| Sketch constraint outside the `sketch_add_constraint` types (for example `Lock`) | none | `sketch.addConstraint` |`
- Reproduction: sketch with one line, then `Sketcher.Constraint("Lock", 0, 1, 1.0, 2.0)` and `Sketcher.Constraint("Lock", 0, 1)`.
- Output:
  ```
  TypeError: Invalid parameters: ('Lock', 0, 1, 1.0, 2.0)
  Constraint constructor accepts: -- empty parameter list -- Constraint type and index
  TypeError: Invalid parameters: ('Lock', 0, 1)
  ```
  FreeCAD source `src/Mod/Sketcher/App/ConstraintPyImp.cpp` has no `"Lock"` type string. The GUI Lock command makes a `DistanceX` and a `DistanceY` constraint. Both are in the `sketch_add_constraint` enum (`tool_catalog.py`). So the example sends a covered operation to `script_exec`, and the script raises.
- Proposed fix: change the example to a type that is outside the enum and accepted by `Sketcher.Constraint`: `Weight`, `SnellsLaw`, `InternalAlignment`, `TangentViaPoint`, `PerpendicularViaPoint`. Add one sentence: a lock is `DistanceX` plus `DistanceY` with `sketch_add_constraint`.

### RT4 (low): two skill texts give different actions when `script_exec` is off

- `skills/freecad-scripting-idioms/references/gap-list.md:6-7`: "When `query_capabilities` reports `exec_enabled: false`, report the operation as blocked."
- `skills/part-sourcing/SKILL.md:44-45`: "If `query_capabilities` reports `exec_enabled: false`, report the import as blocked."
- `skills/freecad-scripting-idioms/SKILL.md:88-93`: "Only when `script_exec` is absent (`query_capabilities` reports `exec_enabled: false`), use a **headless script on the closed document**: close it in the GUI, edit and save with `freecadcmd`, reopen with `document_open` ..."
- One case gives two actions: stop, or run a headless edit. Proposed fix: make the gap list and `part-sourcing` say "use the headless route in `freecad-scripting-idioms` (closed document)", or change `SKILL.md:88-93` to "report as blocked". The owner picks one.

### RT5 (low, AD-15): `part-sourcing` body points into another skill's `references/`

- `skills/part-sourcing/SKILL.md:41-43`: "(a gap in `freecad-scripting-idioms` `references/gap-list.md`, which holds the import script)".
- AD-15 (`ARCHITECTURE-SPINE.md:160`): "a body never imports or `references/`-links into another skill's directory". A prose mention of a sibling skill is allowed, but here the import step depends on a script that exists only in the sibling's `references/`. With `freecad-scripting-idioms` removed (the ablation mode in AD-15), `part-sourcing` has no import route. No other `SKILL.md` body does this (grep for `references/` with another skill's name: one hit, this line).
- Proposed fix: name the skill only ("the gap list in `freecad-scripting-idioms`"), or put the short import script in `part-sourcing/references/`.

### RT6 (low, Q6 check method, pre-existing): `check_skill_shape.py` counts H2 lines inside a code fence

- `scripts/check_skill_shape.py:36-41` treats every line that starts with `## ` as a section heading, also inside ```` ``` ```` fences.
- Reproduction: a temp `skills/fake/SKILL.md` with only prose in the body and the four headings inside a ```` ```markdown ```` fence. `uv run python scripts/check_skill_shape.py <tmp>/skills` → no output, `exit=0`.
- No current skill is affected: the four edited `SKILL.md` files have the four real headings, body words 1424 (`code-cad-conversion`), 1310 (`freecad-scripting-idioms`), 862 (`part-sourcing`), 1494 (`verification-thinking`). The real run gives `exit=0`. Proposed fix (separate change): skip lines inside fences in `_sections`.

### RT7 (low, Q5, pre-existing, outside this Story): `urdf-export` and `sdf-export` name tools that do not exist

- A scan of every backticked `query_|verify_|feature_|sketch_|document_|export_|view_|preview_|script_` name in `skills/**/*.md` against `tool_specs()` plus `SCRIPT_EXEC_SPEC` finds: `export_urdf`, `verify_export_urdf` (`skills/urdf-export/SKILL.md:25-26, 84`), `export_sdf`, `verify_export_sdf` (`skills/sdf-export/SKILL.md:26-27, 82`). (`sketch_state` is a result field, not a tool.)
- These skills say "Phase-5 capabilities", the same wording this Story removed from `part-sourcing`. T-1 lists only `part-sourcing`, so this is outside the Story. Record it for a later Story.

## Not reproduced

- `expect_volume` with `tol.rel` 1e-6 loosened by display rounding (`displayed_deviation`, 2 decimals): refuted. Pin radius 1.5001 against a 1.5 reference (true diff 0.0133 %, overlap 100.0) gave `assert.expect_volume` false, message `|35.35 - 35.34| = 0.00471 <= 3.53429e-05 mm^3`. The kit's volume check catches extra material that the overlap misses.
- Verification-kit snippets (Q8): ran the equality snippet, the case script (`T3`), `verify_recompute`, `verify_shape` with the returned `name`/`ref_vol`, and the restore script. Then a case with a missing reference STEP. Output: equality `OK`, case `T3` recompute `OK` and verify `OK`, `after_restore_PLATE_T` 5.0, failed case raises `RuntimeError: ... File to load not existing or not readable` and leaves `PLATE_T` 5.0, equality after restore `overlap_pct` 100.0. No lost check, no value left set, no failing restore found.
- Q5 shown calls: `query_mass_properties` takes `doc`, `object`. `verify_shape` takes `doc`, `object`, `checks`, `anchor_frame`. `is_valid_solid`, `expect_volume` (`tol` `{rel}`) pass `assertions.validate_check`. `expect_solid_count` is handled in `usecases/verify.py:184-188`. `verify_recompute` takes `doc`. `verify_sketch` takes `doc`, `sketch`. `query_capabilities` reports `exec_enabled`. Multi-object export gap is true: `exports.py:91-93` refuses more than one name.
- Q7: the diff does not touch `freecad-scripting-idioms/SKILL.md` lines 50-72; the own-transaction rule at line 57 is unchanged.
- Q4: `part-sourcing` no longer names the "document/import path". Grep for `import path|document_import|import_step|through the bridge` in `skills/` finds only `build123d.import_step` (a build123d call) and the new gap statement.

## Verdict

FAIL. One reproduced high (RT1, Q1) and two reproduced mediums (RT2, RT3).
