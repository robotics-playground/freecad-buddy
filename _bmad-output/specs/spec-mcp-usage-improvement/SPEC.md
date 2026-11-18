---
id: SPEC-mcp-usage-improvement
companions:
  - keep-problem-try.md
  - tool-contracts.md
  - usage-evidence.md
  - ../../planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# freecad-buddy MCP usage improvement

## Why

Pain to solve. In one month of real modeling (2026-10-18 .. 2026-11-18, 10 sessions, 1,221
calls), agents sent 34% of freecad-buddy calls to `script_exec`, and those calls held most of the
modeling work. Script mutations skip the AD-5 bracket: no diff, no TNP audit, no automatic
transaction. The cause is in the product, not in the agent. Most scripts are chosen before any
typed call: skills and project instructions name `script_exec` as the normal route; Claude Code
defers MCP tools and the agent loads `script_exec` first, so typed tools are seldom loaded; one
missing step (an expression) moves a whole sketch into a script; and typed tools are missing for
frequent operations. Fallback after a typed failure explains only 13 scripts. Speed is not a
cause. Results also carry duplicated text: 26% of result characters. Causes C-1 .. C-6:
`usage-evidence.md`. Goal: `script_exec` becomes a true escape route for rare work. Items with
impact and priority: `keep-problem-try.md`. Contracts per item: `tool-contracts.md`.

## Capabilities

- **CAP-1**
  - **intent:** Agent measures several objects (bbox, volume, validity, solid count), interference and minimum distance between object pairs, and sections at a plane without a script.
  - **success:** Replaying the read-only script classes of `usage-evidence.md` (bbox/volume, `isValid`, interference, slice) on a test document gives the same values through `query_mass_properties`, `query_interference` and `query_section`; a failed boolean never reads as zero overlap.
- **CAP-2**
  - **intent:** Agent creates VarSet properties, sets their values, reads parameters, and binds expressions to properties without a script, inside the AD-5 bracket.
  - **success:** A parametric part with a VarSet that drives sketch constraints, feature lengths and an attachment offset is built, edited, read back and undone with typed tools only.
- **CAP-3**
  - **intent:** Agent deletes objects, writes placement and attachment offset, renames labels, and exports several objects to one STEP, 3MF or STL file without a script.
  - **success:** Each operation runs through a typed tool, returns a mutation diff, and reverts with `document_undo`; a multi-body export passes its `verify_export_*` with per-object volumes.
- **CAP-4**
  - **intent:** A mutating `script_exec` call shows what it changed and is reversible in one step, and a Python error is not reported as a recompute failure.
  - **success:** A script that changes two objects returns `fingerprint_after` and a `changed` list naming both, and one `document_undo` reverts it; a script raising `AttributeError` returns `INVALID_INPUT` with `detail.code` `exec.python_error`.
- **CAP-5**
  - **intent:** Agent calls typed tools correctly the first time: `verify_shape` checks are typed per `fn`, and the TNP audit does not flag an intended re-attachment.
  - **success:** The `verify_shape` schema rejects `{"type": "is_valid_solid"}`; an omitted `object` on a document with more than one shape object returns `INVALID_INPUT`; the datum-follows-sketch edit from `usage-evidence.md` passes with no `REPOINTED` flag.
- **CAP-6**
  - **intent:** Server instructions and skills route each covered operation to its typed tool, get the typed tools loaded first, and name `script_exec` only for listed gaps.
  - **success:** No `skills/**` text routes a covered operation to `script_exec`; `freecad-scripting-idioms` lists every remaining gap, including the traced-outline route; in a Claude Code test modeling session the first tool load holds sketch and feature tools; a session asked "is it done?" loads `verification-thinking`.
- **CAP-7**
  - **intent:** Project documents agree on the role of `script_exec`, and usage is measured by a repeatable report.
  - **success:** `spec-freecad-buddy/SPEC.md`, `mcp-tools-design.md`, AD-4 and AD-5 state the same role; `scripts/automation/usage_report.py` prints the tables of `usage-evidence.md` for a date range.
- **CAP-8**
  - **intent:** Every value in a tool result appears once; the generated `text` field carries no copy of a long string field.
  - **success:** A `script_exec` result holds `value_repr` once; over a test session the `text` field is ≤5% of result characters (from 26%).
- **CAP-9**
  - **intent:** Agent creates Part primitives, Part booleans, and PartDesign loft and sweep through typed mutation tools.
  - **success:** A code-CAD part made of primitives and booleans, and a lofted and a swept feature, are built with `feature_part_primitive`, `feature_part_boolean`, `feature_loft` and `feature_sweep`, each with a mutation diff and undo.

## Constraints

- AD-4: typed tools first; `script_exec` stays registered and on by default.
- Every new mutation tool runs inside the AD-5 bracket (snapshot, transaction, recompute, post-verify, commit or proven rollback).
- AD-5 is amended for `script_exec` to an observe-only bracket: automatic transaction, fingerprint, `changed`, `new_errors`; no rollback and no TNP gate.
- The AD-17 status set stays closed; no new status (AD-28 major bump). New failure kinds use `detail.code`.
- Schema changes are additive (AD-28); `verify_shape` keeps `object` optional.
- New code follows AD-1 ring placement: `contracts/` stdlib only, FreeCAD through `usecases/shim.py`, imports inward only.
- Server text is client-neutral (model agnosticism convention): no client-specific tool-loading text in the server.
- No shipped code holds a plan or replays a recipe (AD-35); workflow and routing knowledge live in skills.
- A measuring tool returns numbers and per-check verdicts, never a "part is done" verdict (AD-35).
- Each `SKILL.md` stays at 4 sections and ≤1,500 words (AD-15).
- Every new or changed tool is proven in the `fcb-desktop` container UAT, never on the host.
- Keep items K-1 .. K-7 in `keep-problem-try.md` must not regress.

## Non-goals

- Removing or disabling `script_exec`.
- A recipe or replay tool in the bridge.
- Ellipse or B-spline sketch geometry in `sketch_add_geometry`; traced organic outlines stay on the documented `script_exec` route.
- Helix and thickness tools.
- Phase 5 work: assemblies, STEP import, TechDraw, part sourcing tools.
- Routing or planning logic inside the MCP server.

## Success signal

- Running `scripts/automation/usage_report.py` on the next month of real modeling sessions shows `script_exec` at ≤15% of freecad-buddy calls (from 34%), read-only scripts at ≤5% of calls (from 19%), zero "export supports a single object" refusals, `text` fields at ≤5% of result characters (from 26%), and every remaining `script_exec` call maps to a gap listed in `freecad-scripting-idioms`.

## Assumptions

- The success targets (≤15%, ≤5%, zero refusals, ≤5% text) are proposed by the analysis, not confirmed by the user.
- Regex classes over script source approximate what each script does; one script can count in several classes.
- Two projects and one month represent normal use.
- Claude Code shows MCP server `instructions` to the agent before the first tool load.

## Open Questions

- Accept the success-signal targets, or set other numbers?
