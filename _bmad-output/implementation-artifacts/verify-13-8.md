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
