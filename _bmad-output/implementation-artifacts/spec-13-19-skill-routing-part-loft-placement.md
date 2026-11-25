---
title: 'Story 13-19: Skill routing to Part, loft, sweep and placement tools'
type: 'chore'
created: '2026-11-26'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '6e15f063b0049651716005d43b524b3fd3f57ced'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-13-lessons.md'
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Skills and the gap list still route Part primitives, Part booleans (`Part::Common` for print pieces), loft, sweep, placement writes and `Label` renames to `script_exec`, although Stories 13-16, 13-17 and 13-18 added typed tools for them. `code-cad-conversion` makes a generator file run by `script_exec` its core method.

**Approach:** Route each operation to its typed tool: `feature_part_primitive`, `feature_part_boolean`, `feature_loft`, `feature_sweep`, `feature_set_parameters` (placement, string). Keep the generator route for what the typed tools cannot make, and the traced-outline route. T-1 rows: `code-cad-conversion`, `design-decomposition`, `tool-selection`; the gap list.

## Boundaries & Constraints

**Always:**
- Every tool name, parameter, payload and refusal code in a skill matches `tool_specs()` of the merged integration branch (checked by a scratch schema-validation script, as in 13-12).
- A typed refusal is a stop with a repair: `part_boolean.untrusted_shape` (repair the input shape), `part_boolean.too_complex` and `loft.too_complex`, `sweep.too_complex` (split the work). No skill sends a refused call to `script_exec` to bypass a guard (L1, L2).
- `code-cad-conversion` keeps the generator route per part, for: `Part::Wedge`/`taper_z`, other Part types the tool does not offer, an enumeration switch, `App::Link` purchased parts. A cut of more than 20 tools is not a gap: chain the cuts.
- Gap list: drop the placement row, the `Label` row and the Part primitives and booleans row; narrow the loft/sweep row; narrow the string row to link and file types; fix the expression-driven-write wording (`parameters.value_overwritten`); add covered rows for the four feature tools.
- Every edited `SKILL.md` keeps 4 sections and at most 1,500 body words (`scripts/check_skill_shape.py`); moved detail lands in `references/` with a pointer.
- Close the `deferred-work.md` entry that names `Part::Common` and the 13-16 gap-list entry, each with a resolution line.

**Never:** Edit `src/`. Move workflow into the MCP. Remove the traced-outline route. Claim a typed route the tool descriptions contradict (report it instead).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected | Check |
|---|---|---|---|
| Print piece | master Body and a region box | `feature_part_boolean` `common`, base the Body | payload validates; empty result named as `part_boolean.empty_result` |
| CSG conversion | box, cylinders, cuts, frame angle | typed primitives, `feature_set_expression`, `feature_part_boolean` in source order | example validates; equality proof unchanged |
| Cut of 36 holes | more than 20 tools | chained `feature_part_boolean` calls | rule stated |
| Wedge or enumeration | source needs a type or property no tool offers | generator route for that part | rule stated |
| Loft or sweep | changing section, constant section on a curve | `feature_loft`, `feature_sweep` with fully constrained sketches | payload validates |
| Place a Body, rename | Placement, Label | `feature_set_parameters`, no `script_exec` | gap list has no row |

</frozen-after-approval>

## Code Map

- `skills/code-cad-conversion/SKILL.md` Scope (line 32), Decision Rules route and build bullets (35-50), Worked Examples, Anti-Patterns; `references/generator-kit.md` "Run it" (typed steps 1 to 3 stay, generator becomes step 4 for unsupported parts), `references/build123d-mapping.md` (typed route note, Booleans table). Body words 1,424: the generator worked example moves to `generator-kit.md`.
- `skills/design-decomposition/SKILL.md:64-70` derived pieces rule.
- `skills/tool-selection/SKILL.md:38-43` loft and sweep, `:58-67` Part booleans and CSG conversion.
- `skills/freecad-scripting-idioms/references/gap-list.md` rows (covered row for `feature_set_parameters`, gaps: placement, Label, Part primitives and booleans, loft/sweep, string).
- `skills/freecad-partdesign/SKILL.md:63-66` loft and sweep names the two tools.
- Tool facts: `tool_catalog.py` `feature_loft`, `feature_sweep`, `feature_set_parameters` (this branch); `feature_part_primitive`, `feature_part_boolean` (branch `story/13-17-part-primitive-boolean`, spec `spec-13-17-part-primitive-boolean.md`, decision 51).
- Do not change: `src/`, tests of tools, other skills' unrelated text.

## Tasks & Acceptance

**Execution:**
- [x] gap list rows and covered rows
- [x] `code-cad-conversion` SKILL.md and references
- [x] `design-decomposition`, `tool-selection`, `freecad-partdesign` routing
- [x] schema-validation script of every shown payload (scratch, result in ledger)
- [x] `deferred-work.md` resolution lines; quality bar `quality-bar-13-19.md`

**Acceptance Criteria:**
- Given the skills after the change, when grepped for `Part::Common`, `Part primitives`, `loft`, `sweep`, `Placement`, `Label`, then none routes a covered operation to `script_exec`.
- Given every payload a skill shows, when validated against `tool_specs()` input schemas, then all pass.
- Given `check_skill_shape.py`, when run, then it passes for every skill.

## Spec Change Log

## Review Triage Log

