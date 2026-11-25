# Verify Story 13-12: skill routing to the measure, parameter and delete tools

Verifier: verifier-13-12. Artifact: commits `7640239c`, `4333288b` on `story/13-12-skill-routing-measure`, base `04574455`. Run on a detached worktree of `4333288b` (`uv sync --extra dev`); worktree removed after the run. Scratch: session scratchpad `verifier-13-12\`.

## Verdict

**FAIL** — 2 medium defects (D1, D2), 3 low defects (D3, D4, D5). All are skill-text fixes. No product code involved.

| Q | Result | Evidence |
| --- | --- | --- |
| Q1 | FAIL (low) | D3, D4: two remaining script-form hits for covered operations |
| Q2 | PASS | 12 payloads, 169 tool-name hits checked against `tool_specs()`; every code and limit matches the code |
| Q3 | PASS | gap list rows match `tool_specs()` |
| Q4 | PASS | `check_skill_shape.py` exit 0; every edited SKILL.md has 4 sections and ≤ 1,500 words |
| Q5 | FAIL (medium) | D1: kit contact script reads an unmeasured overlap as 0. D2: `urdf-export` still says `query_mass_properties` gives mass and inertia |
| Q6 | PASS | kit parameter-limit flow run end to end in freecadcmd; restore proven; no lost check |
| Q7 | PASS | 4 deferred items have a `resolution:` line |

## Commands and counts

- `uv run python scripts/check_skill_shape.py` → exit 0.
- `uv run --extra dev pytest tests/external/test_check_skill_shape.py tests/external/test_parameters_contract.py -q` → 25 passed, 2 skipped.
- Body words (checker's own `_body`), base → head: `code-cad-conversion` 1423 → 1423; `freecad-scripting-idioms` 1310 → 1317; `parametric-patterns` 950 → 1104; `sdf-export` 831 → 853; `urdf-export` 872 → 888; `verification-thinking` 1494 → 1496. Sections: Scope, Decision Rules, Worked Examples, Anti-Patterns in all six.
- Q2 script: `scratchpad\verifier-13-12\check_payloads.py` (jsonschema `Draft202012Validator` against `tool_specs()` input schemas; `doc` added because skills omit it by convention).
- Q6 scripts: `scratchpad\verifier-13-12\run_q6.py`, `run_q6b.py`, run with `"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -u <scratch>\cfg\user.cfg -s <scratch>\cfg\system.cfg`, `FREECAD_USER_HOME=<scratch>\fchome`. Imported package: `D:\Work\Personal\Sources\fcb-verify-13-12\src\freecad_buddy\__init__.py` (worktree copy, not the installed addon). Output: `q6.txt`, `q6b.txt`.

## Q1 — covered operations routed to `script_exec`

