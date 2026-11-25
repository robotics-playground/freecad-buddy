# Story 13-8 verification: `query_section`

Verifier: verifier-13-8. Date: 2026-11-24.
Artifact: commit `d4a258e4e2122b3ac2323a14c2bce42975fb1def` (branch story/13-8-query-section), base `90303e36`.
Own copy: detached worktree `D:\Work\Personal\Sources\fcb-verify-13-8` at that SHA (removed after the run).
Evidence: `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-8-r1\` (JSON results, summary, mutant log, in-FreeCAD log, screenshot, addon log, scripts used).

**Verdict: PASS.** No product defect found. One test-quality note (mutant f survives, equivalent on all probed shapes) and one design-wording note. Details follow.

## 1. Gates (in the copy)

| Gate | Command | Result |
| --- | --- | --- |
| Lint | `uv run ruff check .` | All checks passed |
| Format (changed files) | `uv run ruff format --check` on the 5 changed `.py` files | 5 files already formatted |
| Rings | `uv run python scripts/check_imports.py` | `check_imports OK` |
| Status vocabulary | `uv run python scripts/check_status_vocab.py` | `check_status_vocab OK` |
| Schemas | `uv run python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| Skill shape | `uv run python scripts/check_skill_shape.py` | exit 0 |
| External | `uv run pytest tests/external -q` (PowerShell) | 1834 passed, 32 failed, 4 skipped (188 s) |
| External re-run of the 32 | same 3 files from Git Bash | `test_fcb_py_wrapper.py` + `test_fcb_cua_wrapper.py`: 32 passed; `test_managed_venv.py`: 17 passed |
| In-FreeCAD | host `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg run_infc.py` | 941 run, 0 failures, 0 errors, 1 skip (45 s) |

The 32 failures are environmental, not Story 13-8. Under the PowerShell tool, `bash` resolves to `C:\WINDOWS\system32\bash.EXE` (WSL), which prints `ERROR_FILE_NOT_FOUND`; the 31 wrapper tests pass under Git Bash (`/usr/bin/bash`). The managed-venv failure is the known `pythonhome` flaky test; it passes alone. The diff does not touch these files.

In-FreeCAD import check: the host has an installed `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy` copy that shadows `src`. The wrapper `scripts/run_infc.py` imports FreeCAD first, then puts the copy's `src` first on `sys.path` and asserts the module path. Log line: `IMPORTED D:\Work/Personal/Sources/fcb-verify-13-8/src\freecad_buddy\usecases\queries.py`. The `QuerySectionTest` class alone: 30 tests, 0 failures (baseline before mutants).

## 2. Mutants

Each mutant edits `src/freecad_buddy/usecases/queries.py` in the copy, runs `QuerySectionTest` under host `freecadcmd`, and restores the file byte for byte (`git status` clean after). Log: `mutants.txt`.

| Mutant | Edit | Result | Tests that turned red |
| --- | --- | --- | --- |
| a | `shape.slice(normal, offset)` instead of `shape.section(plane_face)` (`queries.py:1147`) | killed, 6 red | `test_Should_not_read_a_miss_When_the_plane_is_on_or_within_1e5_mm_of_a_face` at offsets 0, 1e-9, 1e-7, 1e-6, 1e-5, 29.99999 |
| b | `area = 0.0` instead of `None` in the not-solids-only / over-limit branch (`queries.py:1156`) | killed, 4 red | `..._null_area_and_open_wires_When_a_face_or_an_open_shell_is_cut` (Face, OpenShell); `..._null_area_not_zero_When_the_wire_count_is_above_the_area_limit`; `..._null_area_When_a_valid_shell_is_cut` |
| c | face limit check disabled (`queries.py:1127`) | killed, 1 red | `test_Should_refuse_before_cutting_When_the_face_count_is_above_the_limit` |
| d1 | `kept = vertices` (no `max_points` cap, `queries.py:1077`) | killed, 2 red | `..._stop_at_max_points_and_flag_truncation_...`; `..._drop_whole_wires_and_flag_truncation_...` |
| d2 | both `truncated` returns forced to `False` | killed, 4 red | `..._drop_the_next_wire_When_the_cap_leaves_fewer_than_two_points` (cap 5, 6); `..._drop_whole_wires_...`; `..._stop_at_max_points_...` |
| e | deflection floor disabled (`queries.py:1141`); only the input-validation test was run | killed, 1 red | `test_Should_raise_When_the_plane_or_points_are_malformed` subtest index 14 (`deflection = diagonal * 1e-7`). The call reaches `discretize` on the straight edges of a box section, which returns; no hanging case was run |
| f | `_named_shape` instead of `_copied_queryable_shape` in `query_section` (`queries.py:1133`) | **survived**, 0 red | none |

