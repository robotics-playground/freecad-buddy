# Usage evidence: freecad-buddy MCP, 2026-10-18 .. 2026-11-18

Evidence behind [keep-problem-try.md](keep-problem-try.md). A later run uses the same method to
measure the success signal in [SPEC.md](SPEC.md).

## Method

| Step | Rule |
|------|------|
| Source | Claude Code transcripts `~/.claude/projects/<project>/<session>.jsonl` and `<project>/<session>/subagents/*.jsonl` |
| Scope | Real modeling projects only: `D--Work-3D-Printers-Ender-3V2---Klipper`, `D--Work-Personal-Sources-3d-print-models-funny-character`. The `freecad-buddy` repo (dev, test, UAT) is excluded. |
| Call | A `tool_use` block whose name contains `freecad-buddy` (both `mcp__freecad-buddy__*` and `mcp__plugin_freecad-buddy_freecad-buddy__*`). Deduplicated by `tool_use.id`, because resumed sessions repeat lines. |
| Outcome | `status` of the paired `tool_result` envelope; for `query_tree_summary` the `<STATUS>:` text prefix. |
| Read-only script | `script_exec` code with no match for `addObject`, `removeObject`, `setExpression`, `addProperty`, `newObject`, `addGeometry`, `addConstraint`, `delGeometry`, `.recompute(`, `.save(`, or an attribute assignment `x.y = ...`. |
| Script class | Regex over the `code` input. One script can match several classes. |

The FreeCAD audit log is not used. The GUI addon writes to `_automation/uat/audit.jsonl`
(`FREECAD_BUDDY_AUDIT_LOG` set in env), which mixes UAT and benchmark runs with real work.

## Totals

- 1,221 calls in 10 sessions (18 transcript files with subagents).
- `script_exec`: 410 calls = 34%. Read-only 230, mutating 180.
- Script size: median 14 lines, p90 36, max 108. One call often holds 10-50 FreeCAD operations, so
  the share of modeling work done by script is higher than the share of calls.
- Calls by family: `script` 410, `verify_*` 181, `document_*` 142, `query_*` 134, `export_*` 118,
  `feature_*` 117, `sketch_*` 110, `view_*` 8, `preview_*` 1.

## Per-tool outcome

| Tool | Calls | OK | Not OK |
|------|------:|---:|--------|
| `script_exec` | 410 | 381 | RECOMPUTE_ERROR 13, INVALID_INPUT 11, TIMEOUT 5 |
| `query_screenshot` | 104 | 103 | RECOMPUTE_ERROR 1 ("Bnd_Box is void") |
| `export_stl` / `verify_export_stl` | 82 / 77 | 82 / 77 | — |
| `document_save` | 55 | 55 | — |
| `sketch_create` / `sketch_add_geometry` | 53 / 52 | 50 / 51 | INVALID_INPUT 3 / 1 |
| `verify_sketch` | 38 | 36 | SPEC_FAILED 2 |
| `feature_set_parameters` | 26 | 21 | SPEC_FAILED 3 (TNP audit), INVALID_INPUT 2 |
| `export_step` / `verify_export_step` | 23 / 18 | 18 / 18 | INVALID_INPUT 5 (multi-object) |
| `feature_pad` / `feature_pocket` / `feature_datum` | 22 / 23 / 23 | 22 / 23 / 22 | INVALID_INPUT 1 |
| `query_tree_summary` | 19 | 15 | 4 with no status prefix read |
| `verify_shape` | 13 | 3 | SPEC_FAILED 5, INVALID_INPUT 5 |
| `export_3mf` / `verify_export_3mf` | 13 / 10 | 11 / 9 | INVALID_INPUT 2 / SPEC_FAILED 1 |
| `document_undo` | 12 | 12 | — |
| `sketch_remove_geometry` | 5 | 2 | SPEC_FAILED 2 (TNP audit), RECOMPUTE_ERROR 1 |

Typed tools with **0 calls** in scope: `query_mass_properties`, `query_dependencies`,
`query_placement`, `sketch_add_constraint`, `sketch_set_datum`, `feature_pattern`,
`feature_mirror`, `document_recompute`.

## What `script_exec` does

| Class | Scripts | Typed tool today |
|-------|--------:|------------------|
| Bounding box or volume read | 284 | `query_mass_properties` (one object, never called) |
| `isValid` check | 163 | `verify_shape` `is_valid_solid` (one object) |
| Face/edge scan | 120 | none |
| VarSet, `addProperty`, `setExpression` | 91 | none |
| Property or expression read | 69 | `query_object` (partly) |
| PartDesign `newObject`/`addObject` | 62 | `feature_*` (partly) |
| `exec` of a local helper or generator file | 58 | none (code-cad-conversion route) |
| Interference: `common` volume, `distToShape` | 57 | none between objects |
| Part primitives and booleans | 47 | none |
| Slice or section | 45 | none |
| Sketch geometry/constraints in script | 40 | `sketch_*` |
| Placement or `AttachmentOffset` write | 35 | none (`feature_set_parameters` refuses `App::PropertyPlacement`) |
| `removeObject` | 26 | none (`document_object_delete` planned, mcp-tools-design.md:123) |
| `json.dump` of measured data to disk | 23 | none |
| `Label` rename | 18 | none |
| Loft, sweep, helix, thickness | 14 | none |
| `App::Link` or clone | 7 | none |

