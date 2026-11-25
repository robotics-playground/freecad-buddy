# Story 13-5: verification report

Verifier: verifier-13-5. Date: 2026-11-24.
Artifact: commit `3527cc20edbd082a8dd960836e5c377942097cf9` (branch `story/13-5-multi-object-export`, base `6c60a23`).
Copy: detached worktree `D:\Work\Personal\Sources\fcb-verify-13-5` (removed after the run).
UAT evidence: `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-5-r1\` (run `13-5-r1`).

## Verdict

**FAIL.** One high product defect: a multi-object 3MF written by the GUI host is not a valid 3MF, and its `verify_export_3mf` returns `SPEC_FAILED`. AC1 is not met for 3MF on the host the Story targets. Every other gate, mutant and UAT step passes.

## Defect D-1 (high): multi-object 3MF from the GUI host has duplicate content types

- **What.** `export_3mf` with two or more objects, in the GUI FreeCAD (container `fcb-desktop`, FreeCAD 1.1.4), writes a `[Content_Types].xml` with one `<Default Extension="png" .../>` line per object. lib3mf refuses the file: `lib3mf.parses` fails with `Lib3MFException 5: A content type is duplicated.` The verdict is `SPEC_FAILED`, so no per-object 3MF check runs.
- **Cause (measured).** In the GUI, FreeCAD's 3MF writer adds one thumbnail resource per mesh (`src/Mod/Mesh/Gui/ThumbnailExtension.cpp:105-111`, `res.extension = "png"`), and writes one `Default` line per resource (`src/Mod/Mesh/App/Core/IO/Writer3MF.cpp:206-207`). The Story writes several meshes through `Mesh.export` in `usecases/shim.py:567-581` (`export_meshes`), and `usecases/exports.py:407` (`_name_3mf_objects`) copies `[Content_Types].xml` unchanged. Headless FreeCAD has no thumbnail extension, so `freecadcmd` tests do not see it.
- **Evidence** (`tests/uat/run/13-5-r1/evidence/`):
  - `summary.json` key `11.verify.3mf`: `SPEC_FAILED`, `lib3mf.parses` false. Same for `11.omitted.3mf`.
  - `cause-summary.json`: FreeCAD's own `Mesh.export` of three meshes, no bridge rename (`cause-raw-three.3mf`) has `png_defaults: 3`; of one mesh (`cause-raw-one.3mf`) has `png_defaults: 1`. The product file `tc-07-11-three.3mf` has `png_defaults: 3`.
  - Same file with the duplicate `Default` lines removed (`cause-dedup-three.3mf`), graded by the Story's own `mesh3mf_oracle`: `ok: true`, `lib3mf.object_count` 3, `lib3mf.object_names` `["Alpha","Beta","Gamma"]`, three `trimesh_3mf.object_volume:*` passed. So the duplicate content type is the only blocker.
  - One-object 3MF in the GUI (K-1 path) still verifies `OK` (`cause-summary.json` key `one_object_3mf`).
- **Reproduction.** Container `fcb-desktop`, FreeCAD GUI running. `document_create`, `script_exec` with the TC-07-11 three-body script, `export_3mf { objects: ["BoxA","Cyl","Sph"] }`, `verify_export_3mf` → `SPEC_FAILED`, `lib3mf.parses`. Script: `tests/uat/run/13-5-r1/uat_13_5.py`.
- **Test gap.** The infc tests run headless (no thumbnails). `tests/external/test_exports_3mf_names.py` uses a synthetic archive. No test reads a GUI-written multi-object 3MF with lib3mf.
- Not fixed (verifier rule).

## Gates (in the copy)

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run python scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `uv run python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `uv run python scripts/check_skill_shape.py` | exit 0 |
| `uv run ruff format --check` on the 12 changed `.py` files | 10 clean; `scripts/check_imports.py` and `tests/external/test_check_imports.py` would reformat. Both also fail at base `6c60a23` (pre-existing) |
| `uv run pytest tests/external -q` | 1 failed, 1860 passed, 4 skipped. Failed: `test_marshal_self_submit.py::test_submitting_to_a_loop_this_thread_must_pump_deadlocks` (`assert time.monotonic() - start >= 0.2`, a timing check). Re-run alone: 3 passed. Not touched by this Story. |
| `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` | `Ran 884 tests`, `OK (skipped=1)`, exit 0. Probe under the same `freecadcmd` with the runner's path setup imported `D:\Work\Personal\Sources\fcb-verify-13-5\src\freecad_buddy\usecases\exports.py` (the copy, not the installed addon). |

