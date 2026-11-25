# Red team: Story 13-12 (skill routing to measure, parameter and delete tools)

Diff: `04574455...4333288b` on `story/13-12-skill-routing-measure`. Copy: detached worktree at `4333288b` (removed after the run).
Runs: host `freecadcmd.exe` 1.1.4 with private `-u`/`-s` cfg and `FREECAD_USER_HOME` in a temp folder; the probes import the worktree `src` (first line of each probe prints the package path, `fcb-redteam-13-12/src`). Probe scripts and outputs: `scratchpad\redteam-13-12\probe1.py` .. `probe3.py`, `probe*.out`, `schema_check.py`.

## Reproduced

### RT-1 — high — Q5 — the kit sends an unmeasured contact to a script that reads the same empty boolean as zero

`skills/code-cad-conversion/references/verification-kit.md:183-191`:

> Pass: `common_volume` at most 0.05 mm3 and `boolean_failed` false. `boolean_failed` true is unmeasured, not zero. With it true and `min_distance` 0 the parts touch, and the tool cannot tell contact from overlap: no typed tool measures that, so use the script below.
> `result = round(a.common(b).Volume, 3)    # pass: <= 0.05 mm3`

The script runs the same `Shape.common` as the tool. When `common` returns an empty shape, the tool reports `boolean_failed: true` (decisions 24 and 26: "an empty result must never read as no overlap"). The script reads the same empty shape as volume 0 and passes it. The script cannot tell contact from overlap either. The kit turns an unmeasured result into a pass.

Reproduction (`probe1.py`): box A 10x10x10 at the origin, a second box touching it on a face, an edge, a vertex and part of a face. For each pair, call `query_interference` `pairs: [["A", other]]`, then run the kit script on the same shapes.

```
INTERF FaceTouch   {"common_volume": null, "min_distance": {"value": 0.0}, "boolean_failed": true} | kit script common: 0.0
INTERF EdgeTouch   {"common_volume": null, "min_distance": {"value": 0.0}, "boolean_failed": true} | kit script common: 0.0
INTERF VertTouch   {"common_volume": null, "min_distance": {"value": 0.0}, "boolean_failed": true} | kit script common: 0.0
INTERF PartialFace {"common_volume": null, "min_distance": {"value": 0.0}, "boolean_failed": true} | kit script common: 0.0
INTERF Overlap     {"common_volume": {"value": 500.0}, "boolean_failed": false}                     | kit script common: 500.0
```

The script adds no information over the tool. On every pair where the tool says "unmeasured", it says 0.

Proposed fix: delete the script route for this case. State the literal reading: `boolean_failed` true with `min_distance` 0 and both shapes valid (`verify_shape` `is_valid_solid`) means "the parts touch; the overlap is unmeasured". Report the pair as unmeasured, never as a pass. If the spec needs a number, measure a modified pair (for example, move one part 0.01 mm away with the placement gap route, then measure `min_distance`), or report the check as not run. Also remove "contact between touching parts" from the script list at `verification-kit.md:9`.

### RT-2 — high — Q3 — the gap list declares "Delete" covered, but deleting one feature from the middle of a Body is still a gap; the route deletes every later feature

`skills/freecad-scripting-idioms/references/gap-list.md:22`:

> | Delete objects, with or without the objects that depend on them | `document_object_delete` (`objects`, `with_dependents`) |

The diff removes the old route from the gap list and from `freecad-scripting-idioms/SKILL.md:89` (`body.removeObject(feature)` "relinks the next feature's `BaseFeature`"). `document_object_delete` counts the next feature in the Body as a dependent (its `OutList` holds the deleted feature through `BaseFeature`). It refuses the call, and its message tells the agent to pass `with_dependents` true. That deletes the next feature and every feature after it.

Reproduction (`probe3.py`): Body with `Box1`, `Box2`, `Cyl3` (PartDesign additive primitives). Delete `Box2`:

