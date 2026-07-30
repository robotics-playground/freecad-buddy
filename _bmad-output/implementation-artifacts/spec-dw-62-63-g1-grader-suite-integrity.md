---
title: 'G1 grader suite integrity: per-kind AND-discriminators + suite hash in validator_sha'
type: 'bugfix'
created: '2026-07-30'
status: 'in-review'
baseline_revision: '6f8a90c3abea9647fe778ce1f8a6ac575537235e'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-automation-verification.md'
warnings: []
---

<intent-contract>

## Intent

**Problem:** Two integrity gaps in the G1 grader fault suite. (DW-62) `grader.py:131-133`'s object-AND-cause conjunction is proven by exactly one discriminator case (`fault-and-discriminator-boss`, break kind `be`); the other three break kinds (`oc`, `pd`, `cut`) have only wrong-object and wrong-cause cases, each of which an OR-of(object,cause) grader would also reject — so an OR regression on those kinds goes uncaught. (DW-63) `score_grader.py:68-80` `_validator_sha` hashes only `grader.py` + `rubric.md`, so a score-preserving fault-suite edit keeps both the sha and the committed numbers identical and slips `--check`, which then reports "committed score matches" over a changed suite.

**Approach:** Add one right-object-plus-foreign-cause discriminator `case.yaml` per remaining break kind (`oc`, `pd`, `cut`), mirroring `fault-and-discriminator-boss`. Fold a hash of the sorted fault `case.yaml` set into `_validator_sha`, and mirror the identical hash in `benchmarks/runner.py` `_VALIDATOR_SOURCES["grader"]` so the runner's leg-b staleness check agrees. Re-score to refresh `validators.yaml`, then prove `--check` green.

## Boundaries & Constraints

**Always:**
- Fault cases are pure text: no `.FCStd`, no fixture, no provenance manifest (`check_provenance._is_text_case` exempts a case declaring `candidate_answer` and no `fixture`/`export_file`/`expected` — new cases must keep that shape, using `expected_findings` not `expected`).
- Each new case: `kind: planted_defect` + `expectation: DETECT` (the scorer hard-fails on a kind/expectation mismatch), `targets_validator: grader`, `gate: g1`, `question_ref` naming a real `benchmarks/g1/dev/broken-docs` case id, and `expected_findings.cause_keywords` copied from that broken-doc's own keyword set.
- Each new `candidate_answer` must name the RIGHT object AND a cause keyword belonging to a DIFFERENT break kind, with NONE of its own `cause_keywords` present (whole-token match per `grader._mentions_cause`). That is the discriminator property: an object-only or OR grader PASSes it (MISS), only the AND grader FAILs it (DETECT).
- The scorer's `_validator_sha` and the runner's `grader` hash must produce byte-identical digests over identical inputs — the runner comment at `runner.py:92-94` already binds the order to the scorer's, so both change together in this one commit or gate leg-b reports the grader permanently stale.
- Hash the suite deterministically: sorted `case.yaml` paths, path-relative-identity plus content, so an added/removed/renamed/edited case all change the digest.
- After the source change, re-run `score_grader.py` WITHOUT `--check` to refresh `validator_sha` + `n`/`r`/`wilson_ci` in `benchmarks/_registry/validators.yaml`, then re-run WITH `--check` and require exit 0.
- Preserve every non-`grader` block in `validators.yaml` (the shared `merge_validators_yaml` already does this — do not hand-edit the file).

**Block If:**
- The refreshed sensitivity drops below 0.95 or false_alarm exceeds 0.05 (a new case MISSED means it is not a valid discriminator, not a bar to lower).
- The runner hash and the scorer hash cannot be made to agree without changing `check_validator_currency`'s contract in `benchmarks/harness/verdict.py`.

