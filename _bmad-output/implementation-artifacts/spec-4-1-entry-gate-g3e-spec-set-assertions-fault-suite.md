---
title: 'Story 4.1: Entry Gate G3.E — Spec Set, Assertions & Fault Suite'
type: 'feature'
created: '2026-10-03'
status: 'done'
baseline_commit: '029a886aa3ab28fe39f4b58949832c99cb27ff22'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
  - '{project-root}/_bmad-output/specs/spec-freecad-buddy/phase-gates.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Gate G3 has no benchmark. No spec set, no compiled assertions, no corrupted-plan fault suite, and the runner does not know `G3`. AD-19 forbids Phase 3 code before its entry gate lands and fails honestly against a stub.

**Approach:** Land `benchmarks/g3/` as data plus gate wiring: a written spec set with compiled assertions in a declared anchor frame, a corrupted-plan fault suite with clean controls, `gate.yaml` for G3.1–G3.6 and the G3.E entry list, runner registration, and a structural self-check. Reuse the pure-data parts of reverted commit `bb42999`; restore no loop, judge or designer code (AD-35).

**Decisions (2026-10-03):**
- **D1 — G3.E scope.** `gate.yaml` lists every G3.E item from `phase-gates.md:77`. The ≥2048 px render and drawing path is owned by Story 4.3, and the three Track W skills by Story 6.5. They report `INVALID_INPUT` until those stories land. G3.E stays open after 4.1.
- **D2 — Epic ACs 2 and 3 move to Story 4.2.** 4.1 lands the cases with `fixture: pending` and a structural scorer only. 4.2 lands the anchor-frame resolver and the 11 primitives, then runs the cross-leg frame check (AC2) and the sensitivity / false-alarm score with `validator_sha` (AC3). This follows the Story 3-1 precedent.
- **D3 — A corrupted plan is a recorded plan.** Each case carries an ordered list of `{tool, args}` steps with one planted defect step marked, in the `harness/scripted_backend.py` `PlanStep` shape. Story 4.2 replays it through the MCP mutation tools, and the spec's assertions grade the resulting part. G3.4 uses this path at exit. No builder script and no loop.
- **D4 — Reuse `bb42999` data.** Restore the 20 dev specs, their provenance, the 14 corrupted-plan cases, and the 7-case sealed held-out split byte-identical (`unseal_events: []`, machine key). Fix `g3-dev-007` and `g3-dev-011` with position/axis checks (DW-122). Disclose that `g3-dev-002` was amended after code existed (DW-129), and that the 007/011 fixes also come after the reverted code existed.
- **D5 — Strengthen weak dev specs (review pass 1).** `g3-dev-019` prose names the datum `PlateCornerDatum` and which corner it sits on. `g3-dev-002`, `g3-dev-008` and `g3-dev-017` gain the position, pitch-circle or axis checks their prose already states. Audit the other 14 specs with one test: can a part that violates a stated requirement pass every check? Fix each one found the same way. Every edit carries the post-hoc disclosure used for 007/011. Edits add requirements the prose states and relax none.
- **D6 — Reuse survey owned by 4.1.** `phase-gates.md:3` requires a recorded reuse survey in every entry gate. `gate.yaml` adds entry item `G3.E.7`, owner 4.1, and `benchmarks/g3/reuse-survey.md` records what was reused from `bb42999`, what was rejected, and why.
- **D8 — Placement prose allowed (review pass 2).** A spec may state where the part sits in its anchor frame when a stated requirement can only be graded in that frame (handedness, position). The sentences in 011, 002 and 019 stand, and 014 gains "plate centred on the origin" so its reused `hole_position (0, 0)` grades a stated requirement. Each is disclosed like D5.
- **D7 — Amend in place.** Review pass 1 work is kept, not reverted. Gap fixes and review patches are applied to the existing tree.

## Boundaries & Constraints

**Always:**
- Assertions use only the 11 closed §7.2 functions: `is_valid_solid`, `count_cylindrical_holes`, `hole_diameter`, `hole_position`, `hole_spacing`, `hole_through`, `distance_between`, `angle_between`, `expect_bbox`, `expect_extent`, `expect_volume`.
- Every spec declares `anchor_frame.kind` from {`named_datum`, `base_sketch_plane`, `largest_planar_face`}.
- Every expected value carries its derivation inline, from the spec prose, never from a measured part.
- Every spec and fault case has a provenance manifest; `check_provenance` passes.
- Each of the four G3 threats maps to at least one planted counter case.
- Reused data is disclosed in `benchmarks/g3/README.md` with its origin commit and known defects.

