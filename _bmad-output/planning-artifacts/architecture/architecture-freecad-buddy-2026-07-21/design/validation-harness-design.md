---
title: 'Validation & Benchmark Harness Design'
status: final
date: '2026-07-21'
ad-refs: [AD-13, AD-14, AD-16, AD-19, AD-17, AD-15, AD-12, AD-20, AD-8, AD-6]
spec-refs: ['_bmad-output/specs/spec-freecad-buddy/phase-gates.md']
---

# Validation & Benchmark Harness Design

The harness is the mechanical executor of `phase-gates.md`. It lives entirely in the **external process** (uv-managed, pytest-orchestrated — AD-12): `benchmarks/runner.py` + `benchmarks/harness/` glue plus the `benchmarks/` data tree. It drives FreeCAD only through the bridge's `document_*`/tool use cases (AD-20 — never raw `App.openDocument`), and it never lets the producing agent grade itself (AD-13).

## 1. `benchmarks/` Layout

```text
benchmarks/
  g0/                       # per-gate dirs mirror phase-gates.md (g0..g2, gs)
    golden-models/          #   5 hand-made reference models (.FCStd + expected.yaml)
    fault-injection/        #   >=10 planted-fault cases (see §6)
    cases/                  #   criterion checks (round-trip, registry introspection...)
  g1/
    dev/                    #   50-question eval + 30 broken-doc cases (tiered n=10->n=30, decision 008)
    heldout/                #   SEALED (see §1.1)
    fault-injection/        #   planted confident-wrong answer cases
    rubric.md               #   human-authored grading rubric (G1.E)
  g2/
    dev/                    #   40-command benchmark, per-command assertions
    heldout/
    fault-injection/        #   wrong-param, 5 TNP scenarios, dress-up drop, #6031 rollback
  gs/
    ablation-sets/          #   design-decomposition n>=40 dedicated set (AD-14)
    dummy-skill/            #   GS.E clean-A/B fixture
  _registry/
    validators.yaml         #   per-validator fault-suite binding + last sensitivity run (§6)
    provenance/             #   one manifest per benchmark artifact (§1.2)
  gate-artifacts/
    <gate-id>/<run-id>/     #   ValidationReports, stats blocks, human tokens (§7)
```

Fault-injection suites live **beside** the dev/heldout split, not inside it — they validate validators, they never count toward pass rates (AD-13, AD-19).

### 1.1 Held-out sealing mechanism (AD-13: "sealed until phase exit")

The held-out set must be *provably unseen* by both the developer and the agent during phase development. Mechanism:

- `heldout/` contains exactly two files: `heldout.tar.age` (age-encrypted archive of the case files) and `SEAL.json`:

```json
{
  "gate": "g2",
  "sealed_at": "2026-08-14T10:02:00Z",
  "sealed_by": "TanNT",
  "case_count": 8,
  "archive_sha256": "ab4f…",
  "case_id_list_sha256": "9c11…",
  "unseal_events": []
}
```

- The decryption key is held by the human only (password manager), never in the repo, env files, or CI secrets during development.
- `gate run --exit` is the **only** code path that unseals: it prompts for the key (or reads `FREECAD_BUDDY_UNSEAL_KEY` set interactively by the human), verifies `archive_sha256`, extracts to a temp dir, runs, deletes the extraction, and appends an unseal event `{run_id, timestamp, git_sha}` to `SEAL.json`. An unseal event on a gate that later fails means the set is **burned**: exit re-runs require newly authored held-out cases (recorded in the manifest). This is what makes "sealed until phase exit" auditable rather than aspirational.
- Dev runs (`gate run` without `--exit`) refuse to touch `heldout/`; CI asserts `heldout/` contains only the two sealed files.

### 1.2 Provenance manifest (AD-16)

Every benchmark artifact (golden model, spec, reference geometry) carries a manifest in `_registry/provenance/<artifact-id>.yaml`. CI fails on any artifact without one, and on any `source.kind` outside the commercial-clean closed set.