```
DELETE Box2 default         {"exc": "ObjectDeleteRefusal", "code": "delete.has_dependents",
                             "msg": "objects that depend on the delete set: Cyl3; pass with_dependents true to delete them too"}
DELETE Box2 with_dependents {"status": "OK", "sc": {"deleted": ["Box2", "Cyl3"], "dependents": ["Cyl3"]}}
after: group ['Box1'] body vol 1000.0
old script route: group ['Box1', 'Cyl3'] Cyl3.BaseFeature Box1 body vol 1345.58
```

The removed script route keeps `Cyl3` and relinks it to `Box1`. The typed route cannot do that. An agent that follows the gap list and the refusal message loses every later feature. `document_undo` can restore them, but only if the agent sees the loss.

Proposed fix: keep a gap row: "Remove one feature from the middle of a Body and keep the later features | none (`document_object_delete` deletes them as dependents) | `body.removeObject(feature)` (relinks the next `BaseFeature`), then `doc.removeObject(feature.Name)`". Narrow the covered row to "Delete objects that nothing else depends on, or delete them together with their dependents". Add one line: before `with_dependents` true, read the `delete.has_dependents` list, and stop if it names a feature the user wants to keep.

### RT-3 — medium — Q5 — touching parts: the skill example is a pair that always gives `boolean_failed`, and the reference sends the agent to look for a broken shape

`skills/verification-thinking/SKILL.md:62-66` uses `query_interference` `{"objects": ["Housing", "Lid"]}`. A lid that sits on a housing touches it on a face. RT-1 shows that face contact gives `boolean_failed: true`, `min_distance` 0. The reference `skills/verification-thinking/references/measuring-clearance-and-sections.md:26-27` says:

> When `boolean_failed` is true, run `verify_shape` on each shape (`is_valid_solid`, `expect_solid_count`) to find which shape is broken before you report a clearance.

For two valid touching solids nothing is broken. The guidance then has no next step and no reading to report. Table line 20 says "Solids that only touch can give this", but the fix line ignores that case.

Reproduction: the `FaceTouch` and `PartialFace` rows of RT-1 (valid boxes, `boolean_failed` true, `min_distance` 0).

Proposed fix: split the fix line. `min_distance` null → a shape is not a valid solid: run `verify_shape`. `min_distance` 0 and both shapes valid → the parts touch, the overlap is unmeasured: report "touching, overlap unmeasured" (see RT-1 for the optional offset measurement).

### RT-4 — medium — Q1 — the code-cad generator still creates the VarSet, binds expressions and deletes objects with `script_exec`, with no stated exemption

`skills/code-cad-conversion/references/generator-kit.md:17-19` (stage `params` deletes every object with `doc.removeObject`), `:89-124` (`doc.addObject("App::VarSet", ...)`, `V.addProperty("App::PropertyFloat" | "App::PropertyBool" | ...)`, `V.setExpression`), `:136` (`o.setExpression(prop, ...)`). `skills/code-cad-conversion/SKILL.md:44-49` routes this stage to `script_exec`: "split into stages (parameters, then one part per call)".

Q1 says that no `skills/**` text routes VarSet create/write, expression bind or delete to `script_exec`. The `params` stage creates only float, bool and enumeration properties. `feature_parameters_define` covers float and bool, and `feature_set_expression` covers the derived values. Only the enumeration property is a gap. The gap list (`gap-list.md:35`) names only that gap and gives no exemption for a generator script.

Reproduction: `grep -n "removeObject\|addProperty\|setExpression\|App::VarSet" skills/code-cad-conversion/references/generator-kit.md` → lines 19, 92, 102, 104, 114, 122, 136.

Proposed fix: choose one route and write it down. Either (a) record in `gap-list.md` that a generator which builds Part primitives (a gap) can create its own VarSet variables and bindings in the same script, with the reason (one call per stage, under the 30 s budget), or (b) move the `params` stage to `feature_parameters_define` (float/bool) and `script_exec` only for enumerations.