**Never:**
- No file from the `bb42999` must-not-restore list: `designer_loop.py`, `verify_visual.py`, `contracts/designer.py`, `contracts/visual.py`, `visual_judge_client.py`, `judge.py`, `actor_run.py`, `make_actor_plans.py`, `actor-plans/`, `actor-results.json`, `judge_double.py`, `planted_plans.py`, `score_g3_infc.py`, `visual-judge/`.
- No sub-element index selector (`Face6`, `Edge3`) and no feature-metadata verdict in any spec.
- No change to `harness/assertions.py` measurement code, no anchor-frame resolver, no render or TechDraw code. Those belong to 4.2 and 4.3.
- No done-predicate, iteration count or repair limit in any shipped file.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Stub run | `runner run G3 --stub` | Every criterion G3.1–G3.6 `FAIL`, verdict `INVALID_INPUT` | Never `PASS`, never crash |
| Bad selector | spec check contains `Face6` | Self-check fails naming the case | — |
| Unknown fn | check `fn: expect_color` | Self-check fails naming the case | — |
| Orphan fault | fault case `spec_ref` names no dev spec, or `detected_by` names no check in that spec | Self-check fails | — |
| Threat gap | one threat has no counter case | Self-check fails naming the threat | — |
| Bad plan step | plan step names a tool absent from `tool_specs()`, or args fail that tool's input schema | Self-check fails naming case and step | — |
| No planted step | planted case with no marked step, or control with one | Self-check fails | — |
| Exit attempt | `runner run G3 --exit` without unseal key | Refused, as for G1/G2 | Existing `FREECAD_BUDDY_UNSEAL_KEY` guard |

</frozen-after-approval>

## Code Map

- `benchmarks/runner.py:55` `KNOWN_GATES = {"G0","G1","G2"}`, `:57` `_SEALABLE_GATES = {"G1","G2"}` -- add `G3`.
- `benchmarks/runner.py:75` `_FAULT_SCORERS`, `:113` `_VALIDATOR_SOURCES`, `:128` `_G2_VALIDATORS`, `:228-294` `validator_sha` -- register the G3 structural scorer by the same pattern.
- `benchmarks/runner.py:137` `StubBridge`; `harness/report_build.py:21` `STUB_NOT_IMPLEMENTED_CODE` -- reuse for the stub run. Do not change.
- `benchmarks/g2/gate.yaml` -- template for `g3/gate.yaml` (`actor`, `grader`, `required_tokens`, `verdict.heldout`, `criteria[].cited_validators`).
- `benchmarks/g2/fault-injection/*/case.yaml` -- fault case shape (`targets_validator`, `fault.kind`, `expectation`, `planted_op`, `provenance`).
- `benchmarks/harness/assertions.py:575` `SUPPORTED_FNS`, `:578` `evaluate` -- read only. No frame concept today; G2 cases declare `largest_planar_face` with `ref: null` and it is ignored.
- `scripts/check_provenance.py` -- confirm it accepts `kind: part-spec` and `fixture: none-spec-to-part`; `bb42999` changed it for that.
- `.github/workflows/ci.yml:20-29` -- G0/G1 `--stub` honest-fail steps. Add G3. (G2 has none; pre-existing gap, report only.)
- `bb42999:benchmarks/g3/dev/*/case.yaml`, `bb42999:benchmarks/_registry/provenance/g3-dev-*.yaml`, `bb42999:benchmarks/g3/heldout/`, `bb42999:benchmarks/g3/fault-injection/corrupted-plan/*/case.yaml` -- reuse source (`git show bb42999:<path>`).
- `tests/external/__pycache__/test_g3_gate*.pyc` -- stale bytecode with no source. Delete; it can shadow a new test of the same name.

## Tasks & Acceptance

