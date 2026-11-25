# Story 13-18 verification: loft and sweep tools

Verifier: verifier-13-18. Date: 2026-11-25.
Artifact: `d8968a1e` on `story/13-18-loft-sweep` (Story commits `6d73b983`, `8a3cf206`; feat merged in).
Own copy: detached worktree `D:\Work\Personal\Sources\fcb-verify-13-18` at `d8968a1e`, `uv sync --extra dev`. Removed at the end.
Evidence: `tests/uat/run/13-18-r1/` in the main repo path (`evidence/`, `scripts/`).

## Verdict

**PASS, with one finding for the leader to judge (F1, Q6 margin).** Every gate is green except one timing test outside the Story (N2). All five mutants turn a named test red. CAP-9 holds live in the container: a 3-section loft, a sweep along a sketch spine and a subtractive sweep each build a valid solid, return a mutation diff, and one `document_undo` each restores the pre-op state (`matches_pre_op: true`). The screenshots show the expected solids and the expected state after undo.

## 1. Gates (from the copy)

| Command | Result |
| --- | --- |
| `uv run --extra dev ruff check .` | All checks passed |
| `uv run --extra dev python scripts/check_imports.py` | OK |
| `uv run --extra dev python scripts/gen_schemas.py --check` | OK |
| `uv run --extra dev python scripts/check_provenance.py` | OK |
| `uv run --extra dev python scripts/check_status_vocab.py` | OK |
| `uv run --extra dev python scripts/check_skill_shape.py` | exit 0 |
| `ruff format --check` on the 6 changed files | 2 "would reformat" (`tests/external/test_feature_contract.py`, `tests/infc/test_feature_tools.py`). Both files fail the same way at base `dd7e8355`; the diff hunks are outside Story lines. Pre-existing. |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | 2108 passed, 6 skipped, **1 failed**: `test_headless_two_process.py::test_should_time_out_within_a_second_of_the_budget_when_a_body_holds_the_gil`. Re-run alone: 1 passed (7.9 s). See N2. |
| freecadcmd `tests/run_tests.py`, temp `-u/-s` cfg, `FREECAD_USER_HOME` temp | `Ran 1232 tests in 68.580s`, `OK (skipped=1)`. 46 of them are `LoftTest`/`SweepTest`. |

Copy's source confirmed under freecadcmd: a probe under the same env printed `FEATURES_FILE=D:\Work\Personal\Sources\fcb-verify-13-18\src\freecad_buddy\usecases\features.py`; the mutant runner prints the same line in every run.

## 2. Mutants

Runner: `scripts/mutant.sh` (one string edit to `features.py`, run `LoftTest` + `SweepTest` under freecadcmd, restore, `git status` clean). Baseline: `RESULT fail=0 error=0 run=46`.

| Mutant | Edit | Result | Red tests (named) |
| --- | --- | --- | --- |
| a1 drop subtractive branch, loft | `type_id = "PartDesign::AdditiveLoft"` always | killed | `LoftTest.test_Should_remove_the_frustum_volume_When_the_loft_is_subtractive` (15999.99 != 15346.67) |
| a2 drop subtractive branch, sweep | `type_id = "PartDesign::AdditivePipe"` always | killed | `SweepTest.test_Should_cut_subtractive_{standard,frenet}_When_the_spine_is_{a_sketch_name,an_edge_selector}` (4) |
| b swap mode map | `{"standard": "Frenet", "frenet": "Standard"}` | killed | all 8 `SweepTest.test_Should_{sweep_additive,cut_subtractive}_{standard,frenet}_...` (`'Frenet' != 'Standard'`) |
| c remove loft cost guard | `if cost > _LOFT_MAX_COST:` -> `if False:` | killed | `LoftTest.test_Should_refuse_with_a_code_When_the_sections_cost_more_than_the_limit` (LoftSweepRefusal not raised) |
| d remove `sweep.degenerate_spine` | `if previous is not None and previous.dot(tangent) < 0.0:` -> `if False:` | killed by hang | `SweepTest.test_Should_refuse_without_hanging_When_the_spine_doubles_back_on_itself` did not finish in 120 s (`timeout` rc=124). This is the R1-N1 hang itself; the test has no watchdog (a GIL hold cannot be interrupted), so the kill is a timeout, not an assertion. |
| e `closed` with 1 section passes | `len(sections) < 2` -> `< 1` | killed | `LoftTest.test_Should_carry_the_documented_code_When_a_loft_refusal_names_one` [closed with one section] and `LoftTest.test_Should_refuse_before_the_bracket_When_the_input_is_not_acceptable` [closed with one section]. The loft then commits with `Closed` silently reset (the L8 case); the later subtests fail on the leftover `Lofted`. |

