# Verify 13-17: Part primitive and Part boolean tools

- Story: 13-17, tools `feature_part_primitive` and `feature_part_boolean` (decisions 44, 51, 52).
- Code verified: branch `story/13-17-part-primitive-boolean` at `deaa2b25`, worktree `D:/Work/Personal/Sources/freecad-buddy-wt-13-17`. The worktree was clean when the gates ran.
- Verifier: verifier-13-17, 2026-11-26.
- Verdict: **PASS** for `deaa2b25`, with one test-gap finding (F1) and one note (N1).

## Worktree changed during the run

At 02:40 to 02:41 (after every run below) the worktree received uncommitted edits: `src/freecad_buddy/usecases/features.py` (placement angle bound `_MAX_PLACEMENT_ANGLE_DEG`, and the stale-input check now walks `OutListRecursive` and `mustExecute()`), `tests/infc/test_feature_part.py`, `tests/infc/test_set_parameters_placement.py`. Those edits are **not verified** here. Every result below is for `deaa2b25`: the gates ran on a clean tree, the mutants ran on `git archive deaa2b25`, and the container addon `features.py` hash `c261574f…` equals `git show deaa2b25:src/freecad_buddy/usecases/features.py`.

## 1. Gates at deaa2b25

| Gate | Result |
| --- | --- |
| `uv run --extra dev ruff check .` | exit 0, "All checks passed!" |
| `scripts/check_imports.py` | exit 0, `check_imports OK` |
| `scripts/check_status_vocab.py` | exit 0, `check_status_vocab OK` |
| `scripts/gen_schemas.py --check` | exit 0, `gen_schemas --check OK` |
| `scripts/check_skill_shape.py` | exit 0 |
| `scripts/check_provenance.py` | exit 0, `check_provenance OK` |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | **2122 passed, 6 skipped**, 136.5 s. No failure, so no re-run. Builder claimed 2121. |
| `freecadcmd -u <tmp>/user.cfg -s <tmp>/system.cfg tests/run_tests.py`, private `FREECAD_USER_HOME` | **Ran 1524 tests, OK (skipped=1)**, 164.8 s. Matches the builder claim. |

## 2. Mutants

Copy: `scratchpad/verifier-13-17/mutcopy` (`git archive deaa2b25 src tests/infc tests/run_tests.py`), removed after the run. Runner: `unittest` on `infc.test_feature_part` (74 tests) under `freecadcmd` with a private profile; the copy's `features.py` was imported (path printed). Baseline: 74 run, 0 fail, 86 s.

| Mutant | Change | Result |
| --- | --- | --- |
| invalid-result, state branch | `if _FAILED_STATES & set(result.State)` → `if False` | KILLED, 2 fail (`..._invalid_code_When_an_input_fails_to_recompute`, `..._kernel_message_with_the_invalid_code_...`) |
| invalid-result, `isValid` branch | `if not shape.isValid()` → `if False` | KILLED, 1 fail (`..._invalid_result_When_the_result_shape_is_a_bowtie_solid`) |
| empty-result | drop `not shape.Solids` | KILLED, 7 fail + 1 error |
| Visibility hide | `obj.Visibility = False` → `pass` | KILLED, 5 fail |
| `state_probe` | drop `state_probe=_object_state` | KILLED, 1 fail (`..._state_probe_that_reads_visibility_...`, a structural test; rollback of Visibility itself still passes without the probe) |
| trust check | `is_measurable_solid` removed from the last loop | KILLED, 9 fail + 2 errors |
| cross-input pairs → base x tools | `across = solids[0] * sum(solids[1:])` | KILLED by assertion in 2 s (`test_Should_refuse_before_any_write_When_the_solid_pairs_are_above_the_limit`: message "8 solid pairs", expected "11"). The real-limit test (`..._crossing_tools_When_their_pairs_with_each_other_pass_the_limit`) hangs in the kernel: 60 s timeout, process ended after 178 s (rc 124). The whole file with this mutant passed the 600 s timeout. |
| in-input count removed | `inside += 0` | **NOT KILLED by an assertion within 60 s** (F1). The only test that catches it, `test_Should_refuse_one_compound_of_crossing_solids_When_it_is_the_only_tool` (`test_feature_part.py:1029`), runs the >600 s kernel call under the mutant: 60 s timeout, ended rc 124 at 61 s. That test is not designed to time out. `..._skip_the_pass_inside_...` and `..._count_only_solids_whose_boxes_overlap_...` pass under the mutant (2 run, 0 fail). |

## 3. Probes under freecadcmd through the real handler