**Execution:**
- [x] `benchmarks/g3/dev/` -- restore 20 `case.yaml`; add position/axis checks to `g3-dev-007` and `g3-dev-011` -- DW-122.
- [x] `benchmarks/_registry/provenance/g3-*.yaml` -- restore dev manifests; add manifests for fault cases.
- [x] `benchmarks/g3/heldout/` -- restore `SEAL.json` and `heldout.tar.enc` byte-identical -- D4.
- [x] `benchmarks/g3/fault-injection/corrupted-plan/` -- restore 14 cases (10 planted, 4 controls); drop every designer-loop field; set `targets_validator: assertions@harness.assertions.evaluate`, `fixture: pending`, and author a `plan:` list of `{tool, args}` steps that builds `spec_ref`, with `planted_step: <index>` on planted cases only -- D3.
- [x] `benchmarks/g3/fault-injection/threat-counters/` -- one case for each threat not already countered: run with no visual findings in the workdir (G3.5), and banner actor id that differs from the run's actor (citability).
- [x] `benchmarks/g3/gate.yaml` -- G3.1–G3.6 from `phase-gates.md:83-88`; `entry:` list with each G3.E item and its owning story (4.1 spec set and fault suite; 4.2 frame check and sensitivity score; 4.3 render/drawing floor; 6.5 skills) -- D1, D2.
- [x] `benchmarks/runner.py` -- add `G3` to `KNOWN_GATES` and `_SEALABLE_GATES`; register structural scorer.
- [x] `benchmarks/g3/fault-injection/score_g3_validators.py` -- structural scorer only (counts, mapping, closed vocabulary); no sensitivity numbers.
- [x] `benchmarks/g3/README.md` -- layout, reuse disclosure, DW-122/DW-129 notes, threat-to-case map.
- [x] `tests/external/test_g3_benchmark.py` -- self-check covering every I/O matrix row.
- [x] `.github/workflows/ci.yml` -- G3 `--stub` honest-fail step.
- [x] `_bmad-output/planning-artifacts/epics.md` -- move Story 4.1 ACs 2 and 3 under Story 4.2 -- D2; keeps the plan and the gate in agreement.
- [x] `benchmarks/g3/dev/g3-dev-{019,002,008,017}/case.yaml` -- 019 prose names `PlateCornerDatum` and its corner; 002 `hole_position`; 008 pitch-circle position or spacing; 017 counterbore axis position; each with derivation and post-hoc disclosure -- D5.
- [x] `benchmarks/g3/dev/` (other 14) -- audit: a part that violates a stated requirement must fail at least one check; fix any found the same way -- D5.
- [x] `benchmarks/g3/reuse-survey.md` + `gate.yaml` `G3.E.7` (owner 4.1) -- recorded reuse survey -- D6.

**Acceptance Criteria:**
- Given `benchmarks/g3/`, when the self-check runs, then 20 dev specs, ≥10 planted corrupted-plan cases plus clean controls, and all four threats countered are asserted, and a falsification (remove one threat case) fails exactly one check.
- Given the stub bridge, when `runner run G3 --stub` runs, then 6/6 criteria fail with `INVALID_INPUT`.

## Implementation Notes

- Restored byte-identical from `bb42999` (checked with `git hash-object`): 18 dev specs, all 20 dev manifests, `heldout/SEAL.json` and `heldout.tar.enc`.
- `g3-dev-007`: added `hole_position` with selector `{diameter: 12.0, axis: [0, 0, 1]}`, which a side-face bore violates.
- `g3-dev-011`: two `hole_position` checks were added, and the spec **prose** also changed ("pivot bore centred on the origin and the arm running along +X"). Without the prose change, a swapped-ends build is the same part turned 180°, so no check can detect it. D4 approved checks only, so the prose change needs human confirmation.
- `scripts/check_provenance.py` on `main` did not accept `kind: part-spec` or `fixture: none-spec-to-part`. The `bb42999` logic was restored and `fault-case` was added. Both kinds bind a manifest to `<artifact>.yaml`.
- `runner.py` gains `_g3_exit_eval` (raises) and `_g3_exit_precondition`, in the same pattern as G2. `--exit` is refused before any unseal.
- Corrupted plans pass schema checks only. None has been replayed in FreeCAD. Story 4.2 replays them.
- Pre-existing failures, not caused by this story, which fail the same way at the baseline: 6 tests in `test_gate_g1_exit.py`, `test_gate_g2_exit.py` and `test_harness_g1.py` (stale `validators.yaml` hashes).

