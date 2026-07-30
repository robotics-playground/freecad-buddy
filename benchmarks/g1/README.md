# G1 Entry Gate — Phase-1 Read-Only Assistant grading machinery

This suite is the AD-19 entry gate for Phase 1: the eval set, broken-doc fixtures, rubric, and
independent grader land and fail honestly against a stub assistant BEFORE any assistant code
(Stories 2.2/2.3), so answer quality is decided by a validated grader, never the assistant
(NFR1).

## Layout

- `gate.yaml` — declarative G1.1–G1.6 mirror of `phase-gates.md`; top-level `actor:` / `grader:`
  config blocks (distinct model ids — the runner's G1 preflight hard-fails on identity),
  `required_tokens: [rubric_review, spot_audit]`, `verdict.heldout: sealed`.
- `grader.py` — the independent **deterministic** expected-findings grader (`DeterministicGrader`)
  + the `GraderClient` protocol seam a model-backed grader plugs into later. FreeCAD-free,
  stdlib-only, CI-reproducible (no network, no LLM).
- `rubric.md` — human-authored grading rubric with worked pass/fail examples (the object-identity
  + cause-match rule the deterministic grader encodes). Reviewed at exit (`rubric_review` token).
- `dev/eval-questions.yaml` — 50 hand-authored questions with independent expected findings
  across tree-explanation / error-diagnosis / next-tool-guidance (FR7).
- `dev/broken-docs/<case>/` — 30 broken-recompute fixtures, each `case.yaml` naming *the* failing
  object + cause; `build_broken_docs.py` is the deterministic FreeCADCmd generator. It rebuilds
  only when `FREECAD_BUDDY_BUILD_BROKEN_DOCS=1` is in the environment — POSIX
  `FREECAD_BUDDY_BUILD_BROKEN_DOCS=1 FreeCADCmd build_broken_docs.py`, PowerShell
  `$env:FREECAD_BUDDY_BUILD_BROKEN_DOCS="1"; FreeCADCmd build_broken_docs.py`. Importing the
  module never rebuilds, for any `sys.argv` — asserted in `tests/infc/test_broken_docs_g1.py`.
- `dev/fixtures/` — small shared read-only `.FCStd` fixtures for eval questions that need a
  concrete document (currently empty; error-diagnosis questions use the broken-docs fixtures).
- `fault-injection/<case>/case.yaml` — planted confident-wrong + clean-correct control text
  cases (no `.FCStd`): wrong-object, wrong-cause, vague, an AND-discriminator (right object +
  another diagnosis's cause), plus controls incl. an alternate-keyword control. `score_grader.py`
  grades them and scores the grader's sensitivity/FA (≥10 planted + ≥1 control enforced in the
  scorer; a degenerate suite raises rather than passing vacuously).
- `heldout/` — sealed placeholder (no live cases; no age/SEAL machinery — that lands at Gate G1
  exit, Story 2.4). CI never sweeps it.

## Tiered n10 → n30 rule (decision 008)

The 30 broken-doc fixtures are tagged `tier: n10` (10) / `tier: n30` (20). The n10 slice spans
**all four break kinds** (over-constrained sketch, broken expression, pad-missing-sketch,
cut-missing-tool) — 3 oc + 3 pd + 2 be + 2 cut — so no kind is absent from the first pass
(asserted in `test_broken_docs_inventory_tiered_30`). Story 2.2's actor run grades the first n=10 and
escalates to the full n=30 **only** on a perfect 10/10; below-perfect concludes at n=10 with the
n=10 Wilson CI (low-confidence flag, AD-14). This story only lands + tiers the set; it does not
run the assistant against them.

## Grader verdict (harness §8)

`GraderVerdict = {pass_, matched_expected, rationale}` — a structured dataclass (no new
`contracts/` wire type is added by this story). The fault scorer maps each verdict into a
contracts `ValidationReport` and computes sensitivity / false-alarm + a Wilson CI. A planted
confident-wrong answer (`DETECT`) is *detected* when the grader FAILs it (`pass_ == False`); a
clean-correct control is a *false alarm* when the grader FAILs it. `grader.py`, `rubric.md` AND the
suite's `case.yaml` set are hashed into `validator_sha` in `_registry/validators.yaml` (a rubric
edit stales the score; so does a case edit, even one that leaves the rate unchanged), so the score
is citable only while the grader, rubric and suite are unedited. After changing any of the three,
re-run `score_grader.py` without `--check` to refresh the committed block.

## Forward note (Stories 2.2/2.3)

The **live-model grader** (for fuzzier G1.1 answer-quality judgment) and the **real read-only
actor run** land in Stories 2.2/2.3. This story ships the deterministic grader (scorable now) and
the seam; `gate run g1` (non-stub actor run) is Story 2.2. Only `--gate G1 --stub` (honest FAIL)
and `faults G1` (grader sensitivity) run here.