## Mutants (in the copy, each reverted with `git checkout -- src`; final `git status` clean)

Baselines: `infc.test_export_tools` 46 run, 0 failed; external oracle/names/surface files 105 passed.

| Mutant | Change | Red tests |
| --- | --- | --- |
| (a) single-object refusal restored | `exports.py:_resolve_export_objects` raises `export supports a single object; got multiple` when `len(objects) != 1` | 13 infc, e.g. `test_Should_pass_with_one_volume_check_per_object_When_three_objects_go_to_step`, `test_Should_write_one_merged_mesh_When_three_objects_go_to_stl` |
| (b) 3MF name rewrite skipped | `exports.py:330` call replaced by `pass` | `test_Should_name_each_mesh_object_by_label_When_three_objects_go_to_3mf`, `test_Should_leave_no_file_When_naming_the_3mf_objects_fails` |
| (b2) 3MF name check always passes | `export_oracle.py` `lib3mf.object_names` `passed: True` | `test_Should_fail_the_name_check_When_a_mesh_object_carries_another_name` |
| (c1) STEP: last object's volume check dropped | `_object_volume_checks` skips the last object | `test_Should_pass_with_one_volume_check_per_object_When_three_objects_go_to_step` |
| (c2) 3MF: last object's volume check dropped | `_object_checks` zips `objects[:-1]` | `test_Should_pass_every_object_check_When_a_multi_object_3mf_matches_its_objects` |
| (d1) STL writer stops recording `facet_counts` | `exports.py:343` → `facet_counts = None` | `test_Should_record_one_facet_count_per_object_When_touching_objects_go_to_stl` |
| (d2) STL oracles weld as one mesh again (R1-H1) | `_facet_groups` always one group; `stl_oracle` per-object branch disabled | `test_Should_pass_both_oracles_When_touching_boxes_are_graded_per_object` |
| (e1) planted STEP per-object mismatch must fail | per-object `passed` forced `True` | `test_Should_fail_and_name_the_object_When_one_recorded_object_volume_is_wrong` (infc) |
| (e2) planted 3MF per-object mismatch must fail | `trimesh_3mf.object_volume:*` `passed` forced `True` | `test_Should_fail_and_name_the_object_When_one_object_volume_is_wrong` (external) |

All mutants killed.

## Quality bar (Q1..Q11)

