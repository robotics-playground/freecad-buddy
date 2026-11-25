# Story 13-11 verification: `document_object_delete`

Verifier: verifier-13-11 (claude-opus-5-5). Date: 2026-11-24.
Artifact: commit `4ee8c26b633aabc1a3dd7deadf58d904788b9e70` (branch `story/13-11-object-delete`), base `3c8efd8d`.
Own copy: detached worktree `fcb-verify-13-11` at 4ee8c26b; base copy `fcb-verify-13-11-base` at 3c8efd8d. Both removed after the run.

## Verdict

**PASS with one product finding (medium, outside the quality bar).** Q1..Q10 hold. R1-U1 is closed: the expression re-link adds no undo step and keeps redo in the GUI host. New finding F1: after a delete of the visible Tip feature, the new Tip stays hidden, so the Body shows no solid in the GUI. Native FreeCAD delete shows the previous feature.

## Gates (copy at 4ee8c26b, Git Bash)

| Command | Result |
| --- | --- |
| `uv run --extra dev ruff check .` | All checks passed |
| `ruff format --check` on the 10 changed `.py` files | 10 files already formatted |
| `scripts/check_imports.py` | `check_imports OK` |
| `scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `scripts/check_provenance.py` | `check_provenance OK` |
| `scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `scripts/check_skill_shape.py` | exit 0 |
| `uv run --extra dev pytest tests/external -q` | **2082 passed, 6 skipped**, 225 s |
| freecadcmd `tests/run_tests.py` (`-u/-s` temp cfg, `FREECAD_USER_HOME` temp) | **Ran 1090 tests, OK (skipped=1)**, 110 s |

Source check: a probe under the same freecadcmd environment imported `D:\Work\Personal\Sources\fcb-verify-13-11\src\freecad_buddy\usecases\features.py` and found `document_object_delete`. The dev junction to the main tree was not loaded.

## Envelope comparison against base (L12, Q9)

Script `tests/uat/run/13-11-r1/scripts/envelopes.py` ran the same sequence under freecadcmd once with the base `src` and once with the head `src`: `sketch_add_constraint` (DistanceX/DistanceY to DoF 0), `feature_pad` (5 mm), `feature_set_parameters` (Length 9), `document_undo`, and `feature_set_parameters` Length 0 (rollback path). Full JSON envelopes were compared key by key.

| Tool | Status base / head | Differences |
| --- | --- | --- |
| `sketch_add_constraint` | OK / OK | 0 |
| `feature_pad` | OK / OK | 0 |
| `feature_set_parameters` | OK / OK | 0 |
| `feature_set_parameters` (Length 0, rollback) | RECOMPUTE_ERROR / RECOMPUTE_ERROR | 0 |
| `document_undo` | OK / OK | 1: `structured_content.doc` (random handle per run) |

The shared-code change (`deleted` in `run_mutation`/`post_verify`/`audit_references`, relink in `document_undo` and in the abort path) does not change these envelopes. Raw files: `scripts/env-base.json`, `scripts/env-head.json`.

## Mutants (each applied to the copy, then reverted with `git checkout -- src`)

Run: `infc.test_object_delete` + `infc.test_tnp_guard` (85 tests, clean run OK).

| Mutant | Change | Result | Named red tests (examples) |
| --- | --- | --- | --- |
| (a) remove TNP delete-set exemption | `tnp_guard.py` exemption `if` → `if False:` | 8 failures, 7 errors | `TnpExemptionTest.test_Should_pass_post_verify_with_a_clean_audit_When_an_owner_of_a_profile_is_deleted`, `test_Should_stay_clean_When_a_deleted_owner_of_a_reference_is_in_the_delete_set`, `DeleteTest.test_Should_remove_the_tip_and_move_the_tip_back_When_the_last_feature_is_deleted` |
| (b) excuse every vanished owner | drop `record["owner"] in deleted and` | 3 failures | `TnpExemptionTest.test_Should_grade_broken_When_an_owner_vanished_outside_the_delete_set`, `test_Should_grade_broken_When_a_second_owner_vanished_that_the_set_does_not_name`, `test_tnp_guard.LayerOneTest.test_a_deleted_snapshot_owner_is_broken_at_layer_one` |
| (c) no relink after undo | `documents.py` `relink_failures = []` | 2 failures | `UndoTest.test_Should_keep_following_the_varset_When_a_bound_pad_is_deleted_and_undone`, `UndoTest.test_Should_report_the_binding_in_errors_When_an_expression_cannot_be_set_again` |
| (d) no relink after abort | `transaction.py` relink call → `pass` | 1 failure | `RollbackTest.test_Should_keep_following_the_varset_When_an_aborted_delete_restored_the_bound_pad` |
| (e) drop the dependents check | `features.py` `if dependents and not with_dependents:` → `if False:` | 4 failures | `DeleteTest.test_Should_refuse_naming_the_dependent_When_a_profile_sketch_is_deleted_alone`, `test_Should_refuse_naming_the_bound_pad_When_a_bound_varset_is_deleted`, `test_Should_refuse_naming_the_next_feature_When_a_middle_feature_is_deleted_alone`, `test_Should_carry_the_dependents_code_When_the_dispatcher_maps_the_refusal` |