Outputs: `evidence/mut-*.out`.

## 3. Quality bar map

| Q | Result | Evidence |
| --- | --- | --- |
| Q1 loft input, Additive/SubtractiveLoft | met | infc `LoftTest` (ruled frustum 5226.67, 3 sections in order, subtractive); live `LoftPart` (`Sections` 2 entries, `Ruled` false, `Closed` false); mutant a1 |
| Q2 sweep input, `spine` oneOf, both modes, both kinds, both spine forms; mode by live enum | met | 8 `assert_straight_sweep` tests; `test_Should_name_only_live_enumeration_members...`; mutant b; live schema `feature_sweep.spine.oneOf` [string, selector object]; live `Mode` reads `Frenet` / `Standard` |
| Q3 AD-5 bracket, mutation diff, one undo | met | infc undo tests; live: 3 calls each with `mutation.changed`/`touched`/`fingerprint_before`/`fingerprint_after`, `rolled_back: false`; 3 `document_undo` with `expect_fingerprint` -> `matches_pre_op: true` |
| Q4 refusals before the bracket with `detail.code` | met | `test_Should_refuse_before_the_bracket...` (loft 10 cases, sweep 11 cases), `..._carry_the_documented_code...` (loft 5, sweep 5); mutant e |
| Q5 no solid -> `RECOMPUTE_ERROR`, proven rollback, undo usable (L14) | met | `test_Should_roll_back_and_leave_undo_usable_When_the_sections_bound_no_solid`, `test_Should_leave_undo_usable_When_a_sweep_rolls_back` |
| Q6 cost guard measured, refused above, worst accepted well inside the budget | met with a margin question (F1) | mutant c; limit tests both sides; timing in section 4: every accepted case < 60 s, worst 32.1 s |
| Q7 TNP audit CLEAN; preview reaches both | met | infc TNP and preview tests; live `post_verify.tnp_audit.status` CLEAN on all 3 calls |
| Q8 design doc agrees with code; no shared-code edits | met | `git show --stat 6d73b983 8a3cf206`: only `features.py`, `tool_catalog.py`, design doc, spec, tests (no `transaction.py`, `rpc_dispatch.py`, `tnp_guard.py`, `confirm.py`); `gen_schemas --check` OK; live `feature_sweep` schema spot-checked against `mcp-tools-design.md` §3.7.4 |

Story ACs: (1) Body with profile square and two sections -> valid loft, one undo restores: met live (`LoftPart`). (2) Profile circle and spine sketch, `mode: "frenet"` -> `Mode` reads `Frenet`, volume = area x spine length: met live, 1696.46 = pi x 3^2 x (30 + 20 x 1.5).

## 4. Timing (host freecadcmd 1.1.4, whole tool call, budget 60 s)

Script `scripts/timing.py`; results `evidence/timing.jsonl`, `evidence/timing2.jsonl`. Sketches use `Block` constraints so the calls commit (`OK`).

