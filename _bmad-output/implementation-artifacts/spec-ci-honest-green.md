---
title: 'Honest green CI: sketch screenshots on default preferences, G0 validator map, no hidden failures'
type: 'bugfix'
created: '2026-10-10'
status: 'done'
route: 'dispatch'
baseline_commit: '63a775bb526721004be2e22d921bf0795e88b633'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/validation-harness-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** CI reports success while it hides two real defects.
- `render` and `g0-verdict` have `continue-on-error: true`, and `g0-verdict` also ends each command with `|| true`.
- **Defect 1:** with FreeCAD's default preferences a sketch draws white lines (`SketchEdgeColor` default `1,1,1`, `ViewProviderSketch.cpp:390-396`) on the white render background (`render_probe.py` `setBackgroundColor(1.0, 1.0, 1.0)`). So `query_screenshot` of a sketch is a blank PNG, but the result still reports `rendered_objects: ["Sketch"]`. Test `infc.test_screenshot.DefaultSetTest.test_should_draw_a_visible_sketch_when_it_is_the_only_object` fails on the CI render leg. It passes locally only because the user's `user.cfg` sets `SketchEdgeColor=#212529`. The failure reproduces locally with an empty `FREECAD_USER_HOME`.
- **Defect 2:** `benchmarks/runner.py` `_VALIDATOR_SOURCES` has no entry for `verify_export_step`, which G0.5 cites. So `_validator_src_hasher` returns `""` and every G0 verdict reports `verify_export_step (stale: source hash mismatch)`, although the registered `validator_sha` (`ac477d9a…`) equals the hash of the scorer's sources (`score_export_verify.py` `VALIDATOR_SOURCES`).

**Approach:** Fix both defects. Then make CI fail when they recur.