Mutant f analysis (`scripts/probe_copy.py`, `probe_copy2.py`): with the copy removed, a fresh fingerprint digest stays equal before and after `query_section` (with `points`) on a `Part::Box`, a `Part::Feature` holding `Part.makeBox`, and a `Part::Cylinder`. The same removal in `query_interference` does change the digest (`interference equal=False`). So the 13-7 effect (`common` of two solids clears a BREP flag) does not appear for `section` / `common` with a plane face on the probed shapes. The mutant is equivalent on every probed input; no fingerprint test can turn red on it. The copy stays as a defence. This is not a product defect. Design note: `mcp-tools-design.md` §3.2.4 says "The cut runs on a copy of the shape, so a fresh fingerprint digest of the document is unchanged." The digest is unchanged, but the probe shows the copy is not the cause on these shapes; the sentence claims a cause that was not observed.

## 3. Acceptance and quality bar map

| Q / AC | Code | Test (`tests/infc/test_query_tools.py`) | Live (container) | Status |
| --- | --- | --- | --- | --- |
| Q1 input, zero normal, NaN, below floor | `queries.py:977` `_section_plane` (`:996` zero), `:1003` `_section_points` (`:1012`, `:1017`), `:1141` floor; schema `tool_catalog.py:1320` | `:1414`, `:1616`, `:1636`, `:1465`, `:1495` | zero normal, deflection 0, deflection 1e-9 → `INVALID_INPUT` | met |
| Q2 values equal `section` / `common` | `queries.py:1147`, `:1154`, `:1056` | `:1156`, `:1203`, `:1216`, `:1229`, `:1242` | 15 cases equal to `script_exec` reference, see §4 | met |
| Q3 miss, at face, 1e-6 inside | `queries.py:1152` | `:1174`, `:1188` | z0, z1e-6, z30, z30-1e-6 → 1 wire, area 200; z40 → 0, 0, bbox null | met |
| Q4 area never 0 when unmeasured | `queries.py:1065`, `:1156` | `:1269`, `:1282`, `:1566` | shell → `area` null (script `common` gives 0.0) | met |
| Q5 untrusted vs valid shell | `queries.py:1024`, `:1038` | `:1302`, `:1253`, `:1550` | reversed solid → `section.untrusted_shape`; shell → wires 1, length 60, area null | met |
| Q6 face limit before cut, timing | `queries.py:940`, `:1127` (before the copy at `:1133`) | `:1326`, `:1339`, `:1532` | 10,002 faces refused in 0.17 s; timing §5 | met |
| Q7 polylines, cap, floor | `queries.py:1068`, `:1077`, `:951` | `:1350`, `:1370`, `:1383`, `:1399`, `:1596` | cap 5 → 5 points, `truncated` true; default → 53 points, r in [4.994, 5.006], z 10 | met |
| Q8 read-only, copy, profile | `queries.py:1133`; `tool_catalog.py:1039` `READ_ONLY_PROFILE` | `:1518`; `test_assistant_readonly_profile.py:48` | fresh digest `8062723987bf...` equal before/after all calls, 2 FreeCAD processes | met (see mutant f note) |
| Q9 frame | docstring `queries.py:1094`; description `tool_catalog.py:1320`; design §3.2.4 | `:1582` | `Moved` box (Placement z 100): z115 hit, bbox z 115; z15 miss | met; decision 30 wording |
| Q10 AD-35, AD-17, AD-1, design counts | `_refusal_envelope` codes `section.*`; no verdict field | `test_mcp_surface.py:62`, `:1466` | gates in §1 | met |
| AC1 box offsets 0, 1e-7, 15, 30 | as Q3 | `:1174`, `:1156` | as Q3 | met |
| AC2 invalid / reversed refused | as Q5 | `:1302` | as Q5 | met |
| AC3 gates | — | — | §1 | met |

