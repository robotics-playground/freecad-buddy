---
title: 'Story 10.5: STEP Export Schema'
type: 'bugfix'
created: '2026-10-05'
status: 'done'
baseline_commit: '7cb9a0a04c1550b127cc473f058d8af901be684a'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `export_step {ap:"AP242"}` and the default write `FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 … }'))`, an AP214 file (F-18; TC-07-05, TC-09-08). `shim.pin_step_config` writes the `Mod/Part/STEP` `Scheme` preference, which `TopoShape::exportStep` never reads; it reads only the OCC static `write.step.schema`. `verify_export_step` does not look at the schema, so the wrong file passes.

**Approach:** Pin the OCC static with its enum name, and add a schema check to the paired verify that reads `FILE_SCHEMA` from the written file.

**Decisions (planning, from evidence):**
- **D1 — pin.** `pin_step_config(ap)` calls `Part.setStaticValue("write.step.schema", <enum>)` with `AP242 → "AP242DIS"`, `AP214 → "AP214IS"`, `AP203 → "AP203"`. Probe on FreeCAD 1.1.3 (fcb env): `setStaticValue("write.step.schema","AP242")` raises `Failed to set 'write.step.schema'`; `"AP242DIS"` succeeds and writes `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF {1 0 10303 442 1 1 4 }`; `"AP214IS"` writes `AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }` (the ambient default). Both re-read to volume 6000, `isValid` true.
- **D2 — no preference write.** The bridge stops writing the user's `Mod/Part/STEP` `Scheme` preference. `shim.step_schema()` and the registry `schema` field are removed. An already-written `Scheme="AP242"` value on a user machine is not repaired.
- **D6 — restore the static after each export (2026-10-05, user, option 1).** `write.step.schema` is process-global and the pin leaks into later exports: File > Export keeps the current static when `Scheme` is unset or unsupported (`AppImportGuiPy.cpp:579-583`), and `Import.export` never resets it. Python has no getter for the static (`AppPartPy.cpp:700` has only `setStaticValue`), so an exact save-and-restore is impossible. After every `exportStep` call, success or raise, the bridge sets the static to what FreeCAD itself would choose: the `Scheme` preference when it is in `Part::supportedSTEPSchemes()` (`ImportStep.h:42-51`: `AP203`, `AP214CD`, `AP214DIS`, `AP214IS`, `AP242DIS`), else `AP214IS` (the OCC default). Accepted limit: a value a macro set directly on the static is overwritten. `write.step.unit` is not restored (unchanged from baseline). The user kept the shipped code as the base for this change.
- **D3 — verify check.** `verify_export_step` adds check `export_step.schema`: `measured` is the first identifier of the file's `FILE_SCHEMA` (header text before `DATA;`, may span lines); `expected` is `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF` (AP242), `AUTOMOTIVE_DESIGN` (AP214), `CONFIG_CONTROL_DESIGN` (AP203) for the recorded `ap`. Exact match passes. No `FILE_SCHEMA` → fails, `measured: null`.
- **D4 — fault coverage (AD-19).** New planted case `step-schema-lie`: the clean box written at AP214, `case.yaml` records `ap: AP242`, so only the schema check can detect it. Every STEP `case.yaml` gains `ap`; the 10 existing STEP files stay byte-identical (AP214 files, `ap: AP214`). The scorer adds the schema check when the case carries `ap`. All three export validators are re-scored (they share `validator_sha` over `exports.py`).
- **D5 — TC-07-05 defect, deferred to Story 10.7.** Its `grep -c "AP214"` on the AP214 file is 0 for a correct file: AP214 `FILE_SCHEMA` reads `AUTOMOTIVE_DESIGN`. Logged in `deferred-work.md`.

## Boundaries & Constraints

**Always:**
- Every fix has a regression test that fails on the baseline commit.
- The tool input schema stays `ap: {enum:["AP214","AP242"], default:"AP242"}` (AD-28, no wire change).
- The schema check reads the written file, never a setting.