### RT-5 — medium — AD-15 — `parametric-patterns` points into another skill's `references/` directory

`skills/parametric-patterns/SKILL.md:55-56`:

> Creating an enumeration property and writing spreadsheet cells have no typed tool: `freecad-scripting-idioms` `references/gap-list.md` names the `script_exec` route.

`skills-structure-design.md:46`: "a body may point to its **own** `references/` files by relative path, never to another skill's directory (AD-15 ...)". This line is new in the diff. Read relative to the skill, `skills/parametric-patterns/references/gap-list.md` does not exist.

Reproduction: for every `references/<file>` path in each `SKILL.md`, test that the file exists under that skill. The only missing path in the tree is `MISSING parametric-patterns: references/gap-list.md :: 56`. The same check on base `04574455` finds none.

Proposed fix: name the sibling skill in prose only, for example "`freecad-scripting-idioms` names the `script_exec` route".

### RT-6 — medium — Q2 — `urdf-export` still says `query_mass_properties` returns mass and the inertia tensor

The diff changes the worked example `skills/urdf-export/SKILL.md:77`: "volume and COM (the tool returns no mass or inertia: take mass from the material density)". The Decision Rule in the same file, `skills/urdf-export/SKILL.md:42-43`, still says:

> Compute each link's `<inertial>` from FreeCAD's **native mass properties** (`query_mass_properties` gives mass, center of mass, and the inertia tensor)

The tool result has no mass and no inertia. Record keys from `probe1`/`probe3`: `name, solid, volume, area, bbox, com, counts, is_valid`. An agent that reads the rule expects an inertia tensor that never comes. `sdf-export/SKILL.md:51-52` ("Compute inertials from FreeCAD's native mass properties (`query_mass_properties`)") gives the same impression.

Proposed fix: make `urdf-export:43` match `:77`, and state that no tool returns the inertia tensor. Then the agent must compute it (for example with `script_exec` `Shape.MatrixOfInertia`, a gap row) or report it as approximated.

### RT-7 — low — Q5 — the `section.plane_on_face` fix "1e-6 mm" is refused again on a shape with a larger face tolerance

`skills/verification-thinking/SKILL.md:69-70` and `measuring-clearance-and-sections.md:48`: "move `offset` 1e-6 mm or more into the part". The tool message adds "more for a shape with a larger tolerance". The skill drops that clause. Imported STEP parts (`part-sourcing`) often have tolerances above 1e-6.

Reproduction (`probe1.py`, box with `fixTolerance(1e-4)`):

```
SECTION Tol z= 9.999999 -> INVALID_INPUT section.plane_on_face
SECTION Tol z= 9.99999  -> INVALID_INPUT section.plane_on_face
SECTION Tol z= 9.9998   -> OK, area 100.0
```

Proposed fix: "move `offset` into the part by more than the face tolerance (1e-6 mm for a native part; an imported part can need 1e-3 mm)".

### RT-8 — low — URDF/SDF: `com` is null for an `App::Part` link and for a compound shape

`urdf-export/SKILL.md:77` and `sdf-export/SKILL.md:80` read "volume and COM" from one `objects` call. `com` is null when the shape is a compound (`_mass_record`, `queries.py:609`).

Reproduction (`probe3.py`): `query_mass_properties` `objects: ["Body5", "Asm", "HolePlate"]` → `[["Body5", com present], ["Asm" (App::Part), com null], ["HolePlate" (Part::Feature from a cut), com null]]`. All three have `solid: true`.

Proposed fix: one clause: "`com` is null for a compound (an `App::Part`, an imported multi-solid STEP): measure each solid's Body, or record the COM as unmeasured".

### RT-9 — low — Q1 — `snapshot-packet-sizing.md` still routes contact distance to `query_mass_properties` / `query_dependencies`

