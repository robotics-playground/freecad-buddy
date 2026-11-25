# Story 13-6: verification report

Verifier: verifier-13-6. Date: 2026-11-24.
Artifact: commit `61dd01fdd53c4a9872cf086a31dfc63b21ffaa63` (branch `story/13-6-mass-properties-objects`, base `116377e`).
Copy: detached worktree `D:\Work\Personal\Sources\fcb-verify-13-6` at `61dd01f`, `uv sync --extra dev`. Copy removed after the run.

**Verdict: PASS.** No product defect found. R1-D3 measured and closed: 3.7 s for 50 heavy objects, budget 30 s.

## 1. Gates (in the copy)

| Command | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check` on the 3 changed source and test files | `3 files already formatted` |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `uv run python scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `uv run pytest tests/external -q` | `1864 passed, 4 skipped, 6 warnings in 196.05s`. The known unstable tests did not fail. |
| `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` | rc 0, `Ran 875 tests`, `OK (skipped=1)` |

Import check: a wrapper run of the same suite printed `QUERIES_MODULE=D:\Work\Personal\Sources\fcb-verify-13-6\src\freecad_buddy\usecases\queries.py`. The suite tested the copy's `src`, not the installed `Mod/FreeCADBuddy` addon. Each mutant run printed the same module path.

The 9 new in-FreeCAD tests (`tests/infc/test_query_tools.py:108-248`) all show `ok`.

## 2. Mutants

Each mutant was applied to `src/freecad_buddy/usecases/queries.py` in the copy, then `tests/infc/test_query_tools.py` ran under `freecadcmd` (23 tests), then the file was restored with `git checkout`. Baseline: 23 run, 0 red.

| Mutant | Change | Red tests |
| --- | --- | --- |
| (a) drop `is_valid` | delete `:617` `"is_valid": bool(shape.isValid()),` | 4 errors: `test_Should_add_is_valid_to_the_record_When_one_object_is_queried`, `test_Should_equal_the_object_record_and_a_direct_shape_read_When_objects_is_used`, `test_Should_report_is_valid_false_and_flag_the_summary_When_the_shape_is_invalid`, `test_Should_return_records_in_input_order_When_several_objects_are_queried` |
| (b) reverse output order | `records = [...][::-1]` at `:663-666` | 3 failures: `..._return_records_in_input_order_...`, `..._return_fifty_records_in_order_When_fifty_objects_are_dispatched`, `..._report_is_valid_false_and_flag_the_summary_...` |
| (c) no-shape object raises | `raise ValidationError` before `records` when a shape is `None` | 2 errors: `test_Should_return_a_null_shape_record_When_an_object_has_a_null_shape`, `..._return_records_in_input_order_...` |
| (d) accept both forms | `:623` becomes `if object is None and objects is None:` | 2 failures: `test_Should_map_both_or_neither_to_invalid_input_When_dispatched` (subtest object+objects), `test_Should_raise_validation_error_When_the_input_form_or_list_is_wrong` (subtest object+objects) |
| (e) allow 51 names | `:573` `_MAX_MASS_OBJECTS = 51` | 2 failures: the same two tests, subtest with 51 names |

All 5 mutants killed.

## 3. Quality bar and acceptance map