```yaml
artifact: g2/dev/bracket-4hole
kind: spec+golden          # spec | golden-model | oracle-geometry
source:
  kind: freecad-parts-library   # freecad-parts-library | freecad-wiki-tutorial |
                                # hand-authored | hf-verified-permissive
  url: https://github.com/FreeCAD/FreeCAD-library/...
  license: CC-BY-3.0
  attribution: "Original part by <author>, FreeCAD Parts Library"  # retained per AD-16
real_world_basis: "Mounting bracket pattern from wiki tutorial X"  # mandatory for hand-authored:
                                                                   # never reverse-fit to agent ability
license_checked: {by: TanNT, date: 2026-07-21}
```

Per the license research: DeepCAD/ABC/Text2CAD lineage and Fusion 360 Gallery are **never shipped** (Onshape creator-copyright / non-commercial ceilings). They may appear only as `kind: oracle-geometry` with `shipped: false` for validator fault-testing (import STEP → assert `verify_shape` fields), and even then the manifest records the lineage.

## 2. Benchmark Case Format

One directory per case; `case.yaml` is the contract:

```yaml
id: g2-dev-012
gate: g2
criterion: G2.1
spec: spec.md                    # NL spec given to the agent (Phase 3) / command (Phase 2)
inputs:
  document: fixtures/base.FCStd  # opened via document_* only (AD-20)
assertions:                      # compiled BEFORE implementation (AD-19); AD-13 vocabulary
  anchor_frame: {kind: base_sketch_plane, ref: Sketch}   # closed derivation set, per spec
  checks:
    - {fn: count_cylindrical_holes, expect: 4}
    - {fn: hole_spacing, pattern: rect, expect: [40.0, 25.0], tol: {abs: 0.05}}
    - {fn: expect_bbox, expect: [80, 50, 6], tol: {rel: 0.001}}
    - {fn: expect_volume, expect: 21430.0, tol: {rel: 0.001}}
  # feature metadata = diagnostic hint only; sub-element index selectors banned (AD-13)
expected_meta:                   # non-scoring diagnostics for reports
  golden_fingerprint: {sha256: "…", serializer: exportBinary}      # AD-6, tagged
  fully_constrained_sketches: [Sketch, Sketch001]                  # AD-8 signal
provenance: ../../_registry/provenance/g2-dev-012.yaml
```

Assertion `fn` names come from the `contracts/` assertion vocabulary; the harness resolves them to deterministic `verify_*` calls re-executed by the runner — agent claims are never echoed as results (AD-17). Tolerances default to fault-injection-calibrated bands (spine conventions).

## 3. Gate Runner

### 3.1 CLI

`gate` is a console-script alias of `benchmarks/runner.py` (project-structure §1/§5 invokes it as `python benchmarks/runner.py --gate G0` in CI — same entry point, two spellings).

```bash
# dev iteration: R=5, dev/ set only, heldout untouched
uv run gate run g2                          # whole gate, all criteria
uv run gate run g2 --criterion G2.3         # single criterion
uv run gate run g2 --case g2-dev-012 -R 1   # one case, quick loop
uv run gate run g2 --skills sketch-patterns,constraint-repair   # forced-subset passthrough (AD-15)

# exit run: unseals heldout, forces R>=10, computes full verdict
uv run gate run g2 --exit                   # prompts for unseal key

# supporting commands
uv run gate faults g2                       # run fault suite -> sensitivity/FA (§6)
uv run gate ablate design-decomposition --set gs/ablation-sets/dd-n40 -R 10   # paired A/B (§5)
uv run gate verdict g2 --run <run-id>       # recompute verdict from stored reports only
uv run gate ci-check G0 --run <run-id>      # CI scope of G0 only (see below)
uv run gate seal g2                         # human ceremony: encrypt heldout, write SEAL.json
```

**CI scope of G0.** CI cannot produce the full G0 verdict. G0.1, G0.3 and G0.5 need local evidence, and leg-d needs the `gui_smoke` token. So the blocking `g0-verdict` CI job runs `run G0` to write the reports, then `ci-check G0`. `ci-check` passes (exit 0) only when two conditions hold:

- the stored G0.4 report re-derives to `OK`;
- every validator that G0 cites is current (leg-b, the same `check_validator_currency` rule as `verdict`).

It prints each failure and exits 1 otherwise. A missing report is exit 2. `ci-check` is a subset of `verdict`, not a replacement: a gate exit still runs the full `verdict`.

`--skills` maps to the AD-15 forced explicit-subset injection path with auto-activation disabled; the routed/injected subset is logged into every `ValidationReport`.

### 3.2 Execution flow

1. **Preflight** — load gate definition (declarative mirror of the phase-gates tables, one YAML per gate); check `_registry/validators.yaml`: every validator cited by this gate must have a *current* fault-suite run (same validator version) at sensitivity ≥95 % / FA ≤5 %, else abort with `INVALID_INPUT` (protocol step 3b).
2. **Spin bridge** — start headless FreeCADCmd bridge (or connect to the GUI listener for G0.1's HTTP leg); handshake records FreeCAD version + `ElementMapVersion` for the report banner.
3. **Run cases ×R** — for each case, R independent repeats (fresh document per repeat via `document_*`; single-writer serialization per AD-20). Actor runs (Phases 1–3) drive the agent through the same MCP tool surface as production. **Timing capture (AD-24):** every case×repeat records one wall-clock measurement on the single AD-24 basis — tool-call entry to envelope return, model time included — carried on the `ValidationReport`. Phase 3 per-part timing spans all repair iterations including judge and TechDraw generation (AD-21 cadence).

   **G1 tiered screen (decision 008, AD-14).** The G1 error-diagnosis gate does not run flat over the fixture set. Grade the first **n=10**; the base gate (G1.2) passes at **≥8/10** and the skill-loaded leg (GS.4, `freecad-troubleshooting`) at **≥9/10**. Escalate to the sealed **n=30** run only on a **10/10** first stage; below 10/10 the gate concludes at n=10 and the result is stamped **low-confidence**. Wilson CI is reported at whichever n concluded, and the concluding n travels with any citation. The AD-14 `R≥10` repeat rules govern ablation and pp-threshold claims, not this screen; the Phase 1 answer eval runs at R=3.
4. **Re-verify** — the runner re-executes every assertion via deterministic `verify_*` calls against the produced artifact (AD-13/AD-17) and emits one contracts-owned `ValidationReport` per case×repeat, banner included (FreeCAD version, `ElementMapVersion`, validator sensitivity, Wilson CI where a rate is claimed, and **the AD-24 budget measured for this gate with its n**).
5. **Aggregate** — stats module (§4): majority-of-R per case, Wilson CI on the rate, per-repeat distribution attached, plus the median of the captured wall-clock times for the gate's AD-24 budget.
6. **Verdict** — gate = PASS iff all five legs of the global protocol hold:
   - (a) every non-human criterion passes its stated pass rule *evaluated on report fields* (never exit-code-0 or log absence);
   - (b) every cited validator's current fault run: sensitivity ≥95 % ∧ FA ≤5 %;
   - (c) exit legs ran on the sealed held-out set, R≥10, majority-of-R, and dev/held-out gap ≤15pp (AD-14 — gap >15pp = overfitting, no exit);
   - (d) each required human token is present and bound to this run (§7);
   - (e) the gate's **AD-24 budget** is met at the stated n — G1 answer latency ≤15 s median, per-part wall-clock ≤10 min median on the spec benchmark. Budgets are pass/fail here, never advisory: a run that satisfies every assertion and blows its budget **fails the gate**.
   `gate verdict` is a pure function over stored `ValidationReport`s + token artifacts — re-runnable by anyone, including an auditing agent, without re-executing cases.

## 4. Stats Module (`usecases/stats.py`)

> Placement note: the AD-14 statistics live in the **use-case** ring, not under `harness/`. `usecases/stats.py` imports only `math`, so it stays AD-12-legal and is importable *inside* FreeCAD — which the in-FreeCAD G2 scorer needs. The external harness imports the same module, so both sides compute rates with one implementation.

Pure functions, stdlib-only math, unit-tested against the research report's computed tables (the tables are the test fixtures).

- **Wilson 95 % CI** (closed form, z=1.96, p=k/n):

  ```text
  center = (p + z²/2n) / (1 + z²/n)
  half   = (z / (1 + z²/n)) · sqrt( p(1-p)/n + z²/4n² )
  ```

- **Exact McNemar** (two-sided): given discordant counts b (skill broke), c (skill fixed): under H₀ c ~ Binomial(b+c, 0.5); p = 2·P(X ≤ min(b,c)), capped at 1.0. Never the chi-square asymptotic version (b+c is tiny at n=20–50).
- **Majority-of-R** — a case passes iff >R/2 repeats pass; per-repeat outcome vector retained in the report (AD-14: the spread is itself a result).
- **Paired 2×2** — built from majority-of-R outcomes of the *same cases* under both arms; a/b/c/d as in the research report.
- **MDE guard** — if b+c < 6, the ablation result is stamped `BELOW_DETECTION_AT_N`, never "no effect" and never a win (AD-14).

Report blocks (verbatim shapes from the stats research; the harness renders these into every gate report):

**Single pass rate (phase gate):**

```text
Held-out: 15/20 passed = 75.0%
  Wilson 95% CI: [53.1%, 88.8%]
  Repeats: R=10 per case; per-case pass distribution attached
  Validator sensitivity: 96%
  Verdict vs ">=70%" gate: point estimate clears; lower CI bound 53% < 70% -> flagged low-confidence
```

**Ablation (skill on vs off):**

```text
Skill: design-decomposition | Benchmark: first-plan success | n=40 paired specs, R=10
  Without skill: 22/40 (55.0%)
  With skill:    30/40 (75.0%)   -> +20.0pp raw
  Paired 2x2: agree-pass=20, agree-fail=8, skill-fixed(c)=10, skill-broke(b)=2
  Net discordant: +8  | Exact McNemar two-sided p = 0.039  -> SIGNIFICANT
  Wilson 95% CI on paired difference: [+3pp, +34pp] (excludes 0)
  VERDICT: measurable margin met (p<0.05 AND CI excludes 0)
```

"Measurable margin" is exactly AD-14: exact-McNemar two-sided p<0.05 **and** Wilson 95 % CI on the paired difference excluding 0. Any specific pp-threshold claim (GS.6 `design-decomposition` +15pp) runs only on its dedicated n≥40 paired set at R≥10 — the stats research proves +15pp is undecidable at n=20 (best-case p=0.25).

## 5. Ablation Runner (GS)

`gate ablate <skill>` runs both arms over the same case set with identical seeds/config apart from the skill: arm A = declared subset **without** the skill, arm B = subset **with** it, both via forced injection with auto-activation disabled (AD-15). The runner asserts the complement is absent from the context transcript (GS.2's "complement excluded" check is a transcript grep, not trust). Output: the ablation report block above, one per skill, feeding GS.3/GS.6.

## 6. Fault-Injection Framework

Purpose: validate validators before their scores are citable (AD-13, AD-19 entry gates).

**Planted-fault case format** — same directory shape as §2 plus a `fault` block:

```yaml
id: g2-fault-007
targets_validator: verify_shape@usecases.verify.shape    # registry key
fault:
  kind: planted_defect          # planted_defect | clean_control
  description: "hole diameter 6.2mm where golden expects 6.0mm"
  expectation: DETECT           # DETECT for defects, PASS_CLEAN for controls
fixture: fixtures/wrong-diameter.FCStd
assertions: {…same vocabulary as §2…}
```

Every suite mixes ≥10 planted defects with clean controls (controls measure false alarms; defects measure sensitivity):

```text
sensitivity  = detected_defects / planted_defects        (bar: >=95%)
false_alarm  = flagged_controls / clean_controls          (bar: <=5%)
```

**Per-validator registry** (`_registry/validators.yaml`): maps each validator id → its fault suite, validator source hash, last run result:

```yaml
verify_shape:
  suite: g0/fault-injection/
  validator_sha: "e91b…"          # hash of validator source; change invalidates the run
  last_run: {run_id: fr-2026-08-02-1, sensitivity: 0.97, false_alarm: 0.02, date: 2026-08-02}
```

A sensitivity run is *current* only while `validator_sha` matches the working tree — edit the validator and its scores are stale until `gate faults` re-runs (global protocol 3b). Each phase's threat→counter map entries (phase-gates §5) must exist as named planted cases in that phase's suite before the gate can be cited; the gate definition lists the required counter case-ids and preflight checks they exist.

## 7. Human-Token Mechanism

Human-only steps are recorded as artifacts the runner *checks for presence and binding* — it never performs them (global protocol step 4). Token = JSON file under `benchmarks/gate-artifacts/<gate>/<run-id>/human/`:

```json
{
  "token_type": "spot_audit",   // spot_audit | rubric_review | gui_smoke | skills_accuracy
  "gate": "g2", "run_id": "g2-exit-1",
  "binds_reports_sha256": "…",  // hash over the run's ValidationReport set
  "scope": {"audited_cases": ["g2-ho-002", "g2-ho-005", "…"], "fraction_of_passing": 0.25},
  "outcome": "PASS",             // any audit-found false pass => outcome FAIL => run invalidated
  "notes": "…",
  "signed_by": "TanNT", "date": "2026-09-30"
}
```

Creation is a guided ceremony (`gate attest g2 --run <id> --type spot_audit`) that computes `binds_reports_sha256` and walks the human through the sample (spot-audit: runner pre-selects ≥20 % of passing results at random per AD-19). Verdict-time checks: token exists for each required type, `binds_reports_sha256` matches the stored reports (a token cannot be recycled across runs), `outcome == PASS`. A `spot_audit` with `outcome: FAIL` marks the run invalidated; the fix-validator → re-run → re-audit loop starts over, and if held-out was unsealed, §1.1's burn rule applies.

Required tokens per gate: G0 → `gui_smoke`; G1 → `rubric_review` + `spot_audit`; G2 → `spot_audit`; GS → `skills_accuracy` (per skill, GS.5) + `spot_audit` on ablation exit runs.

## 8. Independent Grader (Phase 1 / G1)

Where judgment is needed (answer quality, error-diagnosis naming), pass/fail comes from an **independent grader model — never the actor** (AD-13).

- **Config separation:** `g1/gate.yaml` declares `actor:` and `grader:` model configs; preflight hard-fails if they resolve to the same model id + same context (the grader may be a smaller/different model; it must not share the actor's conversation).
- **Grader input:** question, the actor's final answer (not its scratch reasoning), the human-authored rubric (`g1/rubric.md`, with worked pass/fail examples per G1.E), and the case's expected findings (`expected: {object: "Pad003", cause: "missing external reference"}` — G1.2 requires *the* object, not *an* object).
- **Grader output:** structured verdict `{pass: bool, matched_expected: bool, rationale}` validated by schema; the runner maps it into the standard `ValidationReport`. Grader temperature 0; grader transcript stored with the run for audit.
- **Grader validation:** the grader is itself a validator in `_registry/validators.yaml` — its fault suite is the planted confident-wrong answer set (G1.E); its sensitivity/FA must clear the bar before G1.1/G1.2 scores are citable, and `rubric_review` human token covers rubric authorship.
- The rubric is versioned; a rubric edit invalidates prior grader sensitivity runs (same hash-staleness rule as §6).

**Visual review (AD-21)** is not harness wiring. The harness produces the standard visual set — 3D iso render + focus views + dimensioned front/top/right projections, generated on a TempDoc copy from the part's driving parameters and the spec's assertion set (verification-design §7a) — and stops there. The review itself is the driving agent's, following the `visual-review` skill, and its findings land in the AD-17 run workdir rather than in a `ValidationReport` check. There is no judge model, no independence preflight, and no runner-computed done-predicate: "done" is a verdict the agent reaches, never a predicate this repository exports (AD-35).

## 9. Out of Scope / Deferred

Consistent with the spine's Deferred table: exact per-assertion tolerance defaults (calibrated during each phase's fault-injection work) and skill-router rules (ablation-only forced subset is all this harness needs).
