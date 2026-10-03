---
title: 'Story 4.2b: Corrupted-Plan Replay Scoring and Cross-Leg Frames'
type: 'feature'
created: '2026-10-03'
status: 'done'
baseline_commit: '479e44e230575746518bd26c09b9149c3f070d54'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-4-2-assertion-primitives.md'
  - '{project-root}/benchmarks/g3/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** G3.E.3 and G3.E.4 report `INVALID_INPUT`. No corrupted plan has been graded by its spec's assertions, no G3 sensitivity or false-alarm number exists, and nothing shows that an anchor frame resolves the same on the 1.0.x and 1.1.x legs.

**Approach:** An operator-run scorer replays every corrupted plan through the MCP tools on a headless H1 host, grades each part with `verify_shape` using its spec's `checks` and `anchor_frame`, and records sensitivity and false-alarm with a G3 `validator_sha`. The same run records each resolved frame. Each CI leg compares those frames with a committed reference, which proves the legs agree.

**Decisions (2026-10-03, carried from the 4.2 split):**
- **3A — Frame coverage.** Frames are proven on every part the suite builds (controls and reverted planted plans), plus canonical fixtures for every `(kind, ref)` the 20 dev specs declare and a symmetric-part tie-break per kind. `gate.yaml` G3.E.3 lists the specs proven on built parts; the rest are listed as not proven.
- **4A — Reverted controls.** Each of the 10 planted cases gains `faithful_args` for its planted step. The scorer replays each plan planted and reverted. A reverted build that does not grade clean makes the case `INVALID_INPUT`. Reverted builds count as clean controls (14 controls). This is a post-hoc data edit, disclosed in the README.
- **4A amended (2026-10-03, agent decision under the user's "decide per design docs" instruction, for human review).** Three planted defects cannot be reverted by new args on one step: `pocket-before-pad` (an ordering defect; revert swaps steps 9 and 10), `hole-on-wrong-face` (the plan differs from the spec at steps 3, 5 and 6, as 4.1 review P2-5 recorded) and `extra-unrequested-pocket` (an inserted step; revert removes it). These three carry `faithful_steps: {<index>: {tool, args} | null}` (null drops the step) instead of `faithful_args`. A case with neither field, or both, fails the structural check. The README discloses the three and why. The purpose of 4A is unchanged: a reverted build must grade clean before its planted case's DETECT counts.
- **D5 — g3-dev-007 gains a bore-squareness check (2026-10-03, agent decision under the same instruction, for human review).** The `hole-on-wrong-face` planted build fails only `hole_position`, through an empty selector match (`axis: [0, 0, 1]` matches no side bore), so the case can never be a measured DETECT and sensitivity stops at 9/10. The prose states "bore ... into the centre of the top face", so g3-dev-007 gains `angle_between` between the top face (`face: {normal: [0, 0, 1]}`; the anchor is the bottom face, the largest because the bore opening reduces the top face, so frame +Z is up) and the 12 mm hole, `expect: 0.0`, `tol: {abs: 0.1}`, and the case's `detected_by` becomes `angle_between`. The edit adds a stated requirement, relaxes none, and is disclosed like DW-122.

## Boundaries & Constraints

**Always:**
- Replay and grading reach FreeCAD only through MCP tools (`preview_dry_run` then confirm for each mutation, AD-5). Detection comes from measured checks, never from reading the plan (AD-13).
- A planted case counts as detected only when its `detected_by` fn has a failing check without an `invalid_input.*` code. A control or reverted build counts as a false alarm when its verdict is not `OK`.
- A planted case not detected for its `detected_by` reason counts as a miss in sensitivity and is listed. A replay step error or a reverted build that is not clean makes the case `INVALID_INPUT`: listed, excluded from both rates, and the scorer exits non-zero.
- The frame comparison uses kind, origin and axes (rounded), plus `entity` for named kinds only. It never compares a `largest_planar_face` mapped name (`deferred-work.md`, BH1).
- `validator_sha` hashes the measurement sources and the corrupted-plan cases, mirrored byte for byte by `runner.py`.

**Never:**
- No in-process path into `usecases/` from the scorer.
- No held-out file read; no unseal.
- No loop, repair, done-predicate or model call (AD-35).
- No change to measurement semantics in `usecases/assertions.py`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Planted detected | `detected_by` check fails with a measured value | DETECTED | — |
| Planted, only invalid | only `invalid_input.*` checks fail | counts as a miss; listed | bars not met → exit non-zero |
| Reverted not clean | reverted build verdict not `OK` | case `INVALID_INPUT`, excluded | exit non-zero |
| Control flagged | control verdict not `OK` | counts as false alarm | — |
| Step error | a plan step returns non-OK | case `INVALID_INPUT`, excluded, listed | exit non-zero |
| Frame drift | a leg's frame differs from the reference | leg check fails naming case and field | exit non-zero |
| Reference missing | no reference file | G3.E.3 `INVALID_INPUT` | — |
| Stale score | registry sha ≠ hashed sources | G3.E.4 `FAIL (stale)` | — |

</frozen-after-approval>

## Code Map

- `tests/uat/run/2026-10-03-03/evidence/replay_verify.py` -- working replayer: `$doc` binding, preview/confirm, `--headless` stdio H1 spawn, `verify_shape` with spec checks. Source of the scorer's replay loop.
- `scripts/automation/run_mcp_e2e.py:208-226` -- H1 stdio spawn with `freecad_buddy.hosts.main serve --mode inline --transport stdio`.
- `benchmarks/g3/fault-injection/score_g3_validators.py:88` `load_suite`, `:113` `_is_planted`, `:340-362` `entry_status` -- reuse loaders; G3.E.3/G3.E.4 become computed (registry currency + bars; reference + per-leg evidence).
- `benchmarks/g2/fault-injection/score_g2_infc.py:164-199` `_validator_sha`, `:285-367` `score`, `_render_block`; `benchmarks/g0/export-fault-injection/score_export_verify.py` `merge_validators_yaml`; `usecases/stats.py:17,42,49` -- tally, Wilson CI, registry write.
- `benchmarks/runner.py:97-131` `_VALIDATOR_SOURCES`, `:229-273` hasher with per-gate suite fold-in -- add `spec_assertions` and a G3 suite root.
- `benchmarks/g3/gate.yaml:98,110` G3.1/G3.4 `cited_validators: [assertions]` -- cite `spec_assertions`.
- `benchmarks/g3/fault-injection/corrupted-plan/*/case.yaml` -- 10 planted (steps listed in each `planted_step`), 4 controls; `targets_validator: assertions@harness.assertions.evaluate` becomes `spec_assertions@usecases.assertions.evaluate_checks`.
- `.github/workflows/ci.yml:78-121` -- `headless` matrix (1.0.0/py3.11, 1.1.0/py3.12) with `mcp` installed; G0.4 per-leg evidence upload pattern.
- `tests/external/test_g3_benchmark.py:151-164` -- entry-status expectations to update.
- Local FreeCAD: env `fcb` (1.1). Create micromamba env `fcb10` (`freecad=1.0.0 python=3.11`, `pip install --no-deps -e .`, `mcp>=1.28,<2`) to run the 1.0.x leg locally, as CI does.

## Tasks & Acceptance

**Execution:**
- [x] `benchmarks/g3/fault-injection/corrupted-plan/*/case.yaml` (10 planted) -- add `faithful_args` for the planted step, derived from the spec prose and the paired control where one exists; retarget all 14 to `spec_assertions`.
- [x] `benchmarks/g3/fault-injection/score_g3_replay.py` -- new: spawn H1 over stdio, replay planted/reverted/control plans, grade via `verify_shape`, classify per the Always rules, write per-case JSONL and a frames file to `benchmarks/gate-artifacts/g3/<run>/`, merge the `spec_assertions` block into `validators.yaml` (`--check` skips the write), `--leg` labels evidence, `--frames-check REF` compares frames to the reference.
- [x] `benchmarks/g3/fault-injection/frames-reference.json` -- committed from the 1.1.x run.
- [x] `tests/infc/test_assertion_primitives.py` -- canonical frame fixtures with hard-coded expected frames for `XY_Plane`, `XZ_Plane`, `PlateCornerDatum` and a symmetric `largest_planar_face` part; they run on both CI legs.
- [x] `benchmarks/runner.py`, `score_g3_validators.py` -- `spec_assertions` sources + G3 suite fold-in; G3.E.4 from registry currency and bars; G3.E.3 from the reference plus `G3.E.3.<leg>.json` evidence in a given dir, else `INVALID_INPUT`.
- [x] `benchmarks/g3/gate.yaml`, `benchmarks/g3/README.md` -- cite `spec_assertions`; list specs proven on built parts; disclose `faithful_args` as post-hoc.
- [x] `.github/workflows/ci.yml` -- per headless leg: run the replay with `--frames-check`, upload `G3.E.3.<leg>.json`.
- [x] `tests/external/` -- classification, frame comparison, sha mirror and entry-status tests with a fake MCP session; one per I/O row.
- [x] `benchmarks/_registry/validators.yaml` -- `spec_assertions` block from a local 1.1.x run.

**Acceptance Criteria:**
- Given the 1.1.x leg, when the scorer runs, then 10/10 planted are detected for their `detected_by` reason, 14/14 controls and reverted builds are clean, and `validators.yaml` records sensitivity 1.0, false-alarm 0.0 and a current `validator_sha`.
- Given the 1.0.x leg (local `fcb10` or CI), when the scorer runs with `--frames-check`, then every frame equals the reference.
- Given both leg evidence files, when `runner faults G3` runs, then G3.E.3 and G3.E.4 report `OK`; without them G3.E.3 reports `INVALID_INPUT`.

## Design Notes

- Validator id `spec_assertions` keeps the G2 `assertions` score separate: the same code, measured over a different suite, needs its own sha and rates.
- A plan built with a planted step replaced by `faithful_args` is a control because only the step under test changes; that proves each DETECT comes from the planted defect.

## Implementation Notes

- New `score_g3_replay.py` spawns the H1 host over stdio in the running interpreter, replays each plan with preview then confirm, grades with `verify_shape`, writes `cases.jsonl` and `G3.E.3.<leg>.json` under `benchmarks/gate-artifacts/g3/<run>/`, and merges `spec_assertions` into `validators.yaml` unless `--check` or a case is `INVALID_INPUT`. `score_g3_validators.py` computes G3.E.3 (reference plus both leg files from `--frames-evidence`) and G3.E.4 (registry currency and bars); the runner forwards `--frames-evidence` for G3 only.
- Data: 7 planted cases carry `faithful_args`; `pocket-before-pad`, `hole-on-wrong-face` and `extra-unrequested-pocket` carry `faithful_steps` (decision 4A amended). `g3-dev-007` gains the `angle_between` check and `hole-on-wrong-face` is detected by it (D5). All 14 cases target `spec_assertions@usecases.assertions.evaluate_checks`; `gate.yaml` G3.1/G3.4 cite `spec_assertions` and G3.E.3 lists the 8 specs proven on built parts (001, 003, 007, 008, 010, 011, 012, 019) and the 12 not proven. `fixture: pending` is kept on all 14 cases: the structural check still requires it.
- Verified independently by the lead: `score_g3_replay.py --check --frames-check` on 1.1.x (`fcb`) and 1.0.x (`fcb10`, FreeCAD 1.0.0): 10/10 detected, 0/14 flagged, frames OK on both, exit 0. `runner faults G3 --frames-evidence` gives G3.E.3 OK (14 built parts on 1.0.x and 1.1.x) and G3.E.4 OK (sha `2433d350b183`); without the directory G3.E.3 is `INVALID_INPUT`. `FreeCADCmd tests/run_tests.py` on 1.1: 671 run, OK (1 skipped). `pytest tests/external`: 1187 passed, 5 failed (the known G1 grader-hash failures). `ruff check src benchmarks`, `check_imports`, `gen_schemas --check`, `check_provenance` OK.
- FreeCAD 1.0 in-FreeCAD suite: 2 failures and 1 error (`test_feature_tools` linear-pattern default 3 vs 2; `test_document_lifecycle` enum `?` marker). Identical at baseline `479e44e` (checked in a temporary worktree), so pre-existing; they also stop the CI 1.0 leg before the new G3 replay step runs. Logged in `deferred-work.md`.
- The CI replay step adds `sys.prefix/lib` to the child `PYTHONPATH` for Linux; it has not run on Linux yet.
- The local env `fcb10` (FreeCAD 1.0.0, py3.11) was created for the 1.0.x leg; it can be deleted with `micromamba env remove -n fcb10`.

- Review pass 1 patches applied: `validator_sha` also covers `score_g3_replay.py` and each dev spec a case names (runner mirrors it); `frames_status` refuses evidence whose FreeCAD major.minor does not match its leg; CI uploads the whole run directory; tests pin `replay.main` and checker exit codes, both bars, and `faithful_steps` schema checks; stale case comments, the 007 comment, the empty `PYTHONPATH` part and a docstring wrap are corrected. New `spec_assertions` sha `bd8a9e8b6d77`, written by a full 1.1.x run.
- Final verification by the lead after the patches: `--check --frames-check` on 1.1.x and 1.0.x both 10/10 detected, 0/14 flagged, frames OK; the joined read `runner faults G3 --frames-evidence` gives G3.E.3 OK (14 built parts, 1.0.x and 1.1.x) and G3.E.4 OK; runner == scorer == registry sha; `pytest tests/external` 1201 passed, 5 failed (known G1); ruff, format, `check_imports`, `gen_schemas --check`, `check_provenance` OK.
- `.github/workflows/ci.yml` does not parse as YAML at the baseline (`479e44e`, line 68, an unquoted `: ` in a G2 step name; already in `deferred-work.md`), so no CI job runs, including the new G3 step, until that line is quoted.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-10-03). Layers: blind-hunter (BH), edge-case-hunter (EC), verification-gap (VG).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| BH1 | No CI job joins both legs' G3.E.3 files | low | By design each leg compares to the committed reference (frozen Approach); the README must say that CI proves agreement indirectly and `runner faults G3 --frames-evidence` is the joined read | patch (README) |
| BH2 / EC-ci | CI upload keeps only `G3.E.3.*.json`; `cases.jsonl` and host logs lost on failure | low | Upload path names the evidence file only; whole run dir is a one-line change | patch |
| BH3 / EC-sha | `validator_sha` omits the dev specs' checks and the scorer's classification code | medium | This diff changes detection by editing `g3-dev-007` and the score does not go stale; AD-13 makes a score current only while its sha matches what decided it | patch |
| BH4 | Reverted builds can never be false alarms, so 14 overstates the population | false | Decision 4A (human) defines reverted builds as controls and a non-clean one as `INVALID_INPUT`, which blocks the registry write; a written score always has 14 clean builds | reject |
| BH5 | A non-`invalid_input` failure with `measured: None` counts as DETECTED | low | Only `hole_spacing` with fewer than 2 holes yields it, which is a measured result (count) | reject |
| BH6 | `faithful_steps` need not cover `planted_step` | low | All three cases cover it; a gap shows as MISSED or `INVALID_INPUT` at replay; fix adds a guard | reject |
| BH7 | Leg evidence never checked against its `freecad_version` | medium | `frames_status` trusts the `--leg` label; a 1.1 interpreter run as `--leg 1.0.x` passes and the cross-leg claim becomes 1.1 vs 1.1 | patch |
| BH8 / VG1 | `score_g3_replay.main` exit code untested; CI depends on it | medium | Deleting the drift fold or forcing exit 0 passes every test | patch |
| VG2 | `score_g3_validators.main` computed-failure exit untested | medium | Reverting to `return 0 if sound else 1` passes every test | patch |
| VG3 | False-alarm bar unpinned in `bars_met` and `score_status` | medium | Removing either false-alarm condition passes every test | patch |
| BH9 / VG4 | `faithful_steps` schema validation untested | low | Only the `faithful_args` schema branch has a test; one test closes it | patch |
| BH10 | Case comments still say the replay "lands in Story 4.2" | low | Direct correction | patch |
| BH11 | Story-history comments in cases | low | In-file post-hoc disclosure is the established DW-122 convention the epic requires | reject |
| BH12 | `g3-dev-007` comment omits that the bore floor also matches `normal: [0, 0, 1]` | low | `_nearest_pairs` may pair the bore with its floor; both are parallel, so the result holds; comment correction only | patch |
| BH13 | Empty `PYTHONPATH` entry; docstring wrap; module coupling; duplicated steps | low | Empty entry puts cwd on the host path and the wrap is broken (direct corrections); coupling and duplication add no defect | patch (first two) / reject (rest) |
| EC1 | Graded object `None` when the last feature step has no `name` | low | Every plan's last feature step names its object | reject |
| EC2 | A `call_tool` exception aborts the run | low | Loud failure; never shown reachable | reject |
| EC3 | A hung tool call hangs the run | low | CI step timeout is 15 min; fix adds a timeout path | reject |
| EC4 | Malformed case YAML breaks the sha mirror | low | Suite is well formed; structural check runs first | reject |
| EC5 | Bad `planted_step` or non-int `faithful_steps` key aborts replay | low | Structural check refuses these | reject |
| EC6 | Rounding-boundary flip gives spurious drift | low | Needs noise straddling a 1e-6 boundary; none seen on 14 builds x 2 legs | reject |
| EC7 | Malformed evidence JSON prints a traceback | low | Loud failure | reject |
| EC8 | Empty reference reports G3.E.3 OK on 0 parts | low | Reference is committed with 14 builds; a test pins its contents | reject |
| EC9 | Missing `--frames-check` path fails after a full replay | low | Operator input; loud | reject |
| EC10 | A 1.0.x run without `--check` overwrites the 1.1.x score | low | Same suite and sources; run id records the leg | reject |
| EC11 | Sibling check of the same fn credits the DETECT | low | Only 011 has two `hole_position` checks, and its planted defect fails both | reject |
| EC12 | Tie-break "per kind" claim | false | Named kinds have no tie-break; the claim is spec wording | reject |

## Verification

**Commands:**
- `micromamba run -n fcb python benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x` -- expected: exit 0, 10/10 detected, 0/14 flagged.
- `micromamba run -n fcb10 python benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.0.x --check --frames-check benchmarks/g3/fault-injection/frames-reference.json` -- expected: exit 0.
- `uv run python -m benchmarks.runner faults G3 --frames-evidence <dir>` -- expected: G3.E.3 and G3.E.4 `OK`.
- `FreeCADCmd tests/run_tests.py` in both envs; `uv run pytest tests/external`; `ruff check src benchmarks`; `check_imports`; `gen_schemas --check` -- expected: pass (5 known G1 failures).