**Never:**
- Do not edit `benchmarks/g1/grader.py` — the grader is already AND; this is a coverage + currency change, not a behavior change.
- Do not edit `_bmad-output/implementation-artifacts/deferred-work.md` (the orchestrator records resolution).
- Do not touch `benchmarks/g1/heldout/`, any existing case's `candidate_answer`/`expected_findings`, or the `SENSITIVITY_BAR`/`FALSE_ALARM_BAR`/`MIN_PLANTED` constants.
- Do not add a `fixture.FCStd`, provenance manifest, or any FreeCAD build step for the new cases.
- Do not duplicate the suite-hash logic in a third place; the runner and scorer are the only two hash sites.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Per-kind AND-discriminator graded | New `oc`/`pd`/`cut` discriminator case: right object, foreign cause | Grader `pass_ == False` → outcome `DETECTED`; sensitivity stays 1.0 over 16 planted | No error expected |
| OR-regression simulation | Grader passing on object-only (OR semantics) | Each of the four discriminator cases becomes `MISSED` → sensitivity falls below 0.95 | Scorer exits 1, `BARS NOT MET` |
| Suite mutated, score unchanged | A `case.yaml` edited/added/removed with the aggregate rate unchanged | Recomputed `_validator_sha` differs from committed → `--check` exit 1 | `COMMITTED SCORE STALE: committed validator_sha != ...` |
| Runner staleness leg on clean tree | Clean working tree, refreshed `validators.yaml` | `runner._validator_src_hasher("grader")` equals committed `validator_sha`; leg-b reports current | No error expected |
| Fault case unreadable | A `case.yaml` in the suite cannot be read by the runner's hasher | Runner hasher returns `""` (stale, never a traceback) | Leg-b: `grader (stale: source hash mismatch)` |

</intent-contract>

## Code Map

- `benchmarks/g1/fault-injection/score_grader.py` -- owns `_validator_sha()` (lines 68-80) and the `--check` drift comparison (`_committed_score_drift`, line 216 message string); globs `case.yaml` at line 106.
- `benchmarks/runner.py` -- `_VALIDATOR_SOURCES["grader"]` (lines 87-99) + `_validator_src_hasher` (lines 180-196): the mirrored hash consumed as `hasher` by leg-b. Currently a flat tuple of source paths; needs to also cover the fault suite.
- `benchmarks/harness/verdict.py:106-145` -- `check_validator_currency`; compares committed `validator_sha` to `hasher(name)`. Contract unchanged.
- `benchmarks/g1/fault-injection/fault-and-discriminator-boss/case.yaml` -- the shape to mirror (comment explains the discriminator property).
- `benchmarks/g1/dev/broken-docs/{oc-flange-outline,pd-boss-pad,cut-cap-notch}/case.yaml` -- source of the `question_ref` ids, objects, and own `cause_keywords` for the three new cases.
- `benchmarks/_registry/validators.yaml` -- `grader` block, rewritten by the scorer's merge-write (never by hand).
- `tests/external/test_harness_g1.py` -- `test_fault_inventory_counts_and_binding` (inventory + binding), `test_grader_fails_planted_wrong_passes_correct_over_suite` (every planted case must FAIL the grader), `test_score_grader_meets_bars_exit_0` (`--check` exit 0), `test_score_grader_check_flags_stale_committed_score`.
- `tests/external/test_gate_verdict.py:430` -- `test_validator_src_hasher_missing_source_is_stale_not_traceback` mutates `_VALIDATOR_SOURCES["verify_shape"]` to a 1-tuple of a missing path; keep that shape working.
- `scripts/check_provenance.py:103-120` -- `_is_text_case` exemption the new cases rely on.
- `.github/workflows/ci.yml:31` -- `uv run python benchmarks/g1/fault-injection/score_grader.py --check`.

## Tasks & Acceptance