Script `scratchpad/verifier-13-17/probe/probe_13_17.py`: `build_inline_handlers(DocumentRegistry(), ...)` and `MethodRegistry.dispatch`, so refusals come back as envelopes with `detail.code`. Imported `features` from wt-13-17 `src` (path printed). 33 of 33 PASS.

| Probe | Observed | Expected |
| --- | --- | --- |
| box 10x20x30 | 6000.0, `Part::Box`, parent None | 6000 |
| cylinder r2 h30 | 376.99111843 | pi r^2 h = 376.991118 |
| cone r1 5 r2 0 h10 | 261.79938780 | 261.799388 |
| cone frustum r1 5 r2 2 h10 | 408.40704497 | pi h/3 (R^2+Rr+r^2) = 408.407045 |
| sphere r4 | 268.08257311 | 268.082573 |
| torus 10/2 | 789.56835209 | 2 pi^2 R r^2 = 789.568352 |
| placement base (1,2,3), z 90 deg | bbox (-19,2,3)-(1,12,33) | same |
| cut, plate 210x10x10 by 1/2/20 cubes (62.5 overlap each) | 20937.5 / 20875.0 / 19750.0 | 21000 - n x 62.5 |
| fuse, same | 21062.5 / 21125.0 / 22250.0 | 21000 + n x 62.5 |
| common, plate with 1/2/20 staggered 20x10x10 boxes | 1000 / 975 / 525 | (20 - (n-1) x 0.5) x 50 |
| types | Cut/Fuse/Common for 1 tool; Cut+MultiFuse, MultiFuse, MultiCommon for 2 and 20 | spec table |
| several-tool cut | `R_tools` `Part::MultiFuse`, hidden, `R.Tool` is it; `touched` `['R', 'R_tools']` | spec |
| inputs hidden, result visible, `Refine` true by default | all runs | spec |
| 20-tool cut time | 1.25 s | under 120 s |
| disjoint common | `RECOMPUTE_ERROR` `part_boolean.empty_result`, `rolled_back` true, `rollback_proven` `rolled_back_verified`; 2 objects before and after; A and Far visible | spec |
| disjoint common fingerprint | digest not byte-equal, `massprops_equal` true (N1) | equal pre-op |
| next mutation + undo after the rollback | both `OK`, `Ball` gone | usable |
| reversed `Rev` as tool and as base, `OpenShell` as tool, x cut/fuse/common | `INVALID_INPUT` `part_boolean.untrusted_shape`, message names the object and "reversed or degenerate" / "Shell, not made only of solids"; fingerprint unchanged | spec |
| 21 tools | `INVALID_INPUT` `part_boolean.invalid_input`, no `R` | spec |
| `document_undo` after a 1-tool and a 3-tool cut, `expect_fingerprint` = the boolean's `fingerprint_before` | `OK`, `matches_pre_op` true, `R` and `R_tools` gone, inputs visible | spec |

## 4. Acceptance map (code and tests at deaa2b25)

| Q | Evidence | Result |
| --- | --- | --- |
| Q1 primitives, analytic volume | `features.py:4069` `feature_part_primitive`; `test_feature_part.py:133`; probes 1-7; TC-21-04 | PASS |
| Q2 primitive refusals before write | `features.py:4023` `_part_primitive_values`, `:4005` `_part_name_available`; `test_feature_part.py:197`, `:242`, `:269`, `:1161`, `:1179`; TC-21-04 torus 2/2 | PASS |
| Q3 boolean objects, refine, hiding | `features.py:4331`, `:4388` (`Refine`), `:4390` (`Visibility`); `test_feature_part.py:374`, `:389`, `:411`, `:425`, `:452`, `:462`, `:476`; probes; TC-21-01, TC-21-04 | PASS |
| Q4 boolean refusals and limits at boundaries | `features.py:4182` `_part_boolean_inputs`, `:4233` `_check_part_boolean_inputs`; `test_feature_part.py:726`-`:1290` incl. `:933`, `:947`, `:1133` (20 tools), `:1235`, `:1275`; probes (21 tools, reversed, shell); mutants trust/across killed; in-input count see F1 | PASS with F1 |
| Q5 empty/invalid result, rollback | `features.py:4295` `_part_boolean_result_check`; `transaction.py:82` `RecomputeFailure`, `:739`; `test_feature_part.py:486`-`:712`; mutants killed; probe; TC-21-02 | PASS |
| Q6 undo restores | `test_feature_part.py:578`; probe `matches_pre_op` true; TC-21-01 (6 undos), TC-21-04 | PASS |
| Q7 confirm gate and preview | `test_feature_part.py:317`, `:331`, `:1306`, `:1320` | PASS (infc) |
| Q8 shared trust helper | `usecases/shape_trust.py`; `queries.py:22` imports it; `features.py:4283`; `check_imports` OK; query tests in the 1524 run | PASS |
| Q9 shared placement parser | `features.py:4107`, `:4116` `_placement_value`; `test_feature_part.py:177`; probe bbox | PASS |
| Q10 docs, schemas, `detail.code` | `docs/intent.md:254`; `mcp-tools-design.md:192`-`:193`, `:581`-`:582`, §3.7.5 `:749`-`:787`; `tool_catalog.py:934`, `:974`; `test_feature_contract.py:43`-`:44`, `:445`-`:512`; `test_mcp_surface.py:112`-`:113`; `gen_schemas --check` OK; `detail.code` seen in probes and UAT | PASS |
| Q11 near-limit under 60 s | `test_feature_part.py:1340`, `:1366`, `:1382`, `:1399` (assert < 60 s), passed in the 1524 run | PASS |
| Q12 gates, provenance | section 1; `check_provenance` OK | PASS |
| Q13 live container | section 5 | PASS |

