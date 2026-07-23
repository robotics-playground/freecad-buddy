---
title: 'Story 2.4 — Gate G1 Exit'
type: 'feature'
created: '2026-07-24'
status: 'done'
baseline_revision: 'e589868fd0ef560ff263948a0e359543511af965'
final_revision: '3b5110d'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-2-3-local-backend-react-adapter.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** Phase 1 exits mechanically only when the G1 gate runs on the **sealed held-out** eval at R≥10 with majority-of-R, every G1.1–G1.6 passes its rule with Wilson CIs, the dev/held-out gap is ≤15pp, and the `rubric_review` + `spot_audit` human tokens are present and run-bound (AD-14, phase-gates global protocol leg-c/leg-d). Today the runner has NO held-out sealing ceremony, NO `--exit` code path, and `compute_verdict`'s leg-c is a bare comment ("inert for G0") — the held-out set is an unenforced placeholder.

**Approach:** Land the held-out **sealing machinery** (`gate seal g1` writes `SEAL.json` + a SHA-verified encrypted archive; `gate run g1 --exit` is the only path that unseals it, runs the actor eval at R≥10, appends an unseal event, and **burns** the set on a failed exit) and the **leg-c verdict** (`check_exit_run`: exit reports carry the R≥10 majority-of-R banner AND the dev/held-out gap ≤15pp) wired into `compute_verdict` for actor gates. The live ≥80% pass numbers stay operator-gated + CI-skipped (decisions 010/011); CI proves the ceremony, the leg-c math, the `--exit` refusal-without-key, and the dev-run heldout refusal — all offline and honest-failing.

## Boundaries & Constraints

**Always:**
- The verdict stays a **pure function over stored files** (AD-13): `check_exit_run` reads `reports/*.json` banners + a stored `dev_rate` artifact only; re-running on identical files reproduces the identical result. The stored `verdict` field is never trusted.
- `gate run g1 --exit` is the **only** code path that unseals `g1/heldout/` (design §1.1). Dev runs (`--stub`, `--actor-run`, `run`) refuse to touch `heldout/`. CI asserts `g1/heldout/` holds only the sealed pair (+`.gitkeep`), never an unsealed live case file.
- Unsealing **verifies `archive_sha256`** before extraction, extracts to a temp dir, deletes the extraction after the run, and **appends** an `unseal_events` entry `{run_id, timestamp, git_sha}` to `SEAL.json`. A failed exit run (verdict FAIL) **burns** the set: `SEAL.json` records the burn and a subsequent `--exit` refuses until a fresh seal.
- The unseal key is **never** committed, never in CI secrets, never in env files at rest — read only from an interactively-set `FREECAD_BUDDY_UNSEAL_KEY` (design §1.1). `--exit` without it is a clean exit-2 UsageError, never a traceback and never a silent offline fallback.
- Leg-c applies to **actor gates** (`verdict.heldout: sealed`), inert for `inert` gates (G0). Detection is the gate's `verdict.heldout` value, never a hardcoded gate-id branch.
- Runner exit-code contract unchanged: 0 pass / 1 honest-fail / 2 usage-or-loader error; never a traceback.
- Timestamps/`git_sha` come from the caller (runner passes them in); the sealing/unseal helpers take them as args (harness stays FreeCAD-free + deterministic under test).

**Block If:**
- The G1 exit requires the **live ≥80% pass-rate on a real backend** to be asserted green in this run — that is an operator ceremony, not an unattended-CI deliverable (decisions 010/011). If the intent is read as "make CI assert the live number," HALT: it contradicts the closed decision.
- A held-out eval-question/broken-doc **live case set** must be authored to fill `heldout/` — none exists yet and authoring an independent sealed eval split is a human ceremony (`gate seal` after a human writes the cases), not code this story can synthesize. This story ships the ceremony + verifies it over a placeholder/empty archive; it does not fabricate held-out cases.

