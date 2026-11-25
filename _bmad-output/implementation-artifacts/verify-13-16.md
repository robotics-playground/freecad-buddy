# Verify Story 13-16 (`feature_set_parameters` placements and strings)

Head `15a097d6` (wt-13-16). Verifier: verifier-13-16. Date 2026-11-26.

## Verdict

PASS. No product defect. One test-case defect in TC-20 (fixed, uncommitted). Gates green, six of six mutants killed, probes match the contract, container UAT 2 of 2 PASS.

Note: while this verification ran, someone else wrote uncommitted changes to the worktree (mtime 00:34-00:35): `src/freecad_buddy/usecases/features.py` (+`_MAX_PLACEMENT_BASE_MM`, `parameters.out_of_range`, `_is_finite`), `src/freecad_buddy/hosts/tool_catalog.py`, `tests/infc/test_set_parameters_placement.py`. Everything below is on the committed `15a097d6`: the gates finished before those writes, the mutant copy is a `git archive` of `15a097d6`, and the installed addon hash equals `git show 15a097d6:.../features.py` (`0b16d728…6b7`). Those new changes are not verified.

## 1. Gates

| Gate | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `check_imports` / `check_status_vocab` / `gen_schemas --check` / `check_provenance` | OK |
| `check_skill_shape` | exit 0 |
| `pytest tests/external -q` (Git Bash, `uv run --extra dev`) | run 1: 1 failed, 2116 passed, 6 skipped (ran during the `docker compose --build`). Failed: `test_mcp_cache_proxy.py::test_should_answer_both_calls_when_two_parallel_calls_meet_a_lost_session` (`[False, True] == [False, False]`); alone: 1 passed. Run 2 (no load): **2117 passed, 6 skipped**. The test file and the proxy are not changed by the Story: a load-dependent timing failure. |
| `freecadcmd tests/run_tests.py` (private `-u/-s` cfg, private `FREECAD_USER_HOME`) | **Ran 1443, OK (skipped=1)** |

## 2. Mutants (copy `scratchpad/verifier-13-16/mutcopy-15a097d6`, `git archive 15a097d6`, removed after)

Modules run: `infc.test_set_parameters_placement`, `infc.test_confirm_gate`, `infc.test_feature_tools` (271 tests). Baseline: 271 OK.

| Mutant | Result |
| --- | --- |
| read-back skipped (`recompute_check` returns at once) | 7 failures (clamped angle, python feature placement/string, expression numeric/placement, two rollback proofs) |
| `state_probe` `None` | 2 failures (17-digit snapshot proof, label restore through snapshot) |
| float rounding removed (`_stable_float` returns the raw float) | 1 failure (17-digit snapshot proof) |
| `not_attached` back to the `Hidden` test | 2 errors (hidden-offset attached object; MapMode Deactivated) |
| integer compare back to `isclose` | 1 failure (integer off by one in a billion) |
| no-op shortcut always taken | 21 failures, 8 errors |

## 3. Probes under freecadcmd (`scratchpad/verifier-13-16/probe_1316.py`, outputs `probe_out.jsonl`, `probe_out2.jsonl`; source = wt-13-16 `src`)

| Probe | Output |
| --- | --- |
| Body placement x=15, 30 deg Z | `OK`, `undo_steps` 1, stored `Pos=(15,0,0) YPR=(30,0,0)` |
| Pad in Body `Placement` | `INVALID_INPUT` "Block.Placement is read-only; a feature inside a Body follows the Body, so move the Body, or the AttachmentOffset of its sketch"; value unchanged |
| Part::Box placement, axis [1,1,0] 45 deg | `OK`; same call again: `unchanged ["Placement"]`, `undo_steps` 0, no `mutation` |
| Datum plane attached (FlatFace): `Placement` / `AttachmentOffset` | `INVALID_INPUT` "…its attachment sets it, so write AttachmentOffset instead" / `OK`, z 4 |
| Datum plane Deactivated: `AttachmentOffset` / `Placement` | `parameters.not_attached` / `OK`, z 6 |
| Label collisions: Block→"Body", →"Profile", Profile→"Body001", "Mount plate" twice, "", "bad\x00nul" | stored `Body001`, `Profile001`, `Body001` (freed), `Mount plate`, then `unchanged ["Label"]`; `""` stored `""` (accepted); NUL → `parameters.invalid_string` |
| Part::Cylinder `Angle` 400 deg / 400 / 400.0 / -10 deg | `RECOMPUTE_ERROR` `parameters.value_overwritten` ("reads 360.0 deg"; -10 → "reads 0.0 deg"); stored stays 360 |
| Part::RegularPolygon `Polygon` 2 / 7 | `value_overwritten` ("reads 3") / `OK`, 7 |
| Expression-bound Pad `Length` (3 mm), Body `.Placement.Base.x` (7 mm) | `value_overwritten` for Length and for x; writing y alone `OK` (7, 2, 0) |
| `App::PropertyString` bound to `<<fixed>>` | `value_overwritten`, value `fixed` |
| Label + overwritten Length in one call | `value_overwritten`; Label rolled back to `Block` |
| Placement + Label write, then `document_undo(expect_fingerprint=fingerprint_before)` | `OK`, `matches_pre_op` true, placement (0,0,0), label `Free` |
| Label-only write, then undo with fingerprint | `OK`, `matches_pre_op` true, label `Block` |
| Equal Label + equal numeric Length | bracket opens, `undo_steps` 1 (decision 50: shortcut only for all-placement/string calls) |

