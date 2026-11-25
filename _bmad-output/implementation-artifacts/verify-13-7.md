# Story 13-7 verification: `query_interference`

Verifier: verifier-13-7. Date: 2026-11-24.
Artifact: commit `8e381d975a5fd6eb6360014677c08a1249365f14` (branch `story/13-7-query-interference`, base `bda755e`).
Copy: detached worktree `D:\Work\Personal\Sources\fcb-verify-13-7` (removed at the end).
Evidence: `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-7-r1\` (JSON results, `logs/`, `scripts/`, `evidence/freecad-cap1.png`).

**Verdict: PASS, with 2 findings for the leader.** Gates, mutants and the CAP-1 replay pass. R1-D2 is confirmed as a real risk (F2, medium). F1 (low) is a fingerprint change that Q8 asks about.

## 1. Gates (in the copy)

| Command | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check` on the 5 changed `.py` files | 5 files already formatted |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run python scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `uv run python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `uv run python scripts/check_skill_shape.py` | exit 0 |
| `uv run pytest tests/external -q` | 1865 passed, 4 skipped, 0 failed (272.8 s). No known-unstable test failed |
| `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` | `Ran 896 tests`, `OK (skipped=1)`; 19 `QueryInterferenceTest` tests ok (`logs/infc-13-7.log`) |

Import check: a probe under the same `freecadcmd` and private cfg printed `QUERIES=D:\Work\Personal\Sources\fcb-verify-13-7\src\freecad_buddy\usecases\queries.py HAS=True`. The suite ran against the copy's `src`, not the installed `Mod/FreeCADBuddy`.

## 2. Mutants

Each mutant was applied to the copy, then `QueryInterferenceTest` (freecadcmd) and `tests/external/test_mcp_surface.py` + `test_assistant_readonly_profile.py` ran. The files were restored with `git checkout` afterwards. Log: `logs/mutants.log`.

| Mutant | Change | Red tests | Result |
| --- | --- | --- | --- |
| (a) | `queries.py:771` `return None, distance, True` → `return 0.0, distance, False` | `..._When_common_is_empty_at_distance_zero`, `..._common_raises_and_the_distance_is_unknown`, `..._common_raises_and_the_distance_is_zero`, `..._two_solids_only_touch_at_a_face` | killed |
| (b) | drop `"query_interference"` from `READ_ONLY_PROFILE` (`tool_catalog.py:1038`) | `test_allow_list_matches_expected_read_only_set`, `test_build_readonly_profile_registers_exactly_the_allow_list` | killed |
| (c) | delete the self-pair check `queries.py:722-723` | `test_Should_map_bad_input_to_invalid_input_When_dispatched` (subtest `pairs: [["A","A"]]`), `test_Should_name_the_object_When_a_pair_repeats_one_name` | killed |
| (d) | swap `"a": name_b, "b": name_a` (`queries.py:799`) | `..._every_pair_in_order_When_objects_lists_three_names`, `..._given_pairs_in_input_order_When_pairs_is_used`, `..._common_volume_and_zero_distance_When_two_boxes_overlap` | killed |
| (e2) | schema `objects.maxItems` 20 → 21 (`tool_catalog.py`) | `test_Should_advertise_the_interference_input_bounds_When_the_catalog_is_read` | killed |
| (e1) | code bound `_MAX_INTERFERENCE_OBJECTS = 21` (`queries.py:677`) | none | **survived** |

(e1) survives because the dispatch test sends 21 names `A0..A20` that do not exist (`test_query_tools.py`, `test_Should_map_bad_input_to_invalid_input_When_dispatched`). The call fails with "unknown object: A0", which is also `INVALID_INPUT`. The live bridge closes the gap: 21 names gave `Input validation error: [...] is too long` before the call reached FreeCAD (`cap1-replay.json`). So 21 objects cannot get through over MCP. The remaining gap is a test gap only (low): a test with 21 existing objects would kill (e1).

## 3. AC and quality-bar map

| Q | Evidence | Status |
| --- | --- | --- |
| Q1 schema | `tool_catalog.py:1276-1314`; external bounds test `test_mcp_surface.py:1447`; live 21-name refusal | met |
| Q2 record shape | `queries.py:797-804`; live records carry `a, b, common_volume, min_distance, boolean_failed` | met |
| Q3 separated | live `A/Sep` vol 0.0, dist 10.0, failed false | met |
| Q4 overlap | live `A/Over` 125.0; `A/Cyl` 282.74 (script 282.7433) | met |
| Q5 failed boolean | `queries.py:769-771`; live `A/Bowtie` vol null, failed true, script `common().Volume` 0.0; mutant (a) killed | met |
| Q6 touching | live `A/FaceTouch`, `A/VertTouch`: script `common` empty (0 sub-shapes) at dist 0 → tool failed true (decision 24) | met |
| Q7 invalid input | `queries.py:701, 723, 735`; live: self pair, unknown name, both forms → `INVALID_INPUT` with the name | met |
| Q8 read-only | profile entry `tool_catalog.py:1038`; live: names, placements, undo count 0, no Touched change, cached fingerprint equal. **Fresh fingerprint not equal (F1)** | met with F1 |
| Q9 190 pairs in budget | live: 7.8 s overlapping, 5.6 s disjoint | met; R1-D2 below (F2) |
| Q10 numbers only | text `21 pair(s), 5 overlapping, 8 boolean failed.` + per-pair lines; no verdict word | met |
| Q11 design doc, rings, status | `mcp-tools-design.md:132` (§2 row), `:337` (§3.2.3 schema equals the catalog), `:222` says 46; `tool_specs()` returns 46, 9 `query_`. `check_imports`, `check_status_vocab` OK | met |
| Q12 CAP-1 replay | section 4 | met |

## 4. Live CAP-1 replay (container, FreeCAD 1.1.4)

Setup: `build_addon.py --release` from the copy, `docker compose ... up -d --build`, `fcb-freecad start`; healthz `{"freecad_pid":573,...}`. The `freecad-buddy-docker` MCP server did not connect in this session, so a small `mcp` HTTP client (`scripts/mcpcall.py`) called `http://127.0.0.1:18765/mcp`.