| Q | Result | Evidence |
| --- | --- | --- |
| Q1 several objects accepted, refusal gone | PASS | `exports.py:97` `_resolve_export_objects`; mutant (a); UAT `11.write.*` |
| Q2 omitted = visible solids; empty refused | PASS | `exports.py:97-151`; infc `test_Should_export_only_the_body_and_free_solids_When_objects_are_omitted` (`test_export_tools.py:438`); UAT `11.omitted.*` objects `["BoxA","Cyl","Sph"]`, `12.two` `["BoxA","BoxB"]`, `12.hidden` `["BoxA"]`, `11.empty` `document has no objects to export` |
| Q3 STEP product per object named by Label | PASS | `shim.py:522` `export_step_objects`; UAT `11.step_products` `["tc07_three_bodies","Alpha","Beta","Gamma"]`; GUI import tree shows Alpha, Beta, Gamma |
| Q4 3MF one named mesh per object, valid 3MF | **FAIL in GUI** | names correct (`11.3mf_object_tags`, trimesh keys `Alpha`, `Beta`, `Gamma`); archive invalid for lib3mf — D-1 |
| Q5 STL one merged mesh | PASS | `exports.py:314-343`; GUI STL import is one mesh object `tc-07-11-three` holding three solids |
| Q6 per-object verify STEP/3MF, total only STL, mismatch named | STEP PASS, STL PASS, 3MF **not reachable in GUI** (D-1) | STEP: `11.verify.step` three `export_step.object_volume:*` + `objects_matched` passed; `11.planted.step` `SPEC_FAILED`, failed `export_step.volume`, `export_step.object_volume:Cyl`. STL: `11.verify.stl` OK, no `object_volume` id. 3MF: `11.planted.3mf` fails only on `lib3mf.parses`; per-object 3MF logic proven on the deduplicated file and by mutants (c2), (e2) |
| Q7 single-object numbers and ids unchanged (K-1) | PASS | infc `test_Should_keep_the_single_object_check_ids_When_one_object_is_verified` (`test_export_tools.py:616`); UAT `12.single` ids `export_step.volume`, `.valid`, `.topology_counts`, `.schema`, volume 6000.0; one-object 3MF in GUI `OK` |
| Q8 shape-less / solid-less object refused naming it | PASS | `exports.py:177` `_selected_shapes`; infc `test_Should_refuse_naming_the_object_When_a_selected_object_has_no_solid` (`:588`) |
| Q9 additive schema; FreeCAD only through shim | PASS | `gen_schemas --check OK`; `check_imports OK` with `Import` in whitelist (decision 22) |
| Q10 design text matches | PASS | `verification-design.md` §6.2-6.4 and `mcp-tools-design.md` §3.5 describe per-object checks, name rewrite, order matching. They do not mention the GUI thumbnail parts (D-1) |
| Q11 three-body container UAT + GUI visual | STEP PASS, STL PASS, 3MF **FAIL** (D-1) | below |

## AC map

| AC | Code | Tests | UAT |
| --- | --- | --- | --- |
| AC1 three-body export, STEP/3MF per-object OK, STL total OK | `exports.py:255`, `:314-343`, `:490`, `:550`; `shim.py:522`, `:536`, `:567`; `export_oracle.py:316`, `:426`; `tool_catalog.py:101-119`; `rpc_proxy.py:50-68` | infc `:380`, `:652`, `:690`; external `test_export_oracle.py:245`, `:359` | STEP OK, STL OK, **3MF SPEC_FAILED (D-1)** |
| AC2 one-object ids and numbers unchanged | `exports.py:251-256` single path, `:490-497` | infc `:616` | `12.single` OK |
| AC3 altered per-object volume → not OK, failed id names object | `exports.py:550-585`; `export_oracle.py:345` | infc `:399`; external `:265`; mutants (e1), (e2) | STEP PASS (`export_step.object_volume:Cyl`); 3MF blocked by D-1 |

## UAT (container `fcb-desktop`, image `fcb-desktop:local` built from the copy, FreeCAD 1.1.4)

