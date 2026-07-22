---
title: 'Gate G0 Exit — Mechanical Verdict from Stored Reports + Human Token'
type: 'feature'
created: '2026-07-22'
status: 'done'
baseline_revision: '8c35270a6c791fc1fb3d863046e7cdb47a81788e'
final_revision: 'c5274b4a07a6f5e40e263dbac04dd3f0d80a6e27'
review_loop_iteration: 2
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/validation-harness-design.md'
  - '{project-root}/_bmad-output/specs/spec-freecad-buddy/phase-gates.md'
warnings: []
---

<intent-contract>

## Intent

**Problem:** The G0 gate has a declarative `gate.yaml` and a `--stub` runner that only honest-fails, but no machine that computes the actual G0 PASS/FAIL verdict. Story 1.10 (FR17, AD-19) must make Phase 0 exit *exactly the way every later phase will*: the verdict is a pure function over stored `ValidationReport`s + a run-bound human `gui_smoke` token + validator-registry currency — no self-grading, reproducible from files alone by an auditing agent.

**Approach:** Add a run-scoped evidence store (`gate-artifacts/g0/<run-id>/`) and two file-driven commands to `benchmarks/runner.py`: `run` collects one stored `ValidationReport` per criterion (G0.2 from headless tool introspection; G0.3/G0.5 from the in-FreeCAD golden + STEP-round-trip suites; G0.1/G0.4 ingested from stored transport/CI evidence artifacts), plus `attest` to record a run-bound `gui_smoke` token; `verdict` reads *only* stored files and computes the four-leg global protocol (a: every criterion passes its report-field rule; b: every cited validator's fault run current at ≥95%/≤5%; c: exit-run legs — N/A for G0's non-actor gate; d: required human token present + run-bound). `verdict` is pure and re-runnable, matching validation-harness-design §3.2.

## Boundaries & Constraints

**Always:**
- `gate verdict G0 --run <id>` is a **pure function over stored files** (`gate-artifacts/g0/<run-id>/reports/*.json` + `human/*.json` + `_registry/validators.yaml`): no bridge spin-up, no FreeCAD import, no network — re-running it on the same files reproduces the identical verdict (AC3).
- The verdict is computed on **report fields**, never on exit-code-0 or log-absence (design §3.2 leg-6a). A criterion PASSES iff its stored `ValidationReport.verdict == "OK"`.
- All wire objects reuse the existing contracts: per-criterion evidence is a `ValidationReport` (`fcb.validation-report/1`, `contracts/report.py`) whose verdict is **derived** via `derive_verdict`, never hand-asserted. The `gui_smoke` token is a stdlib-only JSON artifact per validation-harness-design §7.
- Token run-binding is proven, not trusted: `binds_reports_sha256` is a SHA-256 over the canonical (sorted-by-criterion, `json.dumps(..., sort_keys=True)`) concatenation of the run's stored report set; `verdict` recomputes it and compares with `hmac.compare_digest`. A token whose hash does not match the stored reports fails leg-d (INVALID token, not a pass).
- Validator currency (leg-b): for every `cited_validators` entry across all criteria, `validators.yaml[name].validator_sha` must match a freshly computed hash of that validator's source AND `last_run.sensitivity >= 0.95` AND `last_run.false_alarm <= 0.05`; otherwise the gate fails with the stale/failing validator named.
- `run` writes each report atomically and deterministically ordered; re-running `run` for the same `--run <id>` overwrites that run's reports (idempotent), never appends duplicates.
- Every command exits: `0` = gate/verdict PASS, `1` = gate/verdict FAIL (honest), `2` = usage/loader error (unknown gate, missing run dir, malformed artifact) — never a traceback. Preserve the existing `--stub` path and its exit semantics unchanged.
- FreeCAD-free by construction: `runner.py` and `harness/` stay contracts-only (AD-12). The in-FreeCAD evidence (G0.3 golden, G0.5 STEP) is produced by an in-FreeCADCmd collector script under `tests/infc/`-style invocation that writes report JSONs; the runner only *reads* those JSONs. `run` with a criterion needing in-FreeCAD evidence that is absent records that criterion's report as a failing `INVALID_INPUT` ("evidence not collected"), never fabricates a pass.

**Block If:**
- The phase-gates G0 table or validation-harness §3.2 verdict protocol contradicts this spec's four-leg computation (e.g. a leg the spec omits is actually required for G0) — HALT `blocked`, cite the doc, do not silently diverge.
- Computing `gui_smoke` run-binding would require a token schema/field not already defined by validation-harness §7 and not derivable — HALT `blocked` rather than invent a token contract shape.

**Never:**
- Never spin a live bridge, import FreeCAD, or hit the network from `verdict` (breaks purity/AC3).
- Never let the runner self-grade: it maps deterministic tool output → checks → `derive_verdict`; it never asserts a verdict directly (AD-13).
- Never mark G0.1/G0.4 green from the runner's own execution — those legs are external (live GUI transport / CI matrix). The runner consumes their **stored** evidence artifacts; absent/failing evidence ⇒ that criterion fails.
- No held-out unsealing, `--exit` heldout ceremony, ablation, McNemar, or grader wiring — those are G1+ (validation-harness §5/§8, story out of scope). G0 has no actor loop, so leg-c (held-out gap) is inert for this gate.
- No new terminal-status values, no new report schema version, no changes to `derive_verdict`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full PASS | All 5 criterion reports `verdict==OK`; all cited validators current ≥95/≤5; `gui_smoke` token present, `binds_reports_sha256` matches | `verdict` prints per-criterion PASS + `gate G0: PASS`, exit 0 | none |
| One criterion report FAIL | e.g. G0.3 golden report `verdict==SPEC_FAILED` | leg-a fails naming G0.3; `gate G0: FAIL`, exit 1 | none (honest fail) |
| Stale validator | `verify_shape` source edited so `validator_sha` mismatches | leg-b fails naming `verify_shape` (stale); exit 1 | none |
| Failing validator run | `validators.yaml` `verify_shape.last_run.sensitivity` 0.90 | leg-b fails naming `verify_shape` (below 0.95 bar); exit 1 | none |
| Missing token | no `human/gui_smoke*.json` in the run dir | leg-d fails ("gui_smoke token absent"); exit 1 | none |
| Recycled/tampered token | token present but `binds_reports_sha256` ≠ recomputed hash | leg-d fails ("token not bound to this run"); exit 1 | none |
| Token outcome FAIL | token present, bound, `outcome:"FAIL"` | leg-d fails ("gui_smoke outcome FAIL — run invalidated"); exit 1 | none |
| Missing run dir | `verdict G0 --run nope` | `error: run 'nope' not found ...` stderr, exit 2 | UsageError |
| Malformed report json | a `reports/*.json` unparseable / not a ValidationReport | `error: malformed report ...` stderr, exit 2 | UsageError |
| Evidence not collected | `run` for a criterion whose in-FreeCAD/CI evidence file is absent | that criterion's stored report = failing `INVALID_INPUT` ("evidence not collected"); `run` exit 1 | none (fabricating a pass is forbidden) |
| Verdict purity | `verdict` re-run on identical files | byte-identical verdict + summary; no FreeCAD/network access | n/a |
| Stub back-compat | `runner.py --gate G0 --stub` | unchanged: 5 INVALID_INPUT reports, exit 1 | unchanged |

