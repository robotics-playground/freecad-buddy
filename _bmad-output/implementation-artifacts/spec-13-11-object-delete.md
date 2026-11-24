---
title: 'document_object_delete tool'
type: 'feature'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '3c8efd8da1aefc95496f9d832f3e700dd9585ec6'
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
  - '{project-root}/docs/decisions/014-tnp-intended-target-is-what-the-op-wrote.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** An agent that must remove an object runs `doc.removeObject` in `script_exec` (CAP-3). Nothing refuses a delete that leaves a Pad without its profile, and a Body feature removed this way can leave `Tip` and `BaseFeature` stale.

**Approach:** New mutation `document_object_delete` (T-4) removes objects inside one AD-5 bracket, refuses a delete that would orphan dependents unless `with_dependents` is true, and is previewable. The TNP audit excuses an owner that the op itself deleted.

## Boundaries & Constraints

**Always:** Input `doc`, `objects` (1 or more object Names, duplicates ignored), `with_dependents` (bool, default false), `confirm`. Output `deleted` (every removed Name), `dependents` (the Names removed only because `with_dependents` was true), `mutation`. A Body in `objects` also deletes its `Group` members, its `Origin` and the Origin features. A Body feature outside a deleted Body goes through `Body.removeObject` first, so `Tip` and the next feature's `BaseFeature` stay valid. Dependents = objects outside the delete set whose `OutList` holds a deleted object, except a container (`Body`, `App::Part`, `App::DocumentObjectGroup`) that only holds it in `Group`. With `with_dependents` false and any dependent: `INVALID_INPUT`, `detail.code` `delete.has_dependents`, the message names them, nothing deleted. With true the closure of dependents is deleted and listed. An `App::Origin` or Origin feature named without its Body: `INVALID_INPUT` `delete.origin_object`. Unknown name: `INVALID_INPUT`. All refusals come before the bracket (no snapshot, no transaction). One `document_undo` restores the whole delete. The rollback proof reads the object set back through a `state_probe` (names, labels, `OutList` names, Body `Tip` and `Group`), because the shape fingerprint does not see a shape-less object. `run_mutation` takes an optional `deleted` set; `audit_references` excuses a vanished owner only when it is in that set and absent from the document (decision 014 style); any other vanished owner stays `BROKEN`. After an abort in the delete bracket and after `document_undo`, the ExpressionEngine entries of the objects FreeCAD restored are re-applied (decision 36), only if the re-link adds no undo step and leaves redo working (measure UndoCount/RedoCount); otherwise no re-link, and the result carries `expressions_relinked: false` with the affected names and the description warns. Previewable through `preview_dry_run`. Not in `READ_ONLY_PROFILE`. Design doc (`mcp-tools-design.md` rows, counts, §3 schema, §3.8 text) agrees with the code.