MCP calls: host `uv` env, runner client `tests/uat/runner/mcp_client.py` at `http://127.0.0.1:18765/mcp` (the session's MCP servers `freecad-buddy-docker` and `cua-driver-docker` were not connected). GUI: `cua-driver` 0.28.1 CLI through `docker exec`. All MCP results: `evidence/mcp-log.json`, compact: `evidence/summary.json`.

### TC-07-11: several objects to one file per format — FAIL (3MF, D-1)

| Step | Result | Evidence |
| --- | --- | --- |
| Three writers OK, `verified` false, `objects` `["BoxA","Cyl","Sph"]` | PASS | `summary.json` `11.write.*` |
| STEP verify OK, three `object_volume` + `objects_matched` | PASS (1000.0, 125.66, 523.6) | `11.verify.step` |
| 3MF verify OK with count, names, per-object volumes | **FAIL**: `SPEC_FAILED`, `lib3mf.parses` | `11.verify.3mf`; D-1 |
| STL verify OK, total only | PASS (`trimesh_stl.volume_band` 1634.03, no `object_volume`) | `11.verify.stl` |
| STEP product names | PASS | `11.step_products` |
| 3MF object names | PASS (file content) | `11.3mf_object_tags`; trimesh `Scene ['Alpha','Beta','Gamma']` |
| Outside re-import (`Part.read`) volume 1649.26 | PASS (1649.26, 3 solids) | `11.reimport` |
| Unknown name refused, no file | PASS (`unknown object: NoSuchObject`, `file_exists: false`) | `11.unknown` |
| Empty document refused | PASS | `11.empty` |
| Added: omitted `objects`, each format | STEP PASS, STL PASS, 3MF FAIL (D-1) | `11.omitted.*` |
| Added: planted wrong file (Cyl height 20 in file) | STEP PASS: `SPEC_FAILED`, failed `export_step.volume`, `export_step.object_volume:Cyl`, message names `Cyl`. 3MF: fails only on `lib3mf.parses` (D-1) | `11.planted.*` |
| Visual before | PASS: box, cylinder, sphere as built; tree Alpha, Beta, Gamma | `evidence/tc-07-11-before.png` |
| Visual STEP, File > Import, Isometric, Fit All | PASS: three solids, same layout; tree `tc07_three_bodies` > Alpha, Beta, Gamma | `evidence/tc-07-11-after-step.png` |
| Visual 3MF, File > Import | three solids visible, same layout. FreeCAD 1.1.4 imports the 3MF as one mesh `tc-07-11-three`: names are not shown in the tree (FreeCAD importer limit, not this Story) | `evidence/tc-07-11-after-3mf.png` |
| Visual STL, File > Import | PASS: one mesh `tc-07-11-three`, three solids visible | `evidence/tc-07-11-after-stl.png` |

### TC-07-12: omitted `objects` — PASS

| Step | Result | Evidence |
| --- | --- | --- |
| Single-object doc, no `objects` | PASS: `objects` `["Box"]`; verify OK, volume 6000.0, no `object_volume` id | `12.single` |
| `objects: []` behaves as omitted | PASS: `["Box"]` | `12.empty_list` |
| Two visible boxes | PASS: `["BoxA","BoxB"]`, both `object_volume` passed | `12.two` |
| Hidden BoxB left out | PASS: `["BoxA"]` | `12.hidden` |
| Outside re-import 6000.0 | PASS (bbox 10 x 20 x 30) | `12.reimport` |
| Visual | PASS: one box, about 1 : 2 : 3 | `evidence/tc-07-12-after.png` |

Foreground delivery (container desktop only) was used for: MDI tab switches and one tree-expand click. Background clicks on those targets did not land (verified from fresh state). The AT-SPI `Toggle` on a tree item selected a different document; it was not used again.

## Observations (no change requested)

- `verify_export_step` matches re-imported products to objects by order and solid count; it does not read the product names. Two objects of equal volume in swapped order would pass. Names are checked by the infc test and the UAT grep only. Decision 20 says "plus a product-name check"; it is not in the verifier. Low.
- External gate flake: `test_marshal_self_submit.py::test_submitting_to_a_loop_this_thread_must_pump_deadlocks` (timing) is not in the known-unstable list.

## Case change (for the leader to commit)

File `tests/uat/testcases/TC-07-verification-and-export-pairing.md`, TC-07-11: three steps added (omitted `objects` per format, planted wrong file, GUI File > Import visual per format). Full diff: `tests/uat/run/13-5-r1/tc07-case-change.diff`. No scenario JSON added. Scripts used: `tests/uat/run/13-5-r1/uat_13_5.py`, `uat_3mf_cause.py`, `gui_import.sh`, `iso_fit_shot.sh`.

## Teardown

`fcb-freecad stop` (window close timed out, process killed by the helper), `docker compose ... down` (container and network removed). Worktree `fcb-verify-13-5` removed.

---

# Round 2

Artifact: commit `9af2ac8` (fixes `80e0b00` from the triage and `9af2ac8` from the round-2 lens review; triage `triage-13-5-r2.md`, red team `redteam-13-5.md`). Copy: a new detached worktree at `9af2ac8`. It is removed now.
UAT evidence: `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-5-r2\` (run `13-5-r2`).

## Round 2 verdict

**PASS.** D-1 is fixed and proven in the GUI host. Every triage row has a test that turns red when its fix is reverted. Single-object outputs are equal to the `6c60a23` outputs (K-1). TC-07-11 and TC-07-12 pass in the container, and the visual check passes for each re-imported file. One low observation is open (O-1), and it does not block.

## Gates (copy at 9af2ac8)

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `check_imports.py` / `check_status_vocab.py` / `gen_schemas.py --check` / `check_skill_shape.py` | OK / OK / OK / exit 0 |
| `ruff format --check` on changed `.py` files | 11 clean. `scripts/check_imports.py` and `tests/external/test_check_imports.py` fail this check at base `6c60a23` too (pre-existing). |
| `uv run pytest tests/external -q` | 1 failed, 1878 passed, 4 skipped. The failure is the known unstable `test_managed_venv.py::...pythonhome`. It passes alone (1 passed). |
| `freecadcmd -u <tmp> -s <tmp> tests/run_tests.py` | `Ran 897 tests`, `OK (skipped=1)` |

## Triage rows: revert each fix, then the named tests go red

Script: `tests/uat/run/13-5-r2/mutants.py`. Output: `host/mutants.json`. Baseline: the infc export tests have 59 run and 0 failed. The external export/names/surface files have 123 passed. After the run, `src` was restored with `git checkout` and `git status` is clean.

| Row | Fix reverted | Red tests |
| --- | --- | --- |
| D-1 | `[Content_Types].xml` copied as written (no de-duplication) | `test_exports_3mf_names.py::test_Should_read_the_archive_with_lib3mf_When_the_gui_writer_repeated_the_png_type`, `::test_Should_read_every_name_with_lib3mf_When_a_real_gui_written_archive_is_named`. Both read a real GUI-written fixture with lib3mf. |
| RT-1 | visibility from the object's own flag only | infc `test_Should_export_only_the_cut_When_a_boolean_hides_two_bodies_in_the_gui_way`, `test_Should_skip_the_tip_of_a_hidden_body_When_objects_are_omitted`, `test_Should_skip_a_solid_inside_a_hidden_part_When_objects_are_omitted` |
| RT-2 | the mirror consumes its source again | infc `test_Should_export_a_visible_mirror_source_with_the_mirror_When_objects_are_omitted` |
| RT-3 / RT-6 | old escapes back (`&#9;`, `&#10;`, raw control characters) | 4 cases of `test_Should_read_the_name_with_lib3mf_as_spaces_When_a_label_holds_a_control_character` (newline, tab, bell, CR), `test_Should_expect_the_file_name_When_an_object_label_holds_a_control_character`. Each reads the file with lib3mf. |
| RT-4 | shared shape not copied (`feature.Shape = shape`) | infc `test_Should_name_each_object_and_verify_When_two_objects_share_one_shape` |
| RT-4 + RT-5 | whole writer back to `Import.export(objects, exportHidden=True)` | infc `test_Should_write_what_it_recorded_When_a_selected_part_holds_a_hidden_child`, `test_Should_name_each_object_and_verify_When_two_objects_share_one_shape`, `test_Should_grade_only_the_solids_...`, `test_Should_name_the_product_after_the_object_name_When_a_label_is_empty` |
| RT-7 | whole mixed shape graded (solid + loose face) | infc `test_Should_grade_only_the_solids_When_an_object_holds_a_solid_and_a_loose_face` |
| L-1 | `export_step.object_names` check not added | infc `test_Should_fail_the_name_check_When_a_recorded_product_name_is_not_in_the_file` (and 2 more) |
| round-2 lens: STEP escapes | product names not decoded | infc `test_Should_pass_the_name_check_When_labels_are_long_or_hold_special_characters`; external `test_exports_step_names.py::test_Should_decode_the_escape_the_writer_used_...` (5 cases) |
| round-2 lens: wrapped lines | wrapped names not joined | external `test_Should_join_a_name_the_writer_wrapped_across_lines`; infc long-label test |
| round-2 lens: root product | scratch document not named after the document | infc `test_Should_name_the_root_product_after_the_document_When_several_objects_go_to_step` |
| RT-8 | not fixed (deferred, triage) | not tested |

## K-1: single-object outputs against 6c60a23

Probe `k1_single.py` under host `freecadcmd`, run once with the base `src` (`git archive 6c60a23`) and once with the head `src`. Cases: a Cylinder, a Body with an AdditiveBox (`objects: ["Body"]`), a hidden sole Sphere, and `objects: ["BoxA"]` in a two-object document. Formats: STEP, STL, 3MF. Outputs: `host/k1-base-6c60a23.json`, `host/k1-head-9af2ac8.json`.

- Export results and verify results (STEP verify, STL and 3MF self-read) are equal, except for the added `objects` key.
- STL files: byte-equal. STEP files: byte-equal after the `FILE_NAME` time header is removed.
- 3MF files: every archive part is byte-equal. The archive hash differs only by the zip entry time.

## Colours (the builder's note)

- Single-object STEP: no colour entities (`COLOUR_RGB` or `STYLED_ITEM`) at `6c60a23` or at `9af2ac8`. The single path calls `TopoShape.exportStep`, which writes no colours. K-1 holds: nothing is lost.
- Multi-object STEP: no colour entities at `9af2ac8` (UAT, `summary.json` `11.step_colour_entities`: 0). The round-1 GUI file from `3527cc2` also has 0 (`13-5-r1/evidence/tc-07-11-three.step`). The App-level `Import.export` writes colours only when the caller passes `(object, colours)` tuples (`Mod/Import/App/AppImportPy.cpp:293-345`), and no version of the Story did that. So "no colours" is not a regression. Multi-object STEP never had colours.

## Round 2 UAT (container `fcb-desktop`, image built from the copy at 9af2ac8, FreeCAD 1.1.4)

Before the run, I checked that the installed addon in the container holds the round-2 code: `_unique_content_types` is present in `~/.local/share/FreeCAD/v1-1/Mod/FreeCADBuddy`. MCP results: `evidence/mcp-log.json`. Compact results: `evidence/summary.json`. All screenshot paths below are under `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-5-r2\evidence\`.

### TC-07-11: several objects export to one file per format and verify per object — PASS

| Step | Result | Evidence |
| --- | --- | --- |
| Three writers `OK`, `verified` false, `objects` `["BoxA","Cyl","Sph"]` | PASS | `summary.json` `11.write.*` |
| STEP verify `OK`: `object_volume` BoxA 1000.0, Cyl 125.66, Sph 523.6; `objects_matched` 3; new `export_step.object_names` passed | PASS | `11.verify.step` |
| 3MF verify `OK`: `lib3mf.parses` true, `object_count` 3, `object_names` `["Alpha","Beta","Gamma"]`, three `trimesh_3mf.object_volume:*` passed | PASS (round 1: FAIL) | `11.verify.3mf` |
| STL verify `OK`, total volume only (1634.03), no `object_volume` | PASS | `11.verify.stl` |
| GUI 3MF declares each content type once: 3 thumbnail parts, 1 `Extension="png"` | PASS | `11.3mf_parts`, `11.3mf_png_defaults` = 1 |
| Outside read of the 3MF | PASS: lib3mf `['Alpha','Beta','Gamma']`; trimesh `['Alpha','Beta','Gamma']`, volume 1634.03 | `outside-3mf-read.txt` |
| STEP product names | PASS: `tc07_three_bodies_export`, `Alpha`, `Beta`, `Gamma` (see O-1) | `11.step_products` |
| Hidden Body (`Hid` hidden, its tip `HidBox` keeps `Visibility` true) is left out of the default export | PASS: `objects` `["BoxA","Cyl","Sph"]` | `11.hidden_body.state`, `11.hidden_body` |
| Omitted `objects`, each format | PASS: the same objects, and all three verifies `OK` | `11.omitted.*` |
| Planted wrong file (in the file, Cyl is 20 mm tall) | PASS: STEP `SPEC_FAILED` on `export_step.volume` and `export_step.object_volume:Cyl`. 3MF `SPEC_FAILED` on `trimesh_3mf.object_volume:Cyl` and `trimesh_3mf.volume_band`. No other object fails. | `11.planted.*` |
| Unknown name refused, no file written | PASS | `11.unknown` |
| Empty document refused | PASS | `11.empty` |
| Outside re-import of the STEP (`Part.read`) | PASS: 1649.26 mm³, 3 solids | `11.reimport` |
| Visual: before | PASS: box, cylinder and sphere as built. The tree shows Alpha, Beta, Gamma, and the hidden Body `Hid` greyed out. | `tc-07-11-before.png` |
| Visual: STEP through File > Import, Isometric, Fit All | PASS: the three solids in the same layout. The tree shows `tc07_three_bodies_export` > Alpha, Beta, Gamma. | `tc-07-11-after-step.png` |
| Visual: 3MF through File > Import | PASS: the three solids in the same layout. FreeCAD 1.1.4 imports a 3MF as one mesh object `tc-07-11-three`. The names are proven by the outside read above. | `tc-07-11-after-3mf.png` |
| Visual: STL through File > Import | PASS: one merged mesh `tc-07-11-three` holding the three solids | `tc-07-11-after-stl.png` |

### TC-07-12: an omitted `objects` exports every visible solid — PASS

| Step | Result | Evidence |
| --- | --- | --- |
| Single-object document, no `objects` | PASS: `["Box"]`, verify `OK`, 6000.0, single-path check ids (no `object_volume`, no `object_names`) | `12.single` |
| `objects: []` behaves as omitted | PASS: `["Box"]` | `12.empty_list` |
| Two visible boxes | PASS: `["BoxA","BoxB"]`, verify `OK` with both `object_volume` checks and `object_names` | `12.two` |
| Hidden BoxB left out | PASS: `["BoxA"]` | `12.hidden` |
| Outside re-import | PASS: 6000.0 mm³, 1 solid | `12.reimport` |
| Visual: re-imported file | PASS: one box of about 1 : 2 : 3 proportions | `tc-07-12-after.png` |

Foreground delivery (on the container desktop only) was used for two clicks: one MDI tab switch and one tree expand. In round 1, the same clicks in background mode did not land.

## Observations

- **O-1 (low).** The multi-object STEP root product is now `<document>_export` (`tc07_three_bodies_export`), not the document name. In round 1 it was `tc07_three_bodies`. Cause: the scratch writer document is named `f"{document_name}_export"` (`shim.py:542`), and FreeCAD's writer names the root product after the internal name of the document it writes from. The commit title says "keep the root product named after the document". The shim docstring states the `_export` suffix. The per-object names are correct, and the user sees the suffix only on the root assembly node after an import. No change requested unless the leader wants the exact document name.
- The case file was not changed in round 2. The builder applied the round-1 diff and added the GUI 3MF and hidden-Body steps.

## Round 2 teardown

`fcb-freecad stop` (the window close timed out, and the helper killed the process). `docker compose ... down`: the container and the network are removed. The worktree `fcb-verify-13-5` is removed. Nothing is left running.