</intent-contract>

## Code Map

- `benchmarks/runner.py` -- **extend** (keep `--stub` path byte-behavior-identical): add `run` / `verdict` / `attest` subcommands driven by `--run <id>`. `run` iterates gate criteria, calls a per-criterion evidence collector, writes `gate-artifacts/g0/<run-id>/reports/<criterion>.json` **with the verdict re-derived from checks (never the ingested value)**; its own PASS/FAIL exit uses that re-derived verdict, so a self-graded evidence file cannot make `run` exit 0. `verdict` reads that dir + `human/` + `validators.yaml` and computes legs a–d. `attest` writes a run-bound `gui_smoke` token. `_validator_src_hasher` hashes each cited validator's source the SAME way the fault scorers did (see `score_verify_shape.py`) so a clean tree is current, not stale. `_load_gate_def` **loads `gate.yaml` exactly once (no raw re-read) and validates gate-level fields**: `required_tokens`, if present, MUST be a list (a scalar ⇒ `UsageError` exit-2, never char-by-char iteration); any YAML error ⇒ `UsageError`, never an escaping traceback. `_ingest_g0_4` **pins the required leg roster `{"1.0.x","1.1.x"}`**: it emits one check per required leg and a failing `INVALID_INPUT` check for any leg whose `G0.4.<leg>.json` is absent — a single present green leg can NEVER green G0.4 (both blocking legs must be proven). New `UsageError` paths for missing run dir / malformed artifact. Argparse gains a subparser while `--gate/--stub/--criterion` legacy invocation still works (route to the stub path when no subcommand given, preserving `test_stub_run_*`).
- `benchmarks/harness/verdict.py` -- **new** (FreeCAD-free, contracts-only): `compute_verdict(run_dir, gate_def, validators, validator_src_hasher) -> VerdictResult` implementing the four legs as a pure function; `bind_hash(reports) -> str` (canonical SHA-256 over sorted reports); `check_validator_currency(gate_def, validators, hasher) -> list[str]` (stale/failing names); `check_token(run_dir, reports, required_tokens) -> list[str]` (leg-d, `hmac.compare_digest`). Returns a structured result the runner prints and exits on. **No stored verdict is ever trusted — leg-a resolves each expected criterion to its `reports/<id>.json` (matched by filename id), verifies the report's `subject.criterion == id` (a mismatch or missing report is a leg-a FAIL, NEVER a silent `{}`→OK fallback), and RE-DERIVES the verdict from checks via `derive_verdict(report)`, passing iff that recomputation is `OK`.** **A stored report with an empty or non-list `checks` is a leg-a FAIL (`INVALID_INPUT`), never a vacuous `derive_verdict`→OK** — enforced in `load_reports`/leg-a WITHOUT changing `derive_verdict` (that contract is untouched: a report with no failing checks but zero checks is rejected before/at leg-a, not by re-defining OK). **`load_reports` reads only the expected criterion report files (`reports/<id>.json` for each gate criterion id), not a glob of every `*.json`** — an orphan/stray file neither rides the bind set nor forces a spurious exit-2. `bind_hash` is over that same expected-id set. **`check_token` accepts a required token type iff ANY `human/*.json` of that type is bound (`binds_reports_sha256` matches via `hmac.compare_digest`) AND `outcome=="PASS"`** — it never lets an earlier-by-filename stale/FAIL token shadow a valid bound-PASS one (no `matching[0]` single-pick).
- `benchmarks/harness/evidence.py` -- **new** (FreeCAD-free): per-criterion evidence collectors that build a `ValidationReport` via `harness.report_build`. `collect_g0_2(tool_specs) -> ValidationReport` introspects `hosts.tool_catalog.tool_specs()`: **the ≥15 count is of tools whose `.name` is IN the `query_`/`document_`/`export_` namespaces (out-of-namespace tools like `verify_`/`sketch_` do NOT count toward the ≥15 bar)**; every counted spec has an `input_schema` object + non-empty description; a non-string `.name` is treated as malformed, never crashes — headless, no FreeCAD. `ingest_report(criterion, path) -> ValidationReport` shape-validates a report JSON dropped by an in-FreeCAD/CI collector (G0.1/G0.3/G0.4/G0.5), **requires a non-empty `checks` list, and RE-DERIVES the returned report's `verdict` from those checks via `report_build.evidence_report(...)` (drops any stored `verdict` field)** so an ingested file can never self-grade. Missing/malformed/empty-checks evidence ⇒ a failing `INVALID_INPUT` report (never a fabricated pass).
- `benchmarks/harness/report_build.py` -- **extend**: add `evidence_report(criterion, checks, banner)` that assembles a `ValidationReport` from real measured checks with the verdict **derived from `checks`** (reusing the existing derive-verdict flow — any incoming `verdict` is ignored), and a `not_collected_report(criterion, reason)` helper for the absent-evidence case. Leave `stub_outcome`/`build_report` untouched (stub path unchanged).
- `benchmarks/g0/gate.yaml` -- **edit**: add `required_tokens: [gui_smoke]` at gate level (this is the ONLY leg-d source — leg-d requires exactly the gate's `required_tokens`) plus a `verdict` block noting leg-c (held-out) is inert for G0. **Do NOT add a per-criterion `gui_smoke: true` marker** (it would be dead config no code reads — the `gui_smoke` token is a gate-level leg-d requirement, and G0.1's leg-a is satisfied by its own transport-probe evidence report, not by the token). Keep the existing criteria/pass_rule/cited_validators verbatim.
- `benchmarks/g0/collect_evidence_infc.py` -- **new** in-FreeCADCmd collector: runs the golden suite (G0.3, reuse `golden-models/expected.yaml` + `verify.verify_shape`) and the create→export-STEP→re-import→compare round-trip (G0.5), writing `evidence/G0.3.json` / `evidence/G0.5.json` into a passed `--run <id>` dir (the runner's `run` ingests + re-derives them into `reports/`). Stdlib + FreeCAD only; contracts imported for report shape. This is the only FreeCAD-touching new file.
- `benchmarks/g0/emit_ci_evidence.py` -- **new** (FreeCAD-free helper the CI G0.4 step calls): emits a per-leg G0.4 evidence report **named `G0.4.<leg>.json` (one file per matrix leg, `leg` ∈ the pinned roster `{"1.0.x","1.1.x"}`, never a single shared `G0.4.json`)** carrying that leg's green boolean + test count. The runner's G0.4 ingest (`_ingest_g0_4`) requires BOTH roster legs present and green ∧ ≥30 tests each; a missing OR red leg ⇒ the combined `reports/G0.4.json` is non-OK — a single present green leg is never enough. Writes into the run's `evidence/` dir so `run` consumes it.
- `tests/external/test_gate_verdict.py` -- **new** pytest (no FreeCAD): the whole verdict matrix over a fabricated `gate-artifacts/g0/<run-id>/` tmp fixture — full PASS, each single-leg FAIL (bad report, stale validator, failing validator, missing token, recycled token, FAIL-outcome token), missing-run-dir/malformed-artifact exit-2, and the **purity assertion** (two `compute_verdict` calls on identical files → equal result; assert no FreeCAD import is required by importing `harness.verdict` with `FreeCAD` absent). G0.2 introspection collector proven against the real `tool_specs()` (count ≥15, schema+doc present).
- `tests/external/test_harness_g0.py` -- **extend** (do not replace existing tests): assert the stub path is unchanged and add a smoke test that `runner.main(["run","G0","--run","t"])` writes the expected report files and that `verdict` reads them.
- `tests/infc/test_g0_evidence.py` -- **new** in-FreeCADCmd `unittest`: `collect_evidence_infc.py` on a live bridge writes G0.3 (golden all ±0.1%) and G0.5 (STEP round-trip volume ±0.1% + isValid + equal topology counts) reports whose derived verdict is `OK`. Skip-guard if FreeCAD golden fixtures absent.
- `.github/workflows/ci.yml` -- **edit**: each headless matrix leg calls `emit_ci_evidence.py` to write `G0.4.<leg>.json` and uploads it as a per-leg artifact. A final **aggregation job** (needs: both headless legs) downloads both leg artifacts into ONE run's `evidence/` dir, then (best-effort, non-blocking) runs `python benchmarks/runner.py run G0 --run ci-<sha>` followed by `verdict G0 --run ci-<sha>` so the G0.4 evidence it just emitted is actually consumed by the verdict (the evidence and the run dir must be the same `--run <sha>` — never a disconnected `g0-ci/` path). Keep existing legs green/blocking as-is; the verdict step stays non-blocking.

## Tasks & Acceptance

**Execution:**
- [ ] **Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `_bmad-output/project-context.md` (authoritative ring/import/wire/verification/security rules — this is a Python project; the TS clean-code/testing skills do NOT apply here).
  - Read `validation-harness-design.md §3` (gate runner CLI + §3.2 execution/verdict flow) and `§7` (human-token mechanism) — mandatory context; the four-leg verdict protocol is binding.
  - Read `phase-gates.md` G0 table + "Global protocol" — the criterion pass-rules and the leg definitions are the contract.
  - Read `contracts/report.py` (`ValidationReport`, `derive_verdict`) and `contracts/status.py` (closed terminal-status set) — reuse, never extend.
- [x] `benchmarks/harness/report_build.py` -- add `evidence_report(criterion, checks, banner)` (assemble a `ValidationReport` from real checks, **verdict derived from `checks` — any incoming `verdict` ignored**) and `not_collected_report(criterion, reason)` (failing `INVALID_INPUT`). Leave `stub_outcome`/`build_report` untouched. -- real-evidence report assembly without touching the stub path.
- [x] `benchmarks/harness/evidence.py` -- **new**: `collect_g0_2(tool_specs)` (headless introspection → report: **the ≥15 count is of tools whose `.name` is IN the `query_`/`document_`/`export_` namespaces — out-of-namespace tools do NOT count toward ≥15**; each counted spec has `input_schema` object + non-empty description; **a non-string `.name` counts as malformed, never raises**); `ingest_report(criterion, path)` (parse + shape-validate a dropped report JSON — **require a non-empty `checks` list and RE-DERIVE the verdict from those checks via `evidence_report`, dropping any stored `verdict`** — else `not_collected_report`). FreeCAD-free. -- criterion evidence collection that cannot be self-graded.
- [x] `benchmarks/harness/verdict.py` -- **new**: `bind_hash(reports)` (canonical sorted SHA-256), `load_reports(run_dir, expected_ids)` (**read only `reports/<id>.json` for the gate's criterion ids — never glob all `*.json`; a report with an empty/non-list `checks` is a malformed/`INVALID_INPUT` leg-a FAIL, never vacuous-OK**), `check_validator_currency(gate_def, validators, hasher)` (**reject a boolean `sensitivity`/`false_alarm`: `type(x) is not int and type(x) is not float` fails**), `check_token(run_dir, reports, required_tokens)` (**accept a token type iff ANY `human/*.json` of that type is bound via `hmac.compare_digest` AND `outcome==PASS` — never let an earlier-by-filename stale/FAIL token shadow a valid one; no `matching[0]` single-pick**), `compute_verdict(run_dir, gate_def, validators, hasher)` composing legs a/b/d (c inert for G0) into a `VerdictResult{passed, per_criterion, failures}`. **Leg-a resolves each expected criterion to its `reports/<id>.json`, verifies `subject.criterion == id` (mismatch/missing ⇒ leg-a FAIL, NEVER a `{}`→OK fallback), and RE-DERIVES the verdict via `derive_verdict(report)` — it never reads the stored `verdict` field.** Pure — no FreeCAD/network/bridge. -- the four-leg pure verdict function (AC1, AC3).
- [x] `benchmarks/runner.py` -- add argparse subcommands `run` / `verdict` / `attest` (all take `--run <id>`), routing the bare `--gate/--stub` legacy invocation to the existing stub path unchanged. `_load_gate_def` **loads `gate.yaml` once (no raw re-read) and validates `required_tokens` is a list (scalar ⇒ `UsageError`); any YAML error ⇒ `UsageError`, never a traceback**. `run` collects+writes `reports/<criterion>.json` (G0.2 via `collect_g0_2`; G0.1/G0.3/G0.5 via `ingest_report` of the run's `evidence/<criterion>.json`; **G0.4 via `_ingest_g0_4` which requires BOTH roster legs `{"1.0.x","1.1.x"}` present+green — a missing OR red leg ⇒ non-OK**; `not_collected_report` when absent), **its own PASS/FAIL exit uses the re-derived verdict**, exit 0/1 on gate PASS/FAIL. `verdict` calls `compute_verdict`, prints per-leg result, exit 0/1. `attest --type gui_smoke` computes `binds_reports_sha256` over the run's reports and writes `human/gui_smoke_<date>.json` (§7 shape). New `UsageError` for missing run dir / malformed artifact (exit 2, no traceback). -- CLI surface + evidence store + token ceremony (AC1, AC2, AC3).
- [x] `benchmarks/g0/gate.yaml` -- add `required_tokens: [gui_smoke]` and a short `verdict:` note that leg-c (held-out) is inert for G0. **No per-criterion `gui_smoke: true` marker** (no code reads it — leg-d is driven solely by gate-level `required_tokens`). Criteria/pass_rule/cited_validators unchanged. -- declarative token requirement.
- [x] `benchmarks/g0/collect_evidence_infc.py` -- **new** in-FreeCADCmd collector: golden suite → `evidence/G0.3.json` (all 5 models ±0.1%), create→export STEP→re-import→compare → `evidence/G0.5.json` (volume ±0.1% ∧ isValid ∧ equal topology counts), each via `evidence_report` with derived verdict. Stdlib + FreeCAD + contracts only. -- the in-FreeCAD evidence producer (AC1).
- [x] `benchmarks/g0/emit_ci_evidence.py` -- **new** FreeCAD-free CI helper: write `evidence/G0.4.<leg>.json` (green boolean + test count, verdict derived) for one matrix leg (`leg` ∈ `{"1.0.x","1.1.x"}`). The G0.4 ingest in `run` requires BOTH roster legs present+green ∧ ≥30 tests; a missing or red leg ⇒ `reports/G0.4.json` non-OK. -- per-leg G0.4 evidence (AC1).
- [x] `.github/workflows/ci.yml` -- each headless leg emits + uploads `G0.4.<leg>.json`; an aggregation job (needs both legs) downloads both into ONE `--run ci-<sha>` `evidence/` dir, then runs `runner.py run G0 --run ci-<sha>` + `verdict G0 --run ci-<sha>` (non-blocking) so the emitted G0.4 evidence is actually consumed. Existing legs unchanged. -- G0.4 stored evidence coherently surfaced.
- [x] `tests/external/test_gate_verdict.py` -- **new** pytest: the full I/O matrix over a fabricated tmp run dir (PASS + every single-leg FAIL + exit-2 cases), the **purity** assertion (identical result on re-run; `harness.verdict` importable with FreeCAD absent), `collect_g0_2` against the real `tool_specs()`, the loop-1 regressions (self-grade→FAIL, empty-checks-ingest→`INVALID_INPUT`, boolean-bar→leg-b FAIL, orphan-file→ignored, `ToolSpec.name=None`→malformed, one-red-leg G0.4→FAIL), **PLUS loop-2 regressions: (g) a stored `reports/G0.3.json` whose `subject.criterion` is wrong/absent → leg-a FAIL (never a `{}`→OK skip); (h) a hand-placed `reports/G0.3.json` with `checks:[]` fed straight to `compute_verdict` → leg-a FAIL (empty-checks not vacuous-OK at verdict time); (i) `_ingest_g0_4` with only ONE roster leg present (green) → combined G0.4 non-OK (missing blocking leg not masked); (j) `check_token` with TWO same-type tokens where the earlier-by-filename is stale/FAIL and a later one is bound-PASS → leg-d PASSES (no stale-shadow); (k) `collect_g0_2` where the 3 namespaces hold <15 tools but total ≥15 (out-of-namespace tools present) → G0.2 count check FAILS; (l) `gate.yaml` `required_tokens` as a scalar string → `UsageError` exit-2, not char-by-char token checks.** -- falsifiable proof of every loop-1 + loop-2 fix (AC1, AC3).
- [x] `tests/external/test_harness_g0.py` -- **extend** (do not replace): stub path unchanged; `run`→`verdict` smoke over a tmp run. -- back-compat + wiring.
- [x] `tests/infc/test_g0_evidence.py` -- **new** in-FreeCADCmd `unittest`: collector writes OK-verdict G0.3 + G0.5 reports on a live bridge; skip-guard on absent fixtures. -- real in-FreeCAD evidence proof (AC1).
- [x] **Final Task: Quality Checks** -- run `python scripts/check_imports.py`, `ruff check src scripts tests benchmarks`, `ruff format --check src scripts tests benchmarks`, `python -m pytest tests/external`; report exact output.

**Acceptance Criteria:**
- Given all 5 stored criterion reports have `verdict==OK`, every cited validator is current (`validator_sha` matches ∧ sensitivity ≥95% ∧ false_alarm ≤5%), and a run-bound `gui_smoke` token with `outcome:"PASS"` exists, when `python benchmarks/runner.py verdict G0 --run <id>` runs, then it prints G0.1–G0.5 PASS + all legs PASS and exits 0. *(AC1 — G0.1–G0.5 on report fields; leg-b validator currency; leg-d token)*
- Given the GUI leg smoke was performed, when `python benchmarks/runner.py attest G0 --run <id> --type gui_smoke --outcome PASS` runs, then a `human/gui_smoke_*.json` token is written whose `binds_reports_sha256` equals the SHA-256 the runner computes over that run's stored reports, and a later `verdict` accepts it only because the hash still matches. *(AC2 — run-bound human token)*
- Given a stored run directory, when `verdict G0 --run <id>` is executed twice on the identical files with no bridge/FreeCAD/network available, then it reproduces the identical verdict and summary (pure function of files alone — an auditing agent could run it), and importing `harness.verdict` does not require FreeCAD. *(AC3 — reproducible pure function)*
- Given any single leg fails (a report not OK, a stale/failing cited validator, an absent/recycled/FAIL-outcome token), when `verdict` runs, then the gate is FAIL, the failing leg + the offending criterion/validator/token is named in the output, and the exit code is 1. *(AC1/AC2 negative paths)*
- Given an evidence/report file that self-grades (a `"verdict":"OK"` stamped over a failing check, or a `"checks":[]` empty set) or a validator `last_run` whose `sensitivity`/`false_alarm` is a boolean, when `run`/`verdict` process it, then the gate is FAIL (verdict re-derived from checks; empty checks ⇒ `INVALID_INPUT`; boolean bar values rejected) — a self-graded or degenerate artifact can never PASS the gate. *(AD-13 no-self-grade guard)*
- Given `python scripts/check_imports.py`, when it runs, then `benchmarks/runner.py`, `harness/verdict.py`, `harness/evidence.py`, and `harness/report_build.py` are FreeCAD-free (only `collect_evidence_infc.py` imports FreeCAD), and the existing `--stub` tests still pass unchanged.

## Spec Change Log

### 2026-07-22 — bad_spec repair (loop 2)
- **Triggering findings:**
  - **[high] leg-a subject-mismatch masks a red criterion.** `compute_verdict` keyed reports by `subject.criterion` (`reports_by_id.get(criterion, {})`) but `load_reports` only guaranteed the filename. A `reports/G0.3.json` whose body `subject.criterion` was wrong/absent resolved to `{}`, and `derive_verdict({})` returns `"OK"` — the red criterion was silently skipped and leg-a passed (false PASS).
  - **[high] Empty/absent `checks` in a STORED report derives OK at verdict time.** loop-1 fixed empty-checks only at the ingest layer; a hand-placed `reports/G0.3.json` with `checks:[]` fed straight to `compute_verdict` still derived vacuous-OK (`derive_verdict` returns OK when no check fails). `verdict` is meant to be an independent auditor over stored files, so this bypassed the loop-1 guard.
  - **[high] `_ingest_g0_4` masks a MISSING blocking leg.** It ANDed only the `G0.4.<leg>.json` files that happened to exist. If one matrix leg's artifact failed to upload/download, the single present green leg greened G0.4 — though the rule demands BOTH blocking legs (1.0.x ∧ 1.1.x).
  - **[medium] `check_token` `matching[0]` shadowing.** With two same-type tokens (cross-day re-attest), the earliest-by-filename won; a stale/FAIL token shadowed a valid bound-PASS one → spurious FAIL.
  - **[medium] G0.2 count included out-of-namespace tools.** `valid` counted every well-formed spec (incl. `verify_`/`sketch_`), but the rule is "≥15 tools across `query_`/`document_`/`export_`". If those three namespaces alone held <15 but the total was ≥15, G0.2 passed wrongly.
  - **[low] `required_tokens` scalar not validated** (a string would be iterated char-by-char → spurious per-char token FAILs); **`_load_gate_def` re-read `gate.yaml` raw** (a mid-read YAML error could escape as an unhandled traceback, violating "never a traceback").
- **Amended (sections outside `<intent-contract>` only — Code Map, Tasks, Design Notes, Verification):** leg-a now resolves each expected criterion to its `reports/<id>.json`, verifies `subject.criterion == id` (mismatch/missing ⇒ leg-a FAIL, no `{}`→OK fallback), and rejects an empty/non-list `checks` as `INVALID_INPUT` at `load_reports`/leg-a WITHOUT changing `derive_verdict`; `_ingest_g0_4` pins the roster `{"1.0.x","1.1.x"}` and fails on any missing/red leg; `check_token` accepts iff ANY matching token is bound+PASS (no single-pick); `collect_g0_2` counts only tools whose name is in the three namespaces; `_load_gate_def` loads gate.yaml once and validates `required_tokens` is a list (scalar/YAML-error ⇒ `UsageError`). New test regressions (g)–(l) pin every fix.
- **Known-bad state avoided:** a gate that greenlights Phase-0 exit on a subject-mismatched or empty-checks report, on a single proven CI leg, or that spuriously fails on a stale shadow token / char-iterated `required_tokens` / a raw-reread YAML race.
- **KEEP (must survive re-derivation):** everything the loop-1 KEEP preserved PLUS the loop-1 fixes that are correct — the ingest-layer re-derivation + empty-checks-at-ingest guard, the boolean-bar rejection (`type(x) is int/float`), the orphan-tolerant `load_reports`, the per-leg `G0.4.<leg>.json` shape, the `emit_ci_evidence.py`/CI aggregation-on-same-run-id wiring, the gate-level `required_tokens` leg-d source (no dead per-criterion marker), the pure FreeCAD/network-free `verdict.py`, `bind_hash` canonical hashing (stable attest↔verdict), `hmac.compare_digest` binding, the `_validator_src_hasher` matching the fault scorers (clean tree current), the atomic writes, the exit-2 paths, the stub back-compat, and ALL loop-0/loop-1 tests + regressions (a)–(f) — ADD (g)–(l), do not replace.

### 2026-07-22 — bad_spec repair (loop 1)
- **Triggering findings:**
  - **[high] Ingested evidence self-grades — the gate can PASS on failing checks.** `ingest_report` returned the dropped JSON verbatim; leg-a and `run`'s exit read the stored `verdict` field. A collector/CI/hand-edited `evidence/G0.x.json` with failing checks but `"verdict":"OK"` (or `"checks":[]`) passed the gate — a direct AD-13 violation (the actor never self-grades; the verdict must be *derived*, never asserted). Both loop-1 reviewers flagged this as the dominant hole.
  - **[medium] leg-b accepts a boolean sensitivity/false_alarm.** `isinstance(True,(int,float))` is `True` and `True < 0.95` is `False`, so a validator registry with `sensitivity: true` cleared the bar. A typo'd/tampered registry could green a validator.
  - **[medium] G0.1 evidence provenance incoherent.** G0.1 was in `_INGESTED_CRITERIA` expecting an `evidence/G0.1.json` that nothing emitted (permanent leg-a FAIL), and `gate.yaml` carried a `gui_smoke: true` marker no code read (dead config). The spec never pinned G0.1's leg-a source vs its leg-d token.
  - **[medium] CI G0.4 evidence disconnected + last-writer overwrite.** `emit_ci_evidence.py` wrote `g0-ci/evidence/` while `run` read `g0/<run>/evidence/` (never consumed), and both matrix legs wrote the same `G0.4.json` (a red leg masked by a later green leg).
  - **[low] verdict globbed all `reports/*.json`.** An orphan/stray file rode the bind set or forced a spurious exit-2.
- **Amended (sections outside `<intent-contract>` only — Code Map, Tasks, Design Notes, Verification):** ingest + leg-a + `run`-exit now RE-DERIVE the verdict from checks (`evidence_report` recomputes, stored `verdict` dropped); empty `checks` ⇒ `INVALID_INPUT`; leg-b rejects boolean bar values (`type(x) is not int and not float`); G0.1 leg-a is its own transport-probe evidence report and leg-d is the gate-level `gui_smoke` token (dead per-criterion marker removed); `emit_ci_evidence.py` writes per-leg `G0.4.<leg>.json` AND-ed by `run` into one `reports/G0.4.json`, and the CI aggregation job runs `run`+`verdict` on the SAME `--run ci-<sha>` dir the evidence landed in; `load_reports` reads only the expected `reports/<criterion>.json` ids; `collect_g0_2` treats a non-string `.name` as malformed. New AC + test tasks (a)–(f) pin every fix.
- **Known-bad state avoided:** a mechanical gate that greenlights Phase-0 exit on a self-graded/degenerate evidence file, a boolean-typo'd validator, a permanently-failing or unread G0.1/G0.4 leg, and a masked red CI leg.
- **KEEP (must survive re-derivation):** the pure-verdict spine is correct and must be preserved — the FreeCAD-free/network-free `verdict.py`; `bind_hash` as a canonical sorted-by-criterion SHA-256 (verified stable across `attest`/`verdict`); `hmac.compare_digest` run-binding + the recycled/FAIL-outcome/absent-token leg-d checks; the four-leg a/b/d structure with c inert for G0; `collect_g0_2`'s namespace-span introspection; the atomic (tmp+replace) report writes; the exit-2 `UsageError` paths for missing run dir / malformed artifact; the `_validator_src_hasher` matching the fault-scorer source sets (verified: clean tree hashes MATCH the registry); the stub back-compat routing (bare `--gate/--stub` untouched); and ALL loop-0 tests — add the (a)–(f) regressions, do not replace.

## Review Triage Log

### 2026-07-22 — Review pass (loop 2 re-review)
- intent_gap: 0
- bad_spec: 0
- patch: 1: (low 1)
- defer: 0
- reject: 2
- addressed_findings:
  - `[low]` `[patch]` `_validator_src_hasher` called `path.read_bytes()` unguarded; a cited-and-registered validator whose source file is renamed/deleted raised an uncaught `FileNotFoundError` that escaped `verdict_command`/`_run_subcommand` (which catch only `ArtifactError`/`UsageError`) as a traceback — violating the runner's "never a traceback, exit 2" contract. Both loop-3 reviewers confirmed it is a spurious-FAIL/crash, NOT a false PASS. Patched: catch `OSError`, return `""` (a hash matching no real `validator_sha` ⇒ clean leg-b "stale" FAIL); added `test_validator_src_hasher_missing_source_is_stale_not_traceback`.
- rejected: `test_count` float (`30.0`) rejected by `isinstance(...,int)` → spurious FAIL (the only writer, `emit_ci_evidence.py`, writes `--tests` as int; guarding a non-existent input path is speculative, forbidden by the project's "no error handling for impossible scenarios" rule); `attest --outcome` defaults to `PASS` (by-design — leg-d is the operator's word per validation-harness §7; a token is a presence-and-binding artifact, not a code-enforced fact). Both loop-3 reviewers otherwise confirmed all 10 invariants hold and NO false-PASS path survives.

### 2026-07-22 — Review pass (loop 1 re-review)
- intent_gap: 0
- bad_spec: 6: (high 3, medium 2, low 1)
- patch: 0
- defer: 1: (low 1)
- reject: 0
- addressed_findings:
  - `[high]` `[bad_spec]` leg-a keyed reports by `subject.criterion` and fell back to `{}` on a miss → a subject-mismatched/absent-subject report resolved to `derive_verdict({})==OK`, masking a red criterion. Spec now resolves by expected-id file + verifies `subject.criterion == id` (mismatch ⇒ FAIL).
  - `[high]` `[bad_spec]` Empty/non-list `checks` in a STORED report derived vacuous-OK at verdict time (loop-1 only guarded the ingest path). Spec now rejects empty-checks at `load_reports`/leg-a as `INVALID_INPUT` (without touching `derive_verdict`).
  - `[high]` `[bad_spec]` `_ingest_g0_4` ANDed only present legs → a single green leg greened G0.4. Spec now pins the roster `{"1.0.x","1.1.x"}`; a missing/red leg ⇒ non-OK.
  - `[medium]` `[bad_spec]` `check_token` `matching[0]` let a stale/FAIL token shadow a valid bound-PASS one (spurious FAIL). Spec now accepts iff ANY matching token is bound+PASS.
  - `[medium]` `[bad_spec]` G0.2 count included out-of-namespace tools. Spec now counts only tools in `query_`/`document_`/`export_`.
  - `[low]` `[bad_spec]` `required_tokens` scalar iterated char-by-char + `_load_gate_def` raw re-read could throw an unhandled traceback. Spec now validates `required_tokens` is a list and loads gate.yaml once (errors ⇒ `UsageError`).
- deferred (appended to `deferred-work.md`): `gate.yaml` cites `verify_shape` for G0.5 (a STEP export round-trip) instead of `verify_export_step` — leg-b hashes the wrong validator source for G0.5; pre-existing in the verbatim-preserved criteria, not introduced by this story.

### 2026-07-22 — Review pass (loop 0)
- intent_gap: 0
- bad_spec: 5: (high 1, medium 3, low 1)
- patch: 0
- defer: 2: (low 2)
- reject: 4
- addressed_findings:
  - `[high]` `[bad_spec]` Ingested evidence trusted verbatim → gate PASS on failing/empty checks (AD-13 self-grade hole). Spec now re-derives the verdict from checks at ingest AND at leg-a, and rejects empty `checks`.
  - `[medium]` `[bad_spec]` leg-b accepted boolean sensitivity/false_alarm. Spec now rejects bool bar values.
  - `[medium]` `[bad_spec]` G0.1 had no evidence source (permanent FAIL) + dead `gui_smoke:true` config. Spec now pins G0.1 leg-a (transport-probe report) vs leg-d (gate-level token) and removes the marker.
  - `[medium]` `[bad_spec]` CI G0.4 evidence written to a dir `run` never reads + last-writer overwrite masks a red leg. Spec now uses per-leg `G0.4.<leg>.json` AND-ed, consumed on the same `--run ci-<sha>` dir.
  - `[low]` `[bad_spec]` verdict globbed all `reports/*.json` (orphan rides bind set / forces exit-2). Spec now reads only expected criterion-id report files.
- deferred (appended to `deferred-work.md`): the `gui_smoke` token is a presence-and-binding artifact with no cryptographic signature — anyone who can write `human/` can forge a valid PASS (design §7 models tokens as checked-not-performed, so this is a design-level posture, not a story defect); a leftover `.json.tmp` can linger after a crash mid-write (harmless to a clean verdict).
- rejected: editing `required_tokens` out of `gate.yaml` to skip leg-d (gate.yaml is trusted operator config, same class as editing a criterion out); token glob prefix-collision selecting a wrong-type file (the `token_type` field-mismatch check fails safe → spurious FAIL, never a false PASS); duplicate-criterion report last-wins (cannot occur under `run`'s per-id filenames); bind-hash cross-interpreter float-format fragility (single-interpreter by construction; no live bug).

## Design Notes

**Why two commands, and why `verdict` is pure.** validation-harness-design §3.2 makes the gate verdict "a pure function over stored `ValidationReport`s + token artifacts — re-runnable by anyone, including an auditing agent, without re-executing cases." That is AC3 verbatim. So evidence *collection* (which may need FreeCAD, a live GUI transport, or CI) is a separate, side-effecting `run`/collector step that drops report JSONs; `verdict` only reads files. This is what lets an auditor reproduce the decision without a bridge.

**The four legs, specialized to G0.** Global protocol legs (design §3.2 leg-6): (a) every non-human criterion passes its stated rule *on report fields* — here, its stored report's derived verdict is `OK`; (b) every cited validator's current fault run ≥95%/≤5% (G0 cites `verify_shape` for G0.3/G0.5 — already scored and registered); (c) exit legs on the sealed held-out set with dev/held-out gap ≤15pp — **inert for G0**: G0 is a deterministic-tool gate with no actor/held-out split, so there is nothing to unseal (the sealed heldout mechanism arrives at G1); (d) each required human token present + run-bound — G0 requires `gui_smoke` (design §7 "Required tokens per gate: G0 → gui_smoke").

**Evidence provenance per criterion (no fabrication, no self-grading).**
- G0.2 (≥15 tools schema'd): pure introspection of `tool_specs()` — headless, deterministic, the runner produces this report itself.
- G0.3 (golden ±0.1%) and G0.5 (STEP round-trip): deterministic but need FreeCAD → produced by `collect_evidence_infc.py` under FreeCADCmd, dropped as `evidence/*.json`, ingested by `run`.
- G0.1 (both transports list+call, GUI leg) and G0.4 (≥30 tests green both legs): cannot be synthesized headlessly. They are stored evidence — G0.4 the per-leg `emit_ci_evidence.py` artifacts AND-ed, G0.1 a live-transport probe evidence report (leg-a) whose GUI human sign-off is the gate-level `gui_smoke` token (leg-d). If the evidence file is absent, `run` records a failing `INVALID_INPUT` report ("evidence not collected") — never a pass.
- **Ingested evidence is never trusted verbatim (AD-13, the actor never self-grades).** An `evidence/*.json` file carries measured *checks*; the runner RE-DERIVES the `ValidationReport.verdict` from those checks via `derive_verdict` at ingest time (`evidence_report` recomputes; any stored `verdict` is dropped) AND leg-a re-derives again at verdict time. A collector or hand-edited file that stamps `"verdict":"OK"` over failing checks — or ships `"checks":[]` — is caught: failing checks ⇒ non-OK, empty checks ⇒ `INVALID_INPUT`. The stored `verdict` field is advisory display only, never the pass signal. This is the property both loop-1 reviewers flagged as the dominant hole.

**Run-binding hash (leg-d).** `binds_reports_sha256 = sha256( "".join( json.dumps(report, sort_keys=True) for report in sorted(reports, by criterion id) ) )`. `attest` computes it at token-creation; `verdict` recomputes over the current stored reports and `hmac.compare_digest`s. Editing any report after attestation breaks the binding (token cannot be recycled across runs — §7).

**Legacy invocation stays green.** `argparse` gets a subparser, but a bare `--gate G0 --stub` (no subcommand) must still route to the untouched stub path so `test_stub_run_report_per_criterion_schema_valid_invalid_input`, `..._banner_element_map_version_is_none`, and `..._file_path_invocation_exits_1` pass verbatim. Detect: if `argv[0]` is not one of `run|verdict|attest`, fall back to the current `_parse_args`/`main` behavior.

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: `check_imports OK` (all new `benchmarks/harness/*` + `runner.py` FreeCAD-free; FreeCAD only in `collect_evidence_infc.py`; `adapters/__init__.py`/`hosts/__init__.py` byte-empty).
- `python -m pytest tests/external -q` -- expected: all pass, including `test_gate_verdict.py` (full verdict matrix + purity) and the unchanged `test_harness_g0.py` stub tests.
- `python benchmarks/runner.py --gate G0 --stub` -- expected: 5 INVALID_INPUT criteria, exit 1 (unchanged back-compat).
- `python benchmarks/runner.py verdict G0 --run <fixture-id>` (over a fabricated all-PASS run dir) -- expected: all legs PASS, exit 0; re-run identical (purity).
- `ruff check src scripts tests benchmarks` and `ruff format --check src scripts tests benchmarks` -- expected: clean (no T201 in `src/`; `benchmarks/` tooling stdout allowed).
- (in-FreeCAD, CI/local) `FreeCADCmd tests/run_tests.py` -- expected: `test_g0_evidence` writes OK-verdict G0.3 + G0.5 reports on both blocking legs.

**Manual checks (if no CLI):**
- Inspect `harness/verdict.py`: no `import FreeCAD`, no socket/network, no bridge spin-up; `compute_verdict` reads only from the passed `run_dir` + `validators` mapping. Inspect `attest`→`verdict`: the same `binds_reports_sha256` bytes are produced by both sides for an unmodified run.

## Auto Run Result

Status: **done** (converged after 2 bad_spec repair loops + 1 clean patch loop).

### Summary
Turned the honest-failing `--stub` G0 runner into a mechanical **verdict machine**: `run` collects one re-derived `ValidationReport` per criterion into a run-scoped `gate-artifacts/g0/<run-id>/` store, `attest` records a run-bound `gui_smoke` token, and `verdict` computes the four-leg global protocol (a: every criterion's report OK; b: cited-validator currency ≥95%/≤5%; c inert for G0; d: required human token present + run-bound) as a **pure function over stored files** — reproducible by an auditing agent with no bridge/FreeCAD/network. The dominant hardening across the loops: an evidence file can never self-grade (verdict always re-derived from checks, empty checks rejected), a missing/red G0.4 matrix leg can never be masked, a subject-mismatched report can never pass, and a stale token can never shadow a valid one.

### Files changed
- `benchmarks/runner.py` — `run`/`verdict`/`attest` subcommands, run store, `_ingest_g0_4` (both-leg roster), `_validator_src_hasher` (OSError-guarded), `_load_gate_def` (single read + `required_tokens` list-validation); stub path untouched.
- `benchmarks/harness/verdict.py` — **new** pure four-leg verdict (`compute_verdict`, `load_reports`, `bind_hash`, `check_validator_currency`, `check_token`).
- `benchmarks/harness/evidence.py` — **new** `collect_g0_2` (in-namespace ≥15 count) + `ingest_report` (re-derives verdict, rejects empty checks).
- `benchmarks/harness/report_build.py` — `evidence_report` + `not_collected_report` (verdict derived, stub helpers untouched).
- `benchmarks/g0/gate.yaml` — gate-level `required_tokens: [gui_smoke]` + leg-c-inert note.
- `benchmarks/g0/collect_evidence_infc.py` — **new** in-FreeCADCmd G0.3/G0.5 collector (only FreeCAD-touching file).
- `benchmarks/g0/emit_ci_evidence.py` — **new** per-leg G0.4 CI evidence emitter.
- `.github/workflows/ci.yml` — per-leg G0.4 emit/upload + non-blocking aggregation job (`run`+`verdict` on one `ci-<sha>` dir).
- `tests/external/test_gate_verdict.py` — **new** full verdict matrix + purity + regressions (a)–(l) + the loop-3 hasher guard.
- `tests/external/test_harness_g0.py` — extended (run→verdict wiring; stub tests verbatim).
- `tests/infc/test_g0_evidence.py` — **new** in-FreeCADCmd collector self-check (skip-guarded).
- `.gitignore` — ignore the `benchmarks/gate-artifacts/` run store.

### Review findings
- Loop 1: 5 bad_spec (high 1 self-grade, medium 3, low 1) → spec amended, code re-derived.
- Loop 2: 6 bad_spec (high 3 false-PASS: subject-mismatch, empty-checks-at-verdict, missing-G0.4-leg; medium 2; low 1) → spec amended, code re-derived.
- Loop 3: 1 low patch (`_validator_src_hasher` traceback-escape → OSError guard), 2 rejected; both reviewers confirmed all invariants hold, no false-PASS survives.
- Deferred (3, in `deferred-work.md`): token has no cryptographic signature (design §7 posture); `.json.tmp` crash-leftover; `gate.yaml` cites `verify_shape` for G0.5 instead of `verify_export_step` (pre-existing in preserved criteria).

### Verification performed
- `python scripts/check_imports.py` → `check_imports OK`.
- `python -m pytest tests/external` → **218 passed** (incl. the full verdict matrix + regressions a–l + the loop-3 guard).
- `python benchmarks/runner.py --gate G0 --stub` → 5 INVALID_INPUT, exit 1 (back-compat unchanged).
- `ruff check src scripts tests benchmarks` → All checks passed. (`ruff format --check` flags 7 pre-existing drift files present on the baseline commit, none touched by this story; all files this story authored/edited are formatted.)
- Independent end-to-end proofs (re-run by the orchestrator, not trusting the dev report): honest all-OK run → attest → verdict PASS exit 0; self-grade (`verdict:OK` over failing check) → FAIL; empty-checks → INVALID_INPUT; boolean sensitivity → leg-b FAIL; orphan report → ignored; subject-mismatch → FAIL; single G0.4 leg → non-OK; stale-token-shadow → PASS; scalar `required_tokens` → exit 2; missing validator source → clean leg-b stale (no traceback).
- Not runnable in this environment (no FreeCADCmd): `tests/infc/test_g0_evidence.py` + the G0.3/G0.5 collector — written for the CI headless legs.

### Residual risks
- G0.1/G0.4 legs depend on externally-supplied stored evidence (live GUI transport probe / CI matrix artifacts); absent evidence honestly fails, but the happy-path end-to-end PASS through real CI evidence is proven only when the CI aggregation job runs.
- The `gui_smoke` token's integrity guarantee is presence-and-binding, not cryptographic (per design §7) — leg-d ultimately trusts the operator's `--outcome`.
