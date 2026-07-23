---
title: 'Story 2.1 — Entry Gate G1.E: Eval Set, Rubric & Grader Validation'
type: 'feature'
created: '2026-07-24'
status: 'done'
baseline_revision: '6522bcfff83e49f8538808eb6be2c754ea90f8ea'
final_revision: '9293b71c208ab8b11329cec451aa683cc5dd58a7'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-1-3-entry-gate-g0e-golden-models-fault-suite.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/validation-harness-design.md'
  - '{project-root}/_bmad-output/specs/spec-freecad-buddy/phase-gates.md'
  - '{project-root}/docs/decisions/008-g1-eval-tiered-n10-n30.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** AD-19 ordering requires the Phase-1 grading machinery — 50-question eval, a 30-case broken-recompute fixture set (tiered n=10→n=30 per decision 008), a human-authored rubric, a sealed dev/held-out split, and a fault-tested **independent grader** — to exist and fail honestly BEFORE any assistant code (Stories 2.2/2.3), so answer quality is decided by a validated grader, never the assistant (NFR1). None of `benchmarks/g1/` exists; the runner only knows `G0`.

**Approach:** Land the G1 entry-gate data + an independent grader validator + a FreeCAD-free G1 gate path, mirroring Story 1.3's G0.E pattern. Deliver: 50 eval questions with expected findings; a 30-case broken-recompute fixture set each naming *the* failing object + cause; a planted confident-wrong-answer fault suite; `rubric.md` with worked pass/fail examples; a **deterministic expected-findings grader** (`benchmarks/g1/grader.py`, external process) that grades a candidate answer against a case's expected findings + rubric and is itself scored to sensitivity ≥95 % / FA ≤5 % on the planted fault suite via `gate faults g1`; `g1/gate.yaml` declaring `actor:` ≠ `grader:` with a preflight identity hard-fail; the `g1/heldout/` sealed placeholder (AR7 shape); provenance manifests for every artifact; and `runner.py --gate G1 --stub` emitting one honest-FAIL `ValidationReport` per G1 criterion against a stub assistant (never green, never crash).

## Boundaries & Constraints

**Always:**
- Expected findings (the failing object identity `{object, cause}` for broken-doc cases; expected finding lists for eval questions) are **independently hand-authored** references, never captured from a running assistant (AD-13; project-context "golden values … never captured from the implementation under test").
- The grader is **independent of the actor** (NFR1, harness §8): `g1/gate.yaml` declares distinct `actor:` and `grader:` config blocks; the runner's G1 preflight **hard-fails with `INVALID_INPUT`** if they resolve to the same model id + shared context. The grader takes only the question, the candidate's final answer, the rubric, and the case's expected findings — never the actor's scratch reasoning.
- The delivered grader is the **deterministic expected-findings matcher** (`grader.py`): given `{object, cause}` expected and a candidate answer, it decides `{pass, matched_expected, rationale}` by rubric-keyed matching of the named object + cause. It is CI-reproducible (no network, no live model) and is the grader whose sensitivity `gate faults g1` scores now. An **LLM-grader adapter seam** (a `GraderClient` protocol the deterministic grader implements) is declared so a model-backed grader can plug in later, but no live-model call ships in this story.
- Grader output is the schema-validated verdict `{pass: bool, matched_expected: bool, rationale: str}`; the fault scorer maps each verdict into the standard contracts `ValidationReport` and computes sensitivity/false-alarm + Wilson CI, then merge-writes ONLY the `grader` block of `_registry/validators.yaml` (reuse the shared `merge_validators_yaml`; never clobber the `verify_*` blocks).
- The 30-case broken-recompute fixture set is authored in full (30), each `.FCStd` carrying a genuinely broken recompute with a known failing object; the **tiered escalation is metadata on the cases + gate.yaml** (`tier: n10` on the first 10, `tier: n30` on the rest) so 2.2 grades n=10 first and escalates only on 10/10 (decision 008). This story lands + tiers the fixtures; it does not run the assistant against them.
- Runner + all `benchmarks/g1/` glue live in the **external uv process**, stdlib + contracts + pyyaml only, FreeCAD-free (AD-12). It consumes the contracts-owned `ValidationReport`/`derive_verdict`/`Check` — never invents a report shape or status string (AD-17); the closed status set is unchanged.
- Broken-doc `.FCStd` fixtures are produced by a committed deterministic generator run under `FreeCADCmd`; a `tests/infc/` unittest opens each committed fixture, recomputes, and asserts the named failing object is actually in error (`getStatusString()` non-empty on the expected object) — an independent self-check on the blocking headless legs.
- Every benchmark artifact carries a provenance manifest under `_registry/provenance/`; `source.kind` ∈ the AD-16 closed set (`hand-authored` here) with a mandatory `real_world_basis`. `check_provenance.py` already gates this recursively; ensure the new artifacts pass.
- The `--stub` G1 run is deterministic and exits non-zero; every G1 criterion yields a schema-valid `ValidationReport` whose `verdict` is `INVALID_INPUT` via `derive_verdict` (honest "cannot evaluate: no assistant yet"), and the run never raises.
- `g1/heldout/` holds only the sealed placeholder (mirror the existing `benchmarks/heldout/.gitkeep` posture: a `.gitkeep`/marker documenting the sealed set, no live cases); CI must never sweep it. Full `heldout.tar.age`/`SEAL.json` sealing ceremony is exercised at Gate G1 exit (Story 2.4), not here — do NOT implement `age` encryption in this story.

