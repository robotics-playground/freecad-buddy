# Tool and content contracts

Implementation contract for each Try item in [keep-problem-try.md](keep-problem-try.md). Shared
types (`Quantity`, `Selector`, `MutationBlock`, `ResultEnvelope`) are the ones in
`mcp-tools-design.md` §1. Every new mutation tool runs the AD-5 bracket and returns a `mutation`
block. Every schema change is additive (AD-28), except where a section says otherwise.

## Common rules

- New tools register in `hosts/tool_catalog.py:tool_specs()`, live in `usecases/`, and get a row
  in `mcp-tools-design.md` §2 and §3 in the same story.
- A tool that measures returns numbers. It never returns a "done" or "pass" for the part (AD-35).
- A multi-object input refuses an unknown object name with `INVALID_INPUT` "unknown object:
  <name>" before any work.
- Results follow "silent on pass, loud on fail": no request echo, compact JSON.

## T-13 Result text without duplicated strings

Change: `contracts/envelope.py:summary_text`.

| Value type | Rendered line |
|------------|---------------|
| `str` with length ≤ 80 and no newline | `key: value` (as today) |
| `str` longer than 80, or with a newline | `key: <N chars>` |
| `dict`, `list` | unchanged: `key: {N fields}`, `key: [N items]` |

A tool with a bespoke `summary` is unchanged. The limit 80 keeps short scalars (handles, names,
paths) readable and drops every `value_repr`/`stdout` copy measured in usage-evidence.md.

Done when: a `script_exec` result holds its `value_repr` once; the `text` field share of result
characters over the test session is ≤5%.

## T-10 Server instructions

Change: the MCP `initialize` result carries `instructions` (`adapters/mcp_server.py`). Plain
text, the same for every client (model agnosticism convention), ≤250 words:

- One line per tool family with its purpose: `document_`, `query_`, `verify_`, `export_` +
  `verify_export_`, `sketch_`, `feature_`, `preview_`, `view_`.
- "Use a typed tool whenever one covers the operation. Before a build, make the sketch_,
  feature_, query_ and verify_ tools available in your client."
- "`script_exec` is for the gaps listed in the `freecad-scripting-idioms` skill."
- One line naming the skills to load first: `design-decomposition`, `freecad-sketcher`,
  `freecad-partdesign`, `verification-thinking`.

`script_exec` description (`hosts/tool_catalog.py:1064-1068`) adds: "Before using it, check the
typed tool families in the server instructions."

## T-2 Measurement tools

### `query_mass_properties` — extend

Input adds `objects: string[]` (1..50). Exactly one of `object` and `objects` is required.

Output with `objects`: `{ "objects": [ <the per-object record of today> + "is_valid": bool ] }`,
in input order. The solid count stays in the record's `counts.solids` (CAP-8: each value once).
With `object`: unchanged plus `is_valid`.

Errors: both or neither of `object`/`objects` → `INVALID_INPUT`; an unknown name in `objects` →
`INVALID_INPUT` naming it; in `objects`, an object with no shape or an empty shape → its record
is `{ "name", "shape": null }` and the call stays `OK`. The `object` path keeps its errors.

### `query_interference` — new, read-only

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "objects": { "type": "array", "items": { "type": "string" }, "minItems": 2, "maxItems": 20,
                 "description": "every pair is measured" },
    "pairs": { "type": "array", "items": { "type": "array", "items": { "type": "string" },
               "minItems": 2, "maxItems": 2 }, "maxItems": 100 }
  }, "required": ["doc"], "additionalProperties": false },
  "outputSchema-result": { "type": "object", "properties": {
    "pairs": { "type": "array", "items": { "type": "object", "properties": {
      "a": { "type": "string" }, "b": { "type": "string" },
      "common_volume": { "$ref": "#/$defs/Quantity" },
      "min_distance": { "$ref": "#/$defs/Quantity" },
      "boolean_failed": { "type": "boolean" } },
      "required": ["a", "b", "common_volume", "min_distance", "boolean_failed"] } }
  }, "required": ["pairs"] } }