| Q / AC | Code | Test | Live | Result |
| --- | --- | --- | --- | --- |
| Q1 input `objects` 1..50, exactly one form, bad list → `INVALID_INPUT` | `usecases/queries.py:621-631` (`_mass_object_names`); schema `hosts/tool_catalog.py:1257-1267` (`minItems` 1, `maxItems` 50, `required: ["doc"]`) | `test_query_tools.py:214`, `:248` | both, neither → `INVALID_INPUT` "give exactly one of 'object' and 'objects'"; 51 → rejected (see O-1) | PASS |
| Q2 `{objects:[...]}` in input order, duplicates kept, record = `object` record + `is_valid` | `queries.py:656`, `:663-668`; record `:585-618` | `:120`, `:158`, `:172` | order `BodyA, Shell, BodyB, Group, BodyC, BodyA` returned as given; each record equals the `object` call record (5/5); duplicate records equal | PASS |
| Q3 no shape / null shape → `{name, shape: null}`, call `OK` | `queries.py:576-582`, `:664` | `:120` (Group), `:144` (null-shape `Part::Feature`) | `{"name": "Group", "shape": null}`, status `OK`, text `Group: no shape.` | PASS |
| Q4 unknown name → whole call `INVALID_INPUT` naming it | `queries.py:656` → `_resolve_object` `:198-200` | `:236`, `:248` | `INVALID_INPUT` "unknown object: Nope" | PASS |
| Q5 `object` path: same record + `is_valid`; no shape still `INVALID_INPUT` | `queries.py:657-661` | `:108`; existing `test_query_mass_properties_matches_analytic_volume` and `test_preview` mass tests `ok` | `object: "Group"` → `INVALID_INPUT` "object has no queryable shape: Group" | PASS |
| Q6 `is_valid` = `shape.isValid()`; planted invalid shape reads `false` | `queries.py:617`; summary flag `:101` | `:189` (self-intersecting bowtie face → `False`, text has `INVALID shape`) | all live shapes valid; `is_valid` equals direct `isValid()` for 4/4 shaped objects | PASS |
| Q7 CAP-1 replay: values equal a script read | — | `:172` (BoundBox, Volume, isValid) | max bbox diff 0.0; volume diff ≤ 2.8e-14; area diff ≤ 2.8e-14; `is_valid` equal; non-solid `Shell` gives `volume: null` (direct `Volume` 60.0, by the DW-28 rule) | PASS |
| Q8 schema additive, design matches code, AD-1 rings | catalog `:1257-1273`; design `mcp-tools-design.md:131` row and §3.2.2 | `gen_schemas --check`, `check_imports` OK | live `inputSchema` equals design §3.2.2 input | PASS (see O-2) |
| AC1 box via `object`: fields unchanged + `is_valid: true` | as Q5 | `:108`, `:172` | yes | PASS |
| AC2 50 names through dispatch, in order | as Q2 | `:158` | 50 heavy records, status `OK` | PASS |
| AC3 gates pass | — | section 1 | — | PASS |

## 4. Live run (container `fcb-desktop`)

Build from the copy: `uv run python scripts/build_addon.py --release` (wheel `freecad_buddy-0.1.1`), `docker compose -f D:\Work\Personal\Sources\fcb-verify-13-6\tests\close-loop\docker\compose.yaml up -d --build`, `docker exec -u cua fcb-desktop fcb-freecad start`. Mounts: copy → `/repo`. Installed addon `/home/cua/.local/share/FreeCAD/v1-1/Mod/FreeCADBuddy/freecad_buddy/usecases/queries.py` contains `_MAX_MASS_OBJECTS`. Health: `{"service":"freecad-buddy-mcp-proxy","freecad_pid":483,...}`.

Client: Python MCP client over `http://127.0.0.1:18765/mcp` (uv env), script `tests/uat/run/13-6-r1/live_13_6.py`.

Fixture (built with `script_exec`): 3 PartDesign bodies `BodyA` (10x20x30), `BodyB` (5x5x5), `BodyC` (40x8x3), a shell `Shell` (`Part::Feature`), a group `Group` (no shape).

| Check | Result |
| --- | --- |
| `objects: [BodyA, Shell, BodyB, Group, BodyC, BodyA]` | `OK`, 6 records in input order, 0.035 s |
| each record vs `object` call | 5/5 shaped records byte-equal; `Group` via `object` → `INVALID_INPUT` |
| each record vs `script_exec` read of `BoundBox`/`Volume`/`Area`/`isValid` | all equal within 2.8e-14 |
| bad inputs | both → `INVALID_INPUT`; neither → `INVALID_INPUT`; unknown `Nope` → `INVALID_INPUT` "unknown object: Nope"; 51 names → MCP `Input validation error` |

Visual check: `get_window_state` screenshot of the FreeCAD window (820 elements, not degraded) after `view_fit_viewport`. Model tree shows `verify_13_6` with `BodyA`, `BodyB`, `BodyC`, `Shell`, `Group`, `Heavy00`..; the 3D view shows the 50 perforated plates and the small bodies. Matches the built document.

Evidence (main repo):
- `tests/uat/run/13-6-r1/evidence/live-13-6.json` — every call, record and timing
- `tests/uat/run/13-6-r1/evidence/freecad-window.png` — container FreeCAD window
- `tests/uat/run/13-6-r1/live_13_6.py` — client script

## 5. R1-D3 timing (`isValid()` cost vs 30 s budget)

Heavy part: plate 200x200x20 mm, 81 through holes (9x9, r 5 mm), 1 mm fillet on the 81 top hole edges, 2 mm fillet on the 4 top outer edges. Per object: 172 faces, 425 edges, 255 vertices, 1 solid, `isValid()` true, volume 671511.35 mm^3. 50 `Part::Feature` objects, each a `copy()` of the shape (own topology, no shared check cache). Total 8600 faces.