**Block If:**
- The broken-doc generator cannot produce a `.FCStd` reproducibly with a genuinely-broken recompute (FreeCADCmd unavailable, or no reliable way to plant a recompute error on a required leg) → HALT `blocked`, condition `broken-doc fixture generation unavailable`.
- A contracts type needed by the runner/grader (ValidationReport shape, ReportBanner fields, terminal-status set, `derive_verdict`) is missing or changed vs Story 1.2 → HALT `blocked`, do NOT redefine it locally.
- The independent-grader model-config decision (which model backs the *live* grader later) is genuinely required to write this story → it is NOT: the deterministic grader is the shippable validator now and the `grader:` config block names a placeholder model id + declares the seam; do not block on the backend pin.

**Never:**
- Never run/implement the assistant, any `query_*` actor loop, or a live LLM call here (Stories 2.2/2.3) — the stub returns "not implemented" and the runner reports honest failure.
- Never grade with the actor or claim a grader sensitivity number the fault run did not produce; the number in `validators.yaml` comes from the real `gate faults g1` run over the planted suite, or is `last_run: null` with the honest reason if the deterministic grader cannot be scored on a required leg.
- Never touch `benchmarks/**/heldout/` beyond adding the `g1/heldout/` sealed placeholder; keep existing placeholders untouched; add no CI glob sweeping any heldout path.
- No `print()` in `src/` (T201); the grader + runner + generators live under `benchmarks/` (tooling, printing allowed) — do NOT add grader/report logic into `src/`.
- Never open a `.FCStd` via raw `App.openDocument` outside a `tests/infc/` self-check (the AD-20 `document_*` usecases exist but the harness stub does not open documents in `--stub` mode; the infc self-check may raw-open with a comment, matching 1.3).
- Never expand the runner into a real G1 actor run; `--gate G1 --stub` is the only new run path. `gate run g1` (non-stub actor run) lands in Story 2.2.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Stub G1 gate run | `runner.py --gate G1 --stub`, no assistant | One `ValidationReport` per G1 criterion (G1.1–G1.6), each `verdict == INVALID_INPUT` (honest FAIL); exit 1 | Never raises; stub "not implemented" is a FAIL report, not a crash |
| Grader fault score | `gate faults g1` over planted confident-wrong + clean-correct answers | sensitivity ≥95 % / FA ≤5 %, Wilson CI; merge-write `grader` block of `validators.yaml` with `validator_sha` | Bars unmet → exit non-zero, print per-case table; never overwrite `verify_*` blocks |
| Actor==grader preflight | `g1/gate.yaml` with `actor.model == grader.model` and same context | Runner G1 preflight aborts `INVALID_INPUT` before any scoring | Clean message naming the identity collision; exit 2 |
| Broken-doc self-check | `tests/infc` under FreeCADCmd | 30 fixtures open + recompute; each named failing object has non-empty `getStatusString()` | Mismatch → test fails naming case + object |
| Fault-suite inventory | `benchmarks/g1/fault-injection/` | ≥10 planted confident-wrong + ≥1 clean-correct control, each `fault.kind` ∈ closed 2-set + bound to `grader` in `validators.yaml` | count < 10 or unbound/typo'd kind → inventory test fails |
| Tiered fixture inventory | `benchmarks/g1/dev/broken-docs/` | exactly 30 cases; exactly 10 tagged `tier: n10`, 20 tagged `tier: n30`; each names `{object, cause}` | wrong count / missing tier / missing expected → test fails naming case |
| Unknown / lowercase gate | `runner.py --gate G9` / `--gate g1` | clean error message, exit 2 | no traceback dump |
| Empty/malformed g1 gate | `gate.yaml` empty/non-mapping/zero-criteria | exit 2, never green | `yaml.YAMLError` caught; no traceback |

</intent-contract>

## Code Map

