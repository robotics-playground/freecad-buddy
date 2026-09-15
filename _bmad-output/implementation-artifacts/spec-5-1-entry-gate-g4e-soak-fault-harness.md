---
title: 'Story 5.1: Entry Gate G4.E — Soak & Fault Harness'
type: 'feature'
created: '2026-09-15'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '_bmad-output/implementation-artifacts/epic-5-context.md'
  - '_bmad-output/implementation-artifacts/ad-19-override-epic-5-2026-09-15.md'
  - '_bmad-output/specs/spec-freecad-buddy/phase-gates.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Phase 4 ships a headless job service whose four failure modes — runaway loop,
unbounded allocation, native crash, and a wrong part carrying a clean report — are exactly the
modes that fail silently if nothing is watching for them. No G4 gate, no fault suite, and no
service code exist today, so any Phase 4 implementation would be graded by measures written
after it.

**Approach:** Land the G4 entry gate before the service: a `benchmarks/g4/` gate definition, a
fault suite with paired planted and control cases per fault, a scorer that reuses the existing
registry and statistics machinery, and an honest-failing stub service that every case is driven
against. Every criterion must FAIL against the stub, and that failure is the acceptance signal.

## Boundaries & Constraints

**Always:**
- Fault suites live beside the dev/held-out split, never inside it. They validate validators and
  never count toward a G4 pass rate.
- Terminal outcomes come only from the existing closed set in `contracts/status.py`. This story
  defines no new status value and edits no contract.
- A validator that measured nothing reports `not_scored` with a reason. A fabricated `0.0` is
  forbidden: "missed every defect" and "no defect was driveable" are different facts.
- The scorer writes `validators.yaml` through the shared `merge_validators_yaml` read-merge-write,
  never by full rewrite, or it clobbers other gates' blocks.
- `_VALIDATOR_SOURCES` in `runner.py` and the scorer's `VALIDATOR_SOURCES` stay byte-identical for
  every shared name, or a clean tree reads as stale at verdict time.
- Every G4 validator gets a NEW registry name. Reusing an existing name restales a G2/G3 score
  that nothing about G2 or G3 changed.
- The stub returns a structured closed-set terminal status. It never bypasses, never returns a
  bare success, and never raises an unstructured exception.

**Never:**
- Do not implement the supervisor, the worker pool, the sandbox, or the job API. Those are
  stories 5.2 to 5.4 and stay blocked behind this one.
- Do not spawn real processes, allocate unbounded memory, or segfault anything. The planted faults
  are declared in case files and answered by the stub; this story runs no jail and no pool.
- Do not seal a held-out split or add G4 to `_SEALABLE_GATES`. G4 has no held-out set until 5.5.
- Do not add a G4 exit evaluator or exit precondition. Exit is story 5.5's.
- Do not edit `contracts/status.py`, `contracts/job.py`, or any generated schema.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Gate loads | `benchmarks/g4/gate.yaml` present, criteria non-empty | `_load_gate("G4")` returns the criteria list | No error expected |
| Gate empty | `gate.yaml` with zero criteria | `UsageError`, exit 2 | Never a green report |
| Faults route | `runner.py faults G4` | Subprocesses `score_g4_validators.py`, forwards its exit code | Scorer exit code is the command's |
| Planted fault caught | Planted case, stub answers with the case's expected terminal status | Row `outcome: DETECTED` | No error expected |
| Planted fault missed | Planted case, stub answers `OK` | Row `outcome: MISSED`, sensitivity drops | Counted, never excluded |
| Control stays clean | `clean_control` case, stub answers `OK` | Row `outcome: PASS_CLEAN` | No error expected |
| Control flagged | `clean_control` case, stub answers a fault status | Row `outcome: FALSE_ALARM` | Counted against the bar |
| Kind/expectation disagree | `planted_defect` with `expectation: PASS_CLEAN` | `SuiteError` | Raised at partition, run refuses |
| No driveable case | Every case unscorable | `not_scored` with a reason | Never a fabricated `0.0` |
| Stub drives whole gate | `runner.py run G4 --run <id>` then `verdict G4` | Every criterion FAILS honestly | Failure IS the entry-gate signal |

</intent-contract>

## Code Map

Read these before editing. Anchors verified on this branch at `7283842`.

