---
title: 'Story 10.3: Feature Tools and the Mutation Protocol'
type: 'bugfix'
created: '2026-10-04'
status: 'done'
baseline_commit: '5cd93c97cf2be28764dfffed4eadb35f2c1e2fe0'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The mutation bracket breaks AD-5 on several paths (UAT run `2026-10-03-04`, F-07..F-11, F-13, F-21). `second_length` is silently ignored. A wrong-typed parameter opens a transaction. A pad on an under-constrained sketch commits. A snapshot restore can never be proven, because `brep_sha256` changes on reopen. A broken Tip is reported `rolled_back_verified`, because null shapes are not fingerprinted. An audit that never ran reports `CLEAN`. Auto-approve audit lines cannot be joined.

**Approach:** Fix each at its root in `usecases/features.py`, `usecases/transaction.py`, `usecases/fingerprint.py`, `usecases/confirm.py` and the two audit adapters. Each fix gets a regression test that fails on the baseline.

**Decisions (planning, not user-visible beyond the ACs):**
- **D1 — F-07.** `second_length` sets `SideType="Two sides"`, `Type2="Length"`, `Length2` (FreeCAD 1.1 `FeatureExtrude.cpp:333-342`). `second_length` with `midplane: true` is `INVALID_INPUT`. `up_to:"TwoLengths"` stays `INVALID_INPUT` (FreeCAD tombstones it as `?TwoLengths`); its message names `second_length`.
- **D2 — F-08.** A wire value must match the property's type family: quantity dict or number for a quantity/float/integer property, bool for `App::PropertyBool`, string for `App::PropertyEnumeration`. Anything else (for example `Part::PropertyPartShape`) is `INVALID_INPUT` naming `<feature>.<prop>` and its type, before the bracket.
- **D3 — F-09.** Post-verify also runs `verify_sketch` on every sketch in the `OutList` of a touched object that is not a container (`PartDesign::Body`, `App::Part`). Body membership alone never pulls a sketch in.
- **D4 — F-10.** The abort path keeps digest equality. The snapshot-restore path proves rollback with `massprops_equal` (`contracts/fingerprint.py:68`) over the same object-name set. AD-6 bans FCStd hashing, not mass properties.
- **D5 — F-11 (amended 2026-10-05 by the user, review 1).** A non-datum object whose `Shape` is null gets an entry `{name, brep_sha256: sha256(b""), massprops: <every field 0.0, quantum Q>}`, and the entry enters the digest. Field types stay `str` and `MassProps`, so `fcb.fingerprint/1` stays valid under AD-28 (a nullable type would be a major bump). A real serialization is never empty, so the hash cannot match a real shape. Objects with no `Shape` attribute stay out.
- **D6 — F-13.** Post-verify runs `audit_references` on every path where the op returned, including the recompute-failure and verify-failure short-circuits; its Layer-0 sweep flags each invalid object `BROKEN`. A path where the audit did not run (setup failure, op raised) reports `UNSUPPORTED`, as `preview._unrun_audit` (`preview.py:239`) already does. No new status value.
- **D7 — F-21 (auto-approve).** The auto-approve path also reads the fingerprint, so the approval line carries `fingerprint_before`.

**Decisions (2026-10-05, user):**
- **D8 — F-21 (Q1 A).** `run_mutation` writes a bracketed mutation's `before`/`after` lines through the host sink (same fallback pattern as `confirm._APPROVAL_SINK`), with the full-params digest and the real fingerprints. For a `method.mutating` call, the adapters (`mcp_server.py`, `rpc_listener.py`) write their own pair only when the envelope carries no `mutation` block, after dispatch; a mutating call refused before the bracket therefore gets its `before` line after execution. Non-mutating audited calls (`debug_exec`, `preview_dry_run`) keep writing `before` before execution (`security-and-service-design.md:38`, `sequence-diagrams.md:466`) — amended 2026-10-05 by the user.
- **D9 — TC-05-16 (Q2 A).** A dress-up (`feature_fillet`, `feature_chamfer`) whose `base` is not the Body's `Tip` is `INVALID_INPUT` naming the Tip, before the bracket. The bridge is stricter than FreeCAD's GUI here on purpose: the GUI lets the result silently drop every feature after the base.

