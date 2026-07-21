---
title: 'Story 1.3 — Entry Gate G0.E: Golden Models, Fault Suite, Honest-Failing Benchmark'
type: 'feature'
created: '2026-07-21'
status: 'done'
baseline_revision: '33b064a083688f469ba92a8c6997b6cfd002620f'
final_revision: 'UNCOMMITTED (working tree — commit withheld per user no-auto-commit policy in CLAUDE.md; branch=main protected)'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/validation-harness-design.md'
  - '{project-root}/_bmad-output/specs/spec-freecad-buddy/phase-gates.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** AD-19 ordering requires the Phase-0 validators' test artifacts (golden reference models, planted-fault suite, gate runner) to exist and fail honestly BEFORE any bridge/verify-tool code, so no tool is ever graded by an untested validator. None of it exists — `benchmarks/` is empty.

**Approach:** Land the G0 entry-gate data + a FreeCAD-free gate runner: 5 hand-made golden `.FCStd` models with independently hand-computed `expected.yaml`, ≥10 planted-fault cases + clean controls bound to the `verify_shape` id in `_registry/validators.yaml`, provenance manifests, and `benchmarks/runner.py --gate G0 --stub` that emits an honest FAIL `ValidationReport` per criterion against a stub bridge (never green, never crash). Sensitivity scoring of the suite is deferred to Story 1.6 (verify_shape does not exist yet); this story only lands and binds the artifacts.

## Boundaries & Constraints

**Always:**
- Golden expected values (volume/bbox/counts) are **independently hand-computed analytic references** (box/cylinder/sphere/boolean primitives), transcribed into `expected.yaml` — NEVER captured from a running verify tool (AD-13; project-context "Golden values … never captured from the implementation under test").
- Runner + all `benchmarks/` glue live in the **external uv process**, stdlib + contracts-only, FreeCAD-free (AD-12). It consumes the contracts-owned `ValidationReport`/`derive_verdict` from Story 1.2 — never invents its own report shape or status string (AD-17).
- Golden `.FCStd` are produced by a committed deterministic generator (`build_golden_models.py`) run under `FreeCADCmd`; a `tests/infc/` unittest regenerates them and asserts each shape's measured volume/bbox/solid-count matches `expected.yaml` within the stated tolerance (independent-oracle self-check on the blocking headless legs).
- Fingerprints in `expected.yaml` are **diagnostic `expected_meta` only**, tagged `exportBinary` (decision 001) — never a scoring metric (whole-shape hashing banned as identity oracle for pass/fail).
- Every benchmark artifact carries a provenance manifest under `_registry/provenance/`; `source.kind` ∈ the AD-16 closed set (`hand-authored` here) with a mandatory `real_world_basis`. A CI check fails on any artifact missing a manifest or with an out-of-set `source.kind`.
- Fault cases carry `fault.kind` (`planted_defect` | `clean_control`) + `expectation` (`DETECT` | `PASS_CLEAN`); ≥10 planted defects PLUS clean controls; all bound to `verify_shape` in `validators.yaml`.
- `--stub` run is deterministic and exits non-zero; every criterion yields a schema-valid `ValidationReport` whose `verdict` is a non-OK terminal status via `derive_verdict` (honest FAIL), and the run never raises.

**Block If:**
- The generator cannot produce a `.FCStd` reproducibly (FreeCADCmd unavailable or `exportBinary` missing on a required leg) → HALT `blocked`, condition `golden model generation unavailable`.
- A contracts type needed by the runner (ValidationReport shape, ReportBanner fields, terminal-status set, `derive_verdict`) is missing or changed vs Story 1.2 → HALT `blocked`, do NOT redefine it locally.

**Never:**
- Never run/implement `verify_shape` or any bridge/`document_*` tool here (Stories 1.4/1.6) — the stub returns "not implemented" and the runner reports honest failure.
- Never compute or claim a sensitivity/false-alarm number for the fault suite in this story — there is no validator to score yet; `validators.yaml` records the binding with a pending/null `last_run`.
- Never touch `benchmarks/*/heldout/` (sealed; keep the existing placeholder untouched).
- No `print()` in `src/` (T201); runner lives under `benchmarks/` (tooling, printing allowed) — do NOT add report/runner logic into `src/`.
- Never open `.FCStd` via raw `App.openDocument`; the runner does not open documents at all in `--stub` mode.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Stub gate run | `runner.py --gate G0 --stub`, no bridge | One `ValidationReport` per G0 criterion (G0.1–G0.5), each `verdict` non-OK (honest FAIL); process exits 1 | Never raises; a stub "not implemented" is a FAIL report, not a crash |
| Golden self-check | `tests/infc` under FreeCADCmd | 5 models regenerated; measured vol/bbox/solids == `expected.yaml` within tol | Mismatch → test fails naming model + field |
| Provenance audit | any artifact under `benchmarks/g0/` | manifest exists, `source.kind` in closed set | missing/invalid → check exits 1 with artifact id |
| Fault-suite inventory | `benchmarks/g0/fault-injection/` | ≥10 `planted_defect` + ≥1 `clean_control`, each valid `fault` block, each bound in `validators.yaml` | count < 10 or unbound case → inventory test fails |
| Unknown gate id | `runner.py --gate G9` | clean error message, exit 2 | no traceback dump |

</intent-contract>

## Code Map

