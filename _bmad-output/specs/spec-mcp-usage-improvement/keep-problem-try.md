# Keep / Problem / Try: freecad-buddy MCP usage

Review of one month of real modeling use (2026-10-18 .. 2026-11-18, 1,221 calls). Numbers,
quotes and causes C-1 .. C-6: [usage-evidence.md](usage-evidence.md). Capabilities: [SPEC.md](SPEC.md). Contracts: [tool-contracts.md](tool-contracts.md).

## Scales

| Scale | Value | Meaning |
|-------|-------|---------|
| Impact | High | Removes ≥50 `script_exec` calls per month, or a core task has no typed path |
| Impact | Medium | Removes 15-49 calls, or a failure repeats across sessions |
| Impact | Low | Removes <15 calls, or hygiene and document consistency |
| Priority | P1 | Next cycle. High value for the effort, or it unblocks other items |
| Priority | P2 | After the P1 items |
| Priority | P3 | Later, or needs a scope decision first |

## Keep

Things that work. Changes must not break them.

| ID | Item | Evidence | Impact | Priority |
|----|------|----------|--------|----------|
| K-1 | `export_*` + `verify_export_*` pair: write, then re-read and grade the file | 196 calls; every STL call OK; STEP failures are only the multi-object refusal (P-5) | High | P1 (protect) |
| K-2 | `query_screenshot` + `view_fit_viewport` for the visual check | 104 calls, 103 OK; second most used tool after `script_exec` | High | P1 (protect) |
| K-3 | Typed `sketch_*` / `feature_*` tools inside the AD-5 bracket, with `document_undo` | pad 22/22, pocket 23/23, datum 22/23, sketch_add_geometry 51/52, undo 12/12 OK | High | P1 (protect) |
| K-4 | Result envelope with closed status vocabulary and a clear message | Failures carry a status and a message that names the cause, e.g. "export supports a single object; got multiple" | Medium | P2 (protect) |
| K-5 | `script_exec` as an escape route, on by default, with source audit | Real work was never blocked: 381 of 410 calls OK | High | P1 (protect, then shrink) |
| K-6 | TNP audit on typed mutations | Caught real breaks: `ExpressionEngine[...] BROKEN` after `sketch_remove_geometry` | Medium | P2 (protect, tune in T-8) |
| K-7 | Skill content for planning and sketching (`design-decomposition`, `freecad-sketcher`, `freecad-partdesign`) | Most-loaded skills: 3 loads each in 10 sessions | Medium | P2 (protect) |

## Problem

| ID | Problem | Evidence | Impact | Priority | Try |
|----|---------|----------|--------|----------|-----|
| P-1 | Skills tell the agent to use `script_exec` for covered and uncovered work, and name only 2 gaps | `parametric-patterns/SKILL.md:38-40`, `code-cad-conversion/SKILL.md:28,44-49,134`, `verification-kit.md:3`, `freecad-scripting-idioms/SKILL.md:74-78`; 58 scripts `exec` a local generator file | High | P1 | T-1 |
| P-2 | No typed tool measures several objects at once, interference between objects, or a section. The one measure tool is never used | 230 read-only scripts: bbox/volume 284, `isValid` 163, interference 57, slice 45; `query_mass_properties` 0 calls | High | P1 | T-2 |
| P-3 | No typed tool creates a VarSet property, sets its value, or binds an expression. One missing step moves the whole operation into a script (cause C-3) | 91 scripts; 26 of 31 sketch-building scripts also bind an expression, so geometry and constraints go to script too | High | P1 | T-3 |
| P-4 | No typed tool deletes an object, writes a placement or attachment offset, or renames a label | `removeObject` 26, placement write 35, `Label` 18 scripts; agent: "The bridge has no delete tool" | High | P1 (delete), P2 (placement, rename) | T-4 |
| P-5 | `export_step` and `export_3mf` accept one object only | 7 refusals "export supports a single object; got multiple"; multi-part prints need one file | Medium | P1 | T-5 |
| P-6 | `script_exec` mutations are raw: no transaction unless the script opens one, `fingerprint_after: None`, no `changed` list, no TNP audit. Python errors report as `RECOMPUTE_ERROR`. A 30 s timeout locks the document as suspect (AD-27 quarantine; by design, kept) | 180 mutating scripts; 8 Python errors labelled `RECOMPUTE_ERROR`; 9 timeouts, 4 suspect refusals | High | P2 | T-6 |
| P-7 | `verify_shape` check schema is untyped (`items: {"type":"object"}`), and an omitted `object` measures the first object without warning | 13 calls, 3 OK; 5 `INVALID_INPUT` (`is_valid_solid needs 'expect'`, `unknown assertion fn: None`) | Medium | P2 | T-7 |
| P-8 | TNP audit flags an intended re-attachment (datum that moves with its parent sketch) as `REPOINTED`, so the agent reroutes the edit through a script | 3 `feature_set_parameters` SPEC_FAILED; agent: "REPOINTED flag was a false positive … rerun … using a VarSet script" | Medium | P2 | T-8 |
| P-9 | No typed Part-workbench primitives or booleans; no loft, sweep, helix, thickness | 47 + 14 scripts; `tool-selection` recommends them | Medium | P3 | T-9 |
| P-10 | Agents do not load typed tools. Claude Code defers MCP tools, and the agent loads `script_exec` first (cause C-2). A tool that is never loaded cannot be chosen. Skills are seldom loaded too | `script_exec` in first `ToolSearch` batch in 11 of 13 transcripts; sketch/feature tools loaded in 2 of 13; 7 typed tools never loaded; `tool-selection`, `verification-thinking`, `freecad-troubleshooting` never loaded | High | P1 | T-10 |
| P-11 | Documents disagree on the role of `script_exec` | `spec-freecad-buddy/SPEC.md:120` "typed-tools-only mutation"; `mcp-tools-design.md:196-200` "never an AI surface"; AD-4 says on by default for the rest | Low | P1 | T-11 |
| P-12 | Stale document handles after a FreeCAD restart; no repeatable usage report; ~90 orphan `rpc-*.json` files | 4 stale-handle errors; this review needed ad-hoc transcript parsing | Low | P3 | T-12 |
| P-13 | Result `text` field repeats long string fields of `structured_content` in full | `contracts/envelope.py:76-77`; `text` = 43% of `script_exec` result chars, 26% across all tools (392,450 of 1,488,681 chars) | Medium | P1 | T-13 |
| P-14 | Agent treats the model as code: tested helper modules run by `script_exec` (cause C-5). Typed calls leave no replayable file | 58 scripts `exec` or import a helper module; `fan3d_helpers.py` "imported inside script_exec" | Medium | P3 | T-14 |