```

Exactly one of `objects` and `pairs`. `common_volume` uses `Shape.common`; `min_distance` uses
`distToShape` and is 0 when the shapes touch or overlap. When `common` raises or returns an
empty shape while `min_distance` is 0, a fuse cross-check runs: if the fuse is valid and its
volume equals the sum of the two volumes within 1e-12 of that sum and no solid lies inside the
other (a probe point just under a face of one shape is not strictly inside the other), the pair
touches without overlap, `common_volume` is 0 and `boolean_failed` is false (Epic 13 decision 41). Otherwise
`boolean_failed` is true and `common_volume` is null. An empty result must never read as "no
overlap" (a measured false pass, usage-evidence.md) unless the fuse proves it. Known limit: an
overlap of less than 1.5e-12 of the summed volume (3e-3 mm^3 for two boxes of 1,000 mm) can read
as touching; for a small part against a large one the limit follows the large part.

A pair is measured only when both shapes are valid solids with positive volume; otherwise
`boolean_failed` is true and `common_volume` and `min_distance` are null (FreeCAD's `common` and
`distToShape` are not reliable on invalid, reversed or non-solid shapes). `min_distance` is also
null when `distToShape` raises. Cost bounds: a pair whose face counts multiply to more than
150,000, or a call still running after 40 s between pairs, returns `INVALID_INPUT` with
`detail.code` `interference.too_complex` and no partial result. Unknown name, self pair, or an
object with no shape → `INVALID_INPUT`.

### `query_section` — new, read-only

Input: `doc`, `object`, `plane: { "normal": "x"|"y"|"z"|[nx,ny,nz], "offset": Quantity }`,
`points: { "deflection": Quantity, "max_points": int ≤ 5000 }` optional.

Output: `wires` (count), `closed_wires`, `area` (of the faces the closed wires bound),
`length`, `bbox`; with `points`, `polylines: [[[x,y,z],…],…]` in mm, capped at `max_points`
total with `truncated: bool`.

Errors: a plane that misses the shape → `OK` with `wires: 0`. A plane on a planar face →
`INVALID_INPUT` `section.plane_on_face`. An invalid or reversed shape → `INVALID_INPUT`
`section.untrusted_shape`; a valid shell or face is cut with `area` null. More than 3,000 faces
or a BSpline pole load above 640,000 → `INVALID_INPUT` `section.too_complex`. `area` is null
when it cannot be measured (open wire, more than 300 wires, or the cross-check against the
closed wires fails). Cut by `Shape.section` with a plane face (`slice` misses planes near a face).

## T-3 Parameters and expressions

### `feature_parameters_define` — new, mutation

Creates the `App::VarSet` when it does not exist, then adds or updates properties.

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "varset": { "type": "string", "description": "VarSet Name; created when missing" },
    "parameters": { "type": "array", "minItems": 1, "items": { "type": "object", "properties": {
      "name": { "type": "string", "pattern": "^[A-Za-z_][A-Za-z0-9_]*$" },
      "type": { "enum": ["length", "angle", "float", "integer", "bool", "string"] },
      "value": {},
      "group": { "type": "string", "default": "Parameters" },
      "description": { "type": "string" } },
      "required": ["name", "type", "value"] } },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "varset", "parameters"] } }
```

Type map: `length` → `App::PropertyLength`, `angle` → `App::PropertyAngle`, `float` →
`App::PropertyFloat`, `integer` → `App::PropertyInteger`, `bool` → `App::PropertyBool`,
`string` → `App::PropertyString`. `length`/`angle` values are `Quantity`.

Errors (`INVALID_INPUT`, before the bracket): a name equal to a unit symbol (`mm`, `deg`, `in`,
…) — FreeCAD's expression parser reads it as a unit; an existing property of another type; a
`varset` name held by a non-VarSet object.

Output: `varset`, `added: [names]`, `updated: [names]`, `mutation`.

### `feature_set_expression` — new, mutation

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "expressions": { "type": "array", "minItems": 1, "maxItems": 100, "items": {
      "type": "object", "properties": {
        "object": { "type": "string" },
        "path": { "type": "string", "description": "property path, e.g. Length, .Constraints.width, .AttachmentOffset.Base.z, .Placement.Base.y" },
        "expression": { "type": ["string", "null"], "description": "null clears the binding" } },
      "required": ["object", "path", "expression"] } },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "expressions"] } }