## 4. Live CAP-1 replay (container)

Environment: `build_addon.py --release` from the copy; `docker compose -f <copy>\tests\close-loop\docker\compose.yaml up -d --build` (mounts `D:\Work\Personal\Sources\fcb-verify-13-8 -> /repo`); `fcb-freecad start`; healthz `freecad_pid` 428 (run 1) and 1168 (run 2, after a restart, see §5). Client: host `uv` MCP client against `http://127.0.0.1:18765/mcp`. Script: `scripts/replay.py`; results `replay.json` (run 1), `replay2.json` (run 2, identical numbers), `replay-summary.txt`.

Reference: one `script_exec` per run computes, for each case, `Shape.section(plane face)` + `Part.sortEdges` wire count, closed count, length, `Shape.common(plane face).Area`, and `Shape.slice` wire count. The reference plane face is 3x larger than the tool's.

| Case | query_section wires / closed / length / area | script reference | `slice` wires |
| --- | --- | --- | --- |
| box 10x20x30, z 15 | 1 / 1 / 60 / 200 | 1 / 1 / 60 / 200 | 1 |
| box, z 0 (bottom face) | 1 / 1 / 60 / 200 | same | **0** |
| box, z 1e-6 | 1 / 1 / 60 / 200 | same | **0** |
| box, z 30 (top face) | 1 / 1 / 60 / 200 | same | 1 |
| box, z 30 - 1e-6 | 1 / 1 / 60 / 200 | same | **0** |
| box, z 40 (miss) | 0 / 0 / 0 / 0, bbox null | 0 / 0 / 0 / 0 | 0 |
| box, x 5 | 1 / 1 / 100 / 600 | same | 1 |
| box, [1,1,1] through centre | 1 / 1 / 84.85 / 346.41 | 84.852814 / 346.410162 | 1 |
| cylinder r5 h20, z 10 | 1 / 1 / 31.42 / 78.54 | 31.415927 / 78.539816 | 1 |
| cylinder, x 0 | 1 / 1 / 60 / 200 | same | 1 |
| plate 100x60x5, 4 holes r3, z 2.5 | 5 / 5 / 395.40 / 5886.90 | 395.398224 / 5886.902664 | 5 |
| bullseye r30/r20 ring + r10 island, z 4 | 3 / 3 / 376.99 / 1884.96 | 376.991118 / 1884.955592 | 3 |
| closed shell of the box, z 15 | 1 / 1 / 60 / **null** | 1 / 1 / 60 / **0.0** | 0 |
| box with Placement z 100, z 115 | 1 / 1 / 60 / 200, bbox z 115 | same | 1 |
| same box, z 15 | 0 / 0 / 0 / 0 | same | 0 |

All counts are equal. Lengths and areas are equal after rounding to 2 decimals: the bridge's `RoundToDisplay` preference (default on, all tools) rounds the returned numbers; every difference is below 0.005. Analytic checks (box 200 / 60, cylinder 25π / 10π, plate 6000 - 36π / 320 + 24π, bullseye 600π / 120π) agree at the same precision. The `slice` column shows the CAP-1 false miss at three offsets that `query_section` measures correctly. The shell row shows a script `common` reading 0.0 where the tool reads null.

