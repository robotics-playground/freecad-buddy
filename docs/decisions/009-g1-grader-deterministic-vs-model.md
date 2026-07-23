# 009 — G1 Grader: Deterministic Expected-Findings Matcher with a Model-Grader Seam (G1.E)

## Decision

The shipped G1 entry-gate grader is a **deterministic expected-findings matcher**
(`benchmarks/g1/grader.py`, `DeterministicGrader`), not a live model-backed judge. It decides
`pass` for an error-diagnosis answer by matching the candidate answer against the case's
independently hand-authored `{object, cause_keywords}`: the answer PASSES iff it names the
expected failing object identity (case-normalized, whole-token) AND at least one expected cause
keyword. A `GraderClient` protocol is declared as the seam a model-backed grader plugs into
later (Stories 2.2/2.3); no live-model call ships in this story.

The grader is scored NOW against a planted confident-wrong + clean-correct fault suite
(`benchmarks/g1/fault-injection/`, `score_grader.py`) and clears sensitivity ≥95% / FA ≤5% (a
real number in `_registry/validators.yaml`, not `null`), because — unlike Story 1.3's
`verify_shape`, which could not be scored until the validator existed — the deterministic grader
is fully implementable now and is independent of the not-yet-existing assistant.

## Rationale

The entry gate must be **reproducible in CI without secrets or network**, and its sensitivity
number must be real, not aspirational. For G1.2's structured expected findings
(`{object, cause}`), a rubric-keyed deterministic matcher is the strongest and most
reproducible grader: it decides `pass` by exactly the thing G1.2 measures — *the* failing
object identity + cause named, not *an* object (the "diagnosis names *an* object not *the*
object" threat). It cannot drift run-to-run, carries no API cost, and its source is hashed into
`validator_sha` so a score is citable only while the grader is unedited (NFR2).

A live LLM-as-judge is deferred, not rejected: G1.1's fuzzier tree-explanation /
answer-quality judgments benefit from a model grader, and the `GraderClient` seam is where one
plugs in when a backend is pinned (Stories 2.2/2.3). That live-model grader's own sensitivity
run is a later ceremony; shipping it now would put an unscorable, non-reproducible, secret-
dependent judge on the entry gate — exactly the ungrounded-number defect the gate exists to
prevent.

## Reuse survey (surveyed alternatives)

G1.E requires a recorded reuse survey. Surveyed:

- **LLM-as-judge frameworks** (generic "grade this answer with a rubric via an API model":
  ragas/DeepEval-style judges, bespoke GPT-4-judge harnesses). Rejected as the *shipped* entry-
  gate grader: (a) non-reproducible in CI (model/version drift, network, secrets); (b) their
  sensitivity cannot be pinned deterministically, so the gate's cited number would be
  aspirational; (c) they grade fuzzy quality, not the structured `{object, cause}` identity
  match G1.2 pins. Retained as the *future* backend behind the `GraderClient` seam for G1.1.
- **Exact-match / string-equality graders.** Too brittle for free-text answers: an exact-match
  on the full answer string fails a correct answer that phrases the diagnosis differently. The
  chosen matcher is exact on the *object identity* (whole-token, case-normalized) but keyword-
  set on the *cause*, so a correctly-phrased answer passes while a wrong-object/wrong-cause
  answer fails — the middle ground exact-match misses.
- **Reusing `verify_shape`/the G0 geometry validators.** Wrong domain: those score geometry
  against hand-computed references, not a natural-language diagnosis against expected findings.
  The reused component here is the shared harness plumbing — the contracts `ValidationReport`
  shape, the FreeCAD-free `stats` Wilson-CI module, and the shared `merge_validators_yaml`
  read-merge-write — not a grader.

## Why nothing existing fit

The gate needs a **CI-reproducible, secret-free, source-hashable grader whose sensitivity is a
real deterministic number**, scoring the structured `{object, cause}` diagnosis G1.2 measures.
No surveyed LLM-judge framework meets the reproducibility bar, and exact-match is too brittle.
The ~90-line deterministic matcher meets all three, and the `GraderClient` protocol preserves
the upgrade path to a model grader without reworking the scorer or the fault suite (reuse-
before-invention: the harness plumbing is reused; only the grading rule is from-scratch, and
this survey records why).

## Scope limits of the deterministic grader (recorded, not hidden)

- **Negation / attribution is out of scope.** Cause matching is substring, so an answer that
  mentions a cause keyword only to deny it ("it is *not* an expression-binding problem") still
  matches. The deterministic grader does not claim negation-robustness; that judgment is deferred
  to the model grader behind `GraderClient`. The planted fault suite therefore contains no
  negated-cause case (adding one would honestly drop the deterministic grader below the bar —
  the limitation is documented here instead of faked).
- **The rubric is part of the validator.** The deterministic grader *encodes* the rubric's pass
  rule but does not *read* `rubric.md` at runtime (the rule is Python). To keep the design's
  rubric-versioning invariant (a rubric edit stales prior sensitivity runs, harness §6/§8), both
  `grader.py` AND `rubric.md` are hashed into `validator_sha` (in `score_grader.py` and the
  runner's `_VALIDATOR_SOURCES`, same file order), so editing the rubric's worked examples or
  keyword sets stales the score.
- **The suite validates the AND conjunction, not just each leg.** Wrong-object cases (right
  cause, wrong object) catch a cause-only grader; wrong-cause cases (right object, wrong cause)
  catch an object-only grader; an explicit AND-discriminator case (right object + a *different*
  diagnosis's cause keyword, own cause absent) catches an OR grader; the degenerate-suite guard
  (≥10 planted + ≥1 control, enforced in the scorer itself, not only in a pytest) prevents a
  vacuous sensitivity=1.0 / FA=0.0.

## Drives

- G1.E reuse-survey + grader-choice artifact (phase-gates entry-gate requirement).
- `benchmarks/g1/grader.py` deterministic-with-seam design; `score_grader.py` scoring it now.
- Story 2.2/2.3: the live-model grader plugs into `GraderClient`; its sensitivity run is a
  later ceremony.