## Boundaries & Constraints

**Always:**
- Input faults return `INVALID_INPUT` before any snapshot or transaction (AD-17).
- A rollback is measured, never assumed (AD-5). An un-run audit is never `CLEAN` (AD-7).
- Every fix has a regression test that fails on the baseline commit.

**Never:**
- No change to UAT test-case files (Story 10.7).
- No FCStd or document-XML hash as a rollback oracle (AD-6).
- No new `TnpStatus` value.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Two-length pad | `feature_pad {length:10, second_length:4}` on 20x30 sketch | `OK`; `SideType` "Two sides", `Length2` 4 mm, volume 8400 | — |
| Two-length + midplane | `{second_length:4, midplane:true}` | `INVALID_INPUT` naming both | before bracket |
| Wrong-typed parameter | `feature_set_parameters {Shape:1}` | `INVALID_INPUT` naming `Pad.Shape` and its type; no `snapshot_path` | before bracket |
| Under-constrained profile | `feature_pad` on sketch with dof 4 | `SPEC_FAILED`, explanation `verify_sketch failed on Sketch (dof=4)`, `fully_constrained:false`, rolled back | — |
| Snapshot restore | abort fails to restore (forced mismatch) | `rollback_proven: rolled_back_via_snapshot` | unproven still `SPEC_FAILED`, snapshot kept |
| UndoMode 0, broken fillet | `feature_fillet radius 500`, undo off | `rolled_back_via_snapshot`; no `Fillet` object; Pad volume unchanged | — |
| Recompute breaks a ref | `Pad.Length` 32 breaks `Fillet` edge link | `RECOMPUTE_ERROR`; `tnp_audit.status` `FLAGGED`, a `BROKEN` layer-0 finding owned by `Fillet` | — |
| Op raises | op throws before recompute | `tnp_audit.status` `UNSUPPORTED`, `findings: []` | — |
| Dress-up off the Tip | `feature_chamfer {base:"Pad"}` with Tip=`Fillet` | `INVALID_INPUT` naming `Fillet` as the Tip; no `snapshot_path` | before bracket |
| Refused call audit | `feature_pad` refused by precheck | one adapter `before`/`after` pair, no bracket lines | — |
| Auto-approve audit | `FREECAD_BUDDY_AUTO_APPROVE=1`, `feature_body_create` | approval, before and after lines share one `params_digest`; all carry the same `fingerprint_before` | — |

</frozen-after-approval>

## Code Map