Round 1 lenses: Blind Hunter af0afaae4ef939701 (opus, high), Edge Case Hunter a8fd093d864c0ae58 (opus, high), Verification Gap a470d703c2d92b81e (sonnet, medium, no gaps). Quality bar: `quality-bar-13-19.md` (integration worktree).

| Lens | Finding | Verdict | Route and evidence |
| --- | --- | --- | --- |
| Blind, Edge, Gap | Worked example: box centring, `hole_2..4` never created, sizes unbound, names break `<part>_<item>` | high | patch: example rewritten (MIN-aligned plate, one hole, all bindings, `bracket_*` names) and run on the 13-17 code under freecadcmd: volume 11,937.168 equals 60x40x5 - pi*4*5, and after `PLATE_T` 8 equals the analytic 19,099.469 |
| Blind, Edge | Typed route drops the rotation seed angle | false | probe: bound `Placement.Rotation.Angle` on an identity-rotation `Part::Box` keeps axis (0,0,1) at 0, 90, -120, 45 deg |
| Edge | Tilted primitive under a frame angle | medium | patch: generator route lists "a primitive tilted off z under a frame angle" |
| Blind, Edge | Mixed part: boundary between typed and generator unstated; kit example builds a box in the generator | medium | patch: generator makes only the object tools cannot make; `feature_part_boolean` takes the Wedge as input (no TypeId whitelist in `_check_part_boolean_inputs`); one-primitive part names the primitive after the part |
| Blind, Edge | `exec_enabled: false` sends the whole conversion headless | medium | patch: typed parts build live; headless only for enumeration or non-offered types |
| Blind, Edge | Refusal list incomplete, no repair route | medium | patch: gap-list paragraph lists every code with its repair (`document_recompute` for a stale input) |
| Blind, Edge | `gap-list` row: attached `Placement` fails as `value_overwritten` | medium | patch: code (`features.py:2655`) refuses an attached or in-Body `Placement` before the bracket; row says so |
| Blind, Edge | `verification-thinking:110` fails on an attached or in-Body part | medium | patch: names the Body's `Placement` |
| Blind, Edge | `design-decomposition`: master hidden after the common; separate document unreachable | medium | patch: Visibility step added; separate-document advice dropped |
| Blind | Coverage script lacks Sphere and Torus | medium | patch: `need` rows added |
| Blind, Edge | Mapping lists Offset2D, Extrusion, Fillet, Chamfer as generator, gap list does not | low | patch: gap row lists them |
| Edge | Non-scalar set_parameters refusals (vector, list) | low | patch: row widened to link, file, vector, list |
| Blind | Loft/sweep guidance: wire count, refusal codes, failure table | low | patch: `feature-failure-tables.md` loft row, `sweep.degenerate_spine` repair |
| Blind | No typed clear or rebuild step; `<name>_tools` in delete lists | low | reject: `generator-kit.md` "Run it" step 1 already says to name every object Name, the Cut's tool objects included |
| Blind | Enumeration step points to a generator step | low | reject: the pointer names "Run it" step 4, which creates enumeration properties by `script_exec` |
| Blind | Deferred Part::Common entry resolved without a run | low | reject: resolution states the doc change; the typed route is covered by the 13-17 tests and the Q9 live check at epic close |
| Blind | `mcp_server.py:69-70` instructions omit loft, sweep, Part tools | medium | defer to leader: `src/` is out of scope; report |
| Edge | Source `loft` still scripted although `feature_loft` exists | low | reject: `feature_loft` makes a PartDesign loft in a Body, which loses the one-to-one CSG map the equality proof needs (`SKILL.md` route bullet) |

Round 2: Edge Case Hunter ac9488a96c530b44c (opus, high), 12 findings.

| Finding | Verdict | Route and evidence |
| --- | --- | --- |
| Kit generator example builds a box and a fuse | medium | patch: example makes only the wedge; plate and fuse typed. Run on the 13-17 code: fuse of `plate` and generator `Wedge` by Name, volume 24,666.667 |
| Wedge passed by Label | medium | patch: "by its Name" in `SKILL.md` and the kit |
| Partial primitives (`Angle*`) listed as a gap | medium | patch: probe on 13-17 code: `feature_set_parameters` `Angle` 90 deg on a cylinder gives 196.3495 (pi*25*10/4), `Angle3` 180 deg on a torus gives 394.7842; gap row and mapping paragraph corrected |
| Body inside an `App::Part`, single large input, later-milestone rebuild | medium | patch: `not_top_level` and `too_complex` repairs; delete then create at milestones |
| Unlisted refusal codes | low | patch: one sentence for `part_primitive.*`, `invalid_input`, `loft.*`, `sweep.invalid_*` |
| `exec_enabled: false` with Link or tilted primitive | low | patch: sentence names "generator-only objects and enumeration properties" |
| Other non-scalar property types (colour, rotation) | low | patch: row reads "another type (link, file, vector, list, colour)"; ledger line matches |
| `verification-thinking:110` for a top-level solid or attached part | low | reject: file is at the 1,500-word cap; the gap-list row states the attached rule |

Gates: `check_skill_shape.py` exit 0 (code-cad-conversion 1,491 words, verification-thinking 1,499), `ruff check` clean, `pytest tests/external` 2,117 passed over two runs (one run had `test_marshal_self_submit` fail on timing; it passes alone and in the other run), payload validator 7 of 7 OK against the 13-17 `tool_specs()`.