Document `Interference137`, 7 `Part::Feature` objects: `A` box 10 at origin; `Sep` 10 mm gap; `Over` 5x5x5 overlap; `FaceTouch` on A's top face; `VertTouch` on one vertex; `Cyl` r3 through A; `Bowtie` self-intersecting extrusion at the origin.

`query_interference` with `objects` (7 names, 21 pairs, 0.12 s) and with `pairs` (6 pairs, mixed order, 0.05 s). One `script_exec` read `a.Shape.common(b.Shape).Volume` and `a.Shape.distToShape(b.Shape)[0]` for every pair. Full table: `cap1-replay.txt`. Extract:

| Pair | Tool vol | Tool dist | failed | Script vol | Script sub-shapes | Script dist |
| --- | --- | --- | --- | --- | --- | --- |
| A/Sep | 0.0 | 10.0 | false | 0.0 | 0 | 10.0 |
| A/Over | 125.0 | 0.0 | false | 124.99999999999997 | 1 | 0.0 |
| A/FaceTouch | null | 0.0 | true | 0.0 | 0 | 0.0 |
| VertTouch/A | null | 0.0 | true | 0.0 | 0 | 0.0 |
| A/Cyl | 282.74 | 0.0 | false | 282.7433388230814 | 1 | 0.0 |
| Bowtie/A | null | 0.0 | true | 0.0 | 0 | 0.0 |
| Over/VertTouch | 0.0 | 8.66 | false | 0.0 | 0 | 8.660254037844387 |