**Execution:**
- [x] `benchmarks/g1/fault-injection/fault-and-discriminator-flange/case.yaml` -- new `oc` discriminator: `question_ref: g1-broken-oc-flange-outline`, object `FlangeOutline`, own keywords `[conflicting, over-constrained, overconstrained, redundant constraint]`, `candidate_answer` naming `FlangeOutline` with an expression-binding (`be`) cause -- closes the `oc` leg of DW-62.
- [x] `benchmarks/g1/fault-injection/fault-and-discriminator-bosspad/case.yaml` -- new `pd` discriminator: `question_ref: g1-broken-pd-boss-pad`, object `BossPad`, own keywords `[missing sketch, no object linked, deleted profile, profile, base sketch]`, `candidate_answer` naming `BossPad` with an over-constrained (`oc`) cause -- closes the `pd` leg of DW-62.
- [x] `benchmarks/g1/fault-injection/fault-and-discriminator-capnotch/case.yaml` -- new `cut` discriminator: `question_ref: g1-broken-cut-cap-notch`, object `CapNotch`, own keywords `[missing tool, linked object, removed tool, boolean, tool]`, `candidate_answer` naming `CapNotch` with an over-constrained (`oc`) cause -- closes the `cut` leg of DW-62.
- [x] `benchmarks/g1/fault-injection/score_grader.py` -- extend `_validator_sha()` to fold a deterministic hash of the sorted fault `case.yaml` set (relative path + content) after `grader.py` + `rubric.md`; update its docstring and the `_committed_score_drift` message so the reported reason names the suite; keep the rubric-missing `SuiteError` -- closes DW-63.
- [x] `benchmarks/runner.py` -- mirror the identical suite hash for `grader` in the validator-currency hasher (extend `_VALIDATOR_SOURCES["grader"]` to include the sorted fault `case.yaml` set, or hash it in `_validator_src_hasher` for `grader`) in the SAME byte order as the scorer; update the lines 92-99 comment to state the suite is part of the grader's currency; keep an unreadable source returning `""` rather than raising -- prevents a permanently-stale leg-b.
- [x] `tests/external/test_harness_g1.py` -- add: (1) a test asserting every break kind (`oc`, `pd`, `cut`, `be`) has at least one AND-discriminator case (right object present, own cause absent) so the per-kind coverage cannot silently regress; (2) a test asserting a fault-suite mutation changes `_validator_sha` (write a temp case into a copied suite dir, or add a case file and assert the digest differs); (3) a test asserting `runner._validator_src_hasher("grader")` equals `score_grader._validator_sha()` on the clean tree -- pins the mirror agreement DW-63 depends on.
- [x] `benchmarks/_registry/validators.yaml` -- refreshed by running `score_grader.py` (no `--check`); expect `validator_sha` changed and `n`/`r` = 16 planted with `sensitivity: 1.0`, `false_alarm: 0.0`; every `verify_*` block byte-preserved.

**Acceptance Criteria:**
- Given the AND grader and the refreshed suite, when `score_grader.py --check` runs, then it exits 0 with `sensitivity >= 0.95` and `false_alarm <= 0.05` over `>= 16` planted and `>= 4` controls.
- Given the grader is regressed to OR-of(object, cause), when the suite is scored, then at least one discriminator case per break kind reports `MISSED` and the scorer exits 1 with `BARS NOT MET`.
- Given a fault `case.yaml` is added, edited, or removed with the aggregate score unchanged, when `score_grader.py --check` runs, then it exits 1 reporting a `validator_sha` mismatch.
- Given a clean working tree with `validators.yaml` refreshed, when `runner._validator_src_hasher("grader")` is compared to the committed `validator_sha`, then they are equal and gate leg-b reports the grader current (not stale).
- Given the new cases carry no `fixture.FCStd` and no provenance manifest, when `scripts/check_provenance.py` runs, then it reports no missing-fixture and no orphan-manifest violation.

## Spec Change Log

## Review Triage Log

### 2026-07-30 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 6: (high 1, medium 3, low 2)
- defer: 3: (medium 1, low 2)
- reject: 8
- addressed_findings:
  - `[high]` `[patch]` An empty/deleted fault suite made `_validator_sha` and the runner mirror collapse to the source-only digest — byte-identical to the previously committed `137c6fb…` — so a deleted suite reported the grader CURRENT against a score measured over a suite that no longer exists (the exact failure DW-63 exists to prevent). Verified by pointing `_GRADER_SUITE_ROOT` at a missing dir. Scorer now raises `SuiteError` on an empty suite; runner returns `""` (stale) and never the source-only digest.
  - `[medium]` `[patch]` `benchmarks/g1/README.md:48` and `docs/decisions/009-g1-grader-deterministic-vs-model.md:77-80` still asserted `validator_sha` = grader.py + rubric.md only — made false by this change. Both updated to name the suite as a third input; the README now also states the refresh step.
  - `[medium]` `[patch]` The new discriminator test hard-indexed `case["question_ref"].split("-")[2]` for every case before the DETECT filter, while the scorer treats `question_ref` as optional (`case.get("question_ref", "")`); a control authored without it passed the scorer then died on a bare `KeyError`. Now asserts the key with a diagnostic message and guards the segment count.
  - `[medium]` `[patch]` The mutation test proved only inequality and never covered the rename leg that the hashed path identity exists to catch. Added a byte-identical-content rename assertion and an emptied-suite `SuiteError` assertion, plus a runner-side missing-suite staleness test.
  - `[low]` `[patch]` The test comment claimed a wholesale OR regression "goes unscored"; measured at 0.312 sensitivity, it is caught loudly. Only a *per-kind* OR regression escaped (`cut`-only scored 1.000 before this change, 0.938 after). Comment corrected to state the real justification.
  - `[low]` `[patch]` Hardcoded `{"oc","pd","cut","be"}` turned legitimate suite growth into a false "suite invalid" failure; the sibling `test_broken_docs_inventory_tiered_30` derives kinds from data. Now derived from `broken-docs` ids, keeping the real `discriminated == kinds` assertion.