| Case | Cost units | Status | Elapsed |
| --- | --- | --- | --- |
| Doubling-back BSpline spine (8 points `x = 0.5 i cos(0.3 i)`) | - | refused `sweep.degenerate_spine` | 0.01 s |
| Loft, 40 sketches of 200-line polygons, smooth | 8,000 (limit) | OK, valid | 5.91 s |
| Loft, 20 periodic BSplines of 400 poles | 8,000 (limit) | OK, valid | 0.50 s |
| Loft, 500 sketches of 16-line polygons, smooth (corner the builder did not measure) | 8,000 + 500 sections (both limits) | OK, valid | 5.35 s |
| Sweep, 100-gon along 100-segment curved polyline | 10,000 (limit) | OK, valid | 13.09 s; re-run 13.29 s |
| Sweep, 480-point BSpline profile along 20-turn helix (194 poles), frenet | ~9,600 | OK, valid | 0.48 s |
| Sweep, 250-gon along 25-turn helix (392 poles), frenet | 10,000 (limit) | OK, valid | 18.30 s; re-run 17.80 s |
| Sweep, circle along 10,000-segment polyline | 10,000 (limit) | OK, valid | **32.09 s** |

The first loft/sweep runs overlapped with a redteam-13-18 `freecadcmd` process; the re-runs ran with no other `freecadcmd` alive and gave the same times.

## 5. Live CAP-9 in the container

Build: `uv run python scripts/build_addon.py --release` from the copy (dist `features.py` holds `feature_loft`, `feature_sweep`), `docker compose -f tests/close-loop/docker/compose.yaml up -d --build`, `fcb-freecad start` (first start aborted, "desktop has not started"; second start ready, `freecad_pid` 890). The live `tools/list` lists both tools. Calls over MCP `http://127.0.0.1:18765/mcp` with `scripts/cap9.py`. Fixture sketches by one `script_exec` transaction per document (all `FullyConstrained` true); the operations under test are typed tools only.

| Document | Call | Result | Expected |
| --- | --- | --- | --- |
| LoftPart | `feature_loft` profile `Base` (square 30, z 0), sections `Mid` (circle r 12, z 20), `Top` (square 16, z 40) | OK, `AdditiveLoft`, valid, 1 solid, bbox 30 x 30 x 40, volume 19834.48, TNP CLEAN, 0.44 s | valid solid through 3 sections |
| SweepPart | `feature_sweep` profile `Ring` (circle r 3), spine `Path` (line 30 + arc r 20, 1.5 rad), `mode: frenet` | OK, `AdditivePipe`, `Mode` Frenet, volume 1696.46, TNP CLEAN, 0.17 s | pi x 9 x 60 = 1696.46 |
| GroovePart | `feature_pad` plate 60 x 40 x 10, then `feature_sweep` `subtractive: true`, profile circle r 4 centred on the top face, spine line 70 mm along X | OK, `SubtractivePipe`, `Mode` Standard, volume 22492.04, bbox 60 x 40 x 10, TNP CLEAN, 0.23 s | 24000 - (pi x 16 / 2) x 60 = 22492.04 |
| each | `document_undo` with `expect_fingerprint` = the call's `fingerprint_before` | OK, `matches_pre_op: true`, undone `buddy: loft Lofted` / `buddy: sweep Swept` / `buddy: sweep Groove`; feature absent from `restored_objects` | one undo removes the feature |

Transcripts: `evidence/build-transcript.json`, `evidence/undo-transcript.json`, logs `build.log`, `undo.log`.