**Registration points — five edits, all in `benchmarks/runner.py`:**
- `:55` — `KNOWN_GATES = {"G0": "g0", ..., "G3": "g3"}`; add `"G4": "g4"`.
- `:75` — `_FAULT_SCORERS`; add the G4 scorer path.
- `:97` — `_VALIDATOR_SOURCES`; one entry per G4 validator name.
- `:159` — add `_G4_SUITE_ROOT = _REPO_ROOT / "benchmarks" / "g4" / "fault-injection"` beside the
  G2/G3 roots.
- `:164` — add `_G4_VALIDATORS = frozenset({...})`, then extend the `:287-288` branch in
  `_validator_src_hasher` to route G4 names to `_G4_SUITE_ROOT`. **Without this branch the hasher
  falls through to the source-only `return hasher.hexdigest()` and never folds the suite in, so
  the scorer's digest and the runner's disagree and every G4 row reads stale forever.**

**Do NOT edit** `:57` `_SEALABLE_GATES`, `_EXIT_EVALUATORS`, or `_EXIT_PRECONDITIONS` — story 5.5's.

**A sixth edit the plan missed, found during implementation:**
- `scripts/check_provenance.py:174` — a THIRD `_DRIVEN_FIXTURES` set, independent of the scorer's
  and the runner's. It flags any case directory with a `case.yaml` and no `fixture.FCStd`, so the
  12 G4 cases broke `test_check_provenance_clean_on_real_tree` until `driven-by-job-service` was
  registered. Its `_declares_driven_fixture` also required a `planted_op`, which no clean control
  has; the rule was relaxed so a declared control is exempt on its declaration alone. Forced by
  this story's own change, so in scope under "clean up your own mess".

**Anchors to read, not edit:**
- `:184` `_load_gate`, `:218` `_load_gate_def` — parse `gate.yaml`; all loader problems raise
  `UsageError` (exit 2), never a traceback. Zero criteria is an error.
- `:262` `_validator_src_hasher`, `:307` `_suite_sources` — the runner-side digest that must agree
  with the scorer's byte for byte.

**Templates to imitate (read, do not import):**
- `benchmarks/g3/fault-injection/score_g3_validators.py` — the scorer to model. Key anchors:
  `:54-55` bars, `:154` `_validator_sha`, `:191` `_partition` (two-way kind/expectation check),
  `:219` `_DRIVEN_FIXTURES`, `:224` `DRIVEN_RESULTS`, `:315` `score_validator`, `:336-371` the five
  `not_scored` branches, `:414` `score`, `:437` `_render_block`, `:480` `main` with `--check`.
- `benchmarks/g3/judge.py` — the honest-failing stub template an entry gate lands. Fixes the
  contract shape before the implementation exists; exports its codes as module constants.
- `benchmarks/g3/gate.yaml` — gate file structure: `gate`, `actor`, `grader`, `required_tokens`,
  `verdict`, `criteria[]` with `id`/`text`/`pass_rule`/`cited_validators`. Its header comment
  states the entry-gate stance to mirror.
- `benchmarks/g3/fault-injection/corrupted-plan/<case-id>/case.yaml` — case schema:
  `id`, `gate`, `criterion`, `targets_validator`, `fault: {kind, description, expectation}`,
  `corruption_class`, `detected_by`, `planted_op`, `fixture`.

**Reuse, do not reimplement:**
- `benchmarks/g0/export-fault-injection/score_export_verify.py:314` `merge_validators_yaml` —
  imported by `sys.path.insert` from every scorer. The read-merge-write that preserves other
  gates' blocks.
- `src/freecad_buddy/usecases/stats.py:17` `wilson_ci(k, n)`, `:42` `sensitivity(detected,
  planted)`, `:49` `false_alarm(flagged, controls)`. Reached via `sys.path.insert(REPO_ROOT/"src")`.
- `benchmarks/harness/verdict.py:106` `check_validator_currency` — the currency rule the registry
  row must satisfy: sha match AND sensitivity >= 0.95 AND false_alarm <= 0.05.

**Contracts that already exist — consume, never edit:**
- `src/freecad_buddy/contracts/status.py` — `TerminalStatus` already carries all four G4.E fault
  statuses (`TIMEOUT`, `OOM_KILLED`, `WORKER_CRASHED`, `SPEC_FAILED`) plus `OK` and
  `INVALID_INPUT`. `JobState = Literal["QUEUED", "RUNNING"] | TerminalStatus`.