## Design Notes

Verified against the working tree (`python` + `grader.DeterministicGrader`) that all three planned `candidate_answer` strings have the discriminator property — object present, own cause absent, AND-grader FAILs:

```
oc   AND_pass=False  names_object=True  own_cause_present=False
pd   AND_pass=False  names_object=True  own_cause_present=False
cut  AND_pass=False  names_object=True  own_cause_present=False
```

Cross-kind foreign causes are safe because the four keyword sets are disjoint under whole-token matching: `oc` = conflicting/over-constrained/overconstrained/redundant constraint; `pd` = missing sketch/no object linked/deleted profile/profile/base sketch; `cut` = missing tool/linked object/removed tool/boolean/tool; `be` = expression/binding/reference/not found. Note `pd` owns the bare token `profile` and `cut` owns the bare token `tool`, so a foreign cause for those two kinds must avoid those words entirely — an `oc` cause ("over-constrained ... conflicting ... redundant constraint") does. Conversely the `oc` case's foreign cause uses `be` wording ("expression binding ... not found").

The suite-hash mirror follows the precedent set when `rubric.md` was added to the hash (spec-2-1 iteration note: scorer + `_VALIDATOR_SOURCES` updated in the same change, same order, "verified hash MATCH"). `_VALIDATOR_SOURCES` values are consumed only by `_validator_src_hasher`, which concatenates `read_bytes()` in order; folding the sorted `case.yaml` paths in after `grader.py`/`rubric.md` keeps that loop unchanged. Content-only hashing would miss a pure rename, so include each case's suite-relative path (POSIX, stable across OS) in the digest alongside its bytes; keep `__pycache__` out of the glob (the existing `rglob("case.yaml")` already only matches case files).

## Verification

**Commands:**
- `uv run python benchmarks/g1/fault-injection/score_grader.py` -- expected: exit 0, per-case table shows `DETECTED` for all 16 planted (incl. 4 discriminators) and `PASS_CLEAN` for all controls, writes `validators.yaml`.
- `uv run python benchmarks/g1/fault-injection/score_grader.py --check` -- expected: exit 0, `--check: committed score matches`.
- `uv run python -c "import sys; sys.path[:0]=['benchmarks/g1/fault-injection','benchmarks/g1','benchmarks/g0/export-fault-injection','.']; import score_grader; from benchmarks import runner; print(score_grader._validator_sha() == runner._validator_src_hasher('grader'))"` -- expected: `True`.
- `uv run pytest tests/external/test_harness_g1.py tests/external/test_gate_verdict.py -q` -- expected: all pass.
- `uv run python scripts/check_provenance.py` -- expected: exit 0, no violations.
- `uv run ruff check benchmarks/ tests/external/test_harness_g1.py` -- expected: clean on touched files (repo-wide `ruff check .` is red on 10 pre-existing E501s in `scripts/automation/` + `tests/external/test_check_imports.py`; those are out of scope).
- `uv run python -c "import sys; sys.path.insert(0,'.'); import yaml; from pathlib import Path; from benchmarks import runner; from benchmarks.harness.verdict import check_validator_currency; v=yaml.safe_load(Path('benchmarks/_registry/validators.yaml').read_text(encoding='utf-8')); print(check_validator_currency({'criteria':[{'cited_validators':['grader']}]}, v, runner._validator_src_hasher))"` -- expected: `[]` (leg-b reports no stale/below-bar validator).

## Auto Run Result

Status: done

**Summary.** Closed both G1 grader fault-suite integrity gaps. DW-62: added one right-object-plus-foreign-cause AND-discriminator case per remaining break kind (`oc`, `pd`, `cut`), so the grader's object-AND-cause conjunction is now discriminator-tested for all four kinds instead of only `be`. DW-63: folded a hash of the sorted fault `case.yaml` set (path identity + bytes) into `score_grader._validator_sha`, mirrored byte-for-byte in the runner's validator hasher, so a score-preserving suite edit stales the committed score instead of slipping `--check`.