Observation (no defect claimed): an empty `Label` `""` is accepted and stored. FreeCAD allows it; the tree then shows a blank row.

## 4. AC map

| Q | Evidence |
| --- | --- |
| Q1 | `features.py` `_placement_value` (~:2357-2405), `_property_family` placement branch; tests `test_set_parameters_placement.py:169`, `:188`, `:45`; UAT TC-20-01 |
| Q2 | `_only_keys`, `_rotation_axis`, `_placement_value` raise `ValidationError` before the bracket; tests `:91`, `:252` |
| Q3 | `_storable_text`, `report` adds `label {requested, stored}`; tests `:458`, `:473`, `:486`, `:498`; probe label collisions; UAT TC-20-02 |
| Q4 | `_parameter_writes` read-only hints `features.py:2267-2276`; `recompute_check` → `parameters.value_overwritten`; tests `:318`, `:338`, `:356`, `:369`, `:400`, `:416`; UAT TC-20-02 |
| Q5 | `_require_attached_offset` (MapMode test); tests `:442`, `:523`, `:533`; mutant `mapmode` killed |
| Q6 | `_written_state` passed as `state_probe`; `_comparable`/`_stable_float`; tests `:615`, `:644`, `:673`; mutants `probe`, `rounding` killed |
| Q7 | `unchanged_names` / `_unchanged_parameters_envelope`; `_recorded_undo_steps`; tests `:202`, `:219`, `:229`, `:241`; mutant `noop` killed; UAT TC-20-01 repeat call |
| Q8 | `test_confirm_gate.py:797`, `:811`, `:823`; `mcp-tools-design.md:104` |
| Q9 | `_placement_value(raw, what, current=None)` defaults; test `:34` |
| Q10 | `mcp-tools-design.md:192`, `:576`, `:581`; `tool_catalog.py:882-891`; `skills/freecad-scripting-idioms/SKILL.md:79-82`; `check_skill_shape` and `gen_schemas --check` OK |
| Q11 | Section 1 |
| Q12 | Section 5 |

## 5. Container UAT (`tests/uat/run/13-16-r1/`, wt-13-16, uncommitted)

Build: `build_addon.py --release`, `compose up -d --build` (mount `/repo` = wt-13-16 read-only, `tests/uat/run` rw), `fcb-freecad start` first try, pid 559. AT-SPI tree 346 elements.

| Case | Verdict | Evidence |
| --- | --- | --- |
| TC-20-01 | PASS | write `OK` `undo_steps` 1; `query_placement` (10, 2, 3) 90 deg Z; repeat `unchanged ["Placement"]`, `undo_steps` 0, no `mutation`; screenshots: block moved lower right; undo → (1, 2, 3) |
| TC-20-02 | PASS (after TC fix) | label `{requested: "Profile", stored: "Profile001"}`; Placement on attached `Profile` `INVALID_INPUT` naming `AttachmentOffset`, z 0.0; offset `OK` z 5.0; screenshots: solid higher, tree shows `Profile001` under `Body`; two undos → `["Block", 0.0]` |

TC defect B1 (`tests/uat/run/13-16-r1/bugs.md`): the TC build made an under-constrained sketch (DoF 8), so the first TC-20-02 execution returned `SPEC_FAILED` `verify_sketch failed on Profile (dof=8)` from the AD-5 post-verify (`transaction.py:177`, `:301-321`), as designed. Fixed in `TC-20-set-parameters-placement-strings.md`: fully constrained sketch with a `('built', True)` check, `label` arg for `document_create`, no fit before the TC-20-02 after capture, and the tree-expand step (AT-SPI `Toggle` only selects; a foreground pixel click on the arrow expands). Both cases re-run from the Given. First executions kept as `*-given-v1.*` and `out-tc20-01-attempt1-wrong-arg.json` (agent fault: `name` instead of `label`).

Teardown: `fcb-freecad stop` (no pid), `compose down` (container and network removed). No `FCB_TMP_snap_*` left. Host `:8765` not touched.

## Round 2 (head `195868c5`, red-team fixes; host only)

Verdict: PASS. All red-team findings T1-T4 and L-1 are closed, and no product defect was found. One doc drift is open (R2-F1, low).

### Gates (worktree clean at `195868c5`)

| Gate | Result |
| --- | --- |
| ruff, check_imports, check_status_vocab, gen_schemas --check, check_skill_shape, check_provenance | all exit 0 / OK |
| `freecadcmd tests/run_tests.py` (private cfg and `FREECAD_USER_HOME`) | **Ran 1450, OK (skipped=1)** |
| `pytest tests/external -q` (Git Bash) | **2117 passed, 6 skipped** |