**Decisions (human, 2026-10-10):**
- D1: Screenshots draw sketch lines in one fixed dark colour (#212529) unless a style or highlight sets a colour. The user's Sketch edge colour preference is not used for renders.
- D2: `g0-verdict` becomes blocking and checks only what CI can produce: G0.4 passes, and every validator G0 cites is current. The full G0 verdict (leg-a G0.1/G0.3/G0.5 local evidence, leg-d GUI smoke token) is not run in CI.
- D3: Canary stays allowed-to-fail per AD-11 ("never blocks"). Remove `continue-on-error`, so a 1.2-dev failure shows red in Actions. It runs only on schedule and dispatch, never on push or PR.

## Boundaries & Constraints

**Always:**
- The fix in `render_probe.py` uses the existing override mechanism (`_wrap_style`).
- A style colour or a highlight still wins over the fixed sketch colour.
- Tests reproduce the CI condition on every machine. The sketch test sets `SketchEdgeColor` to white for its duration and restores it.
- Every validator cited by any `benchmarks/**/gate.yaml` has a `_VALIDATOR_SOURCES` entry. The entry hashes the same files, in the same order, as that validator's scorer.

**Never:**
- No `continue-on-error`, `|| true` or `set +e` that hides a failing exit code in `ci.yml`. The existing G3 `set +e` step checks its exit code explicitly and stays.
- No edits to `validators.yaml` hashes to make a check pass.
- No change to the full `verdict` semantics used at gate exit.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Default prefs sketch | only a Sketch, `SketchEdgeColor` white | PNG has drawn pixels in #212529 | N/A |
| Styled sketch | `styles=[{object: Sketch, color: red}]` | lines red | N/A |
| Highlighted sketch | `highlight: Sketch` | accent colour | N/A |
| Solid unchanged | a Box, no style | rendering as before (no material override) | N/A |
| G0 CI check, clean | G0.4 evidence OK, validators current | exit 0 | N/A |
| G0 CI check, stale | a cited validator's source changed | exit non-zero, names the validator | N/A |
| G0 CI check, G0.4 fail | G0.4 report not OK | exit non-zero | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/adapters/render_probe.py` -- `_add_subgraphs` (builds each subgraph via `gui.subgraphFromObject`, wraps it with `_wrap_style`), `_wrap_style` (prepended `SoMaterial` with `setOverride(True)`, unwritten fields ignored), `_ACCENT_COLOR`. A sketch is `source.isDerivedFrom("Sketcher::SketchObject")`.
- `tests/infc/test_screenshot.py:369-403` -- `DefaultSetTest`, `_drawn_pixels` (counts pixels that differ from the top-left one). Pattern for preference save/restore: `tests/infc/test_document_lifecycle.py:429-432`.
- `benchmarks/runner.py:96-130` -- `_VALIDATOR_SOURCES`; `_validator_src_hasher` (`:259`); `_parse_subcommand` (`:1360`); `_run_subcommand` (`:1392`); `run_command`, `verdict_command`.
- `benchmarks/harness/verdict.py:106` -- `check_validator_currency(gate_def, validators, hasher)`. Reuse it for the CI check.
- `benchmarks/g0/export-fault-injection/score_export_verify.py:36-41` -- the export scorer's `VALIDATOR_SOURCES` (exports.py, export_oracle.py, export_verdict.py, contracts/numbers.py).
- `benchmarks/g0/gate.yaml` -- G0.4 (headless CI), G0.5 cites `verify_export_step`, G0.3 cites `verify_shape`.
- `.github/workflows/ci.yml` -- `g0-verdict` (`:140-158`), `render` (`:160+`). `.github/workflows/canary.yml:12`.
- `_bmad-output/planning-artifacts/sprint-status.yaml` -- Epic 1 action item "Fix gate.yaml G0.5 validator citation" is settled by this change.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/adapters/render_probe.py` -- give a sketch subgraph with no style colour and no highlight an override line colour #212529, through the `_wrap_style` mechanism -- D1.
- [x] `tests/infc/test_screenshot.py` -- the sketch test forces `SketchEdgeColor` white and restores it. Add cases: styled sketch keeps the style colour; the box path is unchanged.
- [x] `benchmarks/runner.py` -- add `verify_export_step` to `_VALIDATOR_SOURCES`, matching `score_export_verify.py`. Add a CI-scope check, `runner.py ci-check G0 --run <id>`. It exits 0 only when the G0.4 report is PASS and `check_validator_currency` returns no failures. It prints each failure.
- [x] `tests/external/` -- a test that every validator cited by any `gate.yaml` has a `_VALIDATOR_SOURCES` entry, plus tests for the new `ci-check` exit codes.
- [x] `.github/workflows/ci.yml` -- `render`: remove `continue-on-error`. `g0-verdict`: remove `continue-on-error` and `|| true`, run `run G0` for the reports and then `ci-check G0` as the blocking step. Update its comment.
- [x] `.github/workflows/canary.yml` -- remove `continue-on-error` and keep the AD-11 comment accurate (red in Actions, never blocks PRs).
- [x] Docs: `validation-harness-design.md` (CI scope of G0), `sprint-status.yaml` (close the G0.5 citation action item), `deferred-work.md` only if something is deferred.

**Acceptance Criteria:**
- Given a push to a branch, when CI runs, then every job is green with no `continue-on-error` in `ci.yml`.
- Given a fresh FreeCAD user folder, when the infc suite runs locally, then the sketch test passes.

## Implementation Notes

- `verify_recompute` exception (team lead, 2026-10-10): G3.2 and G3.3 cite `verify_recompute`, but it has no scorer and no `validators.yaml` entry, so leg-b reports it `not in registry`. The source-map rule cannot apply, because there is no scorer source list to match. `tests/external/test_g0_ci_check.py` names it as the one exception (`_UNSCORED_CITED`). The test fails once a scorer registers it; the fix is to remove it from `_UNSCORED_CITED` and add its `_VALIDATOR_SOURCES` entry. `deferred-work.md` records the gap.
- `run G0` exits 1 in CI, because G0.1, G0.3 and G0.5 have no CI evidence. The `g0-verdict` job checks that exit code explicitly (0 or 1 passes, 2 or more fails), like the G3 step, and `ci-check G0` is the blocking step.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-10-10). Layers: blind-hunter (BH), edge-case-hunter (EC), verification-gap (VG).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| VG1 / EC1 | `ci-check` passes a report filed under the wrong criterion; `verdict` fails it on leg-a | medium | Reproduced by VG: `subject.criterion='G0.1'` in `G0.4.json` gives ci-check exit 0, verdict leg-a FAILURE | patch: same `_criterion_of` check plus a test |
| BH1 | Spine and design docs still call `render` non-blocking | medium | `ARCHITECTURE-SPINE.md:455`, `project-structure.md:281` and section 5.1, `integration-mcp-freecad.md:356`; the frozen Never rule makes `render` blocking | patch (docs) |
| BH2 | Canary doc claims `continue-on-error` and a pinned issue; section 5.1 has no `g0-verdict` row | low | `project-structure.md:318`; `canary.yml` has no issue step | patch (docs) |
| BH3 / EC3 | A traceback in `run G0` exits 1 and passes the step check | low | `runner.main` catches only `UsageError`/`SystemExit`; Python exits 1 on an uncaught exception | patch: the step also requires the `run G0: wrote` summary line |
| BH4 | Nothing stops `continue-on-error`/`\|\| true` from coming back | low | The rule exists only as spec prose | patch: external test over `ci.yml` |
| BH6 / EC4 | Override may fill a closed sketch's face dark | maybe-false | `ViewProviderSketch.cpp:3292-3294` face node; no test asserts the inside stays background | patch: assert the square's centre pixel is background; report if it fails |
| BH5 | Override also replaces a per-object sketch colour (AutoColor false) | low | D1: fixed colour unless a style or highlight sets one | patch (doc): `mcp-tools-design.md` says unstyled sketches render #212529 |
| BH7 | `_UNSCORED_CITED` assertion message points to the wrong fix | low | It fails once `verify_recompute` is registered, even with a source entry | patch: message says remove it from `_UNSCORED_CITED` and add its sources; align the deferred-work and Implementation Notes wording |
| BH10 | `ci-check` missing-run-dir and malformed-report exits untested | low | No test | patch |
| BH12 | `derive_verdict` computed twice per report | low | `ci_check_command` | patch |
| EC2 | G0.2 is CI-producible (PASS in CI) but not in `_CI_CHECK_CRITERIA` | medium | CI log: `G0.2: PASS (verdict=OK)`; D2 names G0.4 only | defer: needs a human decision on extending D2 |
| VG2 | G0.4 half of `ci-check` cannot fail in CI: evidence is emitted with fixed `--green true --tests 30` | medium | `ci.yml` headless job; pre-existing | defer |
| BH8 | Source order is tested for one validator only | low | The other entries already match their scorers: G1/G2 gate verdicts compute the same hashes and passed | reject |
| BH9 | Spec Code Map names the wrong sprint-status path | low | The fix is a spec edit | reject |
| BH11 | Test fixture repeats G0 citations by hand | low | Test-only; G0 citations rarely change | reject |
| EC5 | Nested `gate.yaml` escapes the glob | low | All gates are one level deep (`benchmarks/g*/gate.yaml`) | reject |
| EC6 | Cleanup with a `None` resource link | false | A cleanup error is reported in addition to the assertion failure; it does not hide it | reject |

## Verification

**Commands:**
- `FREECAD_USER_HOME=<empty dir> freecadcmd tests/run_tests.py` -- expected: OK, the sketch test passes.
- `freecadcmd tests/run_tests.py` -- expected: OK.
- `uv run pytest tests/external` and `uv run ruff check .` and `uv run python scripts/check_imports.py` -- expected: pass.
- `uv run python benchmarks/runner.py ci-check G0 --run <local run with G0.4 evidence>` -- expected: exit 0. Change one byte of `export_verdict.py` in a scratch copy: expected non-zero, naming `verify_export_step`.
- Push the branch -- expected: `ci` run green on every job.
