---
title: 'G1 grader suite integrity: per-kind AND-discriminators + suite hash in validator_sha'
type: 'bugfix'
created: '2026-07-30'
status: 'done'
baseline_revision: '6f8a90c3abea9647fe778ce1f8a6ac575537235e'
final_revision: 'ec67dfdf59415c55d538030a5940a6b85ed5dd2f'
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

### 2026-07-30 — Review pass (follow-up)
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 1, medium 2, low 2)
- defer: 2: (low 2)
- reject: 9
- addressed_findings:
  - `[high]` `[patch]` `test_every_break_kind_has_an_and_discriminator_case` did not test what it claimed: the predicate `names_object and not own_cause` is satisfied by the four pre-existing `fault-wrong-cause-*` cases as well as the four real discriminators. Measured over the suite, `wrong-cause-cover`/`-shim` cover `oc` and `-pillar`/`-spacer` cover `be`, so deleting `fault-and-discriminator-flange` left the `oc` leg "discriminated" and the test green — the exact DW-62 regression it exists to pin. The distinguishing property is that only a real discriminator mentions SOME cause keyword (a foreign one); the wrong-cause cases mention none. Predicate now also requires `foreign_cause`; verified by falsification (removing the `oc` discriminator now fails the test).
  - `[medium]` `[patch]` `_validator_sha` appended each case's path and bytes with no delimiter, so a case whose content spells the next case's path collides with a different suite. Verified: a two-case suite (`a/case.yaml` = `id: one`, `b/case.yaml` = `id: two`) and a one-case suite whose bytes are `id: one\nb/case.yamlid: two\n` — which parses as valid YAML — digested identically. Both hash sites now length-prefix the path and the content; collision reproduces as False.
  - `[medium]` `[patch]` The scorer read each `case.yaml` unguarded while the runner wrapped the identical read in `except OSError: return ""`, so an unreadable case crashed `--check` with a raw `PermissionError` traceback against the module's own `SuiteError` contract ("exit non-zero with a clean message, never write"). Reproduced with a directory named `case.yaml`. The read now raises `SuiteError`, so both entry points report the same tree without a traceback.
  - `[low]` `[patch]` `score()` still ordered cases by `sorted(HERE.rglob(...))` (OS-native `Path` order) while the new `_suite_case_files()` sorts by suite-relative POSIX path — two orderings over one set, created by this change, that diverge for any nested or dotted case dir. `score()` now uses the helper.
  - `[low]` `[patch]` `_kind` accepted `'g1-broken-'`, yielding an empty-string kind that counted as a covered break kind. Now asserts the segment is non-empty.

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

**Implemented change.** Closes DW-62 (per-break-kind AND-discriminator coverage) and DW-63 (fault suite bound into `validator_sha`). Three new right-object-plus-foreign-cause discriminator cases give `oc`, `pd` and `cut` the coverage only `be` had; the fault suite's `case.yaml` set is folded into `validator_sha` at both hash sites, so a score-preserving suite edit stales `--check` instead of slipping it.

**Files changed.**
- `benchmarks/g1/fault-injection/fault-and-discriminator-{flange,bosspad,capnotch}/case.yaml` — new `oc`/`pd`/`cut` discriminators, each naming the right object with a foreign cause and none of its own keywords.
- `benchmarks/g1/fault-injection/score_grader.py` — `_suite_case_files()` + suite fold into `_validator_sha()` with length-prefixed path/content, `SuiteError` on an empty suite and on an unreadable case, `score()` sharing the one ordering helper, updated drift message.
- `benchmarks/runner.py` — `_GRADER_SUITE_ROOT` + `_grader_suite_sources()`; `_validator_src_hasher("grader")` mirrors the scorer byte for byte and returns `""` (stale) rather than the source-only digest when the suite is gone.
- `tests/external/test_harness_g1.py` — per-kind discriminator coverage (object present, own cause absent, foreign cause present), suite-mutation staleness across add/edit/rename/remove plus collision-resistance and unreadable-case legs, scorer↔runner mirror equality, runner staleness on a missing suite.
- `benchmarks/_registry/validators.yaml` — refreshed `grader` block: `n`/`r` 16, sensitivity 1.0, false_alarm 0.0, Wilson low 0.8064; every `verify_*` block preserved by the shared merge-write.
- `benchmarks/g1/README.md`, `docs/decisions/009-g1-grader-deterministic-vs-model.md` — both previously asserted `validator_sha` = grader.py + rubric.md only.

**Review findings.** Two review passes. First pass: 6 patched (1 high, 3 medium, 2 low), 3 deferred, 8 rejected. Follow-up pass: 5 patched (1 high, 2 medium, 2 low), 2 deferred, 9 rejected. The high finding in the follow-up pass was a test that could not detect the regression it existed to pin — its predicate was also satisfied by four pre-existing `wrong-cause-*` cases, so the `oc` and `be` legs were unguarded. Rejected as noise or out of scope: the unconditional pre-bar registry write (pre-existing and by design — the registry records the measured rate honestly and the non-zero exit is the gate), the `n=16` planted-only CI denominator (pre-existing convention), `MIN_PLANTED` headroom framing, the dead `except OSError` around `rglob`, decision-009's singular phrasing, `_grader_suite_sources`' tuple shape, case-insensitive-filesystem and symlink speculation, and the stringly-typed `name == "grader"` branch (the spec fixes the two hash sites).

**Verification performed.**
- `score_grader.py` → exit 0, all 16 planted `DETECTED`, all 4 controls `PASS_CLEAN`, sensitivity 1.000, false_alarm 0.000, wrote `validators.yaml`.
- `score_grader.py --check` → exit 0, `--check: committed score matches`.
- Scorer↔runner hash mirror → `True`.
- `check_validator_currency` over the committed block → `[]` (grader current, leg-b not stale).
- `pytest tests/external -q` → 392 passed.
- `ruff check benchmarks/ tests/external/test_harness_g1.py` → All checks passed.
- `check_provenance.py` → `check_provenance OK`.
- Falsification: with `fault-and-discriminator-flange` removed, the coverage test fails (it passed under the old predicate). Case restored, tree clean.
- Collision: the two-suite/one-suite pair that digested identically before now differs.

**Residual risks.** The three new discriminators depend on the four kinds' keyword sets staying disjoint under whole-token matching; nothing pins that coupling, so widening a `broken-docs` keyword set could flip a discriminator to `MISSED` and break the bar. `pd` owns the bare token `profile` and `cut` owns `tool`, so any future foreign cause for those kinds must avoid those words. With 16 planted at sensitivity exactly 1.000, a single miss yields 0.9375 and fails the 0.95 bar — deliberate, but zero-slack. Two low-severity findings deferred to the ledger.