**Never:**
- No change to UAT test-case files (Story 10.7).
- No change to the export-invokes-verify relation in spine AD-9; not in this AC.
- No rebuild of existing fault fixture files.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| AP242 explicit | `export_step {ap:"AP242"}` | file `FILE_SCHEMA` starts `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING`; verify `OK`, `export_step.schema` passed | — |
| Default | `export_step` without `ap` | same as AP242 | — |
| AP214 | `export_step {ap:"AP214"}` after an AP242 export | `FILE_SCHEMA` `AUTOMOTIVE_DESIGN`; verify `OK` | — |
| Schema lie | recorded `ap` AP242, file AP214 | verify not `OK`; `export_step.schema` failed, measured `AUTOMOTIVE_DESIGN` | — |
| No header | file has no `FILE_SCHEMA` | `export_step.schema` failed, `measured: null` | — |
| Restore, pref unset | `Scheme` unset; `export_step {ap:"AP242"}`; then plain `Shape.exportStep` | second file `AUTOMOTIVE_DESIGN` | restored also when `exportStep` raises |
| Restore, pref valid | `Scheme="AP242DIS"`; `export_step {ap:"AP214"}`; then plain `Shape.exportStep` | second file AP242 | — |
| Restore, pref invalid | `Scheme="AP242"`; `export_step {ap:"AP242"}`; then plain `Shape.exportStep` | second file `AUTOMOTIVE_DESIGN` | — |
| Preference untouched | `Scheme` = sentinel; export AP242 then AP214 | `Scheme` still the sentinel | — |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/shim.py:18-19` `_STEP_PARAM_PATH`, `_STEP_SCHEMES` -- D1 mapping; remove `_STEP_PARAM_PATH` if unused. `:388-402` `pin_step_config` -- D1; docstring states the wrong reason and must change. `:405-409` `step_schema` -- delete (D2).
- `src/freecad_buddy/usecases/exports.py:128-174` `export_step` -- drop `"schema": shim.step_schema()` (`:159`); keep `"ap"`. `:287-317` `verify_export_step` -- append the D3 check. `:320` `_step_checks(shape, source)` -- keep signature (scorer calls it); add a separate `_schema_check(path, ap)` plus a header reader. Module docstring `:11-13` lists the checks.
- `tests/infc/test_export_tools.py:97-104` `test_ap242_and_mm_pinned` -- asserts the preference, so it passed on the bug; rewrite to read the file. Fixture `_ExportFixture :29`, box 10x20x30.
- `benchmarks/g0/export-fault-injection/score_export_verify.py:150-161` `_score_step_case` -- D4. `build_export_fault_fixtures.py:343-445` STEP builders, `:449-490` `CASES`, `:518-541` `_write_case_yaml` (emit `ap` for STEP cases). README case table.
- `benchmarks/_registry/validators.yaml:20-63` the three export blocks -- regenerated by the scorer (STEP leg under the fcb env, STL/3MF leg under `uv`).
- `design/verification-design.md:265` §6.2 -- states the static names and the schema check. `mcp-tools-design.md:141,374` stay true.
- Run in-FreeCAD code with the fcb env python: `PYTHONPATH=<env>\Library\bin`, `PATH=<env>\Library\bin;<env>\Library\lib;…`, env `%USERPROFILE%\micromamba\envs\fcb` (FreeCAD 1.1.3). `micromamba` is not on PATH.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/shim.py` -- D1, D2.
- [x] `src/freecad_buddy/usecases/exports.py` -- D2 registry field, D3 check and header reader.
- [x] `tests/infc/test_export_tools.py` -- one test per I/O row; the old preference assertion goes.
- [x] `benchmarks/g0/export-fault-injection/` -- D4: builder pins the schema explicitly for STEP cases and emits `ap`; add `step-schema-lie/` (`export.step` + `case.yaml`) built alone; add `ap: AP214` to the 10 existing STEP `case.yaml`; scorer; README row.
- [x] `benchmarks/_registry/validators.yaml` -- re-score all three export validators; each meets sensitivity ≥ 95 %, false alarm ≤ 5 %.
- [x] `design/verification-design.md` §6.2 -- D1 names, D3 check.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- D5 entry.
- [x] `src/freecad_buddy/usecases/shim.py` + `exports.py` -- D6: a shim function restores the static; `export_step` calls it in a `finally` around `shape.exportStep(path)`. Fix the `pin_step_config` docstring and design §6.2, which claim the GUI export is unaffected; cite `TopoShape.cpp:891` for "`exportStep` reads only the statics".
- [x] `tests/infc/test_export_tools.py` -- the four new I/O rows; save and restore `Scheme` and the static in `setUp`/`tearDown`.
- [x] `tests/infc/` -- new test runs `score_export_verify.score()` STEP leg (model: `tests/infc/test_fault_score.py`): bars met, no `MISSED`/`FALSE_ALARM`, `g0-export-step-schema-lie` `DETECTED`.
- [x] `tests/external/` -- fixture test of `exports._read_file_schema` on fixed header text: the 1.1.4 form `'AP242_…_MIM_LF. {1 0 10303 442 1 1 4 \n}'` and a `FILE_SCHEMA((\n'AUTOMOTIVE_DESIGN { … }'))` split.
- [x] `build_export_fault_fixtures.py` -- strip each `FREECAD_BUDDY_EXPORT_FAULT_CASES` entry.
- [x] `validators.yaml` -- re-score all three export validators (`exports.py` changes again).
- [x] `deferred-work.md` -- TC-07-07 "exactly three checks" (now four, Story 10.7); `mcp-tools-design.md` §3.5 `verify_export_step` output shape predates this story and does not match the `checks` report.