## 5. Container UAT (run `tests/uat/run/13-17-r1/`)

- Build: `build_addon.py --release` in wt-13-17; `compose up -d --build`; `/repo` mount = wt-13-17 (read-only), `tests/uat/run` writable. Installed `features.py` sha256 `c261574f…` = `src` at `deaa2b25`. `fcb-freecad start` worked on the first try; `/healthz` `freecad_pid` 400.
- Harness gate: control yes (`get_window_state` 346 elements, File/Edit/View present); observation yes (window PNGs read by the verifier).
- Driver `evidence/tc21.py` (MCP client after the 13-fu `mcpcall.py` pattern) and `cua-driver` CLI through `docker exec`. Results: `tests/uat/run/13-17-r1/results.md`.

| Case | Verdict | Visual read |
| --- | --- | --- |
| TC-21-01 | PASS | One solid per result; x:y edge ratio 0.5 (cut), 0.5 (common), 1.5 (fuse); inputs nested under each result in the tree; after 6 undos A and B shown. |
| TC-21-02 | PASS | Before and after: two cubes in the same places, tree A and Far. |
| TC-21-03 | PASS | Tree `Rev`, `BodyCut`; no `BadCut`, no `PadCut`. |
| TC-21-04 | PASS | Plate with two holes and a ring; bottom view: pin hole straight through, cone hole a conical wall around a small opening. |

- Logs: `addon.log` no `ERROR`/`Traceback`; `/tmp/freecad.log` no `Traceback`.
- Test-case change (uncommitted): TC-21-04 visual Then adds a bottom view, because the isometric view cannot show that the cone hole narrows.
- Teardown: `fcb-freecad stop` (no pid), `compose down` (container and network removed).

## Findings

- **F1 (low, test gap, not a product defect).** The in-input pair count (`features.py:4267`-`:4272`) is guarded only by `test_feature_part.py:1029`, which under the mutant runs the >600 s kernel call before it can fail. No fast test with a lowered `_PART_BOOLEAN_MAX_SOLID_PAIRS` covers the call site, as `:947` and `:1249` do for the face and cross-input counts. Fix: add one test that patches the limit to a small number and passes one compound of 3 overlapping boxes, asserting `part_boolean.too_complex` and the "overlapping inside one input" text.
- **N1 (note).** After the disjoint-common rollback, the fingerprint digest is not byte-equal to the pre-op digest; `massprops_equal` is true and the bracket reports `rolled_back_verified`. This is the documented proof path (`transaction._prove_rollback`), not a defect.
- No product defect found.

## Round 2 (head 6a320fd2, host only)

Commits checked: `bec5655c` (dependency-closure stale check, placement angle bound, doc text) and `6a320fd2` (fast in-input count test for F1). The worktree was clean at the start of the run. No container.

### Gates

| Gate | Result |
| --- | --- |
| ruff, check_imports, check_status_vocab, gen_schemas --check, check_skill_shape, check_provenance | all exit 0 |
| `pytest tests/external -q` (Git Bash) | 2121 passed, 1 failed, 6 skipped, 137.0 s. Failed: `test_mcp_cache_proxy.py::test_should_answer_both_calls_when_two_parallel_calls_meet_a_lost_session`. It ran in parallel with a freecadcmd probe. Run alone 3 times: 1 passed each time. Whole `test_mcp_cache_proxy.py`: 33 passed. This is the known load-only flaky test. |
| `freecadcmd tests/run_tests.py` (private cfg and `FREECAD_USER_HOME`) | **Ran 1531 tests, OK (skipped=1)**, 161.0 s |