```

All entries run in one AD-5 transaction. Output: `bound: [{object, path, value}]` with the
evaluated value as `Quantity` or scalar, and `mutation`.

Errors: unknown path or a parse error → `INVALID_INPUT` naming `<object>.<path>` and FreeCAD's
message; a circular dependency → `RECOMPUTE_ERROR` with rollback (AD-5).

### `query_parameters` — build the planned tool

As `mcp-tools-design.md` §2: VarSet and Spreadsheet parameters with value, unit, group,
description, plus every expression binding in the document as `{object, path, expression}`.

## T-4 Object edits

### `document_object_delete` — build the planned tool

Input: `doc`, `objects: string[]`, `with_dependents: bool` (default false), `confirm`.

- A Body in `objects` deletes its `Group` and `Origin` too.
- Dependents = objects outside the delete set whose `OutList` holds a deleted object. With
  `with_dependents: false` and any dependent → `INVALID_INPUT` naming them, nothing deleted.
  With `true`, dependents are deleted too and listed.
- Output: `deleted: [names]`, `mutation`. Undo through `document_undo`.
- Allowed as a `preview_dry_run` operation (already named in §3.8).

### `feature_set_parameters` — extend

Accepted property types add:

| Type | Value |
|------|-------|
| `App::PropertyPlacement` (`Placement`, `AttachmentOffset`) | `{ "base": {x,y,z: Quantity}, "rotation": { "axis": [x,y,z], "angle": Quantity } }`; omitted keys keep their value |
| `App::PropertyString` (incl. `Label`) | string |

A `Label` write that FreeCAD changes to make unique returns the stored label in the result.

## T-5 Multi-object export

`export_step`, `export_3mf`, `export_stl` accept `objects` with more than one name, as
`mcp-tools-design.md` §3.5 already specifies (omit = all visible solids). Remove the refusal at
`usecases/exports.py:91-93`.

| Format | File content |
|--------|--------------|
| STEP | One solid per object, object `Label` kept as the STEP product name |
| 3MF | One mesh object per input object, `Label` as the object name (multi-colour print) |
| STL | One merged mesh |

`verify_export_*` compares per-object volume and the total; a per-object mismatch fails the
verdict and names the object.

## T-6 `script_exec` observe-only bracket

Requires the AD-5 amendment (story T-11 writes it). Behaviour:

1. Fingerprint before.
2. If the script did not open a transaction, the bridge opens one named
   `script_exec <first code line>`.
3. Run the script. No rollback on any outcome.
4. Recompute when the document is touched; commit the bridge transaction.
5. Fingerprint after; compute `changed` (AD-6).

Result adds: `fingerprint_after` (digest + serializer), `changed`, and `new_errors: [names]` —
objects in error after the script that were not in error before.

Status:

| Outcome | Status | Detail |
|---------|--------|--------|
| Script ran, no new errors | `OK` | — |
| Script ran, new objects in error | `RECOMPUTE_ERROR` | message names them; changes kept |
| Script raised | `INVALID_INPUT` | `code: exec.python_error`, `data.exception`, `data.traceback`; partial changes kept and listed in `changed` |
| Timeout | `TIMEOUT` | unchanged (AD-27) |

One `document_undo` reverts the whole script. `preview_dry_run` exclusion, audit records and
the 30 s budget stay as today.

## T-7 `verify_shape` input

- `checks.items` becomes `oneOf`, one branch per `fn` with `"fn": {"const": …}`, its own
  required keys and `additionalProperties: false`. Generated from `contracts.ASSERTION_FNS`
  so the vocabulary has one source.
- `object` stays optional (no breaking change). When omitted and the document holds more than
  one shape-bearing object → `INVALID_INPUT` "object is required: document has N shape
  objects", the same fail-closed rule as export.

## T-8 TNP audit expected moves

Requirement: when a sketch or datum keeps the same support object and the same element
(same mapped name), and only its placement changes because a driving value or expression
changed, the audit reports `PASS`, not `REPOINTED`. A change of support object or of mapped
element stays `REPOINTED`. Reproduce first with the datum-follows-sketch case from
usage-evidence.md; the story starts with a written cause in `usecases/tnp_guard.py`.

## T-9 Part workbench and loft/sweep

### `feature_part_primitive` — new, mutation

Input: `doc`, `kind: "box"|"cylinder"|"cone"|"sphere"|"torus"`, `name`, dimension
`Quantity` fields per kind (`length`,`width`,`height` | `radius`,`height` |
`radius1`,`radius2`,`height` | `radius` | `radius1`,`radius2`), `placement` (as T-4),
`confirm`. Creates `Part::<Kind>` at document level, outside any Body.

### `feature_part_boolean` — new, mutation

Input: `doc`, `operation: "cut"|"fuse"|"common"`, `base: string`, `tools: string[]` (≥1),
`name`, `refine: bool` (default true), `confirm`. `fuse` and `common` with several tools use
`Part::MultiFuse`/`Part::MultiCommon`; `cut` with several tools cuts their fuse.
Errors: an input that is a Body feature, not a top-level shape → `INVALID_INPUT`; an empty
result → `RECOMPUTE_ERROR` with rollback.

### `feature_loft` — new, mutation

Input: `doc`, `body`, `profile`, `sections: string[]` (≥1), `ruled: bool`, `closed: bool`,
`subtractive: bool` (default false), `name`, `confirm`. Creates
`PartDesign::AdditiveLoft`/`SubtractiveLoft`.

### `feature_sweep` — new, mutation

Input: `doc`, `body`, `profile`, `spine: Selector | sketch name`, `mode:
"standard"|"frenet"`, `subtractive: bool`, `name`, `confirm`. Creates
`PartDesign::AdditivePipe`/`SubtractivePipe`.

Design changes in the same story: `docs/intent.md` phase list, `mcp-tools-design.md` §2
`feature_` table, skill `tool-selection` routes.

## T-1 Skill routing (and T-14)

| Skill | Change |
|-------|--------|
| `freecad-scripting-idioms` | Full gap list (the operations with no typed tool after this spec), including the accepted traced-outline route: helper modules run by `script_exec` for organic outlines from images, with a transaction, `verify_*` after, and no typed equivalent claimed. Rule: name the missing typed tool before calling `script_exec`. |
| `parametric-patterns` | VarSet and expressions through `feature_parameters_define`, `feature_set_expression`, `query_parameters`. |
| `code-cad-conversion` | Part primitives and booleans through T-9 tools; generator file only for shapes the typed tools cannot make; verification kit uses `query_mass_properties` (`objects`), `query_interference`, `verify_shape`. |
| `design-decomposition` | `Part::Common` through `feature_part_boolean`. |
| `tool-selection` | Loft and sweep name `feature_loft`/`feature_sweep`. |
| `verification-thinking` | Interference and clearance through `query_interference`; sections through `query_section`. |
| `part-sourcing` | Remove the reference to a non-existent import path; state import as a gap. |

Step one (no new tool needed): bounding box, volume, validity through `query_mass_properties`
and `verify_shape`. Each later step lands with its tool. Every `SKILL.md` stays ≤1,500 words
with 4 sections (`scripts/check_skill_shape.py`).

## T-11 Documents

- `ARCHITECTURE-SPINE.md` AD-5: replace "Exception: `script_exec` runs raw…" with the
  observe-only bracket of T-6.
- `mcp-tools-design.md`: move `script_exec` out of the "`debug_` — operator-only … never an AI
  surface" heading into its own "escape route" row; §5 rule 4 and rule 7 match T-6; add rows and
  §3 schemas for every new tool; update counts.
- `spec-freecad-buddy/SPEC.md:120`: "typed tools first; `script_exec` for listed gaps (AD-4)".
- `data-contracts-design.md`: `exec.python_error` detail code.

## T-12 Hygiene and usage report

- `scripts/automation/usage_report.py`: reads Claude Code transcripts for given project folders
  and a date range; prints the tables of usage-evidence.md (totals, per-tool outcome, script
  classes, failure classes, tool loading, `text` share). Dev tool only, not shipped in the addon.
- Stale handle message: "unknown or stale document handle: <doc>; call document_list for the
  current handles".
- On bridge start, delete `rpc-<pid>.json` files whose pid is not a running process.