All five mutants turn named tests red.

## Live run (container `fcb-desktop`, FreeCAD 1.1.4, image built from the copy)

Build: `uv run python scripts/build_addon.py --release` (wheel `freecad_buddy-0.1.1`), `docker compose -f tests/close-loop/docker/compose.yaml up -d --build`, `fcb-freecad start`; `/healthz` gave `freecad_pid` 724. Tool calls went over MCP (`http://127.0.0.1:18765/mcp`) with the `mcp` Python client (`scripts/mcpcall.py`), because the session's `freecad-buddy-docker` tool list predates the new tool. `tools/list` included `document_object_delete` (51 tools). Evidence: `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-11-r1\evidence\` (one JSON per call, screenshots `S1`..`S8`); scripts in `...\13-11-r1\scripts\`.

Fixture `Del1311` (one `script_exec` transaction "fixture"): `Body` = `Sketch1` (20x20) → `Pad1` (10 mm) → `Sketch2` (10x10 at z 10) → `Pad2` (Tip, `Length = VS.L`, VS.L = 5); VarSet `VS`; `Body001` = `Sketch3` → `Pad3` (8 mm) at x 40.

| Step | Call | Result | Evidence |
| --- | --- | --- | --- |
| Refusal, profile sketch | delete `[Sketch1]` | `INVALID_INPUT`, `detail.code` `delete.has_dependents`, "objects that depend on the delete set: Pad1" | `04-refuse-sketch1.json` |
| Refusal, bound VarSet | delete `[VS]` | `delete.has_dependents`, names `Pad2` | `05-refuse-vs.json` |
| Refusal, Origin plane | delete `[XY_Plane]` | `delete.origin_object`, "XY_Plane belongs to the Origin of Body" | `06-refuse-origin-plane.json` |
| Refusal, unknown | delete `[Nope]` | `INVALID_INPUT` "unknown object in objects: Nope" | `07-refuse-unknown.json` |
| Refusals change nothing | `script_exec` read | 25 objects, `UndoCount` 1 before and after | `03`, `08` |
| Preview | `preview_dry_run` delete `[Pad2]` | OK; diff `deleted: ["Pad2"]`, volume 5300 → 4800; live document unchanged (25 objects, UndoCount 1) | `09`, `10` |
| Tip delete | delete `[Pad2]` | OK, `deleted ["Pad2"]`, `post_verify.passed` true, TNP `CLEAN` (7 PASS); Tip = `Pad1`; Group = Sketch1, Pad1, Sketch2 | `11`, `12`, `S2` |
| Undo | `document_undo` | OK, `errors []`; Pad2 back, Tip = Pad2, BaseFeature Pad1, Visibility true, `ExpressionEngine [('Length','VS.L')]`, `VS.InList = [Pad2]` | `14`, `15`, `16`, `S3` |
| Delete with dependents | delete `[Sketch1]`, `with_dependents: true` | OK, `deleted [Sketch1, Pad1, Pad2]`, `dependents [Pad1, Pad2]`, TNP `CLEAN`; Tip None; Sketch2 stays | `22`, `23`, `S5` |
| Undo | `document_undo` | Sketch1, Pad1, Pad2 back; Tip Pad2; `VS.InList [Pad2]` | `24`, `25` |
| Whole Body | delete `[Body001]` | OK, `deleted` = Body001, Origin002, 3 axes, 3 planes, Origin003, Sketch3, Pad3; TNP `CLEAN`; tree shows Body and VS only | `26`, `27`, `S6` |
| Undo | `document_undo` | all 11 objects back | `28`, `29` |