- Live FreeCAD replay (user-requested, `tests/uat/run/2026-10-03-02/report.md`): the first replay gave 0/14, because every `sketch_add_geometry` step lacked `constraints` and the bridge rolls back an under-constrained sketch. All 14 plans now constrain every sketch fully, and replay 14/14 with each control at its spec volume. The two `g3-dev-007` plans use `feature_pocket`, because `feature_hole` adds a 118° drill point that the spec volume does not include (deferred for a spec decision).
- Review pass 2 also renamed every G3 test to `test_should_<outcome>_when_<condition>` with Arrange/Act/Assert, and changed `g3-dev-020` `distance_between` from 50 to 36 (face to face; 50 is the axis spacing that `hole_spacing` grades).

## Spec Change Log

## Review Triage Log

Pass 1 (2026-10-03). Layers: blind-hunter (BH), edge-case-hunter (EC), verification-gap (VG).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| VG1 | `check_provenance.py:245-247` source check on `part-spec`/`fault-case` manifests has no test | medium | All source-block tests mutate `.FCStd`-bound g0 manifests; no test reaches the case-file branch | patch (moot: loopback) |
| VG2 | Scorer `_check_provenance` has no falsification test | medium | Only the clean-tree test covers it; `check_provenance` ignores manifest-less exempt cases | patch (moot) |
| VG3 | `_check_fault_shape`, `_check_spec_count`, `_check_spec_derivations`, no-control branch have no falsification test | medium | No test greps `fault_shape`/`plan_ref`/`planted_evidence`; module docstring claims every check can fail | patch (moot) |
| VG-o1 / BH14 | `test_dev_run_writes_six_failing_reports` reads persistent gitignored `gate-artifacts/g3/pytest-g3-offline` | low | Stale reports from an earlier run satisfy the assertions locally; CI checkout is fresh | patch (moot) |
| VG-o2 | 6 G1/G2 external tests fail at baseline, so CI `External suite` is red before this story | medium | Same 6 fail at `029a886` in a clean worktree | defer |
| BH1 | 10 planted / 4 controls too few to clear the bar with Wilson CI | false | The bar is a point estimate: `score_g2_infc.py:457-458` compares `sensitivity`/`false_alarm` to 0.95/0.05; the CI is reported, not gated | reject |
| BH2 | G3.4 9/10 and G3.E 95 % disagree | false | Different measurements: G3.4 is actor detection at exit, G3.E is validator sensitivity; both copied from `phase-gates.md` | reject |
| BH3 | `g3-dev-002` cites DW-127, README cites DW-129 | low | Both ids concern 002 (DW-127 achiral trap, DW-129 amendment); README cites one | patch (moot) |
| BH4 | `g3-dev-002` handed hole has no `hole_position`, so a mirrored bracket passes | medium | Checks are count, diameter, through only | intent_gap A |
| BH5 | `g3-dev-002` comment names deleted visual fault cases | low | Byte-identical reused text; README does not disclose | patch (moot) |
| BH6 | `g3-dev-019` prose never names `PlateCornerDatum` nor which corner | high | Frame `{kind: named_datum, ref: 'PlateCornerDatum'}`; prose says only "the plate's corner datum", so a faithful build cannot satisfy the frame | intent_gap A |
| BH7 | Named-datum control and planted case put the datum at the global origin | medium | Both attach to `XY_Plane` with the plate corner at (0,0); a resolver that ignores `named_datum` passes both | patch (moot) |
| BH8 | `hole-on-wrong-face` leaves a largest-face tie undecided | false | Tie-break is defined (area, lowest centroid Z, mapped name; epic-4-context); the side bore also misses the axis selector | reject |
| BH9 | `expect_bbox` axis order undefined; `g3-dev-009` on `XZ_Plane` may fail a correct part | maybe-false (medium) | Depends on the 4.2 `expect_bbox` definition, not yet written | defer |
| BH10 | `g3-dev-008` has no pitch-circle/position check; `g3-dev-017` no counterbore/axis check | medium | A wrong PCD keeps volume and count; an off-axis counterbore keeps every check | intent_gap A |
| BH11 / EC10 | `none-spec-to-part` exemption is by declaration, any gate | low | Mirrors the existing `fixture: pending` rule (`check_provenance.py:209-215`); fix adds guards | reject |
| BH12 | = VG1 | — | — | grouped with VG1 |
| BH13 | `_g3_exit_precondition` checks function identity | low | Fails loudly with a message naming the stub; fix adds complexity | reject |
| BH15a | `assert b"anchor_frame" not in archive` runs on an encrypted blob | low | Cannot fail; direct deletion | patch (moot) |
| BH15b | README-claimed pairs `pocket-before-pad`↔`equivalent-step-order` and `tolerance-edge`↔`faithful` untested | low | New tests, not a direct correction | reject |
| BH15c | `mirrored-hole-pattern` uses `feature_pocket`; no 011 control | low | No pairing is claimed for it | reject |
| BH16a | Lack-of-patience threat countered only by an omission plan | false | Counter text `phase-gates.md:90` is "done is assertions passing"; an early stop leaves a failing part | reject |
| BH16b | Entry gate omits the recorded reuse survey (and rubric) | medium | `phase-gates.md:3`: every entry gate "always" carries a reuse survey; `gate.yaml` `entry:` lists none and none exists. Rubric part false: no G3 criterion needs judgment | intent_gap B |
| BH16c | Fault-case manifests signed by the agent, not the operator | medium | `license_checked: {by: claude-agent (not the operator)}` | defer (operator action) |
| EC1-3, EC8 | Scorer tracebacks on malformed YAML / non-dict / unhashable values | false | Loud failure on input never shown reachable; real suite is well formed | reject |
| EC4 | Lowercase or integer index selectors pass | low | No spec uses them; fix adds guards | reject |
| EC5 | Null `ref` for `named_datum`/`base_sketch_plane` passes | low | No spec has one; fix adds guards | reject |
| EC6 | Threat `spec_ref` may differ from its control's `spec_ref` | low | Both current threat cases match; fix adds guards | reject |
| EC7 | Duplicate ids collapse in sets/dicts | low | No duplicates exist; fix adds guards | reject |
| EC9 | G3.E.1 printed `OK` without running the stub | low | CI step and `test_stub_run_fails_all_six_criteria_with_invalid_input` cover it; label overclaims | patch (moot) |
| EC11 | Pairing test skips step 0 entirely | low | Fix adds logic | reject |
| EC12 | I/O matrix command `runner run G3 --stub` does not exist | — | Fix edits this spec's frozen block; Verification section already corrected | reject (spec edit) |
| EC13 | Plan steps are `{tool, args}` mappings, `PlanStep` is a tuple | low | 4.2 replay must convert | defer |