**Files changed.**
- `benchmarks/g1/fault-injection/fault-and-discriminator-flange/case.yaml` (new) -- `oc` discriminator: `FlangeOutline` + a `be` (expression-binding) foreign cause.
- `benchmarks/g1/fault-injection/fault-and-discriminator-bosspad/case.yaml` (new) -- `pd` discriminator: `BossPad` + an `oc` foreign cause.
- `benchmarks/g1/fault-injection/fault-and-discriminator-capnotch/case.yaml` (new) -- `cut` discriminator: `CapNotch` + a `be` foreign cause (varied in review so 3 of 4 discriminators no longer share one keyword family).
- `benchmarks/g1/fault-injection/score_grader.py` -- `_suite_case_files()`; `_validator_sha` folds each case's suite-relative POSIX path + bytes; raises `SuiteError` on an empty suite; drift message names the suite.
- `benchmarks/runner.py` -- `_GRADER_SUITE_ROOT` + `_grader_suite_sources()`; `_validator_src_hasher` folds the same bytes in the same order for `grader`, returns `""` (stale) on an empty or unreadable suite, never raises.
- `tests/external/test_harness_g1.py` -- 4 new tests: per-kind AND-discriminator coverage (kinds derived from `broken-docs`), suite-mutation staleness (add / edit / rename / remove / emptied), scorer-runner hash mirror, runner missing-suite staleness.
- `benchmarks/_registry/validators.yaml` -- `grader` block refreshed by the scorer; all four `verify_*` blocks byte-preserved.
- `benchmarks/g1/README.md`, `docs/decisions/009-g1-grader-deterministic-vs-model.md` -- corrected the now-false "only grader.py + rubric.md are hashed" claims.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- 3 new defer entries appended (no existing entry modified).

**Review findings.** 6 patches applied (1 high, 3 medium, 2 low), 3 deferred, 8 rejected, 0 intent gaps, 0 bad-spec loopbacks. The high-severity patch: an empty/deleted suite made both hashes collapse to the source-only digest — byte-identical to the previously committed `137c6fb…` — so a deleted suite would have reported the grader CURRENT against a score measured over a suite that no longer existed, the exact failure DW-63 exists to prevent. Two reviewer findings were rejected after direct falsification: removing the path-identity line does NOT go green (3 tests fail), and the claimed in-scope requirement to update README/009 came from a different run's bundle file (the docs were still patched, as staleness this change caused).

**Verification.**
- `score_grader.py` (write) then `--check`: exit 0, `planted=16 detected=16 sensitivity=1.000`, `controls=4 flagged=0 false_alarm=0.000`, `wilson_ci=[0.806, 1.000]`, `--check: committed score matches`.
- `validator_sha`: `137c6fbf…feb17` -> `fbdf9d89…d249c` (refreshed after the capnotch variation); `n`/`r` 13 -> 16.
- Scorer/runner mirror: `True`. Leg-b `check_validator_currency` for `grader`: `[]` (current).
- `uv run pytest tests/external -q`: `392 passed`.
- `check_provenance OK`, `check_imports OK`, `ruff check benchmarks/ tests/external/test_harness_g1.py`: `All checks passed!`.
- Falsification (independently run, not reported by a subagent): a wholesale OR regression scores 0.312; per-kind OR regressions now score `oc` 0.750 / `pd` 0.875 / `cut` 0.938 / `be` 0.750 — all four below the 0.95 bar, i.e. CAUGHT. Before this change a `cut`-only OR regression scored 1.000 and escaped the bar. A genuinely score-preserving suite addition (rate unchanged at 1.000/0.000) now fails `--check` with exit 1.

**Residual risks.**
- `verify_shape`, `verify_export_stl`, `verify_export_3mf`, and `verify_export_step` report stale under leg-b. Confirmed pre-existing at baseline `6f8a90c` by stashing this change and re-running (all four stale there too, `grader` current) — not a regression from this work, and out of scope. They need their own G0 re-score.
- The runner's suite fold is an `if name == "grader"` branch inside an otherwise table-driven hasher; a future second suite-bound validator would need another branch. Current behavior is correct and the mirror is test-pinned for `grader` only.
- The `wilson_ci`/`n`/`r` fields remain outside `_committed_score_drift`'s comparison (deferred).