Screenshots (GUI, `cua-driver` in the container; document tab by foreground pixel click, View > Standard Views > Isometric and Fit All by element token; each capture shows the active document's title and tab, so no capture is stale):
- `02-loft-result.png`: square base flaring in to the circle section (seam ellipse at mid height) and out to the smaller top square. Matches the inputs.
- `03-sweep-result.png`: straight tube up, then a smooth bend to the side, constant round section. Matches line + arc.
- `04-groove-result.png`: plate with a half-round groove along its full length on the top face; the profile circle and spine line are drawn (see N1).
- `05/06/07-*-after-undo.png`: the loft sketches only; the sweep profile and spine only; the plain plate with the groove sketches. Each matches the state before the call.

## 6. Findings

**F1 (Q6 margin, medium for the leader to judge; not a defect against the 60 s budget).** The cost model counts a straight spine edge as 1 unit, so at the 10,000-unit limit the spine edge count dominates the time. Accepted at the limit: circle along a 10,000-segment polyline 32.1 s, 250-gon along a 25-turn helix 17.8 s, 100-gon along a 100-segment polyline 13.3 s. The constant's comment (`features.py:847-853`, quoted: "100 profile edges along 100 spine lines (10,000) 5.8 s") and `mcp-tools-design.md:736` give 5.8 s for 10,000 units; the worst measured accepted call is 5.5 times that and uses about half of the 60 s budget. Reproduce: `FCB_CASE=sweep_circle_10000_lines` with `scripts/timing.py` under freecadcmd. Options are the leader's: accept and correct the comment and doc with these timings, or weigh spine line edges higher.

**N1 (note, cosmetic, cause not verified).** After the subtractive sweep the profile and spine sketches stay visible in the GUI (`04-groove-result.png`); after the additive loft and sweep they are hidden (`02`, `03`). No geometry effect.

**N2 (note, outside the Story).** `tests/external/test_headless_two_process.py::test_should_time_out_within_a_second_of_the_budget_when_a_body_holds_the_gil` failed once in the full run, which ran while the full freecadcmd suite ran in parallel on the same host; alone it passes. The file is not in the Story diff. It is not one of the two timing tests deferred in `57e9bdac`; consider adding it to that deferred entry.

No product defect found.

## 7. Teardown

FreeCAD stopped (`fcb-freecad stop`: window close timed out, process killed by the helper; three unsaved test documents). `docker compose ... down`: container `fcb-desktop` and network removed; image `fcb-desktop:local` kept. Worktree `fcb-verify-13-18` removed (`git worktree remove --force`). No `freecadcmd` of this verifier left running. Host port 8765 and `user.cfg` not touched. Scratch: `scratchpad\verifier-13-18\` only.

## Round 2

Artifact: `af61cc66` (round 2 fixes `eaf97e18`, lens patches `af61cc66`). New detached copy `fcb-verify-13-18` at `af61cc66`; removed at the end. Triage `triage-13-18-r2.md`, decision 39. Evidence: `tests/uat/run/13-18-r2/` in the main repo path.

**Verdict: PASS with two low findings (R2-F1, R2-F2) and one recorded residual (R2-R1).** Every row except F1 is proven: reverting its fix turns a named test red. Reverting F1 turns no test red (R2-F1). The red team's two worst lofts are now refused in under 0.4 s. The worst accepted loft took 13.7 s and the worst accepted sweep 9.3 s, inside the 60 s budget.

### Gates

| Command | Result |
| --- | --- |
| ruff check, check_imports, gen_schemas --check, check_provenance, check_status_vocab, check_skill_shape | all OK |
| `ruff format --check src/freecad_buddy/usecases/features.py` | already formatted |
| freecadcmd `tests/run_tests.py` (temp cfg, `FREECAD_USER_HOME` temp) | `Ran 1254 tests`, `OK (skipped=1)`; 68 in `LoftTest`/`SweepTest` (46 in round 1) |
| `uv run --extra dev pytest tests/external -q` (Git Bash, run alone) | 2109 passed, 6 skipped, 0 failed |

The mutant runner prints `FEATURES_FILE=D:\Work\Personal\Sources\fcb-verify-13-18\src\...\features.py` on every run. Baseline: `fail=0 error=0 run=68`.

### Row proofs (revert the fix, run `LoftTest` + `SweepTest`)

| Row | Revert | Result | Red tests |
| --- | --- | --- | --- |
| RT-1 quadratic loft model | `_loft_cost` returns `sum(sizes)` | killed (4) | `test_Should_cost_the_larger_section_of_each_pair_squared_When_sections_differ` (9 != 32), `test_Should_refuse_a_loft_that_the_edge_sum_would_accept_When_sections_are_large`, `test_Should_refuse_with_a_code_When_the_sections_cost_more_than_the_limit`, `test_Should_count_the_poles_When_a_section_edge_is_a_bspline` |
| F1 sweep limit 3,000 | `_SWEEP_MAX_COST = 10000` | **survived** (0 red) | none. See R2-F1. |
| RT-2/RT-6 result check | `check()` returns at once | killed (10 fail, 1 error) | loft: `..._closed_loft_folds_back_through_itself`, `..._subtractive_loft_misses_the_solid`; sweep: `..._spine_lies_in_the_profile_plane`, `..._subtractive_spine_lies_in_the_profile_plane`, `..._spine_climbs_and_falls_back_the_same_way`, `..._profile_is_wider_than_the_bend_of_the_spine` [standard, frenet], `..._subtractive_sweep_misses_the_solid`, `..._shape_holds_more_than_one_solid`, `..._shape_is_not_valid`, `..._leave_the_sketches_visible_and_undo_usable_When_a_sweep_result_is_refused` |
| RT-3 `loft.nothing_to_subtract` | remove `_require_base_to_subtract(..., "loft")` | killed | `test_Should_refuse_before_the_bracket_When_a_subtractive_loft_has_no_solid_to_cut` |
| RT-4 long helix | sample count back to a flat 400 | killed | `test_Should_accept_a_long_helix_When_it_has_more_than_a_hundred_turns` (error: refused); `test_Should_refuse_without_hanging_When_the_spine_doubles_back_on_itself` stays `ok` under the fix and under the revert |
| RT-5 code | unresolvable selector back to plain `ValidationError` | killed | `test_Should_carry_the_documented_code_When_a_sweep_refusal_names_one` [unresolvable edge] |
| N1 loft | `hidden = []` | killed | `test_Should_hide_the_consumed_sketches_When_a_loft_commits_and_show_them_on_undo` ([True, True] != [False, False]) |
| N1 sweep | `hidden = []` | killed | `test_Should_hide_the_consumed_sketches_When_a_sweep_commits_and_show_them_on_undo` |

Outputs: `evidence/mut-*.out`.

### Timing (host freecadcmd 1.1.4, whole tool call, no other freecadcmd running; `scripts/timing.py`, `evidence/timing.jsonl`)

| Case | Cost | Result | Elapsed |
| --- | --- | --- | --- |
| Red team: two 3,999-gons | 15,992,001 | refused `loft.too_complex` | 0.31 s (red team: 111 s at `d8968a1e`) |
| Red team: circle to 4,000-gon | 16,000,000 | refused `loft.too_complex` | 0.14 s (red team: 317 s) |
| Doubling-back spine | - | refused `sweep.degenerate_spine` | 0.01 s |
| Loft circle to 1,000-gon | 1,000,000 (limit) | OK, valid, 1,002 faces | 13.18 s |
| Loft two 1,000-gons | 1,000,000 | OK | 10.56 s |
| Loft 500 sections of 44-gons (both limits; corner the lenses left unmeasured) | 966,064 | OK | **13.69 s (worst loft)** |
| Loft circle to 999-pole BSpline / two 999-pole BSplines | ~998,000 | OK | 0.14 s / 0.16 s |
| Loft two 250-gons (Boolean check runs, 252 faces) | 62,500 | OK | 3.54 s |
| Sweep circle along 3,000-segment polyline | 3,000 (limit) | OK, 3,002 faces | **9.29 s (worst sweep)** |
| Sweep circle along 10,000 segments (round-1 worst, 32 s) | 10,000 | refused `sweep.too_complex` | 0.36 s |
| Sweep 2,999-pole BSpline profile along a line | 2,999 | OK | 0.21 s |
| Sweep 149-pole BSpline profile along 20-turn helix | ~2,980 | OK | 0.30 s |
| Sweep 10-gon along 30 lines (Boolean check runs, 302 faces) | 300 | OK | 0.36 s |
| Sweep circle along 120-turn `Part::Helix` (pitch 2) | 334 | OK, valid | 1.21 s |

The constant comments quote lower whole-call times than measured here (circle to 1,000-gon 10.7 s against 13.2 s; circle along 3,000 lines 4.1 s against 9.3 s). Both limits still keep the worst accepted call at a quarter of the budget or less.

### Builder deviations

**Closed lofts refused as `loft.invalid_result`: accepted.** Probe `scripts/probe.py`, `evidence/probe.jsonl`: closed lofts of 3, 4, 6, 8 and 12 sections around a ring (sketch planes through the Z axis), circle or square, smooth or ruled, built in raw FreeCAD 1.1.4:
- circle smooth: no shape;
- circle ruled and square ruled: `isValid()` false;
- square smooth: valid but the Boolean check reports `BOPAlgo SelfIntersect`, except **8 squares smooth: valid and clean**.

Through the tool, every layout FreeCAD builds bad is refused with `loft.invalid_result` and a precise message, and the 8-square smooth ring returns `OK` (volume 8041.29). The refusals are correct: those shapes really are invalid. Residual: the design doc (`mcp-tools-design.md:734`) says "every closed loft tried ... built an invalid or self-intersecting solid". That is true for the builder's probes, but a valid closed loft exists (R2-F2).

**Self-intersection not detected for BSpline inputs: accepted as a residual (R2-R1).** The layout of `test_Should_refuse_the_result_When_the_profile_is_wider_than_the_bend_of_the_spine`, with the circle profile replaced by a periodic BSpline of 24 points, returns `OK` in both modes. The result has `is_valid` true, 1 solid and volume 942.48, but `Shape.check(True)` reports `BOPAlgo SelfIntersect`. The circle-profile version is refused (`sweep.invalid_result`). This matches the documented limit (`features.py:934`, `mcp-tools-design.md:734`): the check is skipped for BSpline inputs because it can hold the interpreter more than 50 s.

Extra RT-4 probes (pitch 1, radius 5, circle r 0.3, frenet):
- `Part::Helix` with height 120 (3,330 poles) and height 150 (7,165 poles): `OK` in 1.15 s and 1.30 s.
- `Part.makeHelix(5, 2500, 10)` (500 turns, 392 poles): passes the spine check now. FreeCAD's result is then refused as `sweep.invalid_result` in 0.04 s, not with the false "doubles back" reason.

### Live (container, N1)

Build from the copy (dist `features.py` holds `_hide`), `compose up`, `fcb-freecad start` (the first start aborted, the second was ready, pid 582). `scripts/cap9.py` (same as round 1) results:
- Loft, sweep and groove all `OK`, volumes as in round 1: 19834.48, 1696.46, 22492.04.
- `mutation.touched` now lists the hidden sketches, for example `['Groove', 'Body', 'Ring', 'Path']`.
- Three `document_undo` calls: `matches_pre_op: true`.

Screenshots:
- `01-groove-after-subtractive-sweep.png`: isometric, Fit All. The grooved plate shows with no profile circle and no spine line (round 1 `04-groove-result.png` showed both). N1 fixed.
- `02-groove-after-undo.png`: the plain plate, with the profile circle and spine line shown again.

### Findings

**R2-F1 (low, test gap).** The F1 fix is the constant `_SWEEP_MAX_COST = 3000` (`features.py`, sweep cost block). Setting it back to 10000 turns no test red, because every sweep-limit test patches the constant to 0 or 1. A regression of the limit would pass CI. Fix proposal: add a test that pins the value, or one that refuses a known 3,001-unit sweep (for example a circle along 3,001 lines, refused before the bracket).

**R2-F2 (low, doc).** `mcp-tools-design.md:734` says every closed loft tried built an invalid or self-intersecting solid, so `closed: true` is "usually refused". A closed loft of 8 squares (8 x 8 mm, ring radius 20, smooth) builds valid and clean, and the tool accepts it. Proposal: name this layout in the doc. It could also serve as the positive closed-loft test that the round-2 Gap lens asked for; the current test only proves `Closed` is written with the result check off.

**R2-R1 (residual, documented).** Self-intersecting sweep from a BSpline profile returns `OK`, as recorded above.

Round-1 F1 is closed: the 32 s sweep is now refused in 0.36 s. Round-1 N1 is closed.

### Teardown

FreeCAD stopped (window close timed out; helper killed pid 582). Container and network removed; image kept. Worktree removed. No `freecadcmd` running. Host port 8765 and `user.cfg` not touched.