Fingerprint: `script_exec` of `fingerprint(doc, fresh=True)["digest"]` before and after all query calls: `8062723987bfed3bd66cc3e7ccc9ceaa57c22d653a8d1779d0b5e99d0e1c7ada` both times, in both runs.

Refusals live: reversed solid → `INVALID_INPUT` `section.untrusted_shape`; zero normal, deflection 0, deflection 1e-9 (floor 2.449e-5 mm), unknown object → `INVALID_INPUT` with the cause in the message.

Visual check: `freecad-window.png` (container FreeCAD window, after `view_fit_viewport`, captured with `cua-driver get_window_state`). Tree shows Box, Cyl, Plate, Bullseye, Shell, Moved, Reversed. The view shows the moved box above the others, the bullseye ring with its island disc, the plate with holes, and the box. One plate hole sits under the bullseye ring (hole centre (20,15), ring radius 30); the measured 5 wires confirm 4 holes.

## 5. Timing (container, software rendering)

Scripts `timing.py`, `timing2.py`; results `timing.json`, `timing2.json`. Budget 60 s.

| Case | Faces | Wires | area | query_section elapsed | Bridge after (`document_list`) |
| --- | --- | --- | --- | --- | --- |
| compound of 1,666 boxes | 9,996 | 1,666 | null (above 1,500) | 4.96 s; run 2 4.39 s | OK 0.07 s |
| compound of 1,500 boxes | 9,000 | 1,500 | 6000 (measured) | 6.82 s; run 2 6.68 s | OK 0.12 s |
| plate with 1,499 holes | 1,505 | 1,500 | 20890.75 (= 160² - 1499π) | 8.85 s | answered |
| plate with 1,500 holes | 1,506 | 1,501 | null | 5.36 s | answered |
| compound of 1,667 boxes | 10,002 | — | `section.too_complex` | 0.17 s | OK 0.12 s |

The largest measured-area case (1,500 wires on a plate) takes 8.85 s, inside the 60 s budget, matching the design estimate "near 8 s".

Not run: a plate with 9,000 holes. The build step (my `script_exec` with `FaceMakerCheese` and 9,001 wires) passed its 30 s timeout and kept FreeCAD's main thread busy for more than 10 minutes; `query_section` on it never ran (`WORKER_CRASHED` "handshake rejected" because the listener could not answer). I stopped FreeCAD with `fcb-freecad stop` (it killed pid 428) and started it again (pid 1168). This is a cost of the test harness build, not of `query_section`. The builder's measurement for that shape is `Shape.section` 3 s with `area` null.

The two 1,499 / 1,500-hole plate builds also passed the 30 s `script_exec` timeout (about 48 s each) and finished; the section calls after them ran normally. This is pre-existing `script_exec` behaviour (the marshal timeout cannot stop work that holds the interpreter lock), outside this Story.

## 6. Findings

| Id | Severity | Finding | Route |
| --- | --- | --- | --- |
| V1 | low (test) | Mutant f (no `shape.copy()` in `query_section`) survives; on Box, Feature box and Cylinder, `section` + `common` with a plane face leave the fresh digest unchanged without the copy, so `:1518` cannot detect its removal | accept as equivalent mutant; optionally assert the copy directly |
| V2 | low (doc) | `mcp-tools-design.md` §3.2.4: "The cut runs on a copy of the shape, so a fresh fingerprint digest of the document is unchanged" states a cause that the probe did not observe | wording fix when the design is next edited |
| V3 | info | Returned lengths and areas are rounded to 2 decimals by `RoundToDisplay` (default on), so they equal a script value only at display precision | none; existing project behaviour |

No product defect.

## 7. Teardown

Documents closed through `document_close`; `fcb-freecad stop` (status: no FreeCAD pid); `docker compose -f <copy>\...\compose.yaml down` (container and network removed). No host `freecadcmd` of mine left running. Worktree `D:\Work\Personal\Sources\fcb-verify-13-8` removed after this report.