### Red-team probes (copied, run on `git archive 6a320fd2`)

- `p2.py` (A = Reverse(Mid), Mid Touched, A reads Up-to-date): `PartToolRefusal` `part_boolean.untrusted_shape`, "Mid (a dependency of A) is ['Touched'], so the shape of A may be out of date; recompute the document first", 0.02 s. No `Result` object.
- `p3b.py` n=100 (Draft arrays behind `Part::Compound`, arrays Touched): refused `untrusted_shape`, "Array (a dependency of FamX) is ['Touched'] ...", 0.04 s; whole probe under 1 s (was 63.2 s and `OK` on deaa2b25).

### Mutants (copy of 6a320fd2, removed after)

Suite: `infc.test_feature_part` + `infc.test_set_parameters_placement` (125 tests). Baseline: 125 run, 0 fail, 83 s.

| Mutant | Result |
| --- | --- |
| closure reduced to the input (`features.py:4271` `(obj, *obj.OutListRecursive)` → `(obj,)`) | KILLED, 2 fail: `test_feature_part.py:771`, `:789` |
| angle bound removed (`if abs(degrees) > _MAX_PLACEMENT_ANGLE_DEG` → `if False`) | KILLED, 2 fail: `test_feature_part.py:242`, `test_set_parameters_placement.py` `PlacementBoundTest.test_Should_refuse_before_the_bracket_When_a_rotation_angle_is_above_the_bound` |
| in-input count removed (`inside += 0`) | KILLED by assertion in 1 s: `test_feature_part.py:1362` (`PartToolRefusal not raised`). The same test passes on the unmutated copy (1 s). F1 is closed. The older test `:1029` still hangs under this mutant, so the whole file with this mutant hits a 300 s timeout; the fast test is what kills it. |

### Attacks on the dependency check (`scratchpad/verifier-13-17/r2/probes/v_attack.py`, `v_attack2.py`)

| Attack | Result | Verdict |
| --- | --- | --- |
| `App::Link` input, target `T` Touched (L reads Up-to-date) | refused `untrusted_shape`, "T (a dependency of L) is ['Touched']" | PASS |
| `App::Link` input, fresh target | accepted; with `LinkTransform` false the link shape sits at the link's own placement, so cut A - L was empty → `RECOMPUTE_ERROR` `empty_result`, rolled back. FreeCAD Link semantics, not a defect | PASS |
| Dependency in error: `Bad.Length = -1` (`Invalid`, `Touched`) behind `RevRev = Reverse(Reverse(Bad))` (RevRev reads Up-to-date) | refused, "Bad (a dependency of RevRev) is ['Invalid', 'Touched']" | PASS |
| Dependency in error inside a `Part::Compound` (Comp left Touched by the recompute) | refused, "Comp is ['Touched']" (still holds 1 solid of the old shape) | PASS |
| Dependency in another saved document (`App::Link`, `LinkTransform` true, to `a3other#X`) | `OutListRecursive` = `["a3other#X"]`; fresh: `OK`, volume 500.0; after `X.Length = 20` (X Touched, XL Up-to-date): refused "X (a dependency of XL) is ['Touched']" | PASS (N2) |
| Cross-document `PropertyLink` (`Part::Reverse.Source` = external) | FreeCAD refuses the assignment ("PropertyLink does not support external object"); no path | n/a |
| `enforceRecompute()` on a dependency | State `Touched` → refused | PASS |
| Body base whose `Pad` is Touched (Body reads Up-to-date) | refused, "Pad (a dependency of Body) is ['Touched']" | PASS |
| Fresh documents after `recompute()` | Compound-of-Compound of a box (height 20) cut by a shifted cube: `OK`, 1500.0 (analytic 1500); Body (8x16x10 pad) cut by a box: `OK`, 880.0 (analytic 880) | PASS |

- `mustExecute()` is not exposed on `Part::Box` in Python (`'PrimitivePy' object has no attribute 'mustExecute'`). The committed check reads only `State`, so it does not call `mustExecute()`. An uncommitted draft that called it would have raised. `enforceRecompute()` sets `Touched`, so reading `State` covers it.
- **N2 (note, low).** For a stale dependency in another document, the message says "recompute the document first". The stale object `X` is in `a3other`, so the caller may need to recompute that document. This is wording only: the refusal is correct.

### Round 2 verdict

**PASS** at `6a320fd2`. RT-1 is fixed: p2 and p3b are refused before any write, with the dependency named. The angle bound is enforced. F1 is closed. No new defect. N2 is wording only.