| Run | Elapsed (client, full MCP round trip) |
| --- | --- |
| 1 | 3.678 s |
| 2 | 3.682 s |
| 3 | 3.712 s |

All `OK`, 50 records. Worst case 3.71 s = 12% of the 30 s tool timeout. R1-D3: closed with this measurement.

## 6. Observations (not defects of this Story)

- **O-1.** 51 names through MCP are refused by the MCP SDK input validation (`maxItems: 50`) with text `Input validation error: ...`, not by the fcb envelope `INVALID_INPUT`. This is the same for every schema violation on every tool. The envelope path holds when the schema layer is bypassed (dispatch test `test_query_tools.py:248`, mutant (e)).
- **O-2.** `mcp-tools-design.md:131` row still says "Volume/area/bbox/COM/inertia". The record has no inertia field. The word predates this Story; the Story edited the row and kept it. Low.
- **O-3.** `tool-contracts.md` T-2 still lists `solids` (ledger R1-D2, leader-owned).

## 7. Teardown

`fcb-freecad stop` (unsaved document: window close timed out, helper killed pid 483), `fcb-freecad status` shows no pid, `docker compose ... down` (container and network removed), `:18765` closed. Copy worktree removed with `git worktree remove --force`. Host `:8765`, `%APPDATA%\FreeCAD\v1-1\user.cfg` and other worktrees not touched; the in-FreeCAD runs used private temp cfg files.

## Round 2

Artifact: commit `c513a0da4ba5f5229af9df3c03ba9bf2f2fe992c` (red-team fix round, parent `61dd01f`). Triage: `triage-13-6-rt.md`. Fresh detached copy at `c513a0d`, removed after the run. No container.

**Verdict: PASS.** RT-1, RT-2 and RT-4 are fixed and proven. No new defect.

### Gates

| Command | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check` on `usecases/queries.py`, `tests/infc/test_query_tools.py` | `2 files already formatted` |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `uv run pytest tests/external -q` | `1864 passed, 4 skipped, 6 warnings in 228.67s` |
| `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` | rc 0, `Ran 877 tests`, `OK (skipped=1)` (round 1: 875; +2 new tests) |
| `test_query_tools.py` alone | 25 run, 0 red; module `...\fcb-verify-13-6\src\freecad_buddy\usecases\queries.py` (copy `src`, not the addon) |

### Rows

| Id | Proof | Result |
| --- | --- | --- |
| RT-1 | `mcp-tools-design.md:131` now reads `Volume/area/bbox/COM + topology counts + \`is_valid\` for one object, or for 1 to 50 objects (\`objects\`)`. No "inertia" in the row; the 2 other "inertia" hits (`:616-617`) are Phase 5 inertials, out of scope. §3.2.2 `MassRecord.required` = `[area, bbox, com, counts, is_valid, name, solid, volume]`, equal to the keys of a real record (round 1 live `BodyA`, `tests/uat/run/13-6-r1/evidence/live-13-6.json`; `_mass_record` unchanged between `61dd01f` and `c513a0d`). Sub-keys match the descriptions: bbox `xmin..zmax`, com `x,y,z`, counts `faces, edges, vertices, solids`. Null record keys `[name, shape]` match the design `"required": ["name", "shape"]`. | PASS |
| RT-2 | Mutant: `queries.py` `if not all(isinstance(name, str) and name ...)` → `if not all(isinstance(name, str) ...)`. Red: `test_Should_reject_an_empty_name_When_it_is_listed_with_valid_names` (1 of 25). | PASS |
| RT-4 | Mutant: `if shape is None or not shape.BoundBox.isValid()` → `if shape is None`. Red: `test_Should_return_a_null_shape_record_When_a_listed_object_is_an_empty_compound` (1 of 25). | PASS |
| RT-4 `object` path unchanged | Same freecadcmd script on an empty compound (`Part.makeCompound([])`) with `src` of `61dd01f` and of `c513a0d`: `object` outputs are equal (`status OK`, `solid false`, `volume null`, `com null`, area 0.0, bbox `xmin 1.797e308 / xmax -1.797e308`, counts all 0, `is_valid true`, text `EmptyCompound: volume n/a (non-solid), 0 faces, 0 edges.`). `objects` output: `61dd01f` gave the inverted-bbox record; `c513a0d` gives `{"name": "EmptyCompound", "shape": null}`. | PASS |

Note: the `object` path keeps the inverted ±1.797e308 bbox and `is_valid: true` for an empty compound. That is the triage decision (AD-28, no change to an existing response) and is stated in the spec Design Notes and in `mcp-tools-design.md` §3.2.2.