- `src/freecad_buddy/contracts/job.py` — `JobStatus` TypedDict; required keys are `schema` and
  `state` per `tests/external/test_contracts.py:301`.

**Read-only evidence:**
- No `benchmarks/g4/` exists. `find -iname "*g4*"` returns nothing.
- No supervisor, worker-pool, sandbox, job-API, `service_mode`, or `maxtasksperchild` code exists
  anywhere in `src/`, `tests/`, `scripts/`, or `benchmarks/`. `JobStatus` has no producer and no
  consumer outside `contracts/__init__.py`, `scripts/gen_schemas.py`, and the contract test.
- `WORKER_CRASHED` is emitted today only by the RPC transport (`adapters/rpc_client.py`), for a
  dead RPC peer — not a worker pool. Do not mistake it for existing Phase 4 code.

## Tasks & Acceptance

**Execution:**
- `benchmarks/g4/gate.yaml` -- create the declarative mirror of the G4 exit table (G4.1 to G4.5
  from `phase-gates.md`), each criterion with `id`, `text`, `pass_rule`, `cited_validators`; set
  `required_tokens: [spot_audit]`, `verdict: {heldout: inert}`, and a header comment stating that
  every criterion fails honestly until 5.2-5.5 land -- the runner reads criteria, never hardcodes
  them, and `heldout: inert` keeps leg-c inert while G4 has no sealed set.
- `benchmarks/g4/stub_service.py` -- create the honest-failing job-service seam on the
  `benchmarks/g3/judge.py` template: module constants for the fault-injection hook names, a
  `submit(spec) -> JobStatus`-shaped mapping that always resolves to a closed-set terminal status,
  and a schema validator for untrusted job results -- fixes the service contract before the
  service exists, so the fault cases grade a shape that already existed.
- `benchmarks/g4/fault-injection/<leg>/<case-id>/case.yaml` -- author the case set: one planted
  case and one paired `control-` case per canonical fault across legs `timeout/`, `oom/`,
  `crash/`, `wrong-part/`, and `revision-diff/`; at least 10 cases total to meet the entry-gate
  suite-size rule -- paired controls are what make a false-alarm rate measurable at all.
- `benchmarks/g4/fault-injection/score_g4_validators.py` -- create the scorer modeled on
  `score_g3_validators.py`: reuse `merge_validators_yaml` and `stats`, keep the three-way
  `skipped` / `excluded_unscorable` / `not_scored` distinction, add a `driven-by-job-service`
  fixture kind, and support `--check` for a no-write verification run -- the scorer is what makes
  the suite a measurement rather than a folder of YAML.
- `benchmarks/runner.py` -- register G4 at the five points named in the Code Map, including the
  `_G4_VALIDATORS` / `_G4_SUITE_ROOT` pair and the hasher branch that folds the G4 suite into the
  digest -- deliberately NOT `_SEALABLE_GATES`, `_EXIT_EVALUATORS`, or `_EXIT_PRECONDITIONS`,
  which belong to story 5.5.
- `benchmarks/_registry/validators.yaml` -- add the G4 validator rows by running the scorer, never
  by hand -- a hand-written row carries a digest nothing backs.
- `benchmarks/g4/THREATS.md` -- record the threat list the entry gate owes: each Phase 4 threat,
  the counter that addresses it, and the criterion or fault leg that measures the counter; cover at
  minimum "HTTP 200 for a bad part", "revision breaks an unrelated feature silently", and "a leak
  hidden by restart luck" -- an entry gate without a threat list cannot show its cases cover the
  failure modes rather than the convenient ones.
- `benchmarks/g4/REUSE-SURVEY.md` -- record the reuse survey the entry gate owes: what existing
  harness machinery this gate reuses (the shared registry merge, `stats`, the runner's gate
  loader and digest) and what it deliberately builds new, with the reason -- the survey is what
  stops a fourth parallel scorer from being written by habit.
- `benchmarks/g4/README.md` -- state what the gate grades, why every criterion fails today, and
  the suite layout -- the G3 README is the model.