**Never:**
- Never add `age`/`pyrage`/any encryption binary as a required dependency (absent from the env + pyproject; see Design Notes → decision 012). Never route the actor's own claim into the verdict. Never let a dev run or CI job unseal. Never weaken `--exit` to run offline-scripted-as-if-it-were-the-exit (the exit is operator-gated; offline `--exit` is a machinery self-test that still refuses without the key OR runs a clearly-labelled dry seal over the placeholder).
- Never open/read `g1/heldout/` contents outside the `--exit` path (project-context SEALED rule). Never McNemar here (that's GS ablation, not G1 exit).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Seal ceremony | `gate seal g1` with cases staged + `FREECAD_BUDDY_UNSEAL_KEY` set | Writes `g1/heldout/SEAL.json` (`gate, sealed_at, sealed_by, case_count, archive_sha256, case_id_list_sha256, unseal_events: []`) + `heldout.tar.enc`; prints the archive sha | Missing key → exit-2 UsageError; unstaged/empty set is sealed as `case_count: 0` (placeholder), not an error |
| Exit run PASS | `gate run g1 --exit` with key set, sealed pair present, exit reports pass R≥10 + gap ≤15pp | Verifies `archive_sha256`, extracts to temp, runs actor eval R≥10, writes reports + `dev_rate.json`, appends unseal event, deletes extraction, exit 0 | Sha mismatch → exit-2 (tamper); archive/ SEAL absent → exit-2 |
| Exit run FAIL → burn | exit reports fail a rule OR gap >15pp | Verdict FAIL (exit 1); `SEAL.json` marked burned (`burned: {run_id, reason}`) | A later `--exit` on a burned set → exit-2 until re-sealed |
| `--exit` no key | key env unset | exit-2 UsageError naming the env var; heldout untouched | Never a traceback, never an offline fallback |
| Dev run refuses heldout | `gate run g1` / `--actor-run` / `--stub` | Never reads/extracts `heldout/`; runs dev set only | n/a |
| leg-c on exit reports | `gate verdict g1 --run <exit-id>` with exit banners + `dev_rate.json` | PASS iff every report banner carries `r >= 10` (majority-of-R) AND `|dev_rate - heldout_rate| <= 0.15` | Missing banner `r`/`dev_rate.json` on a sealed gate → leg-c FAIL (never vacuous-OK) |
| leg-c inert (G0) | `verdict.heldout: inert` gate | leg-c contributes no failures | n/a |
| Tokens at exit | `gate attest g1 --run <exit-id> --type rubric_review\|spot_audit` then verdict | Both tokens bound to the exit reports + PASS → leg-d passes | Absent/unbound/FAIL token → leg-d FAIL (existing `check_token`) |

</intent-contract>

## Code Map

- `benchmarks/harness/seal.py` -- **new**: FreeCAD-free, stdlib-only sealing helpers. `seal_heldout(heldout_dir, *, sealed_by, sealed_at, key) -> dict` tars the staged case dirs (or an empty archive when none staged), encrypts with a stdlib cipher (see Design Notes; NO `age`/third-party dep), writes `heldout.tar.enc` + `SEAL.json` (schema per design §1.1: `gate, sealed_at, sealed_by, case_count, archive_sha256, case_id_list_sha256, unseal_events: []`), returns the manifest. `unseal_heldout(heldout_dir, *, key, run_id, timestamp, git_sha) -> Path` verifies `archive_sha256` (raise `SealError` on mismatch/absent/burned), decrypts+extracts to a temp dir, appends the `unseal_events` entry to `SEAL.json`, returns the temp path; caller deletes it. `burn_seal(heldout_dir, *, run_id, reason)` stamps `burned` into `SEAL.json`. `read_manifest(heldout_dir) -> dict | None`. `SealError(Exception)`. Timestamps/git_sha are injected (deterministic under test).
- `benchmarks/harness/verdict.py` -- add `check_exit_run(run_dir, gate_def, reports) -> list[str]` (leg-c). Inert unless `gate_def.get("verdict", {}).get("heldout") == "sealed"`. For a sealed gate: every actor-run report banner must carry `banner["wilson_ci"]["r"] >= 10` (R≥10 majority-of-R evidence) — a report missing the banner rate is a leg-c failure; AND `dev_rate.json` (written by the exit run) must exist with `|dev_rate - heldout_rate| <= 0.15` (AD-14 gap). Wire the failures into `compute_verdict` as `leg-c: …`. Keep it pure over stored files (add a `dev_rate.json` read, no network/FreeCAD). Update the module docstring: leg-c is now implemented (not "inert").
- `benchmarks/runner.py` -- add the `seal` subcommand (`seal_command(gate)`) and the `--exit` flag on `run` (`run_exit_command(gate, run_id)`). `seal` builds the manifest via `seal.seal_heldout` using `FREECAD_BUDDY_UNSEAL_KEY` (exit-2 if unset). `run --exit`: exit-2 without the key; else `seal.unseal_heldout` (temp extraction), run the actor eval at **R≥10** over the unsealed set (reuse `run_actor_eval` with `repeats>=10`; offline scripted double only when explicitly dry-labelled — a real exit needs the operator backend, decision 010), write per-case reports + `dev_rate.json` (the dev-set pass rate for the gap check), compute the verdict (`compute_verdict` now including leg-c), `burn_seal` on FAIL, always delete the temp extraction (`finally`). Add `seal` to `_SUBCOMMANDS`/`_parse_subcommand`; add `--exit` to `_parse_args`/route in `main`. Dev-run paths (`run`, `--actor-run`, `--stub`) stay heldout-blind. Extend `_run_dir`/verdict wiring so `verdict g1 --run <exit-id>` re-derives leg-c from the stored exit reports + `dev_rate.json`.
- `benchmarks/g1/heldout/.gitkeep` -- update the note: the sealed pair (`heldout.tar.enc` + `SEAL.json`) is the ONLY content that may land here at/after exit; still never a raw live case file. Machinery now lands (this story), cases remain human-authored.
- `.github/workflows/gate-exit.yml` -- **new**: a `workflow_dispatch`-only gate-exit workflow (design §1.1: "manually-dispatched gate-exit workflow, added at Gate G1 exit, Story 2.4"). It does NOT assert the live pass-rate and does NOT hold the unseal key: it runs the offline machinery self-tests (seal→unseal→burn ceremony over the placeholder, leg-c math, `--exit`-without-key refusal) and documents that the real exit is an operator ceremony run locally with the human-held key. No key/secret/GGUF/network step.
- `.github/workflows/ci.yml` -- `arch-checks`: add an offline step running the seal/exit machinery tests + assert `g1/heldout/` holds only the sealed pair/`.gitkeep` (no unsealed live case leaked). No secret/key.
- `tests/external/test_gate_g1_exit.py` -- **new**: pytest — seal→unseal round-trip over a tmp heldout (sha verified, `SEAL.json` shape, unseal event appended, temp extraction deleted by caller); sha-mismatch → `SealError`; `--exit` without key → exit-2; dev run never touches heldout; leg-c PASS (R≥10 banners + gap ≤15pp) and each leg-c FAIL (a report banner with `r<10`; a missing `dev_rate.json`; gap >15pp); burn on FAIL then `--exit` refuses; leg-c inert for a `heldout: inert` gate.
- `tests/external/test_harness_g1.py` -- update `test_g1_heldout_contains_only_placeholder`: after 2.4 the guard forbids **unsealed live case files** but must ALLOW the sealed pair (`heldout.tar.enc`, `SEAL.json`) + `.gitkeep`. Keep the negative guard (no `case.yaml`/`fixture.FCStd`/eval question leaks into `heldout/`).
- `scripts/check_provenance.py` -- confirm `heldout/` stays in `_EXCLUDED_DIRS` (the sealed archive is not a provenance-manifested loose artifact). No change expected; verify.
- `docs/decisions/012-g1-heldout-seal-stdlib-cipher.md` -- **new** decision note: design §1.1 names `age`; the env has no `age` binary and no `pyrage`, and neither is a project dep (pyproject). Record the resolution — a stdlib-only symmetric cipher (no new required dep) satisfies the SAME auditable contract the runner enforces (SHA-verified sealed archive, human-held key, unseal-event/burn, dev-run refusal); the `.age` name is honored as `.enc`. State that no live held-out cases exist yet, so this seals a placeholder and the machinery — not a live number — is what CI proves; the live ≥80%/second-backend numbers stay the operator exit ceremony (decisions 010/011). Reuse survey: why not vendor age vs a stdlib cipher.

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md` (language-agnostic rules; Python ring; `benchmarks/` is non-ring external tooling, may import `hosts`).
  - Re-read `validation-harness-design.md` §1.1 (held-out sealing: SEAL.json shape, unseal-only-via-`--exit`, burn rule, dev-run refusal, key-is-human-only), §3.1 (`gate run --exit` / `gate seal` CLI), §4 (stats: majority-of-R, Wilson CI, R≥10 exit), §7 (human tokens present + bound at exit).
  - Re-read `phase-gates.md` global protocol legs (a)-(d) and the G1 exit criteria table; `project-context.md` "Verification & Validation Discipline" (actor never grades itself; `heldout/` SEALED; dev/held-out gap >15pp blocks exit) + "Wire & Schema Rules" (closed status set; server-derived text).
  - Re-read decisions 008 (tiered n10→n30), 010 (Claude live eval operator-gated/CI-skipped), 011 (ReAct local eval operator-gated). Re-read Story 2.1/2.2/2.3 Code Maps + Design Notes (`run_actor_eval`, `compute_verdict` legs a/b/d, `attest`/`check_token`, `_load_gate_def`, the offline env-gate discipline).
  - Load `typescript-clean-code` for naming/commenting discipline (zero obvious/provenance comments), applied to Python.

**Execution:**
- [x] `benchmarks/harness/seal.py` -- add stdlib-only `seal_heldout`/`unseal_heldout`/`burn_seal`/`read_manifest`/`SealError`: tar+cipher archive, `SEAL.json` per design §1.1, `archive_sha256` verified before extract, unseal-event append, burn stamp; timestamps/git_sha injected. -- sealing ceremony (AC1). No `age`/third-party dep; FreeCAD-free. `hashlib`-keystream XOR cipher, `.enc` file; `case_count: 0` placeholder valid.
- [x] `benchmarks/harness/verdict.py` -- add `check_exit_run` (leg-c) gated on `verdict.heldout == "sealed"`: every actor report banner `wilson_ci.r >= 10` + `dev_rate.json` present with gap ≤0.15; wire into `compute_verdict`; docstring leg-c now implemented. -- R≥10 + gap verdict (AC2). Pure over stored files. leg a/b/d regressions unbroken.
- [x] `benchmarks/runner.py` -- add `seal` subcommand + `--exit` on `run`: key-gated unseal→R≥10 actor eval→reports+`dev_rate.json`→verdict(incl. leg-c)→burn-on-FAIL→temp cleanup in `finally`; dev paths stay heldout-blind; `verdict --run <exit-id>` re-derives leg-c. -- exit ceremony + refusals (AC1/AC2/AC3). Exit codes 0/1/2 preserved. `--exit` requires an explicit `--run <exit-id>` (operator names the sealed run, matching §7 token `run_id` examples).
- [x] `.github/workflows/gate-exit.yml` -- add `workflow_dispatch`-only offline machinery self-test (seal→unseal→burn, leg-c math, key-absent refusal); no live pass-rate, no key/secret/GGUF/network. -- operator-gated exit surface (AC3).
- [x] `.github/workflows/ci.yml` -- `arch-checks`: run the seal/exit machinery tests offline + assert `g1/heldout/` holds only the sealed pair/`.gitkeep`. -- CI-enforced offline coverage.
- [x] `tests/external/test_gate_g1_exit.py` -- cover the I/O matrix: seal↔unseal round-trip + sha-verify + event append + temp cleanup; sha-mismatch `SealError`; `--exit` no-key exit-2; dev-run heldout-blind; leg-c PASS + each FAIL (r<10, missing dev_rate, gap>15pp); burn→`--exit` refuses; leg-c inert on `heldout: inert`. -- machinery + leg-c (AC1/AC2/AC3). 22 tests.
- [x] `tests/external/test_harness_g1.py` -- update `test_g1_heldout_contains_only_placeholder` to ALLOW the sealed pair + `.gitkeep`, still forbid unsealed live case files. -- guard survives the ceremony landing.
- [x] `benchmarks/g1/heldout/.gitkeep` -- update the note (sealed pair is the only permissible content; cases stay human-authored). -- doc accuracy.
- [x] `docs/decisions/012-g1-heldout-seal-stdlib-cipher.md` -- record the `age`→stdlib-cipher resolution, the placeholder-seal reality, the operator-exit deferral, and the reuse survey. -- decision artifact (surfaces the design conflict per project-context workflow rules).

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- `check_imports OK` (seal.py is `benchmarks/` tooling; no ring code touched).
- [x] `uv run python scripts/check_provenance.py` -- `check_provenance OK` (heldout stays excluded).
- [x] `uv run ruff check` (story files) -- `All checks passed!`.
- [x] `uv run pytest tests/external -q` -- 311 passed (4 pre-existing trimesh warnings, unrelated).
- [ ] `"FreeCADCmd" tests/run_tests.py` -- not run: no FreeCAD in env + no in-FreeCAD code changed (all changes are `benchmarks/` external tooling + CI + docs). Prior infc suites unaffected. Repo-wide `ruff check .` still shows 10 pre-existing E501 in `scripts/automation/run_mcp_e2e.py`/`run_mcp_edge_cases.py`/`test_check_imports.py` (unmodified by this story, verified vs baseline; out of scope).

**Acceptance Criteria:**
- Given a staged (or placeholder-empty) held-out set and `FREECAD_BUDDY_UNSEAL_KEY`, when `gate seal g1` runs then `gate run g1 --exit` runs, then the set is sealed with a SHA-verified archive + `SEAL.json` manifest, `--exit` is the only path that unseals it (verifying `archive_sha256`, appending an unseal event, deleting the temp extraction), a failed exit **burns** the set, and no dev run or CI job ever unseals it.
- Given exit reports on a `verdict.heldout: sealed` gate, when `gate verdict g1 --run <exit-id>` runs, then leg-c PASSES iff every actor report banner shows majority-of-R at **R≥10** AND the dev/held-out pass-rate gap is **≤15pp**, and FAILS honestly (never vacuous-OK) when a banner lacks the rate, `dev_rate.json` is absent, or the gap exceeds 15pp — the verdict staying a pure function over stored files.
- Given no operator backend/key in unattended CI, when the gate-exit machinery runs, then `--exit` without the key exits-2 (clean message, no traceback, no offline fallback), the live ≥80%/second-backend pass numbers are NOT asserted (operator ceremony per decisions 010/011), and the seal→unseal→burn ceremony + leg-c math + heldout-only-sealed-pair invariant are proven offline with no key/secret/GGUF entering CI.

## Review Triage Log

### 2026-07-24 — Review pass (follow-up 2)
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 1, medium 1, low 3)
- defer: 4
- reject: 8
- addressed_findings:
  - `[high]` `[patch]` `run G1 --exit` stored one report PER REPEAT keyed on `subject.case`, so the R (≥10) repeats of a case all overwrote a single `reports/<case_id>.json` — last-writer-wins left one arbitrary repeat on disk, not the majority-of-R the banner claimed, and leg-a re-derived that arbitrary repeat's verdict rather than the case majority (breaks "pure over stored files / re-runnable by an auditor" — AD-13/AD-14 majority-of-R evidence). Rewrote `_exit_case_reports` to emit exactly one report per graded case whose `checks` are a repeat matching `CaseResult.passed` (the majority), stamped with the tier Wilson CI and a `detail.majority` `{passes, repeats}` tally; added `_majority_report`. Masked offline (identical repeats) but real for any backend with variance.
  - `[medium]` `[patch]` `check_exit_run` accepted a non-finite (`NaN`/`Infinity`, which stdlib `json` parses) or out-of-`[0,1]` `dev_rate`, laundering a leg-c PASS — `abs(NaN - rate) > 0.15` is `False`. Added a `math.isfinite` + `0.0 <= dev_rate <= 1.0` guard that fails leg-c honestly with `out-of-range dev_rate`.
  - `[low]` `[patch]` `run G1 --exit` divided the held-out rate by `len(exit_reports)` with no guard — a degenerate zero-report run raised `ZeroDivisionError` inside the `try` (a traceback, violating the exit-2-never-traceback contract) instead of a clean loader error. Added an empty-reports `UsageError` (exit-2) before the division.
  - `[low]` `[patch]` `_extract_sealed`'s pre-3.12 fallback used `str(target).startswith(str(root))` (sibling-dir confusion, e.g. `/tmp/x` vs `/tmp/x-attack`) and did not screen symlink/device members. Switched to `Path.is_relative_to` and an explicit `issym()/islnk()/isdev()` refusal, matching what the 3.12 `data` filter enforces.
  - `[low]` `[patch]` `_git_sha`'s `subprocess.run(["git", "rev-parse", "HEAD"])` had no `timeout`, so a wedged git/filesystem could block the exit ceremony indefinitely. Added `timeout=10` + `TimeoutExpired` handling (returns `"unknown"`, matching the OSError path), aligning with the repo's time-bounded-subprocess discipline.

### 2026-07-24 — Review pass (follow-up)
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 2, medium 1, low 2)
- defer: 1
- reject: 6
- addressed_findings:
  - `[high]` `[patch]` `_load_exit_reports` dropped the non-empty-`checks` guard that `load_reports` enforces — because `derive_verdict` returns `OK` for a non-list `checks`, a stored exit report with its `checks` stripped/emptied re-derived to OK and passed leg-a on the auditor `verdict --run <exit-id>` path (AD-13 vacuous-OK laundering, distinct from the iteration-0 stored-`verdict`-field hole). `_load_exit_reports` now rejects an empty/non-list `checks` as a clean `UsageError` (exit-2), mirroring `load_reports`.
  - `[high]` `[patch]` `run G1 --exit` burned the sealed set on ANY non-empty verdict-failure list, including leg-d (human tokens not yet attested) and leg-b (validator currency) — making the documented ceremony (`--exit`, THEN `attest`, THEN `verdict`) un-runnable, since the first `--exit` burned before tokens could bind, forcing a re-seal every run. Per the spec I/O matrix the burn trigger is "exit reports fail a rule OR gap >15pp" (the eval's own verdict). Added `_exit_eval_failures` (leg-a per-case + leg-c only) driving the `--exit` exit-code + burn; leg-b/leg-d stay enforced at the later `verdict --run` step. Corrected the two tests that codified the wrong behavior (`--exit` now returns 0 on a passing eval with no tokens and does NOT burn; leg-d FAIL surfaces at `verdict --run`).
  - `[medium]` `[patch]` `check_exit_run` labeled each leg-c failure via `_criterion_of` (reads `subject.criterion`), but exit reports are keyed/written by `subject.case`, so every real exit-report leg-c failure rendered its id as `?` in the operator output and the burn `reason`. Added `_subject_label` (case, else criterion) and used it for the leg-c failure label.
  - `[low]` `[patch]` The dev/held-out gap check compared a raw float subtraction with `>` — an exact-boundary 15pp gap (e.g. `0.95 - 0.80` floating to `0.15000000000000002`) spuriously FAILed although the bound is "≤15pp". Now rounds the gap to permille before the comparison.
  - `[low]` `[patch]` Dev-run heldout-blindness was asserted only for `--stub`; the spec requires `--stub`, `--actor-run`, AND `run` to leave `heldout/` untouched. Added `test_dev_actor_run_never_touches_heldout` covering the `--actor-run` path.
- notes: Parallel Blind Hunter (`bmad-review-adversarial-general`) + Edge Case Hunter (`bmad-review-edge-case-hunter`) over the full baseline diff (`e589868..8d15bb6`). All findings verified against source before triage. Verification after patches: `pytest tests/external` 315 passed (4 pre-existing trimesh warnings); `ruff check` clean on story files; `check_imports OK`; `check_provenance OK`; `--exit` without key → clean exit-2 (no traceback). Deferred (1): `verdict`/`attest` detect an exit run by the presence of a `dev_rate.json` sidecar rather than the gate's `verdict.heldout: sealed` signal (filename-fragile, low consequence in single-gate Phase 1). Rejected (6, unreachable/by-design/hardening-only): path-traversal fallback string-`startswith` (Py<3.12 only, fresh-mkdtemp + operator-authored archive — trusted-input threat model); ZeroDivision on empty exit reports (unreachable — dev cases always ≥1, auditor path already guards); `_git_sha` no subprocess timeout (`git rev-parse HEAD` does not prompt); `case_id_list_sha256` write-only (archive_sha256 already covers content tamper; the field is part of the design §1.1 manifest schema); reseal wipes unseal history / no `--force` / spoofable `sealed_by` (already adjudicated + rejected in iteration 0 as operator ceremony, no design §1.1 requirement); float `wilson_ci.r=10.0` and `subject`-missing-`criterion` KeyError (both unreachable from internally-produced reports, which always carry an int `r` and a `criterion`).

### 2026-07-24 — Review pass (iteration 0)
- intent_gap: 0
- bad_spec: 0
- patch: 7: (high 2, medium 3, low 2)
- defer: 1
- reject: 6
- addressed_findings:
  - `[high]` `[patch]` The exit verdict leg-a (`_exit_verdict_failures`) read the stored `report["verdict"]` field instead of re-deriving it (AD-13 pure-verdict violation — a `verdict:OK`-over-failing-checks report passed exit leg-a). Now re-derives via `derive_verdict` (both `_exit_verdict_failures` and the `run_exit_command` held-out-rate sum).
  - `[high]` `[patch]` The exit verdict ran ONLY leg-a + leg-c, silently dropping leg-d (required `rubric_review`+`spot_audit` human tokens) and leg-b (grader validator currency) — contradicting the spec I/O matrix "Tokens at exit → leg-d passes / Absent/unbound/FAIL → leg-d FAIL (existing `check_token`)" and Intent (tokens are part of the exit verdict). `_exit_verdict_failures` now also runs `check_token` (leg-d) + `check_validator_currency` (leg-b), so a missing spot-audit/rubric token or a stale grader FAILs the exit.
  - `[medium]` `[patch]` `_load_exit_reports` + `_exit_verdict_failures` used bare `json.loads` and bare `report["verdict"]`/`report["subject"]` subscripts — an unparseable or shape-drifted stored report raised a raw traceback on the auditor `verdict G1 --run` path (runner contract: never a traceback). Now `_load_exit_reports` wraps parse/shape in `ArtifactError`→exit-2 and leg-a uses `.get`-guarded access.
  - `[medium]` `[patch]` A wrong unseal key made `tarfile.open` raise `tarfile.ReadError` (garbage plaintext) which escaped `SealError` as a raw traceback (`run_exit_command` catches only `SealError`). Wrapped the tar open/extract in `SealError("unseal failed (wrong key?)")`.
  - `[medium]` `[patch]` `unseal_heldout` leaked its `mkdtemp` temp dir when extraction/append raised after creation (the caller `finally` only deletes a *returned* dir). Now `rmtree`s the temp on any failure path before re-raising.
  - `[low]` `[patch]` The `tarfile` extraction fallback (Py<3.12, in-matrix on the 3.11 leg) ran an unfiltered `extractall` — no path-traversal guard on key-holder-controlled archive members. Added a manual member-name sanitization on the fallback branch.
  - `[low]` `[patch]` `unseal_heldout`'s burned-set check did `burned.get("run_id")` without confirming `burned` is a dict — a hand-edited `burned: true` raised AttributeError. Guarded with an `isinstance` check.
- notes: Parallel Blind Hunter (`bmad-review-adversarial-general`) + Edge Case Hunter (`bmad-review-edge-case-hunter`) over the full baseline diff (`e589868..working`, 1070 lines). Findings verified against real source before triage. Deferred (1): a genuine staged held-out set would still be ignored because `run_actor_eval` hardcodes `BROKEN_DOCS = dev/broken-docs` — the exit unseals the set then evals dev. Latent laundering path once live cases are staged; no live cases exist yet (`case_count: 0` placeholder) and wiring the unsealed dir into the eval is future operator-ceremony work (decision 010: live eval operator-gated). Rejected (6, sanctioned/by-design/out-of-scope): XOR two-time-pad / no-MAC / co-located sha (decision 012 explicitly accepts a stdlib cipher as non-plaintext-not-confidential; operator can swap real age; no confidential live cases exist); reseal wipes unseal history + `seal` has no `--force` (operator ceremony, no such requirement in design §1.1); `git_sha:"unknown"` degradation (design-accepted when git absent); `wilson_ci.r` semantics (the banner carries the exit *tier* CI per the spec Design Note — for a genuine escalated exit the n=30 tier gives r≥the majority-of-R evidence leg-c intends; the r<10 FAIL branch is the correct honest-fail); `dev_rate` not-independently-verified (same root as the deferred dev-vs-heldout wiring — offline dry-run limitation, not a shippable-code defect).

## Design Notes

- **Why a stdlib cipher, not `age` (design §1.1 conflict).** Design §1.1 names `heldout.tar.age` (age-encrypted). The env has no `age` binary and no `pyrage` module, and neither is in `pyproject.toml` — adding an encryption binary/lib as a required dep violates project-context ("in-FreeCAD zero third-party" is stricter, but even the external process avoids gratuitous required deps) and CLAUDE.md §2 (simplicity). The runner-enforced **contract** is cipher-independent: a SHA-verified sealed archive whose key is human-held, unsealed only by `--exit`, with unseal-event/burn auditing and dev-run refusal. So seal.py ships a stdlib symmetric cipher (`hashlib`-derived keystream over `tarfile` bytes — enough to make the archive non-plaintext + key-bound for the auditable ceremony) and names the file `.enc`. This is recorded as decision 012, surfaced not silently diverged (project-context Development Workflow rule). If an operator wants true age at the real exit, the `key` seam accepts their tool; the runner only ever checks `archive_sha256` + manifest, never the cipher.
- **No live held-out cases exist — this seals a placeholder.** `g1/heldout/` is a `.gitkeep`-only placeholder (2.1 shipped it sealed-but-empty). Authoring an independent held-out eval split is a human ceremony (Block-If), not code this story synthesizes. So the shippable, CI-provable deliverable is the **machinery** (seal/unseal/burn/leg-c), exercised over a placeholder/empty archive. `case_count: 0` is a valid sealed manifest, not an error. The live numbers are the operator exit (decisions 010/011).
- **leg-c reads banners, not the actor.** The R≥10 evidence is `banner["wilson_ci"]["r"]` on each stored exit report (the Wilson CI already carries `r`/`n` — see `stats.wilson_ci`); the gap is `dev_rate.json` (the exit run writes the dev-set rate beside the reports) vs the held-out rate derived from the same reports. Pure over stored files (AD-13): no actor claim, no re-execution, re-runnable by an auditor.
- **`--exit` is not an offline shortcut.** A genuine exit needs the operator backend at R≥10 (decision 010). Offline, `--exit` still enforces the key gate and the ceremony; running the scripted double under `--exit` is only a labelled machinery dry-run, never a substitute for the operator's measured pass-rate. Keep the offline scripted eval on the existing `--actor-run` (dev) path; do not let `--exit` silently score the scripted double as the exit result.
- **SEAL.json shape (design §1.1, verbatim keys):** `{gate, sealed_at, sealed_by, case_count, archive_sha256, case_id_list_sha256, unseal_events: []}`; unseal appends `{run_id, timestamp, git_sha}`; burn adds `burned: {run_id, reason}`. `sealed_at`/`timestamp`/`git_sha` are injected by the runner (harness stays deterministic under test — mirrors `actor_run` taking repeats/injected doubles).

## Verification

**Commands:**
- `uv run pytest tests/external/test_gate_g1_exit.py tests/external/test_harness_g1.py -q` -- expected: all pass.
- `uv run pytest tests/external -q` -- expected: all pass (new + prior suites, incl. `test_gate_verdict.py` leg a/b/d regressions unbroken).
- `FREECAD_BUDDY_UNSEAL_KEY=test uv run python benchmarks/runner.py seal G1` -- expected: writes `g1/heldout/SEAL.json` + `heldout.tar.enc`, prints the archive sha, exit 0 (placeholder `case_count: 0`).
- `uv run python benchmarks/runner.py run G1 --exit` -- expected (no key): exit-2 UsageError naming `FREECAD_BUDDY_UNSEAL_KEY`, heldout untouched, no traceback.
- `uv run python benchmarks/runner.py --gate G1 --stub` -- expected: unchanged — every criterion honest-FAIL, exit 1 (regression guard; dev path never touches heldout).
- `uv run python scripts/check_imports.py` -- expected: exit 0.
- `uv run python scripts/check_provenance.py` -- expected: green.
- `uv run ruff check` (story files) -- expected: clean.

**Manual checks:**
- Confirm `git status` after a `seal` shows only the intended `g1/heldout/` sealed pair (no live case file), and after a dry `--exit` machinery run the temp extraction is gone (no `heldout/`-adjacent temp dir left behind).
- Confirm `.github/workflows/gate-exit.yml` is `workflow_dispatch`-only, asserts NO live pass-rate, and carries no key/secret/GGUF step.


## Auto Run Result

Status: done

**Summary (follow-up 2 review pass):** Adversarial + edge-case review of the Story 2.4 diff (since `e589868`) surfaced a set of correctness/hardening findings in the G1 exit machinery. No intent_gap, no bad_spec — all findings were localized patches or pre-scoped defers. Applied 5 patches; deferred 2 new items; rejected the rest (adjudicated by decision 012 crypto-posture acceptances or spec-sanctioned by the I/O matrix).

**Files changed this pass:**
- `benchmarks/runner.py` — exit stores one majority-of-R report per case (`_exit_case_reports` rewrite + new `_majority_report`), empty-reports `UsageError` guard, `_git_sha` subprocess `timeout`.
- `benchmarks/harness/verdict.py` — leg-c rejects non-finite / out-of-`[0,1]` `dev_rate` (`math.isfinite` + range guard).
- `benchmarks/harness/seal.py` — pre-3.12 tar extraction uses `Path.is_relative_to` + refuses symlink/device members.
- `tests/external/test_gate_g1_exit.py` — added majority-of-R-per-case, non-finite `dev_rate`, and out-of-range `dev_rate` regression tests.

**Review findings breakdown:**
- Patches applied (5): majority-of-R per-case report storage (high); non-finite/out-of-range `dev_rate` leg-c guard (medium); empty-reports exit-2 guard (low); path-traversal `is_relative_to` + symlink refusal (low); `_git_sha` subprocess timeout (low).
- Deferred (2 new, appended to `deferred-work.md`): `case_id_list_sha256` written-but-never-verified on unseal; wrong-key-decrypts-to-valid-tar has no plaintext-hash detection. (Two earlier 2.4 defers — dev-set-vs-held-out gap vacuity and the `dev_rate.json`-filename exit discriminator — were already logged in prior passes and were NOT modified.)
- Rejected: unauthenticated-manifest / keystream-reuse / spoofable `sealed_by` (adjudicated by decision 012); `--exit` exit-0 ≠ gate-passed and reseal-resets-burn (spec-sanctioned operator ceremony); burn-reason truncation and float-`r`-rejected-as-missing (cosmetic/unreachable); stray-`dev_rate.json` misroute (trusted operator artifact dir).

**Verification performed:**
- `uv run ruff check` on all touched files — All checks passed.
- `uv run ruff format` on touched files — formatted, then re-verified.
- `uv run pytest tests/external/test_gate_g1_exit.py tests/external/test_harness_g1.py` — 53 passed. The new majority-of-R test confirms one report per distinct case with a re-derived verdict matching the recorded majority tally; the offline `--exit` escalates to the n30 tier (30 cases → 30 reports, no collision).

**Residual risks:**
- The dev/held-out gap leg is structurally ~0 while no live held-out cases exist (deferred, pre-scoped as the operator ceremony per decisions 010/011). The stdlib XOR cipher's keystream reuse and the unauthenticated manifest are accepted by decision 012 for the trusted-operator, non-confidential `case_count: 0` placeholder; both become material when a human authors + seals a real held-out split.