## Design Notes

The entry gate is data. Under AD-35 a corrupted plan is an input the actor or a replayer executes, not something the repository generates. The repository only grades the resulting part with the spec's assertions. For that reason the fault suite targets `harness.assertions.evaluate` and never a loop function.

## Verification

**Commands:**
- `uv run pytest tests/external` -- expected: all pass, including `test_g3_benchmark.py`.
- `uv run python scripts/check_provenance.py` -- expected: `check_provenance OK`.
- `python scripts/check_imports.py` -- expected: `check_imports OK`.
- `uv run python benchmarks/runner.py --gate G3 --stub` -- expected: 6/6 `FAIL (verdict=INVALID_INPUT)`, exit 1. (`run` has no `--stub` flag for any gate.)
- `uv run python -m benchmarks.runner faults G3` -- expected: exit 0; G3.E.1–2 `OK`, G3.E.3–6 `INVALID_INPUT`.
- `git diff --stat main -- src/` -- expected: empty.
- `PYTHONUTF8=1 uv run python tests/uat/run/2026-10-03-02/evidence/replay_g3.py` against live FreeCAD on `:8765` -- expected: `REPLAYED 14/14`, each control at its spec `expect_volume`.

**Manual checks:**
- Read the real window screenshot of a planted case and its control after a replay; the part must show the described defect. Reference: `tests/uat/run/2026-10-03-02/report.md`.