Own grep over `skills/**` (not the builder's list). Token counts base → head:

| Token | Before | After |
| --- | --- | --- |
| `removeObject` | 3 | 1 |
| `setExpression` | 7 | 4 |
| `addProperty` | 5 | 4 |
| `App::VarSet` | 3 | 2 |
| `.common(` | 5 | 4 |
| `distToShape` | 1 | 0 |
| `slice(` | 1 | 0 |
| `ExpressionEngine` | 3 | 3 |
| `setattr(V` | 8 | 5 |
| `getattr(V` | 4 | 3 |

Judgement of every remaining hit:

| Hit | Judgement |
| --- | --- |
| `code-cad-conversion/references/generator-kit.md:19,92,102-136` (`removeObject`, `App::VarSet`, `addProperty`, `setExpression`) | Accepted. One generator script builds Part primitives and booleans (gap row) and enumeration variables (gap row) with their bindings in one transaction; the first-stage clear is part of that generator. |
| `code-cad-conversion/SKILL.md:140` (`setExpression` fails) | Accepted. Worked example on the generator's parse error. |
| `verification-kit.md:77-79`, `:164-165` (`common()` with a reference STEP) | Accepted. The reference is not a document object; no typed tool measures it. |
| `verification-kit.md:108-126` (`ExpressionEngine` coverage) | Accepted. The check needs each primitive's `TypeId` and rotation, which `query_parameters` does not return. See O1 for the stated reason. |
| `verification-kit.md:189-192` (contact `common()`) | Defect D1 (Q5). |
| `verification-kit.md:211-213` (countersink probe) | Accepted. A cone is not a cylindrical hole; `verify_shape` has no cone check. |
| `verification-kit.md:68` (`setattr(V, "FASTEN", "tap")`) | **Defect D3.** |
| `failure-table.md:13` ("check `obj.ExpressionEngine`") | **Defect D4.** |
| `gap-list.md:35` (`addProperty`, `sheet.set`, `setAlias`) | Accepted. Enumeration and spreadsheet are gap rows. |
| `freecad-partdesign/references/feature-failure-tables.md:27` (`Shape.isInside`) | Out of scope: not a covered operation. |

## Q2 — names, payloads, codes, limits

All payloads in the changed files validate:

| file:line | Tool | Result |
| --- | --- | --- |
| `verification-kit.md:86` fence | `verify_shape` checks | OK |
| `verification-kit.md:136` | `feature_set_parameters` | OK |
| `verification-kit.md:180` | `query_interference` `objects` | OK |
| `verification-kit.md:183` | `query_interference` `pairs` | OK (checked by hand; the script paired it with the nearer `query_tree_summary`) |
| `verification-kit.md:199` fence | `verify_shape` hole checks | OK |
| `parametric-patterns/SKILL.md:39` | `feature_parameters_define` | OK |
| `parametric-patterns/SKILL.md:43` | `feature_set_expression` | OK |
| `verification-thinking/SKILL.md:63` | `query_interference` | OK |
| `verification-thinking/SKILL.md:68` | `query_section` | OK |
| `verification-thinking/SKILL.md:73` | `query_mass_properties` `objects` | OK |
| `measuring-clearance-and-sections.md:34` | offset quantity `{"value": 12.5, "unit": "mm"}` | OK against `_LENGTH_QUANTITY_SCHEMA` |

Tool names: 169 hits; 14 not in `tool_specs()`, all on unchanged lines: `export_sdf`, `verify_export_sdf`, `export_urdf`, `verify_export_urdf` (Phase 5 tools named by the export skills before this Story) and `sketch_state` (`verification-thinking/SKILL.md:156`, a result field, not a tool).

Codes and limits against the code: `parameters.unit_symbol_name`, `parameters.bound_by_expression`, `expression.cycle`, `expression.unit_mismatch`, `interference.too_complex`, `section.untrusted_shape`, `section.too_complex`, `section.plane_on_face`, `delete.has_dependents` exist (`features.py:1986,2142,2516,2765`, `queries.py:859,1122,1241,1266`). Limits: 150000 face product (`queries.py:697`), 40 s (`queries.py:703`), 2-20 objects and 1-100 pairs, 1-50 `objects` for mass, 500 rows (`queries.py:1463`), 3,000 faces and 800 poles, `max_points` 2-5000. The unit symbols the skill lists (`W T A V N C K J H F S m g s`) are all in `_EXPRESSION_RESERVED_NAMES` (`features.py:1893`). Six parameter types match `PARAMETER_PROPERTY_TYPES` (no enumeration). Live refusals in `q6b.txt` B4, B4b, B4d, B4f, B11 return these codes.

## Q3 — gap list against `tool_specs()`

Dropped rows: Delete, VarSet/expression, measure across objects, section/slice (with the `shape.slice` advice). Each now has a covered row naming a tool that exists in `tool_specs()`. Kept rows: placement, Label rename, enumeration and spreadsheet cell or alias, Part primitives and booleans, loft/sweep/helix/thickness, Groove and PartDesign primitives, sketch constraints outside the typed set, string or link property (narrowed to non-VarSet), ellipse and B-spline, `App::Link`, face scan, STEP import, file write. None of these has a tool in `tool_specs()` (51 tools listed). PASS. See D2 for an operation with no row.

## Q4 — shape and words

PASS. `verification-thinking` is at 1496 of 1500 words. Moved detail is in `verification-thinking/references/measuring-clearance-and-sections.md`; the pointer is at `verification-thinking/SKILL.md:66`.

## Q5 — guidance on tool results

- `boolean_failed` true = unmeasured: correct in `verification-thinking/SKILL.md:65` and the reference. Wrong in the kit: D1.
- Null `area` = unmeasured: correct (`verification-thinking/SKILL.md:69`).
- `undo_steps: 0` = no step recorded: correct (`parametric-patterns/SKILL.md:46-47`); live: `q6.txt` B3b returned `unchanged: ["plate_len"]`, `undo_steps: 0`.
- `section.plane_on_face`: correct. Live: top face at z 30 refused with `section.plane_on_face`; offset 30 − 1e-6 gave area 1200 mm²; 30 + 1e-6 gave `wires` 0, `area` 0 (`q6b.txt` B6b-B6d).
- Mass and inertia: wrong in `urdf-export`: D2.

## Q6 — verification kit run

Parameter-limit flow (`q6.txt` A0-A9), on a VarSet `Params` with `PLATE_T` (float), `COUNTERSINK` (bool), `FASTEN` (enumeration) and `HALF` (bound `PLATE_T / 2`), and boxes bound to them:

1. `query_parameters` read the defaults. Binding row for the derived variable is `{object: "Params", path: "HALF"}`: matches `verification-kit.md:138`.
2. `feature_set_parameters` `{"feature": "Params", "parameters": {"PLATE_T": 3.0, "COUNTERSINK": false}}` → OK, `post_verify.passed` true, box height 3.
3. Case script (verbatim, read-only) → `overlap_pct` 100.0 against the T3 reference.
4. `verify_recompute` OK; `verify_shape` equality OK (volume 600, `rel` 1e-6).
5. Enumeration `{"FASTEN": "tap"}` → OK, value `tap`.
6. Derived `{"HALF": 9.0}` → status OK, no error, value stays 1.5: confirms "reset by the recompute with no error" (`verification-kit.md:139`).
7. Restore from the `query_parameters` values, drivers only: `{"COUNTERSINK": true, "FASTEN": "clear", "PLATE_T": 5.0}` → OK; fingerprint back to the default digest.
8. `query_parameters` after restore equals the defaults: `true`.
9. Default equality overlap 100.0.

Routed examples, one per new tool (`q6b.txt`): `feature_parameters_define` (B1, `added`), `feature_set_expression` on `Length` and `.Constraints.width` (B2, B2b) and `null` clear (B3c), update through `feature_parameters_define` (B3: `updated: ["plate_len"]`, `post_verify.passed` true, `tnp_audit` `CLEAN`, pad 30), `query_parameters` (`q6.txt` B5), `query_section` (B6), `query_mass_properties` `objects` (B7), `query_interference` `objects` (B8: `common_volume` 0, `min_distance` 1.0), `document_object_delete` refusal and `with_dependents` (B11, B11b), `verify_shape` hole checks from `verification-kit.md:199` (`q6.txt` B10: 4 holes, 5.5 mm, through).

No lost check: overlap, recompute, equality, restore proof and hole checks all still run; the hole check is now stronger (diameter tolerance 0.05 against the old ±0.1 probe). PASS. D5 is a wording issue in this section.

## Q7 — deferred items

`deferred-work.md:2155` (13-6 skill text), `:2204` (section/slice), `:2276` (VarSet/expression), `:2295` (delete) each carry a `resolution: resolved by Story 13-12` line. No other open entry names Story 13-12. PASS.

## Defects

### D1 (medium) — kit contact script reports an unmeasured overlap as a pass

`skills/code-cad-conversion/references/verification-kit.md:184-192`:

```
`boolean_failed` true is unmeasured, not zero. With it true and `min_distance` 0
the parts touch, and the tool cannot tell contact from overlap: no typed tool measures that, so
use the script below.
...
result = round(a.common(b).Volume, 3)    # pass: <= 0.05 mm3
```

What breaks: `query_interference` sets `boolean_failed` true at distance 0 only when `common()` returned an empty or null shape (`queries.py:823-843`). The script runs the same `common()` on the same shapes and gets the same empty result, read as volume 0.0. Live, two touching boxes: tool → `common_volume` null, `min_distance` 0, `boolean_failed` true; kit script → `(0.0, isNull False, BoundBox valid False, solids 0)` → "pass" (`q6b.txt` B9). The script cannot tell contact from overlap either; it turns the unmeasured case into a pass, which the line before forbids.

Proposed wording: "With it true and `min_distance` 0 the parts touch or the boolean failed. A script `common()` gives the same empty result (volume 0), so it proves nothing: report the overlap of that pair as unmeasured, run `verify_shape` on both parts, and check with `query_placement` that the spec puts the two faces flush." Delete the script block at `:189-192`, and drop "contact between touching parts" from `:9`.

### D2 (medium) — `urdf-export` says `query_mass_properties` returns mass and the inertia tensor

`skills/urdf-export/SKILL.md:42-43`:

```
- Compute each link's `<inertial>` from FreeCAD's **native mass properties**
  (`query_mass_properties` gives mass, center of mass, and the inertia tensor), not
```

What breaks: the tool returns `name, solid, volume, area, bbox, com, counts, is_valid` (`q6b.txt` B7); no mass, no inertia. The same file now says the opposite at `:77`. An agent that follows `:43` looks for fields that do not exist. No gap-list row names the inertia tensor, so the gap-list rule ("no row … report the operation as blocked") blocks the URDF inertial.

Proposed wording for `:43`: "(`query_mass_properties` gives volume and center of mass; take mass from the material density; the inertia tensor has no typed tool: `freecad-scripting-idioms` `references/gap-list.md`)". Add a gap row: "Read mass or the inertia tensor of a shape | none (`query_mass_properties` returns volume and centre of mass) | `shape.MatrixOfInertia`, scaled by density". `sdf-export/SKILL.md:51-52` needs the same pointer.

### D3 (low) — VarSet enumeration write shown as a script

`skills/code-cad-conversion/references/verification-kit.md:68`:

```
`setattr(V, "FASTEN", "tap")`; only expressions compare its index.
```

`feature_set_parameters` writes it (`q6.txt` A5). Proposed wording: "An enumeration takes the same text value on both sides: `feature_set_parameters` `{"feature": "Params", "parameters": {"FASTEN": "tap"}}`; only expressions compare its index."

### D4 (low) — bindings read routed to `obj.ExpressionEngine`

`skills/code-cad-conversion/references/failure-table.md:13`: "check `obj.ExpressionEngine`". `query_parameters` lists every binding (`query_object` for one object). Proposed wording: "check the bindings with `query_parameters`".

### D5 (low) — stale timing note

`skills/code-cad-conversion/references/verification-kit.md:150-151`: "about 8 s per case for a 100-object, two-part model, recompute included." The case script no longer recomputes; `feature_set_parameters` does. Proposed wording: "the script runs one `common()` per part; the 8 s measured for a 100-object, two-part model included the recompute that `feature_set_parameters` now does."

## Observations (no change needed)

- O1: `verification-kit.md:8-9` gives the 500-row cap of `query_parameters` as the reason for the coverage script. The stronger reason is that the check needs `TypeId` and rotation per primitive, which `query_parameters` does not return. Optional rewording.
- O2: `verification-thinking/SKILL.md:51-52` dropped "read `explanation`" when trimmed for the word limit. Meaning is unchanged (`rollback_proven` is non-null only when a rollback was proven, `contracts/mutation.py:26,95`).
- O3: Skill payloads omit `doc` and `confirm`, as all skills do. The validation added `doc`.
- O4: `feature_set_expression` can bind `.Placement.Base.x`, a partial route for the placement gap row. The row stays until Story 13-16, as the quality bar says.

## Round 2

Artifact: `b4f2f49c` (`1d1150d0` fixes, `b4f2f49c` lens patches) on `story/13-12-skill-routing-measure`. I ran it on a new detached worktree at `b4f2f49c`, then removed the worktree. Probes: `scratchpad\verifier-13-12\run_r2.py`, output `r2.txt`. Host freecadcmd 1.1.4, private `-u`/`-s` cfg, `FREECAD_USER_HOME` in scratch. Imported package: `fcb-verify-13-12\src\freecad_buddy\__init__.py`.

### Verdict round 2

**PASS with 1 medium and 3 low defects (R2-1 to R2-4).** All round 1 defects (D1-D5) and RT-1 to RT-10 are fixed. R2-1 makes the new generator "Run it" step 3 fail when an agent follows it as written. Q1-Q7: PASS, except Q2, which passes only after R2-1 and R2-2 are fixed.

### Commands and counts

- `check_skill_shape.py` → exit 0. `test_check_skill_shape.py` and `test_parameters_contract.py` → 25 passed, 2 skipped.
- Body words: `code-cad-conversion` 1424, `freecad-scripting-idioms` 1331, `parametric-patterns` 1107, `sdf-export` 874, `urdf-export` 908, `verification-thinking` 1497 (limit 1500). Each has 4 sections.
- Payload script (`check_payloads.py . 04574455 b4f2f49c`, now including `generator-kit.md`, `failure-table.md` and `snapshot-packet-sizing.md`): 197 tool-name hits and 15 payloads. All payloads are schema-valid. The 2 reported failures are script pairing errors: the `pairs` payload is paired with `query_tree_summary`, and `{"Visibility": true}` is the `parameters` value on an unchanged line. I validated both by hand: OK. The multi-line `feature_parameters_define` payload at `generator-kit.md:14-17` is also OK by hand and when run live. The 14 unknown names are the same ones as in round 1. The reference-path check (every `references/<file>` in each SKILL.md exists in that skill) finds no missing path.

### D1 / RT-1: fused-volume fallback, live

`query_interference` `pairs: [["A", X]]` against box A (10 mm cube), then the kit script `round(a.Volume + b.Volume - a.fuse(b).Volume, 3)` on the same shapes, then a diagnostic of the fuse:

| Pair | Tool | Kit fuse script | Fuse valid | `common()` |
| --- | --- | --- | --- | --- |
| FaceTouch | `boolean_failed` true, `min_distance` 0 | 0.0 | true | 0.0 |
| EdgeTouch | `boolean_failed` true, 0 | -0.0 | true | 0.0 |
| VertTouch | `boolean_failed` true, 0 | 0.0 | true | 0.0 |
| PartialFace | `boolean_failed` true, 0 | 0.0 | true | 0.0 |
| CylLineTouch (cylinder tangent to a face) | `boolean_failed` true, 0 | 0.0 | true | 0.0 |
| SphPointTouch (sphere on a face) | `boolean_failed` true, `min_distance` 1.74e-10 | 0.0 | true | 0.0 |
| Gap 1e-8 mm | `boolean_failed` true (distance at most 1e-7) | 0.0 | true | 0.0 |
| Overlap 500 | `common_volume` 500, false | 500.0 | true | 500 |
| Contained 2 mm cube | `common_volume` 8, false | 8.0 | true | 8 |
| Identical | `common_volume` 1000, false | 1000.0 | true | 1000 |

The touching cases read 0, each with a valid fuse. The overlapping cases read the true volume. The routing is correct in `verification-kit.md:186-197`, `gap-list.md:36`, `measuring-clearance-and-sections.md:20,26-31` and `verification-thinking/SKILL.md:62-66`. The `common()` script is gone. See R2-3 for the fuse check that is not in the script and R2-4 for the "`min_distance` 0" wording.

### RT-2: mid-Body delete, live

Body with `Box1`, `Box2`, `Cyl3`. `document_object_delete` `["Box2"]` → `delete.has_dependents` (Cyl3). The gap-row route at `gap-list.md:35` (transaction, `body.removeObject(feature)`, `doc.removeObject`, recompute, commit) → group `['Box1', 'Cyl3']`, Tip `Cyl3`, `Cyl3.BaseFeature` = `Box1`. The later feature is kept. After that, `verify_recompute` OK and `verify_shape` `is_valid_solid` and one solid OK. The covered row says "Tip features". I checked it: `document_object_delete` `["Cyl2"]` on a Tip → OK, Tip moves to `Box1`. Note: `document_undo` could not be tried here because headless documents have `UndoMode` 0. The skill text does not depend on it.

### RT-4: generator params stage with typed tools, live

I built a generator from the kit's own "Expression values" and "Parameters" blocks plus a `params()` with a float, a bool, a derived float, an enumeration and a derived value that reads the enumeration. I ran it on a document that held an earlier build:

1. `document_object_delete` exactly as in `generator-kit.md:12` (`{"objects": ["Params", "bracket"]}`) → `unknown object in objects: bracket` (R2-2). With the Names `["Params", "Box"]` → OK, document empty.
2. `feature_parameters_define` exactly as in `:14-17` → OK, `added: ["PLATE_T", "COUNTERSINK"]`.
3. `feature_set_expression` exactly as in `:18-19` (`BOSS_H`) → `expression.invalid_path`: "Params has no property 'BOSS_H'" (R2-1). After `BOSS_H` is created with `feature_parameters_define`, the same call → OK, value 12.
4. The generator `params` stage, then the `bracket` stage, through `script_exec` → OK. `params()` reused `PLATE_T`, `COUNTERSINK` and `BOSS_H` and created `FASTEN` (enumeration) and `FAST_D` (`FASTEN == 0 ? 3 : 4`). Box 20 × 3 × 12. `feature_set_parameters` `{"PLATE_T": 8.0, "FASTEN": "tap"}` → `BOSS_H` 15 and `FAST_D` 4, and the box followed.

The route works when R2-1 and R2-2 are fixed.

### Read-only checks

| Item | Result |
| --- | --- |
| D2 / RT-6 | Fixed: `urdf-export/SKILL.md:42-46` and `:78` say volume and COM, mass from density, inertia tensor "which no tool returns", method recorded; `sdf-export/SKILL.md:51-53` the same. |
| D3 | Fixed: `verification-kit.md:67-69` uses `feature_set_parameters` `{"FASTEN": "tap"}` (schema OK) and names property creation as the gap. |
| D4 | Fixed: `failure-table.md:13` routes to `query_parameters`. |
| D5 / RT-10 | Fixed: "recompute included" removed (`verification-kit.md:153`). The 8 s figure was measured with the recompute in the script, so it is now an upper bound. Acceptable. |
| RT-3 | Fixed: example `{"objects": ["Pin", "Housing"]}` (schema OK); reference splits `min_distance` null (broken shape) from 0 (touching, "overlap unmeasured"). |
| RT-5 | Fixed: `parametric-patterns/SKILL.md:56` names the skill in prose. No cross-skill `references/` path remains. |
| RT-7 | Fixed: reference `:52` says "by more than the face tolerance"; SKILL points to the reference. |
| RT-8 | Fixed: `com` null for a compound, in `gap-list.md:14`, `urdf-export:44`, `sdf-export:52`. |
| RT-9 | Fixed: `snapshot-packet-sizing.md:84-86` names `query_interference` `min_distance` and `query_section`. |

### Defects round 2

**R2-1 (medium): generator "Run it" step 3 binds a variable that step 2 does not create.** `skills/code-cad-conversion/references/generator-kit.md:14-19`:

```
2. Create every plain variable: `feature_parameters_define` ...
3. Bind each derived variable: `feature_set_expression` `{"expressions": [{"object": "Params",
   "path": "BOSS_H", "expression": "Params.PLATE_T + 7"}]}`.
```

What breaks: `BOSS_H` does not exist after step 2, so step 3 is refused with `expression.invalid_path` (`r2.txt` "RT4 step3 literal payload"). Proposed wording for step 2: "Create every variable, plain and derived (`type` `float`; give a derived one any value, step 3 binds it): `feature_parameters_define` ... `{"name": "BOSS_H", "type": "float", "value": 0}`".

**R2-2 (low): step 1 example deletes by a Label.** `generator-kit.md:12` `{"objects": ["Params", "bracket"]}`. The generator sets Labels (`verification-kit.md:183`), and `bracket` is the Label of `Box`. The tool refuses it: `unknown object in objects: bracket`. Proposed wording: `{"objects": ["Params", "Box", "Cut"]}` "(object Names from `query_tree_summary`, not Labels)".

**R2-3 (low): the fuse script does not check the fuse.** `verification-kit.md:193`, `gap-list.md:36`, `measuring-clearance-and-sections.md:29-31`. Every probe gave a valid fuse. But a failed fuse (an invalid shape, or no solids) would give a number with no warning, and the volume difference could then read as a false 0. Proposed: `f = a.fuse(b); assert f.isValid() and f.Solids, "fuse failed: overlap unmeasured"; result = round(a.Volume + b.Volume - f.Volume, 3)`.

**R2-4 (low): "`min_distance` 0" is narrower than the tool.** The tool reports contact at a distance of at most 1e-7 mm (`queries.py:689`, `_CONTACT_DISTANCE_MM`). A sphere on a face gave `boolean_failed` true with `min_distance` 1.74e-10 (`r2.txt`). That value matches neither branch of `measuring-clearance-and-sections.md:20,26-28`, `verification-kit.md:187` or `gap-list.md:36`. Proposed wording: "`min_distance` 0 (at most 1e-7 mm)".

## Round 3

Artifact: `5ad4fe3e` (fixes for R2-1 to R2-4). I ran it on a new detached worktree at `5ad4fe3e`, then removed the worktree. Probe: `scratchpad\verifier-13-12\run_r3.py`, output `r3.txt`. Host freecadcmd 1.1.4, private cfg. Imported package: worktree `src`. The probe reads the payloads and the fuse script directly from the skill files, so the run uses the text as written.

**Verdict: PASS.** R2-1 to R2-4 are fixed. One low observation (O-R3) remains; it does not block.

- `check_skill_shape.py` → exit 0.
- **R2-1 fixed.** Generator "Run it" steps 2-4 run as written, with no manual fix:
  - Step 2 → `added: ["PLATE_T", "BOSS_H", "COUNTERSINK"]`.
  - Step 3 → `bound` `BOSS_H` = 12.
  - Step 4: the `params` and `bracket` stages through `script_exec` → OK. `FASTEN` and `FAST_D` are created by `params()`. `Cut` is valid, volume 2060.708.
  - `feature_set_parameters` `{"PLATE_T": 8.0, "FASTEN": "tap"}` → `BOSS_H` 15, `FAST_D` 4, `Cut` volume 2246.018.
- **R2-2 fixed.** The step 1 example now uses Names, and the text says "Name (not Label)". See O-R3.
- **R2-3 fixed.** The fuse script with the `isValid()` and `Solids` check, run verbatim:
  - Face-touching pair: `query_interference` gives `boolean_failed` true and `min_distance` 0; the script gives 0.0.
  - Pair overlapping by 5 mm: `common_volume` 500; the script gives 500.0.
  - `gap-list.md:36` and the reference give the same check.
- **R2-4 fixed.** "`min_distance` 0 (at most 1e-7 mm)" is in `verification-kit.md:187`, `gap-list.md:36` and `measuring-clearance-and-sections.md:20,28`. `verification-thinking/SKILL.md:65` says "near 0" and points to the reference.

**O-R3 (low, not blocking):** `generator-kit.md:12` gives `{"objects": ["Params", "Box", "Cut"]}`. A `Part::Cut` always has a Tool object too, so no real document matches that list exactly. On a document with `Params`, `Box`, `Cylinder` and `Cut`, the payload as written is refused with `delete.has_dependents` (Cylinder), and nothing is deleted. This is safe. The rule in the same line ("every object Name that `query_tree_summary` lists") works: with all four Names the call returns OK. Optional wording: `["Params", "Box", "Cylinder", "Cut"]`.