**Acceptance Criteria:**
- Given each I/O row, when its test runs on FreeCAD 1.1.x, then it passes, and the AP242 and default rows fail on the baseline commit.
- Given the full suites, when run, then in-FreeCAD and external tests pass, and ruff, `check_imports`, `gen_schemas --check` and `check_provenance` pass.
- Given FreeCAD 1.1.4 GUI with the addon, when TC-07-05 and TC-09-08 export through MCP, then the AP242 and default files name AP242 in `FILE_SCHEMA`, the AP214 file names `AUTOMOTIVE_DESIGN`, and `verify_export_step` returns `OK` for each.

## Implementation Notes

- D4 touched 11 existing STEP `case.yaml` (10 planted + clean control), not 10. The control carries `ap: AP214` so the false-alarm rate covers the schema check. Every `case.yaml` matches generator output (diffed against a full scratch build); no existing `export.step` changed.
- Builder: `_pin_step_ap214()` pins unit and `AP214IS` for every STEP fixture; `build_all(case_ids=...)` and env `FREECAD_BUDDY_EXPORT_FAULT_CASES` build cases alone, because a STEP header carries a write timestamp and a full rebuild rewrites every committed file.
- The 1.1.4 GUI writer (newer OCC than the 1.1.3 env) writes `'AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF. {1 0 10303 442 1 1 4 
}'`, with a `.` after the name. The reader stops at the identifier, so the check passes on both builds.
- Re-score: all three export validators sensitivity 1.0, false alarm 0.0; STEP n=11 (Wilson low 0.7412), STL/3MF n=10. `validator_sha` `fcac8893…` matches the working tree.
- Baseline red: the 5 new tests give 4 FAIL + 1 ERROR on `7cb9a0a`; green after the fix.
- Live GUI (FreeCAD 1.1.4, addon junction to `src`): AP242 and default files name `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF`; AP214 after AP242 names `AUTOMOTIVE_DESIGN`; `verify_export_step` `OK` for all three. The `Mod/Part/STEP` `Scheme` preference is unchanged by the exports. Re-import of the AP242 file: volume 6000.0, valid, 1 solid, bbox 10x20x30; Fit All screenshot shows one closed box.
- D6: `shim.restore_step_schema()` runs in a `finally` around `shape.exportStep(path)`. The four restore rows fail with the call removed (4 FAIL) and pass with it. The raise row exports into a missing folder.
- Re-score after D6: all three export validators sensitivity 1.0, false alarm 0.0; `validator_sha` `5dff26ed…` matches the working tree.
- For Story 10.7, not fixed here: TC-07-05 re-imports the STEP with `document_open`, which accepts only `.FCStd` (`INVALID_INPUT`). TC-09-08 `ap: null` is refused at the MCP schema layer (existing behaviour, as the TC expects).
- Loop 1 live GUI (FreeCAD 1.1.4, addon junction to `src`, 2026-10-05): AP242, default and AP214 bridge exports verify `OK` with `export_step.schema` passed. D6: after a bridge AP242 export, FreeCAD's own `ImportGui.export` and `Shape.exportStep` (macro, no `freecad_buddy` import) both write `AUTOMOTIVE_DESIGN` with `Scheme="AP242"` (unsupported). `Scheme` read `"AP242"` before and after shutdown. Re-import of the AP242 file: 1 solid, volume 6000.0, valid, bbox 10x20x30; Fit All screenshot shows one closed box. Clean exit logged one `rpc_listener` `frame read failed` `ConnectionResetError` line, which is F-31 (Story 10.6).