Result: all 27 records equal the script within the display rounding (2 decimals). The bridge rounds values to display precision, as for other tools. Every record where the script reads volume 0.0 at distance 0 is `boolean_failed` true in the tool: this is the false pass CAP-1 removes. `pairs` keeps the input order (`Over/A`, `VertTouch/A`, `Bowtie/A`).

Screenshot: `evidence/freecad-cap1.png`. The window shows the 7 objects in the tree and the 3D view after `view_fit_viewport`. The boxes, the cylinder through A and the separated box are where the build put them.

## 5. R1-D2 timing (container, through the bridge)

| Case | Pairs | Elapsed | Status |
| --- | --- | --- | --- |
| 20 plates 90x90x5, 81 holes each, neighbours overlap | 190 | 7.8 s | OK, 19 overlapping, 0 failed |
| same, disjoint | 190 | 5.6 s | OK |
| 2 disjoint compounds of 200 boxes | 1 | 4.6 s | OK, dist 4806.0 |
| 2 disjoint compounds of 900 boxes | 1 | **130.2 s** | **TIMEOUT** |

Over-budget behaviour (`timing-compound-n900.json`):
- The call returned `status TIMEOUT`, `detail {"message": "listener read timed out", "data": {"marshal_timeout": false, "maybe_still_running": true}}` after 130 s. That is the proxy read timeout (`rpc_client.py:36` `_DEFAULT_READ_TIMEOUT_S = 130.0`), not the 60 s tool budget.
- After that, every call returned `WORKER_CRASHED` "handshake rejected" for about 8 min (polls 12:32:51 to 12:38:31; first `OK` at 12:38:47). FreeCAD did not crash: healthz showed the same `freecad_pid` 573 all the time.
- Document not suspect: after recovery the same document was open, cached fingerprint `9dbfb187...` equal before and after, `UndoCount` 0, same 4 objects, same Touched set. A follow-up `query_interference` returned OK in 0.07 s.

## 6. Findings

### F2 (medium, confirms R1-D2): budget not enforced; bridge blocked and reported as crashed

Reproduction: document with two `Part::Feature` compounds of 900 boxes 4x4x4 (20 per row, 10 mm pitch), second offset 5000 mm in x (`scripts/timing2.py 900 n900`). Call `query_interference` with `pairs: [["C1","C2"]]`.

Mechanism: `queries.py:760` calls `shape_a.distToShape(shape_b)`. `TopoShapePyImp.cpp` (FreeCAD 1.1 source, `docs/references/FreeCAD/src/Mod/Part/App/TopoShapePyImp.cpp:2350`) has no GIL release (0 matches for `Py_BEGIN_ALLOW_THREADS` / `GILStateRelease` in the file). So the listener thread cannot run while OCC works: the 60 s marshal timeout (`marshal.py` `done.wait(timeout_s)`) cannot fire, and the handshake of every later call fails. This last point is an inference from the source and the observed `marshal_timeout: false`. It is not traced in a debugger.

Effect for a client: one large pair blocks FreeCAD (GUI included) for minutes. The client sees `TIMEOUT` at 130 s and then `WORKER_CRASHED`, which says "crashed" while FreeCAD is alive. The document is safe (read-only). Realistic parts (190 plate pairs) stay well inside 60 s. The 200-box pair took 4.6 s here; the builder measured 45 s on the host with another layout, so cost depends strongly on layout. The leader decides (decision 23 rule: bound changes only with a measurement).

### F1 (low): `query_interference` changes the fresh fingerprint of the objects it measures

Reproduction: `scripts/digest_check.py`. Three `fingerprint(doc, fresh=True)` reads before the query are equal (`14c0b77f...`). After `query_interference` with `objects`, the digest is `0065270801...` and stays there. All 7 objects changed `brep_sha256`, with `massprops` equal. `query_mass_properties` does not change it (`digest-check2.json`). The cached digest (`fingerprint(doc)`, the one mutation results publish) stays equal.