`skills/verification-thinking/references/snapshot-packet-sizing.md:83-84`: "gusset / boss / standoff / rib looks floating → check solid count, labels, and contact distance (`query_mass_properties`, `query_dependencies`)". Neither tool measures a distance. `query_interference` `min_distance` does. Line 85 ("cavity / bore / blind hole looks wrong → section view, then measure wall thickness") does not name `query_section`.

Proposed fix: name `query_interference` (`min_distance`) on line 84 and `query_section` on line 85.

### RT-10 — low — stale text in the parameter-limit test

- `verification-kit.md:149-151`: "Run one case per `script_exec` call ... about 8 s per case for a 100-object, two-part model, recompute included." The case script no longer recomputes (the recompute moved to `feature_set_parameters`), so "recompute included" describes the old script. The measurement now has no source.
- `verification-kit.md:67-68`: "An enumeration takes the same text value on both sides: `setattr(V, "FASTEN", "tap")`". This is a script write of a VarSet enumeration, which `feature_set_parameters` covers (step 1 of the same section, `"an enumeration is its member string"`). The probe confirms `feature_set_parameters` `{"FASTEN": "tap"}` on a VarSet works (`KIT step1 set ... vals 3.0 False tap`).

Proposed fix: delete "recompute included" or measure the new split. Show the enumeration value as `feature_set_parameters` `{"FASTEN": "tap"}`.

## Checked and correct (no finding)

- Q2 payloads: every JSON payload the diff shows validates with `jsonschema` against `tool_specs()` input schemas (`schema_check.py`: 10/10 OK).
- `feature_parameters_define` literal call from `parametric-patterns:39`: `added: ["plate_len"]`. Update to 70: `updated: ["plate_len"]`, `mutation.post_verify.passed` true, `tnp_audit.status` `CLEAN`, Pad recomputed (volume 98000). Same call again: `unchanged: ["plate_len"]`, `undo_steps: 0`, no `mutation`.
- Refusal codes named in `parametric-patterns:51-55`: `W` → `parameters.unit_symbol_name`; angle on `Pad.Length` → `expression.unit_mismatch`; update of a bound variable → `parameters.bound_by_expression`; two-way binding → `RECOMPUTE_ERROR` `expression.cycle`, `rolled_back: true`.
- `.Constraints.width` binding works. `query_parameters` binding row for a VarSet variable is `{object: "Params", path: "derived"}`, as `verification-kit.md:62-63` says.
- `feature_set_parameters` on a bound VarSet variable returns `OK` with `changed: []`, and the value stays 140 mm (silent reset, as `verification-kit.md:62-64` and `gap-list.md:26` say). On a script-made VarSet, `{"PLATE_T": 3.0, "COUNTERSINK": false, "FASTEN": "tap"}` applies and recomputes the bound box.
- `query_section`: a plane on a face → `section.plane_on_face`; 1e-6 mm inside on a native box → area 100; a plane that misses → `wires` 0, `area` 0, `bbox` null. All match the reference.
- `query_interference` on two `App::Part` containers measures in the global frame (500, correct). The Bodies inside them measure in local frames (1000, wrong), which the reference warns about.
- The `verify_shape` hole checks at `verification-kit.md:202-206` pass on a 4-hole plate.
- Q4: `check_skill_shape.py` exits 0. Q7: four `resolution:` lines added in `deferred-work.md`.

## Not reproduced

- low: a pair of valid, overlapping solids whose `common` comes back empty at distance 0 (this would make RT-1 a wrong pass on a real overlap). I did not search for such a pair. RT-1 stands without it, because the script uses the same kernel call.
- low: per-case cost of `feature_set_parameters` on a 100-object VarSet model against the 30 s budget. Not measured.
- low: `verification-thinking:51-52` dropped "read `explanation`" on a failed mutation. That is a lost hint, but no wrong call follows from it.

## Verdict

**FAIL.** RT-1 (Q5) and RT-2 (Q3) are high. RT-3 to RT-6 are medium.