- `tests/external/test_gate_g4_exit.py` -- unit-test the I/O matrix rows: gate loads, empty gate
  raises, each outcome mapping, the kind/expectation disagreement raising `SuiteError`, the
  `not_scored` branches, and that the stub never returns a non-closed-set status -- test naming is
  `Should <outcome> When <condition>` with `// Arrange`/`// Act`/`// Assert` phases.

**Acceptance Criteria:**
- Given the G4 gate is registered, when `uv run python benchmarks/runner.py faults G4` runs, then
  the G4 scorer executes and the command exits with the scorer's own exit code.
- Given the fault suite and the stub service, when the scorer scores every leg, then each G4
  validator reaches sensitivity >= 0.95 and false-alarm <= 0.05 against the stub, or reports
  `not_scored` with a reason.
- Given the scorer has written the registry, when `check_validator_currency` runs over the G4
  criteria, then every cited G4 validator is current, and no G0, G1, G2, or G3 row changed.
- Given no service implementation exists, when `runner.py run G4 --run <id>` then `verdict G4
  --run <id>` runs, then every criterion FAILS and the verdict is red.
- Given the scorer is run twice with no source or case edit, when the second run uses `--check`,
  then it reports no drift and writes nothing.
- Given the entry-gate deliverable list in `phase-gates.md:3`, when the story is complete, then the
  four that apply are present: a threat list, a benchmark runnable against a stub and failing
  honestly, a fault suite of at least 10 cases at the sensitivity bar, and a recorded reuse survey.
  The fifth, a grading rubric, is conditional on judgment being needed; G4.E needs none, and
  `THREATS.md` records that decision rather than leaving the deliverable silently unmet.

## Design Notes

**Why a stub, and why it must fail.** An entry gate exists so the measuring machinery is born
before the thing it measures, and therefore cannot be tuned to it. `benchmarks/g3/judge.py` is the
precedent: it fixed the verdict schema so 4.1's fault cases were authored against a shape that
already existed. The G4 stub does the same for the job contract. A stub that passed anything would
defeat the purpose — a green G4 today would mean the criteria are measuring nothing.

**The three exclusion mechanisms are not interchangeable.** `score_g3_validators.py:382-384` is
explicit about why, and the same rule binds here:

- `skipped` — the case could not be driven at all; out of numerator and denominator.
- `excluded_unscorable` — a caveat on a real measurement; the case was driven but its own
  declaration cannot decide it.
- `not_scored` — no measurement happened; the row carries a reason, never a number.

Folding `excluded_unscorable` into `not_scored` would make "8 of 8 detected, 2 cases their spec
cannot decide" read identically to "nothing was measured".

**No rubric, and that is a decision.** The entry-gate deliverable list requires "a grading rubric
where judgment is needed". G4.E needs none: every case is decided by comparing a terminal status
against a closed set, which is mechanical. The two rubrics in the repo (`benchmarks/g1/rubric.md`,
`benchmarks/g3/fault-injection/visual-judge/RUBRIC.md`) both exist because a model judges prose or
an image. Record this absence in `THREATS.md` so a later reader sees a judged decision rather than
an omission.

**Fault statuses are declared, not produced.** This story plants no real infinite loop and
allocates no real memory. Each case declares the fault it represents and the terminal status a
correct service must answer with; the stub answers from the case declaration. Proving that
`OOM_KILLED` comes from a sandbox rather than the host OOM killer needs story 5.3 and is out of
scope here — recorded so nobody reads this suite as that proof.

## Verification

**Commands:**
- `uv run python benchmarks/runner.py faults G4` -- expected: the scorer runs; every G4 validator
  meets the bars or reports `not_scored` with a reason.
- `uv run python benchmarks/g4/fault-injection/score_g4_validators.py --check` -- expected: no
  drift reported and no file written on a clean tree.
- `uv run pytest tests/external/test_gate_g4_exit.py -q` -- expected: all pass.
- `uv run pytest tests/external -q` -- expected: 1471 pre-existing tests still pass, plus the new
  ones. No G0-G3 registry row changed.
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`.
- `uv run ruff check benchmarks/g4 tests/external/test_gate_g4_exit.py` -- expected: clean. Nine
  pre-existing E501 findings elsewhere are not this story's.
- `git diff --stat benchmarks/_registry/validators.yaml` -- expected: only added G4 blocks; no
  edit to any existing gate's block.