Cause, measured on host freecadcmd (`scripts/probe_diff.py`): `Shape.common` on a disjoint pair changes one BREP flag line of the input shapes, `1100000` → `0100000` (the TShape "free" flag). Geometry, tolerances, volume and `isValid` are unchanged. `common` on copies (`a.copy().common(b.copy())`) leaves the original unchanged (`scripts/probe_mutate.py`). `distToShape` changes nothing.

Effect: no geometry change and no undo entry. A byte-exact comparison against a fresh digest taken before the query fails (for example `document_undo` `expect_fingerprint` with a digest the server did not publish). A held digest matches on per-object invariants and is not affected. Q8 "fingerprint equal" is true for the cached digest and false for a fresh digest.

### Test gap (low): mutant (e1)

See section 2. No product effect over MCP.

## 7. Teardown

All documents closed, `fcb-freecad stop` (window close timed out, helper killed pid 573; status then showed no FreeCAD pid), `docker compose ... down` (container and network removed). verifier-13-5 told the container is free. Worktree `fcb-verify-13-7` removed. Nothing left running.

## Round 2

Artifact: commit `7037fd64` (`0c691e0c` decision 26 trust rule, `718c802a` per-pair guard + shape copies + e1 test, `b7c9d752` sum guard superseded, `7037fd64` 40 s deadline, decision 28). Fresh detached copy `fcb-verify-13-7` at 7037fd6 (removed at the end). Evidence: `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-7-r2\`.

**Verdict round 2: PASS.** F1, F2 and e1 are closed with proof. RT-1..RT-4 are each held by a test that goes red when the fix is reverted. RT-5 is a text change, checked by reading.

### Gates and counts

| Command | Result |
| --- | --- |
| `ruff check .`, `check_imports`, `check_status_vocab`, `gen_schemas --check`, `check_skill_shape` | all OK / exit 0 |
| `ruff format --check` on the changed `.py` files | 5 files already formatted |
| `pytest tests/external -q` | 1865 passed, 4 skipped, 0 failed (`logs/ext-r2.log`) |
| `freecadcmd ... tests/run_tests.py` | `Ran 911 tests`, `OK (skipped=1)`; 34 `QueryInterferenceTest` tests (`logs/infc-13-7-r2.log`) |

The import probe printed `QUERIES=D:\Work\Personal\Sources\fcb-verify-13-7\src\...\queries.py HAS=True`.

### Fix reverts (each in the copy, then `QueryInterferenceTest`; files restored, `src` clean after)

Log: `logs/mutants-r2.log`, script `logs/mutants_r2.py`.

| Row | Revert in `queries.py` | Red tests |
| --- | --- | --- |
| RT-1 invalid solid | drop `and bool(shape.isValid())` (`:792`) | `..._When_one_shape_is_an_invalid_solid_at_distance_zero` |
| RT-2 reversed solid | `volume > 0` → `volume != 0` (`:790`) | `..._When_a_reversed_solid_contains_the_other_shape`, `..._When_a_reversed_solid_overlaps_a_box` |
| RT-3 shell | `_solid_volumes` non-solid `yield None` → `yield float(shape.Volume)` (`:774`) | `..._When_a_closed_shell_contains_a_solid`, `..._When_objects_mixes_shapes` |
| RT-4 text | overlap count back to the raw value (`:707`) | `test_Should_not_count_a_pair_as_overlapping_When_its_volume_rounds_to_zero` |
| F1 copies | `return shape.copy()` → `return shape` (`:759`) | `test_Should_leave_a_fresh_fingerprint_digest_equal_When_pairs_are_measured` |
| e1 bound | `_MAX_INTERFERENCE_OBJECTS = 21` (`:679`) | `test_Should_map_bad_input_to_invalid_input_When_dispatched` (subtest 21 names). Killed now; survived in round 1 |
| per-pair guard | face-product check → `if False:` (`:851`) | `test_Should_refuse_the_call_with_a_code_When_a_pair_is_above_the_face_limit` |
| deadline | `clock() - started > _CALL_DEADLINE_SECONDS` → `if False:` (`:895`) | `test_Should_stop_with_a_code_and_the_count_When_the_deadline_passes_between_pairs` (injected clock) |
| whole trust rule | `if measurable[a] and measurable[b]:` → `if True:` (`:900`) | 8 tests red |

Note on RT-1: the red team's case (`..._When_an_invalid_solid_contains_the_other_shape`) stays green when only `isValid()` is dropped. The bowtie solid also fails the positive-volume check, so two independent checks hold it. Removing the whole trust rule turns it red.

RT-5: `mcp-tools-design.md` §3.2.3 and the tool description now say every object is measured in its container's frame, with a feature inside a `PartDesign::Body` measured in the Body's local frame ("name the Body, not a feature inside it").

### Container (rebuilt from the copy, FreeCAD 1.1.4)

The first `fcb-freecad start` ran before the XFCE session was up ("no xfce4-session is running"), and FreeCAD exited. A second start worked (healthz `freecad_pid` 560). This is environment timing, not the product.

CAP-1 replay (`cap1-replay.txt`, `cap1-replay.json`): the round 1 document plus `Reversed` (`Part::Reverse` of a box, volume -1000), `InRev` (box inside the reversed box) and `Shell` (closed 50 mm shell around A). 10 objects: `objects` form 45 pairs in 0.49 s, `pairs` form 7 pairs in 0.07 s. **52 records, 0 mismatches**:
- Trusted pairs equal the script's `common().Volume` and `distToShape()[0]` within display rounding (for example `A/Over` 125.0, `A/Cyl` 282.74, `Over/VertTouch` 8.66). Touching pairs stay `boolean_failed` true at distance 0 (decision 24).
- Every pair with `Bowtie`, `Reversed` or `Shell` is `boolean_failed` true, with `common_volume` and `min_distance` null. The script shows the false results this removes: `Reversed/InRev` volume 0.0, distance 4.0 (the box is inside); `Shell/A` volume 0.0, distance 20.0 (A is inside the shell); `A/Reversed` volume 1000 against a true 0.
- Fresh fingerprint equal before and after both queries (F1 closed live). Cached digest equal, `UndoCount` 0, no Touched change.

Screenshot `evidence/freecad-cap1-r2.png`: tree with the 11 objects (incl. `RevSrc`); the view shows the 50 mm shell, the reversed box sticking out at +x, and the in-reversed box.

Timing and guard (through the bridge):

| Case | Status | Elapsed |
| --- | --- | --- |
| 20 plates, 81 holes, overlapping, 190 pairs | OK, 19 overlapping, 0 failed | 5.6 s |
| same, disjoint | OK | 3.4 s |
| 2 compounds of 900 boxes (5400 faces each) | `INVALID_INPUT`, `detail.code` `interference.too_complex`, "pair C1/C2 is too complex to measure: 5400 and 5400 faces, limit 150000 ..." | 1.6 s |
| normal call right after (P/Q) | OK | 0.23 s; healthz same pid; document, cached digest, undo unchanged |
| 1 dense pair near the limit (378 x 378 = 142,884 faces product, 1 mm apart) | OK, dist 1.0 | 6.9 s |
| 8 copies of that pair in one call | `INVALID_INPUT` `interference.too_complex` "stopped after 6 of 8 pairs; measure fewer pairs per call" | 40.5 s |
| call right after | OK | 6.9 s |

F2 is closed: the bridge stays usable and no call goes past the 60 s budget in these cases. Remaining risk, accepted by decision 28: face count is a proxy for cost, so a shape with few but very complex faces is not measured by these cases. A deadline stop also drops the pairs already measured; the client must split the call.

### Teardown

All documents closed, `fcb-freecad stop`, `docker compose down` (container removed), worktree removed. Nothing left running.