- `benchmarks/g0/golden-models/build_golden_models.py` -- FreeCADCmd generator emitting the 5 `.FCStd` deterministically (fixed object Names/order; `exportBinary`-based save). Run manually + by the infc self-check.
- `benchmarks/g0/golden-models/*.FCStd` -- 5 committed reference models: `box-10-20-30`, `cylinder-r5-h20`, `sphere-r10`, `box40-hole-r5`, `two-box-compound`.
- `benchmarks/g0/golden-models/expected.yaml` -- per-model hand-computed `volume`/`bbox`/`solids` + tolerance band + a documentary `expected_meta.serializer: exportBinary` marker (NO committed `sha256` — unverifiable now; real fingerprint oracle is Story 1.6).
- `benchmarks/g0/fault-injection/*/case.yaml` (+ `fixture.FCStd`) -- ≥10 planted-defect cases (wrong volume, non-watertight, dropped solid, unit lie, degenerate face, wrong-solid-count, negative volume, open shell, self-intersecting, wrong-bbox) + ≥1 clean control; each `targets_validator: verify_shape`, `fault.kind`, `expectation`.
- `benchmarks/g0/gate.yaml` -- declarative mirror of the G0 exit-criteria table (G0.1–G0.5 ids, criterion text, pass rule, cited validator ids); the runner reads this, does not hardcode criteria.
- `benchmarks/_registry/validators.yaml` -- binds `verify_shape` → `g0/fault-injection/` suite; `validator_sha: null`, `last_run: null` (pending — scored in Story 1.6).
- `benchmarks/_registry/provenance/*.yaml` -- one manifest per golden model + per fault fixture (`kind`, `source.kind: hand-authored`, `real_world_basis`, `license_checked`).
- `benchmarks/runner.py` -- gate runner core: safely load `gate.yaml` (catch `yaml.YAMLError`; reject non-mapping / empty-`criteria`), `StubBridge` (every tool → "not implemented"), build one `ValidationReport` per criterion via contracts + `derive_verdict`, aggregate verdict, print summary. Exit 0 ONLY if all criteria pass, 1 if any fails, 2 on any usage/loader error (unknown gate, malformed/empty/non-mapping gate, criterion missing `id`, `--criterion` matching nothing) — never green on zero criteria, never a traceback. Invoked as `python benchmarks/runner.py --gate G0 --stub` (file-path entry) and importable as `benchmarks.runner`.
- `benchmarks/__init__.py`, `benchmarks/harness/__init__.py`, `benchmarks/harness/report_build.py` -- `benchmarks` is a top-level importable package (so `tests/external` can `from benchmarks.runner import ...` and `from benchmarks.harness.report_build import ...` in the uv env where `src/` is installed but `benchmarks/` is imported from the repo root on `sys.path`); `report_build` is the single builder of contracts `ValidationReport`/`ReportBanner`/`Check` from a criterion + stub outcome (no duplicated report shaping).
- `scripts/check_provenance.py` -- CI check: every `benchmarks/**` artifact has a manifest with closed-set `source.kind`; exit 1 + artifact id on violation.
- `tests/external/test_harness_g0.py` -- pytest: stub run yields honest-FAIL reports for all criteria (schema-valid, non-OK verdict, exit 1); fault-suite inventory (≥10 defects + control, all bound); provenance audit passes on the tree; unknown-gate exits 2 without traceback.
- `tests/infc/test_golden_models.py` -- stdlib unittest under FreeCADCmd: regenerate models, assert measured vol/bbox/solids == `expected.yaml`.
- `pyproject.toml` -- add `pyyaml` to `[project.optional-dependencies].dev` (external harness parses `gate.yaml`/`case.yaml`/`validators.yaml`/`expected.yaml`; PyYAML is external-process-only, never imported by in-FreeCAD code — AD-12 permits third-party in the uv env); add `benchmarks` to `[tool.ruff] src`. Do NOT add a `gate` console-script (benchmarks lives outside `src/`, not in the wheel; the runner is invoked by file path per harness §3.1).
- `.github/workflows/ci.yml` -- `arch-checks`: add `check_provenance.py` (blocking) + a step running `runner.py --gate G0 --stub` asserting honest non-zero exit; `headless`: add `pyyaml` to the pip install so `pytest tests/external` can import the harness, and the infc golden self-check runs via the existing `tests/run_tests.py` discovery.
- `docs/decisions/007-benchmark-harness-reuse-survey.md` -- recorded reuse survey (G0.E requires it): surveyed pytest-as-runner / existing eval frameworks vs a thin stdlib runner; decision + why nothing existing fit.

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md` (language-agnostic rules; Python ring).
  - Re-read `validation-harness-design.md` §1–§3, §6 (layout, case format, gate runner, fault framework) and `phase-gates.md` G0 + Global protocol — binding contract for this story.
  - Re-read `project-context.md` "Verification & Validation Discipline" + "Testing & CI Rules" (golden values independent; heldout sealed; two test worlds).
  - Load `typescript-clean-code` for naming/commenting discipline (zero obvious comments), applied to Python.
  - Read decisions `001-serializer-exportbinary.md` (fingerprint tag) + `002-conda-freecadcmd-path.md` (FreeCADCmd invocation).

**Execution:**
- [x] `benchmarks/g0/golden-models/build_golden_models.py` -- deterministic FreeCADCmd generator for the 5 models with fixed Names/placements; save via `exportBinary` serializer; no timestamps in output. -- reproducible golden fixtures (AD-13).
- [x] `benchmarks/g0/golden-models/expected.yaml` -- transcribe the hand-computed analytic values: box-10-20-30 vol=6000, bbox=[10,20,30], solids=1; cylinder-r5-h20 vol=1570.7963, bbox=[10,10,20], solids=1; sphere-r10 vol=4188.7902, bbox=[20,20,20], solids=1; box40-hole-r5 vol=15214.6018, bbox=[40,40,10], solids=1; two-box-compound vol=2000, bbox=[30,10,10], solids=2. Tolerance `rel: 0.001`. **Do NOT commit `golden_fingerprint.sha256` values** — no test re-derives them and the generators save via `saveAs` (non-reproducible zip), so a committed hash is unverifiable dead metadata (the ungrounded-number defect). Keep at most a documentary `expected_meta.serializer: exportBinary` marker noting the Story-1.6 `fingerprint()` will hash with that serializer; omit `sha256` entirely. -- independent golden references (never impl-captured; no unverifiable hashes).
- [x] `benchmarks/g0/fault-injection/<id>/case.yaml` + `fixture.FCStd` -- ≥10 planted-defect cases + ≥1 clean control. Each: `targets_validator: verify_shape`, `fault.kind`, `expectation`, `assertions`, `provenance:` link; fixtures built by a generator paralleling the golden one. **CRITICAL — assertions encode the REFERENCE (correct-shape) expectation, so DETECT fires from the defective fixture deviating from it (NOT from a hand-picked defective value).** For a planted defect targeting property P, the `assertions` state what a CORRECT shape yields for P; the fixture violates P; a validator that measures P and compares to the assertion detects the deviation. Concretely per case:
  - `wrong-volume` (fixture vol 7200): assert `expect_volume: 6000` (fires: 7200≠6000). ✓ already correct.
  - `wrong-bbox` (fixture Z=60): assert `expect_bbox: [10,20,30]` (fires). ✓.
  - `non-watertight-open-shell` (open shell, 0 solids): assert `expect_watertight: true` (the correct reference IS watertight; the open shell is not). Do NOT assert `expect_solid_count: 1` as the detection signal — watertightness is the named defect. A `expect_solid_count: 1` line is allowed only as a secondary diagnostic, not the primary.
  - `degenerate-face` (zero-area face): assert `expect_valid: true` (reference is valid; degenerate face is `isValid()==False`). Detection is validity, not solid count.
  - `zero-volume-lamina` (planar face, vol 0): assert `expect_volume` to a POSITIVE reference matching what a solid of that footprint would give (e.g. `100` for a would-be 10×10×1), OR assert `expect_solid_count: 1` — but the description and expected value MUST be internally consistent with a lamina (do NOT paste box-10-20-30's 6000). Prefer asserting the defect directly: `expect_volume` > 0 reference the lamina fails.
  - `dropped-solid` (1 solid): assert `expect_solid_count: 2` (reference two-box compound has 2). ✓.
  - `wrong-solid-count` (3 solids): assert `expect_solid_count: 2`. ✓.
  - `unit-lie` (1/10 scale, vol 6): assert `expect_volume: 6000` + `expect_bbox: [10,20,30]` (reference mm values; the cm model fails). ✓.
  - `negative-volume` (reversed solid, signed −1000): the defect is orientation, and OCCT signed-volume is version-fragile. Re-target this case to a robust signal: assert `expect_valid: true` AND `expect_volume: 1000` where the reference is the +1000 a correctly-oriented unit cube gives; document that detection depends on signed volume. **If signed-volume detection is not robust across the CI legs, REPLACE this case with a different, unambiguous defect** (e.g. a shape with an inverted face that fails `isValid()`), so the suite never relies on a version-fragile signal. Resolve this during implementation using local FreeCAD 1.1; record the choice in the case description.
  - `self-intersecting` (2 overlapping solids in a compound): the named defect is interference, not count. Since Phase-0 assertion vocabulary has no interference check, either (a) re-target the assertion to the honest observable — `expect_solid_count: 1` because a correctly-booleaned union of two overlapping boxes is ONE solid (the compound wrongly has 2) — and update the description to say "should have been fused to 1 solid", OR (b) drop this case and add a distinct unambiguous defect to preserve ≥10. Pick (a).
  - `non-manifold`: the generator's three-separate-faces `Part.Shell` may NOT actually share one OCCT edge (>2 adjacent faces) — verify under local FreeCAD that the fixture is genuinely non-manifold (inspect edge-sharing); if it is not, rebuild it so it is (sew the faces so the shared edge is one edge), or replace with another unambiguous defect. Assert the reference `expect_watertight: true` (a manifold solid is watertight; the non-manifold shell is not).
  - `clean-control` (exact box-10-20-30 rebuild): assert the true reference `expect_volume: 6000`, `expect_bbox: [10,20,30]`, `expect_solid_count: 1`; `expectation: PASS_CLEAN`. ✓.
  Every `fn` name comes from the documented forward-declared reserved set (see Design Notes "Assertion vocabulary"). -- fault suite with reference-anchored assertions (AC2; AD-19).
- [x] `benchmarks/g0/gate.yaml` -- declarative G0 mirror: for each of G0.1–G0.5 the id, criterion text, pass-rule string, `cited_validators` (e.g. `verify_shape` for G0.3/G0.5). Runner-consumed. -- gate definition, not hardcoded criteria.
- [x] `benchmarks/_registry/validators.yaml` -- bind `verify_shape` → `suite: g0/fault-injection/`, `validator_sha: null`, `last_run: null`; comment: sensitivity scored in Story 1.6. -- validator↔suite binding (AC2).
- [x] `benchmarks/_registry/provenance/*.yaml` -- one manifest per golden model + per fault fixture: `kind`, `source.kind: hand-authored`, `real_world_basis` (e.g. "canonical primitive / mechanical part pattern"), `license_checked`. -- AD-16 provenance.
- [x] `benchmarks/__init__.py` + `benchmarks/harness/__init__.py` -- make `benchmarks` + `benchmarks.harness` importable packages (empty). -- import surface for tests.
- [x] `benchmarks/harness/report_build.py` -- single builder: `(criterion, outcome) -> ValidationReport` with a `ReportBanner` (freecad_version="stub", `element_map_version=None` — the schema requires `integer | null`, so `None`, NOT the string `"n/a"`) and one `Check` per criterion; call contracts `derive_verdict`. **The stub outcome's `detail.code` is `invalid_input.not_implemented`** (maps via `derive_verdict` to `INVALID_INPUT` — the honest "this criterion cannot be evaluated: no bridge/tool exists yet" class), NOT `recompute.unimplemented` (which would falsely assert a recompute error occurred for non-recompute criteria like G0.1/G0.2/G0.4). -- one report shaper; honest verdict class.
- [x] `benchmarks/runner.py` -- argparse (`--gate`, `--stub`, `--criterion`); **drop `--case`** (it was accepted but silently ignored — either omit it or, if kept for forward-compat, reject it in stub mode with a clean message + exit 2). `StubBridge` returns a structured "not implemented" outcome for every call; load `gate.yaml`, iterate criteria, build a FAIL `ValidationReport` each, aggregate, print summary, exit 1 when any criterion fails / 0 only if all pass / 2 on usage errors. **Honest-fail guards (all → exit 2 with a one-line message, NEVER exit 0, NEVER a traceback):** unknown/lowercase gate id; `gate.yaml` missing/unparseable (`yaml.YAMLError` caught) / not a mapping / with an empty-or-missing `criteria` list (zero criteria must NOT report green — that would defeat AD-19); a criterion entry missing `id` (guard with `.get`, treat as a usage error). `--criterion` that matches nothing → exit 2. `main()` guarded by `if __name__ == "__main__"` for file-path invocation. FreeCAD-free. -- honest-failing stub runner, non-defeasible (AC3).
- [x] `scripts/check_provenance.py` -- **recursively walk `benchmarks/**`** (not two hardcoded dirs) for artifact files (`*.FCStd`), excluding `heldout/`, `_registry/provenance/` itself, and `__pycache__`; every artifact must have a provenance manifest whose `source.kind` ∈ the closed set; **flag a fault case dir that has `case.yaml` but no `fixture.FCStd`**; **flag duplicate `artifact` ids across manifests** (a duplicate must not silently overwrite). Print `path -- rule` + exit 1 on any violation, else exit 0. -- CI provenance gate, full-tree coverage.
- [x] `tests/external/test_harness_g0.py` -- pytest, NON-tautological (validate real report objects + real exit codes): (a) stub run returns a report per G0 criterion, each schema-valid against `validation-report.schema.json` AND `verdict != OK` AND process exit==1; **assert the actual reachable verdict class is `INVALID_INPUT` for every criterion (not a permissive 3-value set that hides that other branches are dead)**; (b) fault inventory ≥10 `planted_defect` + ≥1 `clean_control`, **assert EVERY case's `fault.kind` ∈ the closed 2-set (a typo'd kind fails, not silently dropped)**, every case `targets_validator: verify_shape` and present in `validators.yaml` binding, **and every case's declared `fixture` file exists**; (c) `check_provenance.py` exits 0 on the real tree, 1 on a tmp copy with a manifest deleted, **and 1 on a tmp copy with a duplicate `artifact` id and on a case dir missing its `fixture.FCStd`**; (d) **runner honest-fail guards: unknown `--gate` → exit 2 no traceback; a tmp `gate.yaml` with empty `criteria` → exit 2 (NOT 0); a malformed/non-mapping tmp `gate.yaml` → exit 2 no traceback; `--criterion` matching nothing → exit 2**. -- AC1/AC2/AC3 coverage + honest-fail guard coverage.
- [x] `tests/infc/test_golden_models.py` -- stdlib unittest under FreeCADCmd, discovered by `tests/run_tests.py`. **Must validate the COMMITTED artifacts, not just the live generator:** (1) for each model, `App.openDocument` the committed `benchmarks/g0/golden-models/<id>.FCStd`, read its `Shape`, and assert measured `Volume`/`BoundBox`/`len(Solids)` == `expected.yaml` within `rel:0.001` (this catches a stale/corrupted committed file); (2) assert `isValid()` on the 4 solid models; (3) **set-equality both directions**: the set of model ids in `expected.yaml` == the set in the generator's `MODELS` == the set of committed `*.FCStd` basenames (a model in one but not another fails); (4) a regenerate-and-remeasure drift check: rebuild each via `build_model` and assert its measured values also match `expected.yaml` (guards generator drift). Open docs via `App.openDocument` and close them (test-local; the AD-20 `document_*` usecases do not exist yet, so a raw open in a TEST is acceptable — note this in a comment). -- independent-oracle self-check over the committed shapes.
- [x] `pyproject.toml` -- add `pyyaml` to `[project.optional-dependencies].dev`; add `benchmarks` to `[tool.ruff] src` so runner/harness are linted. Do NOT add a `gate` console-script (benchmarks is outside `src/`, not in the wheel; run by file path). -- YAML dep + lint coverage.
- [x] `.github/workflows/ci.yml` -- `arch-checks` (has pyyaml via `uv sync --all-extras`): add blocking `uv run python scripts/check_provenance.py`, and a step running `uv run python benchmarks/runner.py --gate G0 --stub` that asserts a NON-zero exit is the pass condition (e.g. shell `if uv run ... ; then echo "runner unexpectedly green"; exit 1; fi`). `headless`: add `pyyaml` to the `pip install` line (external suite imports the harness); the golden self-check runs via the existing `FreeCADCmd tests/run_tests.py` (FreeCAD bundles PyYAML 6.x). -- CI-enforced provenance + honest-fail + golden values.
- [x] `docs/decisions/007-benchmark-harness-reuse-survey.md` -- record the reuse survey required by G0.E: what was surveyed (pytest-as-harness, existing CAD eval sets), decision (thin stdlib runner over contracts), why nothing existing fit. -- G0.E reuse-survey artifact.

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- rings clean (runner/harness are external, import contracts only).
- [x] `uv run ruff check .` -- clean.
- [x] `uv run pytest tests/external -q` -- all green (harness + prior contract/scaffold suites).
- [x] `"FreeCADCmd" tests/run_tests.py` -- golden self-check green (local FreeCAD 1.1 present; CI runs both legs).

**Acceptance Criteria:**
- Given `benchmarks/g0/golden-models/`, when inspected, then it holds 5 `.FCStd` + `expected.yaml` with known volume/bbox/counts, each covered by a provenance manifest passing the AD-16 closed-source-kind check; and the infc self-check proves the committed models match the independently hand-computed expected values.
- Given `benchmarks/g0/fault-injection/`, when inspected, then it holds ≥10 planted-defect cases + clean control(s), each with `fault.kind` + `expectation`, and `_registry/validators.yaml` binds them to `verify_shape` (sensitivity run deferred to Story 1.6, recorded as pending).
- Given no bridge implementation, when `python benchmarks/runner.py --gate G0 --stub` runs, then every G0 criterion FAILS honestly with a schema-valid contracts `ValidationReport` (non-OK verdict via `derive_verdict`), the process exits non-zero, and it never crashes.

## Spec Change Log

### 2026-07-21 — bad_spec loopback (iteration 1)

- **Triggering findings (both adversarial reviewers, deduplicated):**
  1. `[high] bad_spec` — **Fault-case `assertions` encode contradictory / defect-side values, so several cases do not actually pin the defect they claim.** `negative-volume` asserts `expect_volume: 1000` while its own description says signed `-1000`; `zero-volume-lamina` pastes box-10-20-30's `expect_volume: 6000` + `solid_count: 1` onto a 0-volume, 0-solid lamina; `open-shell`/`non-manifold`/`self-intersecting`/`degenerate-face` assert `expect_solid_count: 1` on fixtures with 0 (or 2) solids. They "detect" only by an incidental count mismatch, and several collapse to the same `solid_count≠1` signal. In Story 1.6 (where `verify_shape` scores this suite) these misgrade. Root cause: the spec's fault task did not state the invariant that **each case's `assertions` must encode the value a CORRECT shape yields** (the reference expectation), so the DETECT fires from the true defect deviating from that reference — not from a hand-picked defective number. → bad_spec.
  2. `[high] bad_spec` — **Assertion `fn` names (`expect_volume`, `expect_bbox`, `expect_solid_count`, `expect_valid`, `expect_watertight`) are ad-hoc; the contracts assertion vocabulary is explicitly deferred to Phase 3 (`contracts/assertions.py`).** The spec pointed at "§2 vocabulary" without resolving that the vocabulary does not exist yet. The case files must declare these fn names as a **forward-declared Phase-0 reserved set documented in the story** (a small closed list the runner will bind in 1.6), not silently invent them, and the runner must NOT claim to resolve them yet. → bad_spec.
  3. `[medium] bad_spec` — **The infc self-check rebuilds shapes from the generator in-process and never opens the committed `.FCStd`, so the shipped fixtures are unvalidated** (a corrupted/stale committed model passes CI). Intent (AC1 "committed models match") requires the test to OPEN `benchmarks/g0/golden-models/*.FCStd` and re-measure those, plus a regenerate-and-remeasure drift check. Spec task wording ("run the generator in-process") caused the literal-but-wrong impl. → bad_spec.
  4. `[high] bad_spec` — **Runner honest-fail is defeasible: an empty/missing `criteria` list yields `reports=[]` → `any([])==False` → exit 0 (green).** Also a non-dict/malformed `gate.yaml` or a criterion missing `id` raises an uncaught traceback, contradicting the "never raises, unknown/bad gate → exit 2" contract. The spec must pin: zero-criteria / unparseable / non-mapping gate → exit 2 with a clean message (never 0, never traceback). → bad_spec.
  5. `[medium] bad_spec` — **All stub verdicts are `RECOMPUTE_ERROR`, mislabeling G0.1/G0.2/G0.4 (not recompute failures).** The stub "not implemented" should map to `INVALID_INPUT` (the honest "this criterion cannot be evaluated — no bridge/tool" class), which is also more truthful than asserting a recompute error occurred. Pin the code so the verdict class is honest. Update the test to assert the ACTUAL single reachable class, not a 3-value set that hides that two branches are dead.
  6. `[medium] patch-in-respec` — `check_provenance.py` walks two hardcoded dirs (future `benchmarks/**` artifacts escape), silently overwrites duplicate `artifact` ids, and skips a fault case that has `case.yaml` but no `fixture.FCStd`. Broaden to a recursive `benchmarks/**` walk (excluding `heldout/`, `_registry/provenance/`, `__pycache__`, and non-artifact `.py`/`.yaml`), flag duplicate ids, and flag a case dir missing its declared `fixture`.
  7. `[medium] patch-in-respec` — Generators save via `doc.saveAs` (not `exportBinary`); committed `golden_fingerprint.sha256` values are never re-derived by any test, so determinism is unproven and the fingerprints are dead metadata. Either (a) drop the sha256 fields (keep only the `serializer` tag as a forward marker) OR (b) add a test that recomputes the tagged fingerprint from the committed shape and compares. Choose (a) — a real fingerprint oracle is Story 1.6's `fingerprint()`; committing unverifiable hashes now is the ungrounded-number defect. Keep the `serializer: exportBinary` tag as documentation.
  8. `[low] patch-in-respec` — `--case` is accepted but silently ignored (reject the flag with exit 2 in stub mode, or drop it); infc test iterates only `expected.yaml` keys (add set-equality both directions vs the generator's `MODELS`); inventory test silently drops an unknown `fault.kind` (assert every case kind ∈ the closed 2-set); the `element_map_version` used `None` (schema-correct) where the spec text said `"n/a"` (schema-invalid) — fix the spec text to `null`/`None`.

- **Amended (outside `<intent-contract>` only) — Code Map, Tasks, Design Notes updated to pin all of the above.**

- **KEEP (must survive re-derivation):**
  - The 5 golden `.FCStd` generators + the independently hand-computed analytic expected values (6000 / 1570.7963 / 4188.7902 / 15214.6018 / 2000) — these are CORRECT (both reviewers confirmed the math) and independent of the tool. Do NOT recapture from FreeCAD.
  - The honest-fail architecture (StubBridge → single `report_build` → contracts `derive_verdict`, no invented status string, no sensitivity number, `validators.yaml.last_run: null`) — the AD-19 core works; only the verdict *class* and the empty-criteria guard change.
  - The `benchmarks/` external-process placement + PyYAML-only-external decision + the CI honest-fail step + provenance gate wiring + `benchmarks` importable package — all correct.
  - Fixtures genuinely carrying the defect via real `Part` geometry (open shell, lamina, reversed solid, overlapping compound) — the GEOMETRY is right; only the `assertions` blocks are re-authored to encode the reference (correct-shape) expectation.
  - The `.gitignore` `*.FCBak`/`*.FCStd.*` rule and junk cleanup.

## Review Triage Log

### 2026-07-21 — Review pass (iteration 2, post-loopback)
- intent_gap: 0
- bad_spec: 0
- patch: 3 (low 3)
- defer: 1
- reject: 4
- addressed_findings:
  - `[low]` `[patch]` `--stub` was parsed but never read (silent no-op). Made it required: a bare `runner.py --gate G0` now exits 2 with a clean message; added `test_missing_stub_flag_exits_2`.
  - `[low]` `[patch]` `test_decision_notes_exist` `>=6`/{001..006} did not pin decision 007 (this story's required reuse survey). Tightened to `>=7` + {001..007}.
  - `[low]` `[patch]` infc committed-file check could throw an opaque `IndexError` on a corrupt zero-object `.FCStd`. Added an explicit `len(doc.Objects) == 1` assertion naming the model.
  - `[low]` `[defer]` `check_provenance.py` does not flag an ORPHAN manifest (manifest whose artifact was renamed/deleted) — no orphan exists now; reverse-coverage deferred to first benchmark-set churn.
  - `[low]` `[reject]` non-manifold & open-shell both assert `expect_watertight: true`, and self-intersecting-compound detects via `expect_solid_count: 1` — the spec's fault task EXPLICITLY sanctioned these observable-signal choices (Phase-0 vocabulary has no manifold/interference primitive); documented, not a defect.
  - `[low]` `[reject]` generator abort-mid-loop with no case attribution — generators are manual dev tooling; a Python traceback already names the failing case; committed fixtures are the artifact.
  - `[low]` `[reject]` `expected_meta.serializer` bare vs design's `golden_fingerprint` wrapper — cosmetic; nothing reads it, no sha256 committed by design.
  - `[low]` `[reject]` set-equality "masks duplicate basename" — a filesystem cannot hold two files with the same name in one dir; concern is moot.

### 2026-07-21 — Review pass (iteration 1)
- intent_gap: 0
- bad_spec: 5 (high 3, medium 2)
- patch: 3 (medium 2, low 1) — folded into the bad_spec re-derivation, not applied standalone
- defer: 1
- reject: 1
- addressed_findings:
  - `[high]` `[bad_spec]` Fault-case assertions re-specified to encode reference (correct-shape) expectations so each defect is detected by deviation, not by an incidental/contradictory hand-picked value.
  - `[high]` `[bad_spec]` Assertion `fn` names pinned as a documented forward-declared Phase-0 reserved set; runner does not claim to resolve them.
  - `[high]` `[bad_spec]` Runner honest-fail hardened: zero-criteria / non-mapping / malformed gate → exit 2 clean, never green, never traceback; missing-`id` guarded.
  - `[medium]` `[bad_spec]` infc self-check re-specified to OPEN the committed `.FCStd` (+ regenerate drift check), so shipped fixtures are validated.
  - `[medium]` `[bad_spec]` Stub verdict class corrected to `INVALID_INPUT` (honest "cannot evaluate"); test asserts the real reachable class.
  - `[medium]` `[patch]` check_provenance broadened to recursive walk + duplicate-id + missing-fixture detection.
  - `[medium]` `[patch]` Committed fingerprint sha256 dropped (unverifiable now); serializer tag kept as marker.
  - `[low]` `[patch]` `--case` rejected in stub mode; infc set-equality both directions; inventory asserts closed `fault.kind` set; spec `element_map_version` text fixed to `null`.
  - `[low]` `[defer]` AD-16 checker lacks url/license/attribution enforcement for non-`hand-authored` source kinds (no such artifact ships in this story) → deferred to the first shipped non-hand-authored artifact.
  - `[low]` `[reject]` `real_world_basis` "tautological" critique — the strings do name a real-world CAD basis for hand-authored primitives; AD-16 requires a basis, not an external URL, for `hand-authored`.

## Design Notes

- **Independent golden values, verified analytically.** All five expected values were hand-derived and cross-checked once against FreeCAD 1.1 during planning (box 10·20·30=6000; cyl π·5²·20=1570.7963; sphere ⁴⁄₃π·10³=4188.7902; box40²·10−π·5²·10=15214.6018; two disjoint 10³ boxes compound=2000, solids=2, bbox 30·10·10). The values live in `expected.yaml` as the authority; the infc self-check re-derives them from the shapes, so a generator drift is caught, but the SCORING reference is the hand-computed number, not the tool.
- **Why the runner is honest-failing, not stubbed-green.** AD-19 demands the gate artifacts fail against a stub before tool code exists. The `StubBridge` returns a structured "not implemented" for every verify/query/export call; `report_build` turns that into a `Check{passed: false, detail.code: "invalid_input.not_implemented"}`, and `derive_verdict` maps it to `INVALID_INPUT`. `INVALID_INPUT` (not `RECOMPUTE_ERROR`) is the honest class: no recompute was attempted — the criterion simply cannot be evaluated because no bridge/tool exists. A green stub, OR a zero-criteria gate silently reporting green, both defeat the gate's purpose, so the runner treats an empty/missing/malformed `criteria` list as a usage error (exit 2), never exit 0.
- **Sensitivity is deferred, not faked.** `verify_shape` lands in Story 1.6; only then can the fault suite produce a real sensitivity/FA number (global-protocol 3b). This story lands + binds the suite; `validators.yaml.last_run = null` is the honest state. Claiming ≥95 % now would be an ungrounded number (the same class of defect the gate exists to prevent).
- **No committed fingerprint hashes.** A whole-shape hash is banned as a scoring oracle, and the generators save via `saveAs` (a zip with embedded version/GUID/timestamps — not byte-reproducible), so a committed `sha256` would be unverifiable dead metadata. `expected.yaml` keeps only a documentary `serializer: exportBinary` marker; the real, verifiable `fingerprint()` oracle is Story 1.6. The scored fields are volume/bbox/solid-count.
- **Assertion vocabulary is a forward-declared reserved set, not the contracts vocabulary (which is deferred).** `contracts/assertions.py` defers the full assertion vocabulary to Phase 3. This story therefore fixes a small CLOSED Phase-0 reserved set of `fn` names — `expect_volume`, `expect_bbox`, `expect_solid_count`, `expect_valid`, `expect_watertight` — used by the golden `expected.yaml` and the fault `case.yaml` assertions, and documents it here + in `gate.yaml`/a suite README so it is not silently invented. The Story-0 runner does NOT resolve or execute these (no `verify_shape` yet); they are the contract the Story-1.6 validator will bind. Story 1.6, when it lands the real vocabulary, either adopts these names or migrates the case files in the same change (recorded in its spec).
- **Fault assertions encode the reference, not the defect.** Each planted-defect `case.yaml` states, in its `assertions`, the value a CORRECT shape yields for the targeted property (e.g. the open-shell case asserts `expect_watertight: true` — the correct reference IS watertight; the fixture is not). Detection is the defective fixture DEVIATING from that reference. This is why the same `fn` set works for every case and why an assertion must never be hand-set to the defective value (that would make the case pass on the defect). Fixtures are built from real `Part` geometry (open shell, planar lamina, reversed/inverted solid, overlapping compound) so the geometry genuinely carries the defect — the assertion just names the reference the defect breaks.
- **PyYAML placement.** All harness data is YAML per the design (`gate.yaml`, `case.yaml`, `validators.yaml`, `expected.yaml`). PyYAML is added to the external (uv) process only — `contracts/` and any in-FreeCAD code stay stdlib-only (AD-12). `check_imports.py` stays green because the harness lives under `benchmarks/`, outside the enforced rings. FreeCAD's bundled interpreter already ships PyYAML 6.x, so the infc golden self-check reads `expected.yaml` with no extra install; the headless leg's `pip install` gains `pyyaml` because `pytest tests/external` imports the harness.

## Verification

**Commands:**
- `uv run python benchmarks/runner.py --gate G0 --stub` -- expected: prints per-criterion FAIL summary, exits 1 (honest fail; CI asserts non-zero).
- `uv run python scripts/check_provenance.py` -- expected: exit 0 on the real tree.
- `uv run python scripts/check_imports.py` -- expected: exit 0 (rings clean).
- `uv run pytest tests/external -q` -- expected: all pass (harness g0 + prior suites).
- `uv run ruff check .` -- expected: clean.
- `"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" tests/run_tests.py` -- expected: golden self-check green (5 models match expected within rel 0.001).

**Manual checks:**
- `benchmarks/g0/golden-models/` has exactly 5 `.FCStd` + `expected.yaml`; each model has a `_registry/provenance/*.yaml`.
- `benchmarks/g0/fault-injection/` has ≥10 `planted_defect` case dirs + ≥1 `clean_control`; each `case.yaml` names `verify_shape` and appears in `validators.yaml`.
- `benchmarks/*/heldout/` untouched (still the two-file sealed placeholder).

## Auto Run Result

Status: **done** (converged after 1 bad_spec loopback + a clean 2nd review pass with 3 low patches)

### Summary

Landed the G0 entry gate (AD-19): 5 hand-made golden `.FCStd` reference models with independently hand-computed `expected.yaml` (volume/bbox/solid-count), an 11-planted-defect + 1-clean-control fault suite bound to `verify_shape` in `validators.yaml` (sensitivity scoring honestly deferred to Story 1.6), AD-16 provenance manifests for all 17 artifacts, and a FreeCAD-free `benchmarks/runner.py --gate G0 --stub` that emits one schema-valid contracts `ValidationReport` per G0 criterion — every verdict `INVALID_INPUT` (honest "cannot evaluate: no bridge yet"), process exit 1, never green, never a traceback. All three ACs satisfied and independently falsified by the orchestrator (not merely reported by the implementer).

### Files changed

- `benchmarks/g0/golden-models/{build_golden_models.py, *.FCStd (5), expected.yaml}` — deterministic FreeCADCmd generator + 5 committed reference models + hand-computed analytic expected values (no committed sha256).
- `benchmarks/g0/fault-injection/{build_fault_fixtures.py, README.md, <case>/case.yaml + fixture.FCStd (12)}` — fault generator + suite; assertions encode the REFERENCE (correct-shape) value so the defect is detected by deviation; fn names are a documented forward-declared Phase-0 reserved set.
- `benchmarks/g0/gate.yaml` — declarative G0.1–G0.5 mirror (runner-consumed, not hardcoded).
- `benchmarks/_registry/{validators.yaml, provenance/*.yaml (17)}` — validator↔suite binding (`last_run: null`) + one provenance manifest per artifact (`source.kind: hand-authored`).
- `benchmarks/{__init__.py, runner.py, harness/__init__.py, harness/report_build.py}` — importable harness package; single `ValidationReport` builder using contracts `derive_verdict`; runner with non-defeasible honest-fail guards (unknown/lowercase gate, malformed/non-mapping/empty-criteria gate, criterion-missing-`id`, empty `--criterion`, missing `--stub` → exit 2).
- `scripts/check_provenance.py` — recursive `benchmarks/**` provenance gate (dup-id + missing-fixture detection).
- `tests/external/test_harness_g0.py` — AC1/AC2/AC3 + honest-fail guard coverage (non-tautological: real reports, real exit codes, real schema validation).
- `tests/infc/test_golden_models.py` — opens the COMMITTED `.FCStd` + regenerate-drift + set-equality (expected.yaml == generator MODELS == committed basenames).
- `docs/decisions/007-benchmark-harness-reuse-survey.md` — G0.E reuse survey.
- `pyproject.toml` (+pyyaml dev, benchmarks in ruff src + T201 exempt), `.github/workflows/ci.yml` (provenance + honest-fail steps; headless +pyyaml/jsonschema), `.gitignore` (`*.FCBak`/`*.FCStd.*`), `tests/external/test_scaffold.py` (decision count 6→7, pins 007).

### Review findings breakdown

- **Iteration 1 (bad_spec, 5 findings — 3 high, 2 medium):** fault-case assertions encoded contradictory/defect-side values (negative-volume asserted +1000 for signed −1000; zero-volume-lamina pasted box-10-20-30's 6000; open-shell/non-manifold/self-intersecting/degenerate all detected via incidental `solid_count`); assertion `fn` vocabulary invented while contracts defers it to Phase 3; infc self-check rebuilt from the generator and never opened the committed `.FCStd`; runner honest-fail was defeasible (empty criteria → exit 0) and could traceback; all stub verdicts mislabeled `RECOMPUTE_ERROR`. → spec amended (assertions reference-anchored, fn set forward-declared+documented, infc opens committed files, runner guards pinned, verdict class → `INVALID_INPUT`, sha256 dropped, provenance recursive), code fully re-derived. `negative-volume` replaced with an unambiguous `invalid-self-intersecting-solid` (isValid False); `non-manifold` fixture verified genuinely non-manifold (edge adjacency 3).
- **Iteration 2 (converged — 3 low patches, 1 defer, 4 reject, NO loopback):** `--stub` made required (was a silent no-op); `test_decision_notes_exist` tightened to pin 007; infc committed-file check guards a zero-object corrupt file. Deferred: `check_provenance` orphan-manifest reverse-coverage. Rejected: spec-sanctioned observable-signal fault assertions, generator abort attribution, cosmetic `expected_meta` shape, moot duplicate-basename concern.

### Verification performed (independently re-run by the orchestrator, not trusting subagent reports)

- `uv run python benchmarks/runner.py --gate G0 --stub` → exit 1; 5 reports, each schema-valid against `validation-report.schema.json`, each `verdict == INVALID_INPUT` (via the real contracts `derive_verdict`).
- Honest-fail guards falsified live: unknown/lowercase `--gate` → exit 2; empty-`criteria` gate → exit 2 (NOT 0); malformed gate.yaml → exit 2 (caught `ScannerError`, no traceback); bare invocation without `--stub` → exit 2.
- `uv run python scripts/check_provenance.py` → exit 0 (17 manifests, all `hand-authored`).
- `uv run python scripts/check_imports.py` → exit 0 (rings stdlib-only; harness outside rings).
- `uv run ruff check .` → clean.
- `uv run pytest tests/external -q` → 92 passed.
- `FreeCADCmd tests/run_tests.py` → exit 0; proven non-empty: 3 infc tests DISCOVERED + RAN + passed, opening the committed `.FCStd` and matching the hand-computed values within rel 0.001.
- Inventory: 5 golden `.FCStd`, 11 planted + 1 clean-control fault cases, 17 provenance manifests; `benchmarks/heldout/` untouched; no `.FCBak`/temp junk committed.

### Residual risks

- Two blocking CI legs (FreeCAD 1.0.x/1.1.x) were not exercised locally — only local FreeCAD 1.1 is installed. The golden self-check + external suite pass locally; the 1.0.x leg and the headless-`pyyaml` install run first in CI.
- The fault suite's sensitivity/false-alarm is intentionally UNscored here (`validators.yaml.last_run: null`); Story 1.6 (`verify_shape`) is responsible for scoring it and, when it lands the real Phase-3 assertion vocabulary, for adopting or migrating this suite's forward-declared `fn` names.
- `non-manifold`/`open-shell` share a watertightness signal and `self-intersecting-compound` detects via solid-count (spec-sanctioned, Phase-0 has no manifold/interference primitive) — Story 1.6 must ensure `verify_shape` sees the specific defect, not just the proxy.
