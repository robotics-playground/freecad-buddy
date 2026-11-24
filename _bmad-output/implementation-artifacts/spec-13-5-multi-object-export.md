---
title: 'Story 13-5: multi-object STEP, 3MF and STL export'
type: 'feature'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
baseline_commit: '6c60a23'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `export_step`, `export_3mf` and `export_stl` refuse more than one object (`usecases/exports.py:91-93`, `:98-104`), although `mcp-tools-design.md` §3.5 says "omit = all visible solids". Agents fall back to `script_exec` (CAP-3).

**Approach:** Accept several objects and an omitted `objects`. STEP and 3MF keep one product or mesh object per input object, named by `Label`. STL writes one merged mesh. `verify_export_step` and `verify_export_3mf` add one volume check per object that names the object; `verify_export_stl` checks the total volume only (decision 6).

## Boundaries & Constraints

**Always:** A one-object export keeps its code path, its recorded numbers and its check ids (K-1). Solids come from `obj.Shape` (AD-6). FreeCAD calls stay behind `usecases/shim.py` for new code. Output schemas stay additive (AD-28). A shape-less object in the selection gives `INVALID_INPUT` "object has no shape: <Name>".

**Never:** No change to the verify tool input schemas. No per-object STL volume check. No edits to `tool_catalog.py` outside the three export tool descriptions.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Several objects | `objects: [A, B, C]` | One file; result lists exported names; verify passes with one volume check per object (STEP, 3MF) | N/A |
| Omitted objects | Document with a Body, a Box, a Fuse of two boxes (their inputs and the Body's features are covered by those) | Exports Body, Box, Fuse only | No visible solid: `INVALID_INPUT` "document has no visible solid objects to export" |
| One object | `objects: [A]` or omitted on a one-solid document | Same file, numbers and check ids as before | N/A |
| Per-object mismatch | Recorded volume of B altered | Verdict not `OK`; failed check id `export_step.object_volume:B` | N/A |
| Duplicate name | `objects: [A, A]` | Exported once | N/A |
| Unknown name | `objects: [A, Nope]` | Nothing written | `INVALID_INPUT` "unknown object: Nope" |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/exports.py:83-105` -- `_resolve_export_object`: replace by `_resolve_export_objects` (list, de-duplicated, omit = visible solids that no other candidate consumes and that sit in no Body or Part group).
- `exports.py:141-188` `export_step`: one object keeps `shape.exportStep`; several use new `shim.export_step_objects` (`Import.export`, product name = Label). Verified on host FreeCAD 1.1: `Import.export` honours `write.step.schema` and `write.step.unit` statics.
- `exports.py:191-253` `_mesh_export`: STL = one `meshFromShape` over `Part.makeCompound`; 3MF several = one `meshFromShape` per object, written through `shim.export_3mf_objects`.
- `exports.py:302-388` `verify_export_step` and `_step_checks`: multi path re-imports through `shim.read_step_leaves` and adds per-object checks. Re-import of a multi-solid object yields one leaf per solid, so objects consume leaves in order until their recorded solid count is met.
- `exports.py:416-455` `_self_read`: add per-object band and names to the facts.
- `src/freecad_buddy/usecases/shim.py:484-520` -- STEP pin and restore; new writers and reader sit beside them.
- `src/freecad_buddy/adapters/export_oracle.py:221-320` `mesh3mf_oracle`: multi-mesh trimesh leg over all meshes, per-object volume checks, object count and name checks. Called from `hosts/tool_catalog.py:105-115` and `hosts/rpc_proxy.py:55-64` (pass the new `objects` argument in both).
- `src/freecad_buddy/hosts/tool_catalog.py:1357-1380` -- descriptions of three export tools only.
- `tests/infc/test_export_tools.py:428-435` -- refusal test becomes multi-object tests. `tests/external/test_export_oracle.py` -- multi-mesh 3MF oracle tests.
- `tests/uat/testcases/TC-07-verification-and-export-pairing.md:425-495` (TC-07-11, TC-07-12) -- rewrite; no scenario JSON exists for them.
- Design: `verification-design.md` §6.2 to §6.4 -- per-object checks, 3MF names.

## Tasks & Acceptance

**Execution:**
- [ ] `usecases/shim.py` -- add `export_step_objects`, `read_step_leaves`, `export_3mf_objects` (temp Mesh::Feature document, `Mesh.export`, then rewrite `3D/3dmodel.model` with `name` attributes) -- FreeCAD's `Writer3MF` ignores names (`Exporter.cpp:307`), so the name needs a post-write step
- [ ] `usecases/exports.py` -- multi resolve, writers, source facts (aggregate keys unchanged plus `objects`), per-object STEP checks, self-read facts -- the contract
- [ ] `adapters/export_oracle.py`, `hosts/tool_catalog.py`, `hosts/rpc_proxy.py` -- multi-mesh 3MF checks and descriptions
- [ ] tests (infc and external), TC-07-11 and TC-07-12, `verification-design.md` §6 -- cover the matrix

**Acceptance Criteria:**
- Given a three-body document, when each format is exported with all three names and verified, then STEP and 3MF verdicts are `OK` with three per-object volume checks, and STL is `OK` with total volume only.
- Given a one-object export, when verified, then the check ids and numbers equal those before this Story.
- Given an altered recorded volume for one object, when verified, then the verdict is not `OK` and the failed check id names that object.

## Verification

**Commands:**
- `uv run ruff check .` and `uv run ruff format --check <changed files>` -- clean
- `uv run python scripts/check_imports.py` and `uv run python scripts/gen_schemas.py --check` -- clean
- `uv run pytest tests/external -q` -- pass
- `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` -- pass

## Implementation Notes

- `Import` joins the FreeCAD App whitelist of `usecases/` (`scripts/check_imports.py`, `project-structure.md`): the multi-object STEP writer and reader need it.
- Default selection: a candidate is consumed when another candidate holds it in a link property (`Base`, `Tool`, `Shapes`, a Body `Group`); `AttachmentSupport` and expression references do not consume. A document with exactly one object exports it whatever its visibility (K-1).
- STL of several objects records `facet_counts`; trimesh and the second oracle weld per object, because two touching objects fail as one welded mesh (measured: two boxes sharing a face failed all five checks).
- Importer and exporter options that come from `Mod/Import` preferences are passed explicitly in the shim.
- Round 2 (container UAT and red team):
  - The GUI writer repeats `Default Extension="png"` once per mesh thumbnail; the rewrite keeps one entry per extension. Tested with a fixture archive and lib3mf (headless FreeCAD cannot produce it).
  - A hidden Body or Part hides its children (default selection). A mirror's `Source` is not consumed; consuming links are an allow-list.
  - Several objects: STEP writes scratch `Part::Feature` copies of each object's solids, so each object gets its own product named by its `Label`, the hidden child of a selected `App::Part` is not written, and a loose face is dropped. Decision: copies, not the original objects, because OCCT shares one product between objects that share a shape.
  - 3MF names: each control character becomes a space (lib3mf refuses numeric character references); the verifier compares against that file name.
  - `verify_export_step` reads the product names from the file (`export_step.object_names`).
  - Not changed: BooleanFragments fails `topology_counts` on the single path too. OCCT writes non-ASCII labels as raw UTF-8 (RT-8), recorded in `deferred-work.md` by the leader.
- Deferred: App::Part placement (pre-existing), App::Link visibility (low).

## Review Triage Log

Lenses: Blind Hunter a04acfda514f282a5, Edge Case Hunter a44d449d801e1aea6, Verification Gap ac6b4727dd7c46902.

| Finding | Verdict | Evidence and route |
|---------|---------|--------------------|
| B1/E1 expression or attachment drops a solid from the default export | medium | `OutListRecursive` includes expression and attachment targets. Patched: `_shape_inputs`; infc test. |
| B2/E7/E8 `Import` preferences change structure | medium | `AppImportPy.cpp:204-217, 282-288` read settings when the kwarg is absent. Patched: explicit kwargs in `shim`. |
| B3/E10 STEP leaf label unused, reorder risk | low | Label field removed; a reorder fails the volume checks loudly. `objects_matched` mismatch test added. |
| B4 descriptions promise names for one object | medium | Patched: descriptions and design say "several objects". |
| B5/G2 no-solid refusal only for several objects | low | Intended (K-1); design text states it. |
| B6/E3 App::Part placement | low, pre-existing | Measured: single and multi path agree, both local. Deferred. |
| B7 Q2 test has one feature | low | Patched: `AdditiveBox` added to the Body. |
| B8 failed rename leaves file, reported as bad input | medium | Patched: `RuntimeError`, file removed, missing model part raises; test. |
| B9/G1 handler wiring untested | medium | Patched: six tests in `test_mcp_surface.py` (catalog and proxy). |
| B10/E19/E20 hidden sole object refused | medium | K-1 regression. Patched: one-object document exports as before; test; design text. |
| B11 output docs omit `objects` | low | Design §3.5 states `objects` in the result. |
| B12 no `maxItems` on `objects` | low | Rejected: other tools bound by an agent prompt, not a hard limit; 120 s timeout covers it. |
| B13 container plus contents selected | low | Rejected: documented as exported as given. |
| B14 UAT visual for STL and 3MF | low | Rejected: TC-07-03 and TC-07-09 already open each format; TC-07-11 reads the 3MF names with an outside tool. |
| B15 rename tests in wrong file | low | Patched: `test_exports_3mf_names.py`. |
| E2 hidden parent group | low | Rejected: not reproduced; deferred note. |
| E4 App::Link | low | Rejected, deferred note. |
| E5/E6 wrong file extension | low | Rejected: pre-existing for one object; the new failure path removes the file. |
| E9 shared TShape twice | low | Rejected: not reproduced. |
| E11 `all([])` valid | false | Empty leaves fail `objects_matched`. |
| E12 `write.step.assembly` static | false | `TopoShape.cpp:896` sets it to Off before each single write; `ExportOCAF2.cpp:76` sets Auto for each multi write. |
| E13 compound counts dedupe shared sub-shapes | low | Patched: totals are sums over objects. |
| E14 STL of touching objects fails oracles | high | Reproduced (five failed checks). Patched: `facet_counts`, per-object welding; external and infc tests. |
| E15 type="surface" regex | low | Patched: regex keeps the type. |
| E16 INVALID_INPUT with file left | medium | Same as B8. |
| E17 control characters in label | low | Patched: newline, return, tab as character references. |

### Round 2 (container UAT D-1, red team RT-1 to RT-8, lenses round 2)

Lenses: Blind Hunter ab25971a900789028, Edge Case Hunter aa71fe06eaf454d5b, Verification Gap a0669763dbe56b3c4.

| Finding | Verdict | Evidence and route |
|---------|---------|--------------------|
| D-1 GUI 3MF repeats the png content type | high | Patched: `_unique_content_types`; test with the GUI-written archive from the UAT and lib3mf (it refuses the file before the fix). |
| RT-1 hidden Body or Part keeps visible children | high | Patched: `_is_shown` walks the groups above an object; tests. |
| RT-2 mirror source dropped | medium | Patched: a mirror consumes nothing. |
| RT-3, RT-6 control characters in 3MF names | medium | Patched: each becomes a space; read back with lib3mf. |
| RT-4 shared shape, one product name | medium | Patched: scratch `Part::Feature` copies; decision recorded in Implementation Notes. |
| RT-5 hidden child of a selected Part | medium | Patched: the written shape is the recorded shape. |
| RT-7 solid plus loose face | low | Patched: only the solids are recorded and written. BooleanFragments counts: pre-existing, deferred. |
| L-1 no product-name check | low | Patched: `export_step.object_names`. |
| RT-8 non-ASCII labels | low | Not fixed: OCCT writer; leader records it. |
| Lens: link allow-list drops compound and other links | medium | Patched: links consume unless attachment or mirror; compound test. |
| Lens: root product named `FCB_TMP_step_write` | medium | Patched: scratch document named `<document name>_export`. Colours are not carried (stated in the design). |
| Lens: long, tab, newline, quote, backslash and empty labels fail the name check | high | Reproduced on host; patched (line join, escape decoding, empty label uses the object name); tests. |
| Lens: duplicate labels use set membership | low | Patched: counts. |
| Lens: tests that cannot fail (loose face, hidden child) | low | Patched: assert faces, solids, volume. |
| Lens: `file_name` hand-off untested | medium | Patched: infc test reads it from the self-read facts. |
| Lens: name matched to geometry only by file order | low | Rejected: the writer sends each label with its shape; a swap is not a writer fault. |
| Lens: expected name taken from the writer return value | low | Rejected: needed for labels FreeCAD makes unique in the scratch document. |
| Lens: plain group hidden by script, nested groups | low | Rejected: not reproduced in the GUI, where hiding sets the children. |
| Lens: design and ledger wording | low | Patched. |