## Failure classes that push the agent to `script_exec`

| Class | Count | Example message |
|-------|------:|-----------------|
| `script_exec` timeout | 9 | `marshaled call timed out` (30 s budget) |
| Python error reported as `RECOMPUTE_ERROR` | 8 | `'NoneType' object has no attribute 'Shape'` |
| Multi-object export refused | 7 | `export supports a single object; got multiple` |
| `verify_shape` input rejected | 5 | `is_valid_solid needs 'expect'`; `unknown assertion fn: None` (agent sent `type`, not `fn`) |
| TNP audit flag on a typed mutation | 5 | `TNP audit flagged 4 reference(s): ... AttachmentSupport REPOINTED` |
| Stale document handle | 4 | `unknown or stale document handle: fcb-doc:...` |
| Document-suspect refusal after timeout | 4 | `document-suspect: a prior call timed out on this document` |
| `feature_set_parameters` cannot write | 2 | `AttachmentOffset is a App::PropertyPlacement, which feature_set_parameters cannot write` |

## Agent statements

- "The bridge has no delete tool. **One script deletes these 2 bodies only. May I run it?**"
- "The bridge audit's REPOINTED flag was a false positive, triggered by a datum plane that's
  supposed to move with its parent sketch. I'll rerun the same edit test using a VarSet script
  instead."
- "Build helper module first (segment → sketch geometry with Block constraints, outline offsets,
  pad/pocket with VarSet expressions). Then one `script_exec` per body."

## Routing in shipped skills and docs

| Location | Text |
|----------|------|
| `skills/parametric-patterns/SKILL.md:38-40` | "Write VarSet variables and expressions with `script_exec`: no typed tool adds a property or calls `setExpression`." |
| `skills/code-cad-conversion/SKILL.md:28, 44-49, 134` | All steps run through `script_exec`; "Build with a generator file run by `script_exec`"; "One `script_exec` runs it." |
| `skills/code-cad-conversion/references/verification-kit.md:3` | "Run the FreeCAD snippets with `script_exec`" |
| `skills/design-decomposition/SKILL.md:68-70` | "No typed tool creates a `Part::Common`" — closed-document script fallback |
| `skills/freecad-scripting-idioms/SKILL.md:74-78` | Names only two gaps (placement, delete). The real gap list is longer (table above). |
| `skills/tool-selection/SKILL.md:39-43, 60-67` | Recommends loft, sweep and Part booleans; no typed tool exists for them. |
| `skills/part-sourcing/SKILL.md:43` | Points to a "bridge's document/import path" that does not exist. |
| `ARCHITECTURE-SPINE.md:63-69` (AD-4) | Typed tools first, `script_exec` for the rest, on by default. |
| `spec-freecad-buddy/SPEC.md:120` | "typed-tools-only mutation (AD-4)" — conflicts with AD-4. |
| `mcp-tools-design.md:196-200` | Lists `script_exec` under "operator-only (AD-4; never an AI surface)" — conflicts with §5 and AD-4. |

`script_exec` implementation (`src/freecad_buddy/usecases/script_exec.py:30-61`): plain `exec`
with `FreeCAD`, `App`, `Part`, `doc`; returns `fingerprint_after: None`; no diff, no TNP audit,
no automatic transaction. Errors map to `INVALID_INPUT` for TypeError/ValueError/KeyError and to
`RECOMPUTE_ERROR` for every other exception (`adapters/rpc_dispatch.py:144-157`).

`verify_shape` types `checks` items as `{"type":"object"}` (`hosts/tool_catalog.py:1313`). The
check vocabulary is in prose only. With `object` omitted it measures the first document object
(`usecases/verify.py:241-245`).

## Why the agent chooses `script_exec`

Causes ranked by the number of scripts they explain. C-1 to C-5 act before any typed call.
Failure fallback (C-6) is small.