### Red-team probes (copied to `scratchpad/verifier-13-16/rt/`, run against wt-13-16 `src`)

| Probe | 15a097d6 (red team) | 195868c5 |
| --- | --- | --- |
| rt1 P7 base x = 10**400 | `RECOMPUTE_ERROR` | `INVALID_INPUT` "Body.Placement.base.x value must be finite" |
| rt1 P7 angle = 10**400 | `RECOMPUTE_ERROR` | `INVALID_INPUT` "…rotation.angle value must be finite" |
| rt2 P8b Base.x = 1/3000 (snapshot path) | `SPEC_FAILED`, not proven | `RECOMPUTE_ERROR`, `rolled_back` true, `rolled_back_via_snapshot`, 0 snapshots left |
| rt2 P8c rotation 0.5 deg (snapshot path) | `SPEC_FAILED`, not proven | same as P8b; probe equal true (Q z 0.004363309284746571 → …547) |
| rt3 P10 FuzzyTolerance = 1/3000 | `SPEC_FAILED` | `RECOMPUTE_ERROR` `value_overwritten`, `rolled_back_via_snapshot` |
| rt6 x = 1e150 | committed, then `SPEC_FAILED` | `INVALID_INPUT` `parameters.out_of_range` (±1e9 mm), x stays 0, no bridge undo step |
| rt7 P2d Count = 2**31 | `SPEC_FAILED` | `INVALID_INPUT` `parameters.out_of_range`, Count stays 5 |
| rt2 P2b Count = 2**31 - 1 | — | `OK`, 2147483647 |
| rt7 P16 hidden-offset real state | OK | OK (z 10 → 12) |

`rt3.test_b_mutant_12_digits` errors because it patches the removed `_stable_float`. The probe is obsolete; this is not a product failure.

### Mutants (`git archive 195868c5` copy, removed; 278 tests of the three set_parameters modules, baseline OK)

| Mutant | Killed by |
| --- | --- |
| float compare made exact (`first == second`) | 4 failures (storage-error test, 17-digit proof, small-values proof) |
| overflow catch removed in `_is_finite` | 1 failure + 2 errors (beyond float range: number, length, angle) |
| base bound removed | 1 failure (`…above_the_bound`) |
| integer bound removed | 1 failure (`…exceeds_the_int32_range`) |
| `placements` report removed | 1 error (`…report_the_stored_placement…`) |

### Attacks on the new compare rule and bounds (`rt/vr2.py`, output `rt/out-vr2.txt`)

Each snapshot case uses an expression on `Base.y` that overwrites the write. A `Visibility` write in the same call forces the snapshot restore.

| Case | Result |
| --- | --- |
| pre x = 999999999.1234567 | `rolled_back_via_snapshot`, value restored exactly |
| pre x = -0.0, z = -0.0 | proven; -0.0 kept |
| pre rotation 270 deg Z (quaternion w < 0) | proven; same quaternion sign after restore |
| pre rotation 400 deg about (1,2,3) | proven |
| pre rotation 1e-9 deg | proven; restore keeps Q z 8.72665e-12 for 8.726646e-12 (FreeCAD storage, 4e-17 absolute, inside the 1e-15 rule) |
| pre FuzzyTolerance NaN | proven; NaN kept |
| `_Reading` unit: 1e9 vs 1e9+1e-7 equal; 1e9 vs 1e9+2e-6 different; 1e-7 vs 1.001e-7 different; 0 vs -0 equal; NaN vs NaN equal; NaN vs 0 different; 0.3 vs 0.1+0.2 equal | as the comment states |
| base x = 1e9 / -1e9 / 1e9+1 / -1e9-1 / 1e9+1e-6 | OK / OK / `out_of_range` ×3 |
| no-op: current x -0.0, request 0.0 | `unchanged`, `undo_steps` 0 |
| rotation axis [0,0,2], 400 deg | `OK`; `placements.stored` axis [0,0,1], angle 400; same request again → `unchanged` |
| integer 2147483647 / -2147483647 / -2147483648 / 2**31 / 10**19 | OK / OK / `out_of_range` / `out_of_range` / `out_of_range` |

Observations (no defect claimed): the bound refuses -2**31, which int32 holds; the message states ±2147483647, so code and message agree. A placement write of x = 1e-300 onto x = 0 returns `unchanged`, because FreeCAD's `isSame(…, 0.0)` reads the two values as equal.

### Finding

- **R2-F1 (low, doc drift, Q10):** `mcp-tools-design.md:576` and `:581` describe `feature_set_parameters` without the new rules. Missing: the `parameters.out_of_range` refusal (base x, y, z within ±1e9 mm; integers within ±2147483647) and the `placements: {property: {requested, stored}}` result field. `tool_catalog.py` and the spec have them. Fix: add both to the two design paragraphs.