**Never:** Pass or verdict (AD-35). A new status value (AD-17: `detail.code` only). Change other tools' behaviour. Delete children of an `App::Part` or group that is deleted (they stay, outside the group).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Tip feature | `Pad2` (Tip) | gone; `Tip` = previous feature; Body valid | N/A |
| Sketch with pad | `Sketch`, no flag | nothing deleted | `delete.has_dependents` names `Pad` |
| Sketch with pad | `Sketch`, `with_dependents` true | `Sketch`, `Pad`, downstream features, `dependents` filled | N/A |
| Whole Body | `Body` | Body, members, Origin, Origin features gone | N/A |
| Origin plane | `XY_Plane` | nothing | `delete.origin_object` |
| VarSet bound by expression | `VS`, no flag | nothing | `delete.has_dependents` names the bound object |
| Unknown | `Nope` | nothing | `INVALID_INPUT` |
| Undo | `document_undo` after delete | every object, link, Tip, Group, expression back | N/A |
| Rollback | op fails after one removal | object set as before, proven by `state_probe` | rollback |
| Preview | `preview_dry_run` delete | diff lists names deleted; live document unchanged | N/A |
| TNP | delete an owner of `Profile` | `post_verify` passes; other vanished owners stay `BROKEN` | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/features.py:348` `_feature_mutation` -- reuse (`precheck`, `report`, `state_probe`); new `document_object_delete`, `ObjectDeleteRefusal(CodedValidationError)` beside `ParameterRefusal` (`:1924`); `_resolve_object` (`:180`).
- `src/freecad_buddy/usecases/transaction.py:578` `run_mutation`, `:229` `post_verify` -- pass optional `deleted` to `audit_references`.
- `src/freecad_buddy/usecases/tnp_guard.py:628` `_grade_record`, `:~690` `_reference_findings` -- skip a record whose owner is in `deleted` and absent; `audit_references` signature (`:~410`).
- `src/freecad_buddy/hosts/tool_catalog.py:1057` `preview_op_table`, `_feature_method` (`:579`), `tool_specs` after `document_undo` (`:1346`) -- spec; table includes it.
- `src/freecad_buddy/usecases/documents.py:597` `document_undo` -- only if Open Question answer is (a).
- `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md:123,211,224,626` -- planned to shipped, counts, schema.
- FreeCAD source: `Mod/PartDesign/App/Body.cpp:338` `Body::removeObject` (relinks `BaseFeature`, moves `Tip`); `Document::_remObject` breaks links of remaining objects. Probed 1.1.4: `OutList` includes expression targets (twice) and Body `Group`, `Origin`; one `undo()` restored Body delete and a Tip delete exactly.
- Tests: `tests/infc/test_feature_tools.py` (new class), `tests/infc/test_tnp_guard.py`, `tests/external/test_mcp_surface.py`, `test_confirm_contract.py`, `test_assistant_readonly_profile.py`.
- Do not change: `confirm.py`, fingerprint, other tools.

## Tasks & Acceptance

**Execution:**
- [x] `tnp_guard.py`, `transaction.py` -- `deleted` set, vanished-owner exemption, tests
- [x] `features.py` -- delete set and dependents closure, refusals, `op`, `state_probe`, `report`
- [x] `tool_catalog.py` -- spec, previewable
- [x] `documents.py` -- expression relink after undo (if answer is a)
- [x] design doc -- rows, counts, schema
- [x] tests -- one per matrix row, undo round trip, rollback by real state, dispatch, preview, shared-code envelopes of two other tools

**Acceptance Criteria:**
- Given a Body with sketch, pad and a second pad, when the Tip pad is deleted, then one `document_undo` restores it and `matches_pre_op` is true.
- Given a pad owning a `Profile` link, when it is deleted, then the call is `OK` and the TNP audit is `CLEAN`.

## Implementation Notes

- Implemented directly by the builder (decision: the investigation lived in this session, a fresh subagent would have lacked it).
- Expression re-link: clearing then setting each binding (`shim.relink_expressions`); writing the same text is skipped by FreeCAD. Applied after an abort in `_bracket` and in `document_undo`; failures of `document_undo` re-link go to `errors` (status `RECOMPUTE_ERROR`).
- `deleted` flows `_feature_mutation` (filled by `precheck`) -> `run_mutation` -> `post_verify` -> `audit_references`.
- Added `delete.origin_object` handling for any object with an `Origin` link (Body and Part).
- Re-scored the G2 validators (`score_g2_infc`, exit 1 BARS NOT MET as on base) to refresh `validator_sha` of `run_mutation` and `audit_references`.

## Spec Change Log

## Review Triage Log

Lenses: Blind Hunter a7e01f6f1eb288383 (opus, high), Edge Case Hunter aab97bc4cd83e74b3 (opus, high), Verification Gap a890bf9fa4a755ce8 (sonnet, medium).

| Lens | Finding | Verdict | Route and evidence |
| --- | --- | --- | --- |
| Blind, Edge, Gap | Mid-feature delete refused, design text said `BaseFeature` follows | medium | patch: contract rule (OutList dependents) is intended; design text corrected, test added (`Pad1` alone refused naming `Pad2`) |
| Blind, Edge | `Origin` attribute that is a vector (FEM function) crashes precheck | medium | patch: `_origin_objects` checks `TypeId`; test with a stub |
| Edge | Body after its Origin in document order: `getObject` None crash | high | patch: skip a gone target; test with `copyObject`; mutation removing the guard fails it |
| Edge | `Part::LocalCoordinateSystem` carries `OriginFeatures` itself | low | patch: `_origin_objects` covers it (no test: the type needs the Part workbench object; the helper is shared with Body) |
| Edge | Link from another open document not scanned | low | defer: rare, scan needs cross-document `InList` |
| Edge | `with_dependents` non-bool over RPC | false | the MCP schema types it boolean before dispatch; same as every other tool |
| Edge | clear then set fails: binding lost, text not reported | medium | patch: failure tuple carries the text, `document_undo` error names it |
| Blind, Gap | Abort-path relink failure dropped | low | rejected: the rollback proof reads the dependency back and falls back to the snapshot, so the document is correct; decision 36 guard 2 applies only when relink cannot work, and it can |
| Blind, Gap | Relink failure status `RECOMPUTE_ERROR` | low | rejected: the existing `errors` envelope of `document_undo` is the status for an undo that left a problem |
| Blind | Q7 measured only headless | maybe-false | defer to container UAT: GUI `_checkTransaction` could open a transaction; verifier checks UndoCount and RedoCount |
| Blind, Gap | Q6 gaps: Whole-Body undo, Tip undo, Visibility, VS with dependents | medium | patch: four tests added |
| Gap | Part delete untested | medium | patch: test (children survive, origin removed) |
| Gap | `Origin` object named untested | low | patch: test |
| Blind | Q9 envelope comparison absent | false | done by the builder: `feature_pad` and `document_undo` envelope shapes identical to base (git archive of 3c8efd8d) |
| Blind | Skill gap-list still routes delete to `script_exec` | low | defer: Story 13-12 owns skill routing |
| Blind | Stale docstring "neither spec list" | low | patch |
| Blind | Fixed index `[3]` for the plane | low | patch: select by `Role` |
| Blind | `deleted` set filled by `precheck` as a side effect | low | rejected: one call site, and the clean-audit test fails when the set is empty |
| Blind | `validators.yaml` run_id unchanged | false | the scorer rewrites the hashes; `check_provenance` passes |
| Blind | Empty-list test weak | low | patch: uses `assert_rejected_pre_bracket` |
| Gap | Source-text assertion in `test_mutation_contract.py` weak | low | rejected: pre-existing style; infc test covers the threading |

## Verification

**Commands:**
- `uv run --extra dev ruff check`, `ruff format --check <changed files>`, `check_imports`, `gen_schemas --check`, `check_provenance` -- expected: pass
- `uv run --extra dev pytest tests/external -q` -- expected: pass
- freecadcmd `tests/run_tests.py` with temp cfg and `FREECAD_USER_HOME` -- expected: pass

### Round 2 (red team RT-1..RT-3, verifier F1/F2, three lenses on 4ee8c26b..b83276a0)

Lenses: Blind Hunter a74611b22f08d2fa4 (opus, high), Edge Case Hunter a78f48fd5e37d3364 (opus, high), Verification Gap a3ac4f00fa17466bc (sonnet, medium).

| Source | Finding | Verdict | Route and evidence |
| --- | --- | --- | --- |
| RT-1 | `PartDesign::Boolean` operand Body treated as a container member | high | patch: `_is_member_container` excludes `PartDesign::Boolean`; tests refuse and volume after `with_dependents` |
| RT-2 | container expression on its own member | medium | patch: `_expression_names` makes the container a dependent; tests |
| F1 | new Tip hidden after a visible Tip delete | medium | patch: visible deleted feature shows its `BaseFeature` (GUI rule), `touched` lists it, undo and abort tests |
| RT-3 | `App::Link` array elements orphaned | low | patch: elements deleted with the array (GUI rule), `App::LinkPython` too; tests |
| F2 | preview argument text | low | patch |
| Blind, Edge | exact TypeId list refuses members of Assembly, FemAnalysis, GroupPython | high | patch: `hasExtension("App::GroupExtension")` minus Boolean; container test for Part, group, group python (mutation fails it) |
| Blind, Edge | `App::LinkPython` missed | medium | patch: `isDerivedFrom`; test |
| Blind, Edge | expression regex matched `VS.Pad2` | medium | patch: Name only at the start of a path; test |
| Gap | `<<Label>>` branch untested | medium | patch: test |
| Blind | visibility not in rollback probe or `touched` | low | patch: `_object_state` reads `Visibility`; abort test |
| Blind, Edge | description and design text inexact about Tip | low | patch: text follows the BaseFeature rule |
| Blind | one element of a live array named alone: GUI refuses, tool lists the array as dependent | low | rejected: consistent with the dependents rule; `with_dependents` is an explicit opt-in |
| Blind | two tests with Act in Assert | low | patch: split |
| Gap | Tip None path, plain link `ElementCount` 0, Boolean preview | low | rejected: Tip None is asserted by the closure test; the others add no observable behaviour |
| Gap | GUI visibility | maybe-false | UAT (verifier) |