Visual check: `S1` (before) and `S3` (after undo) are the same picture (stepped block + cube); `S2` shows the Tip delete; `S4` shows the taller small pad after VS.L = 7; `S5` shows only Sketch2 left in Body; `S6` shows Body001 gone. The redo arrow is active in `S3`.

## R1-U1: undo and redo counts in the GUI host (closed)

| Moment | UndoCount | RedoCount | UndoNames / RedoNames | Pad2 |
| --- | --- | --- | --- | --- |
| After fixture | 1 | 0 | `[fixture]` / `[]` | Length 5, ZMax 15 |
| After delete Pad2 | 2 | 0 | `[buddy: delete Pad2, fixture]` / `[]` | gone |
| After `document_undo` (relink ran) | **1** | **1** | `[fixture]` / `[buddy: delete Pad2]` | back, `OutList` has VS |
| After `doc.redo()` (script_exec) | 2 | 0 | redo re-deleted Pad2; Tip Pad1 | gone |
| After `document_undo` again | 1 | 1 | as above | back |
| After `feature_parameters_define` VS.L = 7 | 2 | 0 | `[buddy: define parameters on VS, fixture]` | **Length 7.0, ZMax 17.0** (`changed` names Body, Pad2) |

The re-link adds no undo step (UndoCount returns to 1), redo still redoes the delete, and the restored pad follows the VarSet. `addon.log`: 0 lines with `error` or `traceback`.

## Acceptance and quality-bar map

| Item | Evidence | Result |
| --- | --- | --- |
| AC1 Tip pad delete, one undo restores | infc `UndoTest.test_Should_restore_the_tip_and_the_visibility_When_a_tip_delete_is_undone`; live steps 11-16 | PASS |
| AC2 pad owning `Profile` deleted → OK, TNP `CLEAN` | infc `TnpExemptionTest.test_Should_pass_post_verify_with_a_clean_audit_When_an_owner_of_a_profile_is_deleted`; live 11, 22 | PASS |
| Q1 bracket, result fields | live 11, 22, 26 | PASS |
| Q2 dependents and origin refusals | live 04-07; mutant (e) | PASS |
| Q3 Body delete, Tip valid | live 12, 26-27 | PASS (see F1 for visibility) |
| Q4 TNP exemption only for the delete set | mutants (a), (b) | PASS |
| Q5 rollback proof by `state_probe` | infc `RollbackTest.test_Should_restore_the_object_set_and_prove_it_When_a_delete_fails_after_a_removal` | PASS (infc only) |
| Q6 one undo restores names, Group, Tip, BaseFeature, Visibility, expression links | live 15-16, 25, 29; mutants (c), (d) | PASS |
| Q7 relink adds no undo step, keeps redo | R1-U1 table | PASS |
| Q8 preview | live 09-10 | PASS |
| Q9 other envelopes unchanged | envelope table | PASS |
| Q10 design doc, AD-17 | `mcp-tools-design.md` row shipped, counts 50/51, §3.7.2 schema matches the live `inputSchema`; refusals use `detail.code` only | PASS |

## Findings

### F1 (medium, product, outside Q1-Q10): new Tip stays hidden after a Tip delete

- Where: `src/freecad_buddy/usecases/features.py:2486` `body.removeObject(target)` and `:2489` `document.removeObject(name)` in `document_object_delete`. The Python path never runs the PartDesign view provider's `onDelete`.
- FreeCAD reference: `docs/references/FreeCAD/src/Mod/PartDesign/Gui/ViewProvider.cpp:345-350`: "If the visible object is the one being deleted, we make the previous object visible." `Std_Delete` calls this; `Document.removeObject` does not.
- Reproduction with typed tools only (document `VisRepro`): `feature_body_create Body`; `sketch_create SkA` (XY, Body) + circle r 10 with Coincident and Radius; `feature_pad PadA` 5 mm; `sketch_create SkB` + circle r 4; `feature_pad PadB` 15 mm. Visibility: PadA false, PadB true (normal PartDesign state). Then `document_object_delete {"objects":["PadB"]}` → OK, Tip = PadA, but PadA `Visibility` stays **false**. `S7` (before) shows the stepped cylinder; `S8` (after) shows only the two sketch circles and no solid. Same in `Del1311` (`13-visibility-after-delete.json`, `S2`: Pad1 hidden).
- Effect: the result is `OK` and geometry is correct, but the human sees an empty Body until they toggle visibility. One `document_undo` restores the old visibility.
- Not fixed (verifier does not edit product code).