- `usecases/features.py:405-417` `_extrude_type`, `:419-445` `_precheck_extrude`, `:471-491` extrude `op` -- D1. Pocket shares the helper.
- `usecases/features.py:1647-1681` `_parameter_writes` / `_parameter_value` -- D2; type id already read at `:1668`.
- `usecases/features.py:961-1003` `_dressup_base` -- D9 refusal goes here (`body.Tip`).
- `usecases/features.py:369-372` gate, approval, `run_mutation` call -- D8 wiring.
- `usecases/transaction.py:190-196` `_unrun_tnp_audit` -- D6: becomes `UNSUPPORTED`; reuse the shape of `preview._unrun_audit`.
- `usecases/transaction.py:225-263` short-circuits -- D6: attach `audit_references(document, refs_before, refs_written)`; D3: extend `_sketches` input with consumed sketches.
- `usecases/transaction.py:304-328` `_prove_rollback` -- D4: snapshot branch uses `massprops_equal`.
- `usecases/transaction.py:446-482` `_audit` -- D8.
- `usecases/fingerprint.py:142-175` -- D5. `contracts/fingerprint.py:22-25` `ObjectFingerprint` fields become nullable; regenerate `contracts/jsonschema/`.
- `usecases/confirm.py:326-337` -- D7: read `fingerprint_now` on auto-approve too.
- `adapters/mcp_server.py:208-222`, `adapters/rpc_listener.py:326-341` -- D8.
- Docs to correct: `verification-design.md:68` and `:115`, `data-contracts-design.md:295`, `mcp-tools-design.md:436-439` (`up_to` enum, `second_length`), `tool_catalog.py:592-593`.
- Tests: `tests/infc/test_feature_tools.py` (`PadTest :250`, `SetParametersTest :1809`, copy `test_an_unknown_property_is_rejected_before_the_bracket :1849`), `tests/infc/test_mutation_protocol.py` (`:133`, `:486`), `tests/infc/test_confirm_gate.py :487`, `tests/external/test_contracts.py :507-524`, `tests/external/test_fingerprint_contract.py`.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/features.py` -- D1, D2, D9 -- F-07, F-08, TC-05-16.
- [x] `src/freecad_buddy/usecases/transaction.py` -- D3, D4, D6, D8 -- F-09, F-10, F-13, F-21.
- [x] `src/freecad_buddy/usecases/fingerprint.py`, `contracts/fingerprint.py`, regenerated schema -- D5 -- F-11.
- [x] `src/freecad_buddy/usecases/confirm.py`, `adapters/mcp_server.py`, `adapters/rpc_listener.py` -- D7, D8 -- F-21.
- [x] Tests -- one per I/O row, in the files the Code Map names.
- [x] Docs and `tool_catalog.py` -- per Code Map.
- [x] Re-score validators whose sources change (`benchmarks/runner.py:96-128`): `fingerprint`, `verify_shape` (G0); `run_mutation`, `audit_references` (G2); `spec_assertions` (G3).

**Acceptance Criteria:**
- Given each I/O row, when its regression test runs on FreeCAD 1.1.3, then it passes, and it fails on the baseline commit.
- Given the full suites, when run, then in-FreeCAD and external tests pass, and ruff, `check_imports`, `gen_schemas --check` and `check_provenance` pass, and every validator score is current.

## Implementation Notes

## Spec Change Log

- **Review 1 (intent gap, resolved by user: D5 option B; targeted rework, not full revert).** Trigger: triage row 1 — D5's nullable `brep_sha256`/`massprops` is a type change under `fcb.fingerprint/1`, which AD-28 makes a major bump. Amended: D5 now encodes a null shape as `sha256(b"")` plus zeroed `MassProps`. Known-bad state avoided: a `/1` reader receiving `null` in fields typed `str`/`MassProps`. KEEP: everything else in the diff — D1-D4, D6-D9 code and tests, the D8 Option B adapter split and its `debug_exec` ordering tests, the `document_undo` expectation check, docs, the validator re-score. Revert only the nullable contract types, the regenerated schemas' nullable entries, and the null-accepting branch in `documents._check_expectation`.

## Review Triage Log

| # | Source | Finding | Verdict | Route / evidence |
|---|--------|---------|---------|------------------|
| 1 | blind, edge | D5 made `ObjectFingerprint.brep_sha256`/`massprops` nullable under `fcb.fingerprint/1` | high | intent_gap: AD-28 (`ARCHITECTURE-SPINE.md:250`, `data-contracts-design.md:43`) makes a type change a major bump with the old schema retained; D5 fixed the representation without settling the version. Resolved: D5 amended to option B. |
| 2 | gap 1, blind | No test that `build_server`/`RpcListener` install the sink `run_mutation` writes through; deleting `set_approval_sink` silently drops every bracketed audit line | medium | patch: assert `confirm.host_audit_sink() is sink` after construction, both adapters. |
| 3 | blind, edge | `_parameter_value` accepts `2.5` or a `{value, unit}` dict for an integer property, and a dict for a unitless float; FreeCAD then raises inside the bracket | medium | patch under AC2: integer property takes an int only; unitless float takes a bare number only; quantity property takes dict or number. |
| 4 | blind | `run_mutation` validator sources omit `contracts/fingerprint.py`, which now holds the rollback proof (`massprops_equal`) | medium | patch: add it to `runner._VALIDATOR_SOURCES["run_mutation"]` and `score_g2_infc.py:88`, re-score. |
| 5 | blind, edge | `security-and-service-design.md` §3 still says every mutation tool call logs before execution; D8 writes a refused mutating call's pair after dispatch | low | patch (doc) per D8. |
| 6 | gap 2 | Container exclusion in `_involved_sketches` unpinned | medium | patch: pad beside an unrelated loose sketch returns `OK`. |
| 7 | gap 3 | `saveCopy` failure path's `fingerprint_before` unasserted | low | patch: one assertion pair. |
| 8 | gap 4 | Commit-failure paths' real `tnp_audit` unasserted | low | patch: assert status on both `BracketGuardTest` cases. |
| 9 | blind | `massprops_equal` docstring calls it a render check; null-entry and name-set cases untested | low | patch: docstring + three contract tests. |
| 10 | blind, gap, edge | Marshal timeout on a bracketed mutation yields the adapter's TIMEOUT pair plus the bracket's later pair | low | patch (comment): document it at `wrote_own_audit`; both lines are true records, suppressing either loses the hang or the outcome. |
| 11 | edge | `up_to:"?TwoLengths"` would pass `_checked_enum` if the live enum lists the tombstone | low | patch: compare `up_to.lstrip("?")`. |
| 12 | blind | Body snapshot-restore test never asserts its premise (digest differs after reopen) | low | patch: one assertion. |
| 13 | blind, gap, edge | A raise out of `_bracket` (restore error, fingerprint in rollback branch) leaves an orphan bracket `before` line plus an adapter pair | low | rejected: the raises are pre-existing and not reached in tests or UAT; fix adds a guard branch. |
| 14 | blind, edge | `_involved_sketches` follows every `OutList` entry: reference axes, external-geometry sketches | low | rejected: D3 states exactly this; MCP-built sketches are always fully constrained. |
| 15 | blind | Under-constrained profile caught after the bracket, not in precheck | false | AC3 requires post-verify to cover it. |
| 16 | blind, edge | No precheck for a build without `SideType` | false | FreeCAD 1.0 dropped (`spec-drop-freecad-1-0-support.md`); every CI leg is 1.1.x. |
| 17 | blind | Auto-approve fingerprints twice; unreadable shape now `INVALID_INPUT` | low | rejected: D7 as approved; the refusal matches the token path. |
| 18 | blind | Duplicated audit branch in both adapters | low | rejected: the two adapters already mirror each other line for line; a shared helper changes both call sites for 4 lines. |
| 19 | blind | `feature_set_parameters {Type:"TwoLengths"}` gets the generic message | low | rejected: generic message is correct; cosmetic. |
| 20 | blind | `mcp-tools-design.md` lists `UpToShape` with no shape input | low | rejected: the list describes the live enum; behaviour unchanged by this diff. |
| 21 | blind | Rotation about COM passes `massprops_equal` | low | rejected: the restore reopens the file `saveCopy` wrote; the existing divergent-restore test (`test_mutation_protocol.py:225-242`) covers a wrong restore. |
| 22 | edge | Quantization boundary could fail a correct restore | low | rejected: values come from the same B-rep; no observed failure. |
| 23 | edge | `_sketch_state` raising a non-`ValidationError` after the bracket gives a second pair | low | rejected: pre-existing raise, not reached. |
| 24 | edge | `audit_references` raising on a short-circuit replaces `RECOMPUTE_ERROR` with `SPEC_FAILED` | maybe-false | defer: settle by running `sketch_remove_geometry` that leaves a Pad with a null shape (TC-05-17) through post-verify. |
| 25 | blind | Cross-document `OutList` entry resolved by local name | low | rejected: `getObject` returns `None` or a non-sketch; no cross-document links in scope. |
| 26 | blind | Listener tests order by `time.sleep(0.05)` | low | rejected: the assertion is on call order recorded in-process, not timing. |
| 27 | blind | No pocket `second_length` test | low | rejected: pad and pocket share the one `op` path. |

## Verification

**Commands:**
- `micromamba run -n fcb freecadcmd tests/run_tests.py` -- expected: OK.
- `uv run pytest tests/external` -- expected: all pass.
- `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check`, `uv run python scripts/check_provenance.py` -- expected: pass.