## Spec Change Log

- **Loop 1 (intent_gap, triage row 1).** Trigger: the pinned `write.step.schema` static leaked into later exports; frozen D2 claimed File > Export re-reads the preference, which holds only for a supported `Scheme` value. Amended: D2 lost the false claim; the user added D6 (restore the static to FreeCAD's own choice after every export); four I/O rows; tasks for D6 and the patch findings (rows 2-6) and deferrals (rows 7-8). Known-bad state avoided: a bridge AP242 export silently switching the user's own STEP exports to AP242 for the rest of the session. KEEP: the shipped D1 pin, D3 header reader and check, D4 fault case and scorer change, and the existing tests; the user chose to keep this code as the base rather than revert.

## Review Triage Log

| # | Source | Finding | Verdict | Route / evidence |
|---|--------|---------|---------|------------------|
| 1 | blind, edge (x3) | Pinned `write.step.schema` static is never restored; D2 and design §6.2 claim a GUI export is unaffected | medium | intent_gap: `AppImportGuiPy.cpp:579-583` falls back to the current static when `Scheme` is unset and skips the reset when `Scheme` is unsupported (the old bridge wrote `"AP242"`); `Import.export` (`AppImportPy.cpp:~350`) never resets it. A default install's File > Export STEP after a bridge AP242 export writes AP242, not AP214. No Python getter for the static exists (`AppPartPy.cpp:700` has only `setStaticValue`), so an exact restore is impossible. The false premise is inside frozen D2. |
| 2 | blind, gap | No test asserts the `Scheme` preference is left unchanged | medium | patch: add an infc test with a sentinel value. |
| 3 | gap | No test runs the STEP leg of `score_export_verify.score()`; `step-schema-lie` detection and `ap` parsing are unchecked | medium | patch: infc test modelled on `tests/infc/test_fault_score.py`. |
| 4 | gap | `_read_file_schema` tested only on the 1.1.3 header; the 1.1.4 `…MIM_LF. {…
}` form is uncovered | medium | patch: external fixture test with fixed header text. |
| 5 | blind, edge | `FREECAD_BUDDY_EXPORT_FAULT_CASES` entries are not stripped | low | patch: `.strip()`. |
| 6 | blind | Design §6.2 "`TopoShape::exportStep` reads only the statics" has no source citation | low | patch: cite `TopoShape.cpp:891`. |
| 7 | blind | TC-07-07 asserts exactly three checks; `verify_export_step` now returns four | low | defer: UAT test-case files are Story 10.7 (frozen Never). |
| 8 | blind | `mcp-tools-design.md` §3.5 `verify_export_step.outputSchema-result` lacks the schema check | low | defer: that block (`reimport`, `PASS/FAIL`) already did not match the shipped `checks` report at baseline; pre-existing drift. |
| 9 | blind | AP203 mapped but unreachable through the tool enum | low | rejected: D1 and D3 (frozen) name AP203; `_STEP_SCHEMES` held AP203 at baseline. |
| 10 | blind, edge (x2) | Two AP tables; unknown `ap` raises `KeyError` in verify or scorer | low | rejected: different mappings (OCC enum vs header name); `ap` is enum-gated at the tool and a fixture typo fails loudly. |
| 11 | blind | Header parser can stop at `DATA;` or match `FILE_SCHEMA` inside a quoted string | false | OCC writes fixed header strings (`'FreeCAD Model'`, `'Open CASCADE Shape Model'`); the bridge never writes caller text into the header. |
| 12 | blind | Mesh validator run records may claim a run that did not happen | false | re-ran the mesh leg under `uv`: output identical to the committed blocks (line endings aside). |
| 13 | blind | `_recorded_ap` sits outside `CASES` | low | rejected: one schema case; restructuring the table adds churn for no named harm. |
| 14 | blind | Deferred entry uses the AP242 prefix, design uses the full name | false | the prefix is deliberate: 1.1.4 writes `…MIM_LF.`, so a full-string grep would fail a correct file. |
| 15 | blind | Test mutates `_by_id`; default-row test duplicates the AP242 test | false | `_by_id` mutation is the existing pattern (`test_verify_export_step_detects_dropped_solid`); the default row is its own I/O row. |
| 16 | blind | Spec and sprint status missing from the patch | false | excluded by the review procedure. |
| 17 | edge | Lower-case `FILE_SCHEMA` identifier fails the case-sensitive compare | false | STEP schema names are upper case and OCC writes them so. |
| 18 | edge | AP214 test leaves the static at `AP214IS` for later tests | low | rejected: every test export goes through `export_step`, which pins; moot if row 1 restores. |
| 19 | blind, edge (loop 2) | `write.step.unit` stays pinned at `MM` after each export; File > Export then ignores a user `Unit` preference of `M` or `INCH` | medium | defer: pre-existing since Story 1.7 (baseline pinned the unit, never restored); D6 left the unit unchanged. FreeCAD sets the unit from `Mod/Part/STEP` `Unit` only at Part load (`OCAF/ImportExportSettings.cpp:133-147`, `AppPart.cpp:577`). Restorable: `Part.exportUnits()` returns `write.step.unit` (`AppPartPy.cpp:2426-2446`). |
| 20 | blind (loop 2) | `verify_export_step` tool description (`tool_catalog.py:1341`) does not name the schema check | low | patch: one-sentence correction. |
| 21 | blind, edge (loop 2) | Restore-on-raise test uses `assertRaises(Exception)`, which also passes if something raises before the pin | low | patch: match the `exportStep` failure message. |
| 22 | blind, gap (loop 2) | AP203 mapped but unreachable | low | carried row 9: rejected. |
| 23 | blind, edge (loop 2) | Two AP tables; unknown or quoted `ap` gives `KeyError` in verify or scorer | low | carried row 10: rejected. |
| 24 | blind, edge, gap (loop 2) | Scorer rebuilds the check list; a STEP case without `ap` silently skips the schema check | low | rejected: all 12 STEP cases carry `ap` and the builder writes it; the schema-lie test fails if the scorer stops reading `ap`; a guard adds a branch for an unlikely edit. |
| 25 | blind (loop 2) | `_read_file_schema` stops at `DATA;` inside a quoted header string | false | carried row 11. |
| 26 | blind (loop 2) | External fixture test covers two header forms only | low | rejected: no-`FILE_SCHEMA` and AP242/AP214 live forms are covered in `test_export_tools.py`; CRLF is handled by Python text mode. |
| 27 | blind (loop 2) | Mesh validator run records lack evidence | false | re-ran the mesh leg after loop 1: output identical to the committed blocks (line endings aside). |
| 28 | blind (loop 2) | Test repeats `STEP_PARAM_PATH` | low | rejected: a test reading the preference independently of the code under test is intended. |
| 29 | blind (loop 2) | Patch omits the spec | false | carried row 16. |
| 30 | blind (loop 2) | `mcp-tools-design.md` §3.5 should list `export_step.schema` now | low | carried row 8: the §3.5 output block does not describe the shipped `checks` report at all; adding one id to it would not make it true. Deferred entry stands. |
| 31 | gap, edge (loop 2) | `build_all(case_ids=...)` filter and unknown-id refusal untested; an env value of only commas rebuilds every case | low | rejected: developer-only rebuild tool; a wrong rebuild shows as a diff of every committed fixture; a test needs FreeCAD fixture builds for no product behaviour. |

## Verification

**Commands:**
- `<fcb-env>\python.exe tests/run_tests.py` -- expected: OK.
- `uv run pytest tests/external` -- expected: all pass.
- `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check`, `uv run python scripts/check_provenance.py` -- expected: pass.

**Manual checks:**
- Live GUI: the three exported files' `FILE_SCHEMA` lines, and a screenshot of the re-imported AP242 box.