- `benchmarks/g1/gate.yaml` -- declarative G1.1–G1.6 mirror (phase-gates G1 table): per-criterion id, text, pass_rule, `cited_validators` (`grader` for G1.1/G1.2). Adds top-level `actor:` and `grader:` model-config blocks (harness §8), `required_tokens: [rubric_review, spot_audit]`, and `verdict.heldout: sealed` (unsealed only at exit, Story 2.4). Comments the tiered n10→n30 rule + the Phase-1 grader-verdict schema. Runner-consumed, not hardcoded.
- `benchmarks/g1/dev/eval-questions.yaml` -- 50 questions, each `{id, question, doc_fixture?, expected_findings: [...], criterion}`; expected findings are independently hand-authored. Covers tree-explanation, error-diagnosis, next-tool-guidance (FR7). Small shared read-only `.FCStd` fixtures under `dev/fixtures/` where a question needs a concrete document.
- `benchmarks/g1/dev/broken-docs/<case>/case.yaml` (+ `fixture.FCStd`) -- 30 broken-recompute cases; each `{id, tier: n10|n30, expected: {object, cause}, criterion: G1.2}`. 10 `tier: n10`, 20 `tier: n30`. Fixtures built by a committed generator.
- `benchmarks/g1/dev/broken-docs/build_broken_docs.py` -- deterministic FreeCADCmd generator: builds each broken-recompute fixture (e.g. deleted external reference, missing sketch support, over-constrained sketch, broken attachment, dangling expression) with a fixed failing object Name; no timestamps.
- `benchmarks/g1/fault-injection/<case>/case.yaml` -- ≥10 planted confident-wrong answer cases + ≥1 clean-correct control; each `{targets_validator: grader, fault.kind: planted_defect|clean_control, expectation: DETECT|PASS_CLEAN, question_ref, expected_findings, candidate_answer}`. The `candidate_answer` is the planted (confidently-wrong or correct) text the grader must judge. No `.FCStd` needed (text cases).
- `benchmarks/g1/fault-injection/score_grader.py` -- external-process scorer (mirrors `score_verify_shape.py` shape, but text not geometry, and runs under uv not FreeCADCmd): for each case run `grader.grade(question, candidate_answer, rubric, expected_findings)`, compare verdict.pass to `expectation`, compute sensitivity/FA + Wilson CI, hash the grader source into `validator_sha`, merge-write ONLY the `grader` block of `validators.yaml` via the shared `merge_validators_yaml`. Exit non-zero when bars unmet.
- `benchmarks/g1/grader.py` -- the independent deterministic expected-findings grader: `GraderClient` protocol + `DeterministicGrader` implementing it; `grade(question, answer, rubric, expected) -> GraderVerdict{pass, matched_expected, rationale}`. Rubric-keyed matching of the named object + cause (case-normalized object identity match + cause keyword match per rubric). FreeCAD-free, stdlib-only. The LLM-grader seam is the protocol; no live call here.
- `benchmarks/g1/rubric.md` -- human-authored grading rubric with worked pass/fail examples (per G1.E): how a correct answer names *the* failing object + cause; worked examples of a confident-wrong answer that must FAIL and a correct answer that must PASS; the object-identity + cause-match rule the deterministic grader encodes. Covered by the `rubric_review` token at exit (Story 2.4), authored here.
- `benchmarks/g1/heldout/.gitkeep` -- sealed-set placeholder mirroring `benchmarks/heldout/.gitkeep` posture (documents the sealed split; no live cases; CI never sweeps). No `age`/`SEAL.json` machinery in this story.
- `benchmarks/g1/README.md` -- suite map: the tiered n10→n30 rule (decision 008), the grader-verdict schema, the forward note that the live-model grader + real actor land in 2.2/2.3.
- `benchmarks/_registry/validators.yaml` -- add a `grader` block bound to `g1/fault-injection/`; `last_run` populated by `score_grader.py` (real deterministic score) or `null` with reason if unscorable on a leg.
- `benchmarks/_registry/provenance/g1-*.yaml` -- one manifest per broken-doc fixture + per shared eval fixture (`source.kind: hand-authored`, `real_world_basis`, `license_checked`). Text-only fault/eval cases that ship no `.FCStd` need no manifest (check_provenance walks `*.FCStd`); confirm the walker is satisfied.
- `benchmarks/runner.py` -- extend `KNOWN_GATES` with `"G1": "g1"`; add the G1 criteria set to the ingested/stub logic so `--gate G1 --stub` builds one honest-FAIL report per criterion; add the **G1 preflight** actor≠grader identity check (reads `gate.yaml` `actor:`/`grader:`; identity → exit 2 `INVALID_INPUT`); wire the `faults` subcommand to invoke `score_grader.py` for G1. Keep all existing G0 behavior + honest-fail guards intact.
- `benchmarks/harness/report_build.py` -- reuse as-is if the G1 stub report shape fits; only extend if a G1 criterion needs a distinct check id (prefer no change — the stub outcome + `derive_verdict` already produce `INVALID_INPUT`).
- `tests/external/test_harness_g1.py` -- pytest, non-tautological: (a) stub G1 run → one schema-valid report per G1 criterion, each `verdict == INVALID_INPUT`, exit 1; (b) fault inventory ≥10 planted + ≥1 control, every `fault.kind` ∈ closed 2-set, every case `targets_validator: grader` + bound in `validators.yaml`; (c) broken-doc inventory: exactly 30 cases, 10 `n10` + 20 `n30`, each with `{object, cause}`; (d) grader determinism + correctness: `DeterministicGrader` FAILS a planted confident-wrong answer and PASSES the matched correct answer over the fault suite (real grade calls, real verdicts); (e) actor==grader `gate.yaml` copy → runner G1 preflight exit 2; (f) honest-fail guards for `--gate G1` (unknown/lowercase gate, empty/malformed gate.yaml, `--criterion` miss → exit 2).
- `tests/infc/test_broken_docs_g1.py` -- stdlib unittest under FreeCADCmd (discovered by `tests/run_tests.py`): open each committed broken-doc `fixture.FCStd`, `recompute()`, assert the case's named `expected.object` exists and has a non-empty `getStatusString()` (genuinely broken); set-equality: case dirs == generator `CASES` == committed fixture basenames; count == 30. Raw-open with a comment (test-local, matching 1.3).
- `pyproject.toml` -- no new runtime dep (pyyaml already dev). Confirm `benchmarks` still in `[tool.ruff] src`; the grader/scorer/generators are linted + T201-exempt under the existing `benchmarks/**` rule.
- `.github/workflows/ci.yml` -- `arch-checks`: add a step running `uv run python benchmarks/runner.py --gate G1 --stub` asserting a NON-zero exit is the pass condition; add `uv run python benchmarks/g1/fault-injection/score_grader.py` (deterministic, no network — safe in CI) asserting the grader clears the bars; `headless`: the broken-doc infc self-check runs via the existing `FreeCADCmd tests/run_tests.py` discovery (FreeCAD bundles PyYAML). Do NOT add a heldout sweep.
- `docs/decisions/009-g1-grader-deterministic-vs-model.md` -- decision note: why the shipped G1 grader is the deterministic expected-findings matcher (CI-reproducible, scorable now, no secrets) with a `GraderClient` seam for a later model-backed grader; the reuse survey (surveyed: LLM-as-judge frameworks, exact-match graders) + why nothing existing fit the entry-gate reproducibility need.

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md` (language-agnostic rules; Python ring).
  - Re-read `validation-harness-design.md` §1–§3, §6, §7, §8 (layout, case format, gate runner, fault framework, human tokens, **independent grader**) and `phase-gates.md` G1 + Global protocol — binding contract for this story.
  - Re-read `project-context.md` "Verification & Validation Discipline" + "Testing & CI Rules" (grader independent of actor; golden/expected values independent; heldout sealed; two test worlds).
  - Re-read Story 1.3's spec (the G0.E analog) — this story mirrors its honest-fail-stub + fault-suite + provenance + infc-self-check architecture.
  - Read decision `008-g1-eval-tiered-n10-n30.md` (30 fixtures, tiered n10→n30 escalation).
  - Load `typescript-clean-code` for naming/commenting discipline (zero obvious comments), applied to Python.

**Execution:**
- [x] `benchmarks/g1/gate.yaml` -- declarative G1.1–G1.6 mirror with `actor:`/`grader:` config blocks, `required_tokens: [rubric_review, spot_audit]`, `verdict.heldout: sealed`, `cited_validators: [grader]` on G1.1/G1.2; comment the tiered rule + grader-verdict schema + forward-declared nature. -- gate definition (AC1).
- [x] `benchmarks/g1/dev/eval-questions.yaml` (+ `dev/fixtures/*.FCStd` as needed) -- 50 questions with independently hand-authored `expected_findings`, spanning tree-explanation / error-diagnosis / next-tool-guidance. -- 50-question eval (AC1).
- [x] `benchmarks/g1/dev/broken-docs/build_broken_docs.py` -- deterministic FreeCADCmd generator for 30 broken-recompute fixtures with fixed failing-object Names; distinct break kinds (deleted external ref, missing sketch support, over-constrained sketch, broken attachment, dangling expression, …). -- reproducible broken fixtures.
- [x] `benchmarks/g1/dev/broken-docs/<case>/case.yaml` + `fixture.FCStd` -- 30 cases, 10 `tier: n10` + 20 `tier: n30`, each `{id, tier, expected: {object, cause}, criterion: G1.2, provenance}`; the `expected.object` is *the* failing object (G1.2 requires *the*, not *an*). -- 30-case tiered set naming the object+cause (AC1).
- [x] `benchmarks/g1/rubric.md` -- human-authored rubric with ≥2 worked examples (one confident-wrong → FAIL, one correct → PASS) and the object-identity + cause-match pass rule the deterministic grader encodes. -- rubric with worked examples (AC1).
- [x] `benchmarks/g1/grader.py` -- `GraderClient` protocol + `DeterministicGrader.grade(question, answer, rubric, expected) -> GraderVerdict{pass, matched_expected, rationale}` (object-identity + cause-keyword match), FreeCAD-free, stdlib-only, schema-validatable verdict. -- independent grader + LLM seam (AC2).
- [x] `benchmarks/g1/fault-injection/<case>/case.yaml` -- ≥10 planted confident-wrong-answer cases + ≥1 clean-correct control; each `{targets_validator: grader, fault.kind, expectation, question_ref, expected_findings, candidate_answer}`. -- grader fault suite (AC2).
- [x] `benchmarks/g1/fault-injection/score_grader.py` -- external scorer: grade every case, compare to `expectation`, compute sensitivity/FA + Wilson CI, hash grader source → `validator_sha`, merge-write ONLY the `grader` block of `validators.yaml` (shared `merge_validators_yaml`); exit non-zero if sensitivity < 0.95 or FA > 0.05. -- grader sensitivity run (AC2).
- [x] `benchmarks/_registry/validators.yaml` -- add `grader` → `suite: g1/fault-injection/`; `last_run` filled by `score_grader.py` (real deterministic score) — never faked. -- validator↔suite binding (AC2).
- [x] `benchmarks/_registry/provenance/g1-*.yaml` -- one manifest per broken-doc fixture + per shared `dev/fixtures/*.FCStd` (`source.kind: hand-authored`, `real_world_basis`, `license_checked`). -- AD-16 provenance.
- [x] `benchmarks/g1/heldout/.gitkeep` + `benchmarks/g1/README.md` -- sealed placeholder (mirror repo-level posture; no live cases, no age/SEAL machinery) + suite README (tiered rule, grader schema, 2.2/2.3 forward note). -- sealed-split shape (AR7) + suite map.
- [x] `benchmarks/runner.py` -- add `"G1": "g1"` to `KNOWN_GATES`; make `--gate G1 --stub` build one honest-FAIL `INVALID_INPUT` report per G1 criterion; add the G1 **actor≠grader preflight** (identity → exit 2, clean message); route `faults g1` → `score_grader.py`. Preserve all G0 behavior + honest-fail guards. -- G1 stub run + preflight + faults wiring (AC2, AC3).
- [x] `tests/external/test_harness_g1.py` -- non-tautological coverage of I/O matrix rows (a)–(f): stub reports + verdict class + exit 1; fault inventory + closed kinds + binding; 30-case tiered inventory + `{object,cause}`; `DeterministicGrader` FAILs planted-wrong / PASSes correct over the suite; actor==grader preflight → exit 2; G1 honest-fail guards. -- AC1/AC2/AC3 + guards.
- [x] `tests/infc/test_broken_docs_g1.py` -- open each committed broken-doc `.FCStd`, recompute, assert named object is genuinely in error (`getStatusString()` non-empty); set-equality (cases == generator CASES == committed basenames) + count 30. -- independent broken-fixture self-check.
- [x] `.github/workflows/ci.yml` -- `arch-checks`: add G1 stub honest-fail step (non-zero exit = pass) + `score_grader.py` bar-check step (deterministic, no network); `headless`: broken-doc infc self-check via existing `tests/run_tests.py`. No heldout sweep. -- CI-enforced G1 entry gate.
- [x] `docs/decisions/009-g1-grader-deterministic-vs-model.md` -- record the deterministic-grader-with-seam decision + reuse survey (G1.E requires a recorded reuse survey). -- G1.E reuse-survey + grader-choice artifact.

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- rings clean (grader/runner/harness external, import contracts only).
- [x] `uv run python scripts/check_provenance.py` -- provenance gate green on the new artifacts.
- [x] `uv run ruff check .` -- clean.
- [x] `uv run pytest tests/external -q` -- all green (G1 harness + prior suites).
- [x] `"FreeCADCmd" tests/run_tests.py` -- broken-doc self-check green (local FreeCAD 1.1; CI runs both legs).

**Acceptance Criteria:**
- Given `benchmarks/g1/`, when inspected, then it holds 50 eval questions with expected findings, a 30-case broken-recompute fixture set (10 `n10` + 20 `n30`, each naming *the* failing object + cause per decision 008), `rubric.md` with worked pass/fail examples, and the `g1/heldout/` sealed placeholder — all `.FCStd` artifacts provenance-manifested and passing the AD-16 closed-source-kind check; and the infc self-check proves each committed broken fixture is genuinely in error on its named object.
- Given planted confident-wrong answers, when `gate faults g1` (i.e. `runner.py faults G1` → `score_grader.py`) runs the independent deterministic grader over them, then grader sensitivity ≥95 % / FA ≤5 % is recorded in `_registry/validators.yaml` with the grader source hash; and `g1/gate.yaml` declares `actor:` ≠ `grader:` with the runner's G1 preflight hard-failing (`INVALID_INPUT`, exit 2) on identity.
- Given no assistant implementation, when `python benchmarks/runner.py --gate G1 --stub` runs, then every G1 criterion FAILS honestly with a schema-valid contracts `ValidationReport` (`verdict == INVALID_INPUT` via `derive_verdict`), the process exits non-zero, and it never crashes.

## Spec Change Log

_No bad_spec loopback occurred. The review pass produced only patches + defers; the `<intent-contract>` was never amended._

## Review Triage Log

### 2026-07-24 — Review pass (iteration 3, follow-up)
- intent_gap: 0
- bad_spec: 0
- patch: 1 (low 1)
- defer: 2 (low 2)
- reject: many (already-litigated in iterations 1–2, by-design, or philosophical)
- addressed_findings:
  - `[low]` `[patch]` `test_faults_g1_routes_to_scorer_exit_0` ran the real `faults G1`, which merge-WRITES the committed `benchmarks/_registry/validators.yaml` (no `--check`), leaving the routing assertion non-hermetic — iteration 2 fixed the two scorer tests to `--check` but missed this runner-routing test. Today the write is byte-identical (committed score current) so the tree stays clean, but a future committed drift would be silently overwritten by the test. Snapshot + restore the registry around the subprocess (try/finally). Verified: 24/24 G1 tests + 247/247 external pass, `validators.yaml` untouched after the run.
  - `[low]` `[defer]` DW-8: the grader's object-AND-cause conjunction is discriminator-tested for only the `be` break kind (`fault-and-discriminator-boss`); `oc`/`pd`/`cut` have no right-object+foreign-cause case, so an OR-regression on those kinds would go uncaught. Coverage gap, grader is AND today.
  - `[low]` `[defer]` DW-9: committed `validator_sha` = sha256(grader.py + rubric.md) excludes the fault `case.yaml` set; `--check` catches any score-CHANGING suite edit, but a score-PRESERVING mutation (swap one detected planted answer for another) slips currency. Low consequence; fold a case-set hash into `validator_sha`.

### 2026-07-24 — Review pass (iteration 2, follow-up)
- intent_gap: 0
- bad_spec: 0
- patch: 8 (medium 4, low 4)
- defer: 1 (low 1)
- reject: 4 (low 4)
- addressed_findings:
  - `[medium]` `[patch]` `score_grader.py --check` recomputed a fresh score but never compared it to the COMMITTED `validators.yaml` block, so its docstring claim ("committed score is verified") was false — a stale/garbage committed sha or sensitivity survived CI (proven: `sensitivity: 0.0` + `validator_sha: DEADBEEF` still exited 0). Added `_committed_score_drift()`; `--check` now hard-fails (exit 1) when the committed `validator_sha != sha256(grader.py+rubric.md)` or committed `sensitivity`/`false_alarm` differ from the fresh run. Added `test_score_grader_check_flags_stale_committed_score`.
  - `[medium]` `[patch]` `_mentions_cause` matched cause keywords by bare substring, so single-word keywords (`tool`, `profile`, `binding`) spuriously matched inside longer words (`toolbar`/`tooltip`) — a fluent-wrong answer or control could pass on an unrelated word. Switched to whole-token (space-padded) matching, which still matches multi-word phrases (`missing tool`) as contiguous runs; sensitivity/FA unchanged at 13/13, 0/4. Added `test_grader_cause_keyword_is_whole_token_not_substring`.
  - `[medium]` `[patch]` The `faults G1` scoring path scored + write-merged the grader WITHOUT the actor≠grader identity preflight (NFR1 applied only to the stub `run_gate`). Added `_preflight_actor_grader(gate)` to `faults_command` before the scorer spawns, so a colliding gate never scores the grader.
  - `[medium]` `[patch]` The `score()` scorer promised "clean SuiteError, never a traceback" but raised raw `AttributeError`/`ValueError`/`TypeError` on a malformed suite (non-dict `case.yaml`, non-dict `fault`/`expected_findings`, or a grader `ValueError`). Hardened `_load_case` + `score()` to raise `SuiteError` on every malformed shape; the grader now raises a typed `ValueError` on a non-dict `expected` (also closes the latent G1.1 list-of-strings landmine). Added `test_grader_rejects_non_dict_expected`.
  - `[low]` `[patch]` The actor≠grader preflight ran AFTER `_filter_criteria`, so a non-matching `--criterion` exited before the NFR1 identity check (order-dependent guard). Reordered `run_gate` to validate the gate (`_load_gate`) → preflight → filter; the unknown/lowercase-gate honest-fail (`KeyError` → clean exit 2) is preserved.
  - `[low]` `[patch]` `_validator_sha`/`score()` silently tolerated a missing `rubric.md` (`if RUBRIC.is_file()`), weakening the "rubric edit stales the score" invariant to "…unless the rubric is absent". The rubric is a required part of the validator (decision 009): both now raise `SuiteError` when it is missing.
  - `[low]` `[patch]` The two write-mode scorer tests dirtied the committed `validators.yaml` (non-hermetic). `test_score_grader_meets_bars_exit_0` now runs `--check` (hermetic + asserts committed currency); `test_score_grader_check_mode_does_not_write` seeds its sentinel from the current committed block so `--check` passes without a write.
  - `[low]` `[patch]` `README.md` said the n10 tier "is not kind-skewed" while it is 3 oc + 3 pd + 2 be + 2 cut; softened to "no kind is absent from the first pass" (the load-bearing property the test asserts).
  - `[low]` `[defer]` DW-7: `merge_validators_yaml`'s block-preservation (grader appended while all four `verify_*` blocks survive) is exercised only against the already-populated committed file — no test starts from a verify-only YAML. Pre-existing shared-seam gap (the G0 export scorer has the same untested path), surfaced here.
  - `[low]` `[reject]` subprocess negative/signal return code (POSIX) — harness treats any non-zero as fail (already rejected iteration 1); `_kind` positional id parse — coupled to a stable id scheme, works; `_HEADER` dropped if `validators.yaml` lacks a header — committed file has the header, unreachable; `build_broken_docs` argv import-guard + cross-leg break-kind reliability — already tracked as open DW-6/DW-5, not re-filed.

### 2026-07-24 — Review pass (iteration 1)
- intent_gap: 0
- bad_spec: 0
- patch: 12 (medium 7, low 5)
- defer: 2 (low 2)
- reject: 3 (low 3)
- addressed_findings:
  - `[medium]` `[patch]` Scorer went green on a degenerate suite (0 controls → FA vacuously 0.0; 0 planted → sensitivity vacuous). The `≥10 planted + ≥1 control` invariant lived only in a pytest, not the CI scorer step. `score_grader.py` now hard-fails (`SuiteError`, no write) on `<10 planted` or `<1 control`; added `test_score_grader_rejects_degenerate_suite`.
  - `[medium]` `[patch]` Fault suite validated each leg (object-only caught by wrong-object cases, cause-only by wrong-cause cases) but had no case that only an `AND` grader rejects. Added `fault-and-discriminator-boss` (right object + a different diagnosis's cause, own cause absent) so an OR grader is caught; sensitivity now 13/13.
  - `[medium]` `[patch]` actor≠grader preflight only fired on `model AND context` collision — same model with a cosmetically different `context` bypassed NFR1. Tightened to fire on same model id regardless of context.
  - `[medium]` `[patch]` Rubric edits did not stale the grader sensitivity run (design §6/§8 invariant): `validator_sha` hashed only `grader.py`. Now hashes `grader.py` + `rubric.md` (scorer) and added `grader` → `(grader.py, rubric.md)` to the runner's `_VALIDATOR_SOURCES` (same order) so the runner's staleness leg agrees — verified hash MATCH.
  - `[medium]` `[patch]` `expected` with empty/null/scalar `cause_keywords` (or blank `object`) degraded to a silent all-FAIL case (inflating sensitivity, false-alarming a control). Grader now raises `ValueError` on malformed `expected` via `_cause_keywords` + object guard.
  - `[medium]` `[patch]` CI `score_grader.py` step mutated the tracked `validators.yaml` (dirty tree / date drift). Added `--check` mode (evaluate bars, do not write); CI uses it; added `test_score_grader_check_mode_does_not_write`.
  - `[medium]` `[patch]` No assertion paired `fault.kind` ↔ `expectation`; a mis-tagged case would be silently mis-partitioned. Scorer now raises on a `planted_defect`/`DETECT` (and `clean_control`/`PASS_CLEAN`) disagreement.
  - `[low]` `[patch]` n=10 tier slice covered only 2 of 4 break kinds (8 oc + 2 be), so 2.2's first-pass gate was kind-skewed. Re-tiered to 3 oc + 2 be + 3 pd + 2 cut (all 4 kinds); added the n10-spans-all-kinds assertion to `test_broken_docs_inventory_tiered_30`.
  - `[low]` `[patch]` Fault-case cause keywords (`[conflicting]`) were narrower than the broken-doc set, so the grader was never tested on the alternate keywords it faces in production. Added `control-bracket-altkeyword` (a correct answer phrased with "redundant constraint" / "overconstrained").
  - `[low]` `[patch]` `_is_text_case` exempted ANY case carrying `candidate_answer` from the fixture-presence check repo-wide. Scoped the exemption to a case that declares NEITHER `fixture`/`export_file` NOR `expected`, so a geometry case with a stray key is still flagged.
  - `[low]` `[patch]` No CI/test guard that `g1/heldout/` stays placeholder-only (design §1.1). Added `test_g1_heldout_contains_only_placeholder`.
  - `[low]` `[patch]` "schema-validated/validatable verdict" wording overstated (no JSON schema for `GraderVerdict`; `matched_expected` == `pass_`). Softened to "structured dataclass verdict" in grader docstring + README + Design Notes; recorded scope limits in decision 009.
  - `[low]` `[defer]` DW-5: G1 break kinds verified genuinely-broken only on local FreeCAD 1.1; the 1.0.x infc leg is the honest guard (a non-broken fixture reds that leg, not a silent pass).
  - `[low]` `[defer]` DW-6: `build_broken_docs` import-side-effect guard is argv-based; a path-passing discovery runner could re-trigger a rebuild-on-import (no such runner exists).
  - `[low]` `[reject]` Object-substring false-match (`HousingBore` in `HousingBoreTool`) — guarded by the whole-token space-padded compare + `_normalize` not splitting camelCase; not reachable. Multi-word object Names — none in this suite (all single-token camelCase). Subprocess negative return code on signal — POSIX edge, harness treats non-zero as fail.

## Design Notes

- **Why a deterministic grader ships now (not a live model).** The entry gate must be reproducible in CI without secrets or network, and its sensitivity number must be real, not aspirational. For G1.2's structured expected findings (`{object, cause}`), a rubric-keyed deterministic matcher is the strongest and most reproducible grader — it decides `pass` by matching the named failing object identity + cause keywords, exactly the thing G1.2 measures ("*the* failing object + cause named"). It is scorable now against the planted confident-wrong suite, so `validators.yaml.last_run` carries a genuine sensitivity/FA, not `null`. The `GraderClient` protocol is the seam a model-backed grader (for fuzzier G1.1 answer-quality judgment) plugs into when a backend lands in 2.2/2.3; that live-model grader's own sensitivity run is a later ceremony. This mirrors 1.3's discipline (land + bind + prove the machinery honestly), but here the validator is the grader and it CAN be scored now because it is independent of the not-yet-existing assistant.
- **Actor≠grader is enforced, not documented.** `g1/gate.yaml` carries both config blocks; the runner's G1 preflight aborts `INVALID_INPUT` on **same model id regardless of context** (the stronger NFR1 reading — a different `context` string does not make the same model an independent grader; harness §8). A test copies the gate with a matching model id and asserts exit 2.
- **Tiered fixtures are data + metadata, not runner logic here.** The 30 cases are authored and tagged `tier: n10`/`tier: n30`; the *escalation* (grade n=10, escalate on 10/10) is Story 2.2's actor-run logic. This story only lands the tiered set + asserts its shape (10 + 20 = 30) so 2.2 has the fixtures decision 008 requires.
- **Honest-fail stub, same as G0.** The G1 stub assistant returns structured "not implemented" for every call; `report_build` → `Check{passed: false, detail.code: invalid_input.not_implemented}` → `derive_verdict` → `INVALID_INPUT`. Empty/malformed/zero-criteria `g1/gate.yaml` → exit 2 (never green), unknown/lowercase gate → exit 2, no traceback — the existing G0 guards apply unchanged once `G1` is a known gate.
- **Grader-verdict schema.** `GraderVerdict = {pass: bool, matched_expected: bool, rationale: str}` (harness §8). The scorer maps it into a contracts `Check`/`ValidationReport`; DETECT (planted-wrong) is "detected" when `pass == False`, a clean-correct control is a false alarm when `pass == False`. Keep the verdict a plain dataclass/TypedDict in `benchmarks/` (external), NOT a new `contracts/` type — no wire type is added by this story.
- **PyYAML placement unchanged.** All G1 harness data is YAML (`gate.yaml`, `case.yaml`, `eval-questions.yaml`, `validators.yaml`); PyYAML stays external-process-only; the infc broken-doc self-check reads case YAML with FreeCAD's bundled PyYAML.

## Verification

**Commands:**
- `uv run python benchmarks/runner.py --gate G1 --stub` -- expected: per-criterion FAIL summary (G1.1–G1.6, all `INVALID_INPUT`), exits 1.
- `uv run python benchmarks/g1/fault-injection/score_grader.py` -- expected: sensitivity ≥0.95 / FA ≤0.05, merge-writes the `grader` block, exit 0.
- `uv run python scripts/check_provenance.py` -- expected: exit 0 (new g1 manifests valid).
- `uv run python scripts/check_imports.py` -- expected: exit 0 (rings clean; harness outside rings).
- `uv run pytest tests/external -q` -- expected: all pass (G1 harness + prior suites).
- `uv run ruff check .` -- expected: clean.
- `"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" tests/run_tests.py` -- expected: broken-doc self-check green (30 fixtures each genuinely in error on the named object).

**Manual checks:**
- `benchmarks/g1/dev/` has `eval-questions.yaml` (50) + `broken-docs/` (30 cases, 10 `n10` + 20 `n30`) + `rubric.md`.
- `benchmarks/g1/fault-injection/` has ≥10 planted-wrong + ≥1 clean control, each naming `grader` and present in `validators.yaml`.
- `benchmarks/g1/heldout/` holds only the sealed placeholder; no live cases; no age/SEAL machinery added.

## Auto Run Result

### 2026-07-24 — Follow-up review pass (iteration 3)

**Summary:** Re-reviewed the completed G1 entry-gate implementation (`done` spec → fresh review pass). Two adversarial reviewers (Blind Hunter, Edge Case Hunter) surfaced findings; nearly all were already litigated in iterations 1–2, by-design, or philosophical. One genuinely new low-severity test-hermeticity issue was patched; two new low coverage/currency gaps were deferred.

**Files changed this pass:**
- `tests/external/test_harness_g1.py` — `test_faults_g1_routes_to_scorer_exit_0` now snapshots + restores the committed `validators.yaml` around the real `faults G1` subprocess (which merge-writes it), keeping the routing assertion hermetic.
- `_bmad-output/implementation-artifacts/deferred-work.md` — appended DW-8 (AND-conjunction discriminator-tested for only the `be` break kind) and DW-9 (`validator_sha` excludes fault `case.yaml` set, so a score-preserving suite edit slips `--check`).

**Review findings breakdown:** patch 1 (low), defer 2 (low), reject many.
- Rejected as already-addressed (iter 1/2): actor≠grader model-only preflight (deliberate stronger reading), whole-token cause matching, multi-word object names, OR-vs-AND (patched + discriminator added), non-hermetic scorer tests (fixed to `--check`), degenerate-suite guard.
- Rejected as by-design / disclosed: coarse FA over few controls (MIN_CONTROLS=1), single Wilson CI on sensitivity arm, `sys.executable` uv assumption, empty `dev/fixtures/` (Story 2.2 authors runnable fixtures), POSIX signal return code.

**Verification:**
- `uv run pytest tests/external/test_harness_g1.py -q` → 24 passed; `validators.yaml` byte-unchanged after run (hermeticity fix confirmed).
- `uv run pytest tests/external -q` → 247 passed (4 pre-existing trimesh warnings, unrelated).
- `uv run ruff check tests/external/test_harness_g1.py` → clean.

**Follow-up review recommendation:** `false` — the sole code change is a localized low-consequence test-hermeticity fix (no product code touched); the two defers are recorded coverage/currency gaps, not defects.

**Residual risks:** DW-8/DW-9 (deferred, low). DW-5/DW-6/DW-7 from prior passes remain open. The grader's independence is nominal (keyword matcher authored alongside the fixtures) — disclosed in decision 009; the model-backed grader (Stories 2.2/2.3) is where fuzzier answer-quality judgment lands.