Pass 2 (2026-10-03), after D5-D7 amendments. Rows marked `carried` repeat a pass-1 claim.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| P2-1 | Selector-less checks: `g3-dev-002:60`, `g3-dev-015:30` `angle_between`, `g3-dev-020:39` `distance_between` (from BH "check shape not validated") | high | `verification-design.md:297-298` signatures require `sel_a, sel_b`; the check is unevaluable, so a faithful part fails G3.1 | patch |
| P2-2 | Empty selector match and a replay tool error have no defined result (BH) | medium | `hole-on-wrong-face` makes 007's axis-selected `hole_position` match zero holes; README "every value must equal" reads as a vacuous pass | patch |
| P2-3 | `hole_diameter` on a merged counterbore hole has no defined result (BH) | medium | `g3-dev-017` asserts 6.5 on a logical hole holding 6.5 and 11 cylinders (§7.3 rule 4) | patch |
| P2-4 | README orientation rule contradicts the 012 plans (BH) | low | 012 pads forward and pockets `reversed: true`; direct doc correction | patch |
| P2-5 | `hole-on-wrong-face` changes steps 3, 5, 6 but marks only 5 (VG) | low | Steps 3 and 6 place the block so the side face lies on XZ; description silent | patch |
| P2-6 | 20 spec comments say "exempts it by kind"; code exempts by fixture value (BH) | low | `_declares_spec_to_part` reads `fixture` only; direct comment correction | patch |
| P2-7 | Story 4.1 in `epics.md` has no AC for G3.E.2 and G3.E.7 it owns (BH) | medium | Only the stub AC remains after D2 | patch |
| P2-8 | `test_g3_benchmark.py` ignores CLAUDE.md §9 naming and Arrange/Act/Assert (BH) | medium | `test_framing.py` follows the standard; the new file does not | patch |
| P2-9 | `MUST_NOT_RESTORE` bans bare names, misses `benchmarks/harness`, omits survey-rejected paths (BH, EC) | medium | Bare `visual.py`/`judge.py` would fail a legitimate 4.3 file; `judge_double.py` lives outside searched roots | patch |
| P2-10 | CI G3 stub step accepts any non-zero exit (EC) | medium | A crash or usage error (exit 2) reads as an honest failure | patch |
| P2-11 | Seven scorer rejection branches untested (VG) | medium | No mutation test for kind/expectation, criterion, threat planted, no plan, step shape, no checks, no provenance key | patch |
| P2-12 | `main` exit code and `entry_status(sound=False)` untested (VG) | medium | Only the clean tree and `sound=True` are exercised | patch |
| P2-13 | 014 `hole_position (0, 0)` grades an unstated centring (impl risk) | high | Resolved by D8: add placement prose | patch |
| P2-14 | Planted plans for 003, 007, 008, 010, 011 have no faithful control; a DETECT may come from an authoring error (BH, VG, EC) | medium | Only 3 of 10 pairs are pinned; proving the rest needs a FreeCAD replay | defer |
| P2-15 | `_g3_exit_eval` exists only to raise (BH) | low | `run_exit_command` looks up the evaluator before the precondition (`runner.py:872-877`), same shape as G2 | reject |
| P2-16 | Feature metadata without `::`, `Derivations:` anywhere, dangling plan refs, double source reporting, missing jsonschema (EC) | low | No instance exists; each fix adds guards | reject |
| carried | Malformed YAML tracebacks (EC) | false | carried: EC1-3, EC8 | reject |
| carried | Duplicate ids, index-selector variants (EC) | low | carried: EC7, EC4 | reject |
| carried | Exemption keyed on fixture value, case-file without manifest (BH, EC) | low | carried: BH11/EC10 | reject |
| carried | 4 controls and 9/10 vs 95 % bars (BH) | false | carried: BH1, BH2 | reject |
| carried | Patience threat counter (BH) | false | carried: BH16a | reject |
| carried | 012 pair claim untested (BH, VG) | low | carried: BH15b | reject |
| carried | Test writes under gitignored `gate-artifacts` (BH) | low | carried: VG-o1, patched in pass 1 by clearing the run dir | reject |
| carried | Agent-signed license (BH) | medium | carried: BH16c | defer (logged) |
| carried | Largest-face tie-break unstated (BH) | false | carried: BH8 | reject |
| carried | `runner run G3 --stub` claim, `PlanStep` shape (EC) | — | carried: EC12, EC13 | reject / defer (logged) |