## Try

| ID | Try | Fixes | Capability | Impact | Priority | Done when |
|----|-----|-------|------------|--------|----------|-----------|
| T-1 | Rewrite skill routing: each skill names the typed tool for an operation; `freecad-scripting-idioms` holds the full gap list; add a rule "name the missing typed tool before `script_exec`". Do it in two steps: the cheap step now (point bbox/volume/validity to existing tools), the rest as each new tool lands | P-1 | CAP-6 | High | P1 | No skill text routes a covered operation to `script_exec` |
| T-2 | `query_mass_properties` takes `objects`; new `query_interference` (common volume, min distance, failed-boolean flag) and `query_section` (wires, area, optional capped polylines) | P-2 | CAP-1 | High | P1 | A modeling session measures interference and clearance with no script |
| T-3 | New `feature_parameters_define` (VarSet properties) and `feature_set_expression` (bind or clear, batched); build planned `query_parameters` | P-3 | CAP-2 | High | P1 | A parametric part is built with no script |
| T-4 | Build planned `document_object_delete`; `feature_set_parameters` writes `App::PropertyPlacement` and `App::PropertyString` (incl. `Label`) | P-4 | CAP-3 | High | P1 (delete), P2 (rest) | Delete, move and rename run through typed tools with undo |
| T-5 | Multi-object `export_step`, `export_3mf`, `export_stl` as `mcp-tools-design.md` §3.5 already specifies; per-object `verify_export_*` | P-5 | CAP-3 | Medium | P1 | Several bodies export to one file and verify OK |
| T-6 | Observe-only bracket for `script_exec` (AD-5 amendment): automatic transaction, `fingerprint_after`, `changed`, `new_errors`, no rollback; Python exception → `INVALID_INPUT` `exec.python_error` | P-6 | CAP-4 | High | P2 | A script mutation returns a diff and undoes with one `document_undo` |
| T-7 | Typed `verify_shape` schema: one `oneOf` branch per check `fn` with its own required fields; make `object` required | P-7 | CAP-5 | Medium | P2 | Schema rejects a wrong check before dispatch; no silent first-object default |
| T-8 | TNP audit tells an expected move (reference follows its own parent) from a broken reference | P-8 | CAP-5 | Medium | P2 | The datum-follows-sketch edit passes with no flag |
| T-9 | New `feature_part_primitive`, `feature_part_boolean`, `feature_loft`, `feature_sweep` (in scope, user decision) | P-9 | CAP-9 | Medium | P3 | A primitive-and-boolean part, a loft and a sweep are built with typed tools |
| T-10 | Make typed tools load first: MCP server instructions list each tool family with the exact `ToolSearch` select line for a modeling session (sketch, feature, measure, export), and say `script_exec` is for listed gaps; `script_exec` description points to that list; sharper skill trigger text | P-10 | CAP-6 | High | P1 | First `ToolSearch` batch of a modeling session holds sketch and feature tools; `verification-thinking` loads on a "done?" check |
| T-11 | Correct `spec-freecad-buddy/SPEC.md:120` and `mcp-tools-design.md:196-200` to match AD-4 | P-11 | CAP-7 | Low | P1 | All three documents state the same role |
| T-12 | Repeatable usage report over transcripts (the method in usage-evidence.md); stale-handle message names `document_list` as the fix; clean orphan `rpc-*.json` files at start | P-12 | CAP-7 | Low | P3 | One command prints the tables in usage-evidence.md |
| T-13 | `summary_text` renders a string longer than a set limit as a size signal (`key: <N chars>`), the same as it does for dicts and lists | P-13 | CAP-8 | Medium | P1 | A `script_exec` result holds `value_repr` once; `text` share of result chars ≤5% |
| T-14 | Accept traced-outline helper modules run by `script_exec` as a documented gap (user decision); no recipe tool (AD-35). Lands in T-1 text | P-14 | CAP-6 | Medium | P3 | `freecad-scripting-idioms` lists the route with its rules |

## Order

1. P1 cheap: T-13, T-10, T-11, T-1 step one, T-5.
2. P1 tools: T-2, T-3, T-4 (delete). Then T-1 step two for each tool.
3. P2: T-6, T-7, T-8, T-4 (placement, rename).
4. P3: T-9, T-14, T-12.