# Round 2

Artifact: commit `f2548a20d21b4b974fc6da2c2daf3c33173e3cd8` (b29c92b4 triage fixes, f2548a20 lens fixes), compared with `d4a258e4`. Inputs: `triage-13-8-r2.md`, `redteam-13-8.md`, `quality-bar-13-8.md` (Q3 and Q6 for decision 31).
Own copy: fresh detached worktree `D:\Work\Personal\Sources\fcb-verify-13-8` at that SHA (removed after the run).
Evidence: `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-8-r2\`.

**Verdict round 2: PASS.** No product defect found. Two fix rows have a guard test that cannot fail: RT-4 (the bbox test) and RT-3b (the open-wire condition). For RT-4, the old bbox call is exact on every plane the tool still accepts. For RT-3b, the RT-3a cross-check also catches an open wire, so removing the condition alone changes no result. Details in R2.2.

## R2.1 Gates (in the copy)

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `ruff format --check` on `queries.py`, `tool_catalog.py`, `test_query_tools.py` | 3 files already formatted |
| `check_imports.py`, `check_status_vocab.py`, `gen_schemas.py --check`, `check_skill_shape.py` | OK, OK, OK, exit 0 |
| `uv run pytest tests/external -q` from Git Bash | **1866 passed, 4 skipped**, 0 failed (145 s) |
| In-FreeCAD suite (host `freecadcmd`, private temp cfg; the wrapper asserts the import comes from the copy: `IMPORTED D:\Work/Personal/Sources/fcb-verify-13-8/src\...\queries.py`) | **953 run, 0 failures, 0 errors, 1 skip** (59 s) |
| `QuerySectionTest` alone (baseline before mutants) | 42 run, 0 failures (37 s) |

## R2.2 Each fix reverted: which test turns red

Script `scripts/mutants2.py`: edit `queries.py` in the copy, run `QuerySectionTest` under host `freecadcmd`, restore the file byte for byte (`git status` clean after every run). Logs `mutants-part1.txt`, `mutants-rt1a.txt`, `mutants-rt1b.txt`.

| Row | Revert | Result | Red tests |
| --- | --- | --- | --- |
| RT-1 face limit | `_MAX_SECTION_FACES = 10_000` (old value) | killed | `test_Should_finish_well_inside_the_query_budget_When_shapes_are_at_the_limits` (Prism: the 10,000-face prism runs past 30 s) |
| RT-1 face guard | face check disabled (round-1 mutant c) | killed | `test_Should_refuse_a_prism_When_it_has_one_face_above_the_limit`; `test_Should_refuse_before_cutting_When_the_face_count_is_above_the_limit` |
| RT-1 pole load | pole-load check disabled | killed (118 s run) | `test_Should_refuse_a_coil_spring_When_its_bspline_face_has_too_many_poles`; `test_Should_refuse_the_shape_When_the_pole_load_is_above_the_limit_by_one` (error) |
| RT-2 worst-layout budget test / 300-wire area limit | `_MAX_AREA_WIRES = 1500` (old value) | killed | `..._finish_well_inside_the_query_budget_...` (Plate: 496 wires must give `area` null) |
| RT-3a area cross-check | `_section_area` instead of `_checked_section_area` | killed | `test_Should_return_null_area_When_the_wires_and_the_boolean_disagree` |
| RT-3b open wire gives null | `closed == len(wires)` condition removed | **survived** | none: `FaceMakerBullseye` cannot build a face from the open wire, so the RT-3a check already gives null |
| RT-3a + RT-3b | both removed | killed | `test_Should_return_null_area_When_a_wire_is_open`; `..._wires_and_the_boolean_disagree` |
| RT-4 `optimalBoundingBox` | `Part.Compound(edges).BoundBox` (old call) | **survived** | none, see the note below |
| RT-5 plane on face | `on_face = False` | killed | `test_Should_refuse_the_plane_When_it_lies_on_a_planar_face`, all 13 subtests; `test_Should_refuse_as_untrusted_When_a_face_surface_cannot_be_read` |
| RT-5 face tolerance | tolerance fixed at 1e-7 (face tolerance ignored) | killed | `..._refuse_the_plane_When_it_lies_on_a_planar_face` (LooseBox, z 1e-6) |
| RT-5 BSpline planes | `findPlane` branch for BSpline/Bezier faces removed | killed | `..._refuse_the_plane_...` (NurbsBox z 0, z 30) |
| R1 a | `slice` instead of `section` | killed | `test_Should_not_read_a_miss_When_the_plane_is_within_1e5_mm_of_a_face` (1e-6, 1e-5, 29.99999, 29.999999); `test_Should_return_null_area_When_a_wire_is_open` |
| R1 b | `area = 0.0` instead of null | killed | open shell and face (2), shell, above-area-limit, wire-open, budget Plate (6 in all) |
| R1 c | face guard disabled | killed | as in the RT-1 face guard row |
| R1 d1 / d2 | no `max_points` cap / `truncated` forced false | killed | 2 / 4 polyline tests, as in round 1 |
| R1 e | deflection floor disabled (only the input-validation test is run) | killed | `test_Should_raise_When_the_plane_or_points_are_malformed` subtest 14 |
| R1 f | no `shape.copy()` | survived | equivalent mutant, as in round 1. The design wording is now fixed: "runs on a copy of the shape so the document's shapes are never modified" |

RT-4 note (`scripts/probe_bbox.py`): I cut a NURBS cylinder, a NURBS sphere, a NURBS torus and an extruded BSpline profile at z 1e-6, z 2.5, z 15, x 3 and an oblique plane. In every case, `BoundBox` and `optimalBoundingBox()` of the section edges differ by 0.000000 mm (all edges are `BSplineCurve`). The red team's loose box (-12.08 against -10) was on a cap face (z 0), which RT-5 now refuses. The fix is correct and costs little. On every plane the tool still accepts, the old call gives the same box. So `test_Should_report_an_exact_bbox_When_the_section_edge_is_a_bspline` cannot fail when the fix is reverted. This is not a product defect.

## R2.3 Live: red team shapes through the container bridge

Setup:
- Container rebuilt from the copy: `build_addon.py --release`, then `compose up -d --build`. The compose file mounts `D:\Work\Personal\Sources\fcb-verify-13-8 -> /repo`.
- `fcb-freecad start`; healthz `freecad_pid` 600. Calls come from a host `uv` MCP client.
- Scripts `timing_r2.py`, `timing_r2_springs.py`; results `timing_r2_part1.json`, `timing_r2_springs.json`.
- Each shape is built with `script_exec`. The reference is a `script_exec` on the same plane that computes `section` + `sortEdges`, the `common` area and a `FaceMakerBullseye` area.

| Shape | Faces / pole load | query_section | Elapsed | Reference (script) | Bridge after |
| --- | --- | --- | --- | --- | --- |
| Spring 30 turns, plane y 0.5 | 3 / 5,503,716 | `section.too_complex` (pole load, limit 640,000) | 0.10 s | — | OK |
| Prism 9,990 sides | 9,992 / 0 | `section.too_complex` (faces, limit 3,000) | 0.09 s | — | OK |
| Prism 2,898 sides, z 5 | 2,900 / 0 | OK: 1 wire, length 314.16, area 7853.98 | **6.83 s** | 1 wire, 314.159204, common 7853.975481, Bullseye 7853.975481 | OK 0.11 s |
| Plate with 1,400 hex holes, z 5 | 8,406 | `section.too_complex` (faces) | 0.14 s | — | OK |
| Spring 5 turns, y 0.5 | 3 / 171,396 | OK: 10 wires, 10 closed, length 62.84, area 31.43 | **2.19 s** | 10 / 10, 62.841606, common 31.425754, Bullseye 31.421871 | OK 0.06 s |
| Spring 6 turns, y 0.5 (added: the largest spring under the limit) | 3 / 236,196 | OK: 12 wires, length 75.41, area 37.71 | **3.14 s** | 12 / 12, 75.409932, common 37.710910 | OK 0.11 s |
| Spring 10 turns, y 0.5 | 3 / 675,684 | `section.too_complex` (pole load) | 0.10 s | 20 / 20, 125.683213, common 62.851509 (script 8.1 s) | OK 0.10 s |

All accepted cases are far inside the 60 s budget. The worst is the 2,900-face prism at 6.8 s, which matches the "near 7 s" in the constant's comment. The tool's areas equal the script's `common` area at 2 decimals, and `common` and Bullseye agree within the 5e-3 tolerance.

The 10-turn spring is refused by design: 822 poles squared is above 800 squared. In the container, the script's `section` + `common` on it took 8.1 s, so this refusal is conservative. That follows from decision 31; it is not a defect.

Harness notes:
- The 1,400-hole plate build (`plate.cut` of 1,400 prisms) ran past the 30 s `script_exec` timeout (39.7 s). The bridge answered again after 0.3 s.
- The timeout marked the document "suspect", so the next `script_exec` builds were refused with `INVALID_INPUT` "document-suspect: a prior call timed out on this document; run a query_* read to confirm state before mutating". This is expected bridge behaviour. I ran a `query_tree_summary` read, closed the document, and ran the springs in a new document.

## R2.4 CAP-1 replay, round-1 cases (container)

`scripts/replay.py` unchanged; results `replay_r2.json`, `replay_r2-summary.txt`.

- Box z 0 and box z 30 (planes on a face) now return `INVALID_INPUT` `section.plane_on_face`: "the plane lies on a face of Box; offset it by a small amount (1e-6 mm or more, more for a shape with a larger tolerance)". This is decision 31.
- Box z 1e-6 and z 30 - 1e-6 are still cut: 1 wire, area 200, length 60. `slice` reads 0 wires at both.
- Every other case gives the same numbers as round 1. These are: z 15, the miss at z 40, x 5, the oblique plane, the cylinder z 10 and x 0, the 4-hole plate, the bullseye, the shell (`area` null), the moved box hit and miss, the polylines cap 5 and the default polyline, and the refusals (reversed, zero normal, deflection 0 and below the floor, unknown object).
- Fresh fingerprint digest before and after: `8062723987bfed3bd66cc3e7ccc9ceaa57c22d653a8d1779d0b5e99d0e1c7ada`, equal.
- Screenshot `freecad-window-r2.png` checked: the same scene as round 1, tree with 7 objects, nothing unexpected.
- `addon-r2.log` has no ERROR lines, only the two standard SECURITY warnings.

## R2.5 Findings

| Id | Severity | Finding | Route |
| --- | --- | --- | --- |
| V4 | low (test) | The RT-4 guard test cannot fail. On every plane the tool still accepts (no plane on a face), `BoundBox` of BSpline section edges was exact in every probe, so reverting to `BoundBox` turns nothing red. | accept. A test would need a case where `BoundBox` is loose off a face, and no probe found one. |
| V5 | info (test) | The RT-3b revert (open wire allowed) survives alone because the RT-3a cross-check also gives null. With both removed, the open-wire test turns red. | accept: two layers, both covered together |
| V6 | info | The 10-turn spring is refused (pole load 675,684 > 640,000), though its script section + common took 8.1 s in the container. | none: decision 31 accepts a conservative limit |

## R2.6 Teardown

Documents closed; `fcb-freecad stop`; `docker compose ... down` (container and network removed). No `freecadcmd` of mine running. The copy's `git status` was clean, then the worktree was removed.