### F2 (low, doc): `preview_dry_run` input text

`src/freecad_buddy/hosts/tool_catalog.py:1039` (at 4ee8c26b): `"description": "a registered sketch_/feature_ mutation tool"`. Preview accepts `document_object_delete` (live step 09), so the text is now incomplete.

### Notes (no action for this Story)

- Refusal envelopes carry the Python traceback in `detail.data.traceback` (seen on all four refusals). This comes from `rpc_dispatch` and applies to every tool; not new.
- `feature_pad` leaves the profile sketch visible (fixture `VisRepro`); pre-existing behaviour.
- TC-02 has no delete case yet; `APPENDIX-A-deferred-coverage.md` records it.

## Teardown

`fcb-freecad stop` (window close timed out on the unsaved documents; the helper killed pid 724), `docker compose ... down` (container and network removed), both worktrees removed (`git worktree list` shows neither). Scratch: `scratchpad\verifier-13-11\`. Host port 8765 and `%APPDATA%\FreeCAD\v1-1\user.cfg` not touched. Nothing left running.

## Round 2

Artifact: head of `story/13-11-object-delete` = `e7163db49e374b9c3a7d9eef3c7c2a2a10354145` (`b83276a0` triage fixes + `e7163db4` lens patch). Fresh detached copy `fcb-verify-13-11` at e7163db4, removed after the run. Triage: `triage-13-11-r2.md`; red team: `redteam-13-11.md`.

### Verdict round 2

**PASS.** RT-1, RT-2, RT-3 and F1 are fixed, and each fix is pinned: reverting it turns named tests red. F2 is fixed, but no test pins the text. F1 and RT-1 pass live in the GUI. One new low finding (R2-1): the container rule that the builder widened ignores a non-Group link from a holder to its own member.

### Gates (copy at e7163db4, Git Bash)

| Command | Result |
| --- | --- |
| ruff check / check_imports / gen_schemas --check / check_provenance / check_status_vocab / check_skill_shape | all OK (exit 0) |
| `ruff format --check` on changed `.py` files since 3c8efd8d | 10 files already formatted |
| `uv run --extra dev pytest tests/external -q` | **2082 passed, 6 skipped** |
| freecadcmd `tests/run_tests.py` (temp cfg, `FREECAD_USER_HOME` temp) | **Ran 1104 tests, OK (skipped=1)**; source probe: copy's `src` |

### Revert proofs (fix removed in the copy, then `git checkout -- src`; run `infc.test_object_delete` + `infc.test_tnp_guard`, clean = 99 OK)

| Row | Revert | Red tests |
| --- | --- | --- |
| RT-1 | `_OPERAND_GROUP_TYPES = ()` (`features.py:42`) | `test_Should_refuse_naming_the_boolean_When_an_operand_body_is_deleted`, `test_Should_drop_the_operand_volume_When_the_boolean_is_deleted_with_its_operand` |
| RT-2 | `if only_members:` without `_expression_names` (`features.py:2415`) | `test_Should_refuse_naming_the_body_When_an_expression_on_it_names_a_member`, `..._by_label`, `test_Should_delete_the_body_and_succeed_When_dependents_are_allowed_for_a_bound_member` |
| RT-3 | link-array branch `if False:` (`features.py:2360`) | `test_Should_delete_the_elements_with_the_array_When_a_link_array_is_deleted`, `test_Should_delete_the_elements_When_the_array_is_a_python_link` |
| F1 | `previous.Visibility = True` → `pass` (`features.py:2538`) | `test_Should_show_the_previous_feature_When_a_visible_tip_is_deleted` |
| F2 | `git apply -R` of the `tool_catalog.py` diff | **none**: `gen_schemas --check` OK, external 2082 passed. A text-only fix; no test pins the `preview_dry_run` description. |

### Widened container rule (`_is_member_container`, `features.py:2374`: any `App::GroupExtension` holder except `PartDesign::Boolean`)

Probe `tests/uat/run/13-11-r2/scripts/groupprobe.py` (freecadcmd, copy's `src`), result `groupprobe.json`:

| Holder | Delete | Result |
| --- | --- | --- |
| `App::DocumentObjectGroupPython` G, member Box | `[Box]` | OK, G.Group `[]` |
| `Fem::FemAnalysis`, member Box | `[Box]` | OK, Group `[]` |
| `Assembly::AssemblyObject` (GroupExtension true), member Box | `[Box]` | OK, Group `[]` |
| `Fem::FemPostPipeline` (GroupExtension true), member `Fem::FemPostClipFilter` | `[Clip]` | OK, Group `[]` (the pipeline re-chains its filters on a Group change) |
| `App::FeaturePython` + `App::GroupExtensionPython` Holder, `PropertyLink Source` = Box, Box also in Group | `[Box]` | **OK, Holder.Source silently set to `None`** → R2-1 |

FreeCAD source sweep (`docs/references/FreeCAD/src`): the GroupExtension holders in C++ are DocumentObjectGroup, Part, Datums/LCS, BodyBase/Body, FemPostPipeline, FemPostBranchFilter and PartDesign::Boolean. In Python they are Assembly views and simulations, BIM BuildingPart, Project and Site, the CAM Job, FEM solvers and post visualizations. Of these, only `PartDesign::Boolean` keeps stale geometry when it loses a member, and it is now a dependent. `ArchSite` keeps `Terrain` out of `Group` (`ArchSite.py:926-934`). The CAM Job links Operations, Model and Stock through properties. Its `Group` holds none of them, so a held object outside `Group` still counts as a dependent. The Body's Tip and BaseFeature links are handled by `Body.removeObject`. I found no stock type that both links to a member by property and lists it in `Group`, so R2-1 needs a custom or Python feature.

**R2-1 (low, product):** `features.py:2414` `only_members = _is_member_container(obj) and held <= _names(obj.Group)` compares names only. A holder that also links to a Group member through another property (`PropertyLink`, link list) is exempt. The delete returns `OK` and clears that link. The cheapest fix is to exempt the holder only when the member reaches its `OutList` through `Group` alone, by checking the holder's other link properties. Reproduction: the last row above.

### Live (container `fcb-desktop`, rebuilt from the copy, FreeCAD 1.1.4)

The first `fcb-freecad start` ran right after `compose up` and FreeCAD aborted ("no Qt platform plugin could be initialized"). The desktop was not ready yet. A second start worked (`freecad_pid` 821). Calls over MCP at `127.0.0.1:18765/mcp`. Evidence: `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-11-r2\evidence\`.

| Step | Result | Evidence |
| --- | --- | --- |
| Fixture, typed tools only: Body, SkA circle r10 → PadA 5 mm, SkB circle r4 → PadB 15 mm | PadA hidden, PadB visible, Tip PadB, volume 2073.451 | `02`..`06`, `S1` |
| F1: delete `[PadB]` (visible Tip) | OK, TNP CLEAN, `touched [PadB, PadA, Body]`; Tip PadA, **PadA Visibility true**, volume 1570.796; GUI shows the solid disc | `07`, `08`, `S2` |
| Undo | PadB back and visible, PadA hidden again, UndoCount 7, RedoCount 1 | `09`, `10` |
| RT-1 fixture (`script_exec`, one transaction): Body2 (10x10x10 at x 25..35) fused into Body by `Bool` | Tip Bool, volume 3073.451 | `11`, `S3` |
| RT-1: delete `[Body2]` | `INVALID_INPUT` `delete.has_dependents` "objects that depend on the delete set: Bool"; state unchanged | `12`, `13` |
| RT-1: delete `[Body2]`, `with_dependents: true` | OK, `dependents [Bool]`, TNP CLEAN; Tip PadB (visible), **volume 2073.451** (operand volume gone); GUI shows no cube | `14`, `15`, `S4` |
| Undo | Bool, Body2, PadC back; Tip Bool; volume 3073.451 | `16`, `17` |

`addon.log`: 0 lines with `error` or `traceback`.

### Teardown round 2

`fcb-freecad stop` (close timed out on the unsaved document; pid 821 killed), `docker compose down`, copy removed (`git worktree list` has no `fcb-verify`). Nothing left running.