| ID | Cause | Evidence |
|----|-------|----------|
| C-1 | Instructions name `script_exec` as the normal route | Skill text in the routing table below. funny-character `AGENTS.md:25,70,132-138` sets style rules for "Python passed to `script_exec`". Agent: "load the FreeCAD scripting skill (most of the build goes through `script_exec`)". Ender `CLAUDE.md:168` forbids scripts in `freecadcmd` only, not `script_exec`. |
| C-2 | Deferred tool loading: the agent loads `script_exec` first and seldom loads typed tools | Claude Code defers MCP tools: the agent sees only names and must call `ToolSearch` to load a schema. Table below. |
| C-3 | One missing step moves the whole operation into a script | 26 of 31 scripts that build sketch geometry also bind an expression or VarSet. Typed sketch tools cannot bind an expression, so geometry, constraints and expressions all go into one script. |
| C-4 | Real capability gaps | Delete, placement write, label, multi-object export, measure across objects, Part booleans, loft (classes table above). Ellipse or B-spline geometry: 8 scripts (`sketch_add_geometry` takes `line_segment`, `circle`, `arc_of_circle`, `point` only). Linked copy: "the FreeCAD tool can make only one linked copy". |
| C-5 | Code as the artifact | 58 scripts `exec` or import a local helper module. `fan3d_helpers.py:1`: "FreeCAD-side helpers … (imported inside script_exec)". Agent: "Build helper module first … Then one `script_exec` per body." Plan skill: "plan code is real, not guessed". The helper is tested, committed and rerun for each body; typed calls leave no replayable file. |
| C-6 | Fallback after a typed failure | 41 typed failures. Next call: same tool 21, `script_exec` 13, other typed tool 7. |

Not a cause:
- Speed. Median latency: typed tools 0.2-0.4 s, `script_exec` 0.4 s.
- Batch size. Scripts that create objects create a median of 2 (p90 6, max 8).

Tool loading per transcript (13 transcripts that load freecad-buddy tools):

| Tool group | In first `ToolSearch` batch | Ever loaded |
|------------|----------------------------:|------------:|
| `script_exec` | 11 | 13 |
| `document_list` / `query_tree_summary` | 13 / 11 | 13 / 13 |
| `query_screenshot` | 9 | 10 |
| `query_mass_properties` | 2 | 5 |
| `sketch_create`, `sketch_add_geometry`, `feature_pad`, `feature_pocket` | 1 | 2 |
| `feature_fillet`, `feature_chamfer`, `feature_hole`, `feature_revolve` | 0 | 1 |
| `query_dependencies`, `query_placement`, `feature_pattern`, `feature_mirror`, `sketch_remove_constraint`, `sketch_toggle_construction`, `sketch_add_external_geometry` | 0 | 0 |

The two transcripts that loaded sketch and feature tools are both Ender sessions (2026-10-18 and
2026-11-15). Ender `CLAUDE.md:168` says "Build and edit geometry with MCP tools". No
funny-character session loaded them. Instructions (C-1) decide which tools get loaded (C-2).

## Duplicated tokens in results

The `text` field of the result envelope repeats long string fields of `structured_content`.
Cause: `src/freecad_buddy/contracts/envelope.py:76-77` writes every scalar in full:

```python
        else:
            lines.append(f"{key}: {value}")
```

Dicts and lists already render as a size signal (`key: {N fields}`, `key: [N items]`), but
strings do not. `script_exec` returns `value_repr` and `stdout` as strings, so the summary holds a
second full copy:

```text
"structured_content":{"doc":"fcb-doc:…","stdout":"","value_repr":"{('hotend_mount_original', -60.91): (4.19, 4.21), …}","fingerprint_after":null},
"text":"doc: fcb-doc:…\nfingerprint_after: None\nstdout: \nvalue_repr: {('hotend_mount_original', -60.91): (4.19, 4.21), …}"
```

| Tool | Results | Result chars | `text` field chars | Share |
|------|--------:|-------------:|-------------------:|------:|
| `script_exec` | 410 | 646,518 | 277,804 | 43% |
| `document_save` | 55 | 37,467 | 15,072 | 40% |
| `export_stl` | 82 | 49,751 | 15,321 | 31% |
| All freecad-buddy tools | 1,201 | 1,488,681 | 392,450 | 26% |

On the wire, `_to_call_result` (`src/freecad_buddy/adapters/mcp_server.py:116-122`) also sends
`content[0]` = `json.dumps(body)`, the same body as `structuredContent`. A client that reads
both gets the body twice.

## Skill loads

About 20 freecad-buddy skill loads in 10 sessions. Loaded: `design-decomposition`,
`freecad-sketcher`, `freecad-partdesign`, `freecad-scripting-idioms` (3 each), plus one load each
of `design-intent`, `parametric-patterns`, `freecad-datums-references` from a project copy.
Never loaded: `tool-selection`, `verification-thinking`, `freecad-troubleshooting`,
`sketch-strategy`, `freecad-fundamentals`.

## Hygiene

About 90 orphan `rpc-<pid>.json` files in `%APPDATA%/FreeCAD/v1-1/freecad-buddy/`, dated
2026-08-01 .. 2026-11-09.
