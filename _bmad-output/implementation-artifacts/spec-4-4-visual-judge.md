---
title: 'Story 4.4 — Visual Judge (`verify_visual`)'
type: 'feature'
epic: 4
story: '4-4-visual-judge'
created: '2026-09-14'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/decisions/010-claude-backend-live-eval-out-of-ci.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Done is defined as geometry ∧ visual (AD-21), and the visual half does not exist.
`benchmarks/g3/judge.py` is a seam that answers every call `visual.unavailable`, so every G3 part is
correctly not-done and G3.7 cannot be met. No repo code sends an image to a model API.

**Approach:** Land `verify_visual` as the conjunctive second leg: a vision-backed judge behind the
existing seam, its verdict validated against the schema story 4.1 fixed, mapped into the
`ValidationReport` as check `visual.judge`, with model independence enforced at preflight. Following
decision 010, the **live model call is operator-gated and skipped in unattended CI**; CI exercises
every deterministic part against a scripted double. The sensitivity number is a measured operator
run, never a green CI job.

## Boundaries & Constraints

**Always:**
- Fail closed. Render unavailable, drawing unavailable, or judge unreachable → the part is **not
  done**, reported as `visual.unavailable`. The only bypass is an explicit operator waiver, and the
  waiver is audit-logged with its reason. There is no silent pass and no default-true.
- The judge is never the actor. Preflight hard-fails `INVALID_INPUT` (exit 2) when the judge resolves
  to the same model id **and** context as any actor descriptor — check every actor block in
  `gate.yaml`, not just the first, the way the G1 preflight does.
- Model output is untrusted. Every verdict goes through `judge.validate_verdict` before any field is
  read; a malformed verdict is an error, never a pass. Temperature 0.
- Geometry stays authoritative. A drawing-callout-vs-spec mismatch is a **blocking finding** that
  triggers investigation, but it never overrides a passing deterministic measurement — findings are
  re-checked against `verify_*` before rework.
- The judge runs once per candidate part, at the end of a repair iteration whose geometry assertions
  **all pass**. Never on an iteration geometry already failed: the verdict is conjunctive, so it
  could not change the outcome, and spending a judge call there wastes the ≤3 repair budget.
- A judge failure counts as one repair iteration against the ≤3 cap.
- Judge images bypass the user-facing render budget and must meet the ≥2048 px floor. They travel to
  the judge API, not through client context.
- The judge registers in `_registry/validators.yaml` with its planted-fault suite. Editing the
  rubric or checklist stales the sensitivity run (same hash rule as every other validator).
- Secrets come from the environment only. No key in the repo, in a fixture, in a test, or in CI.

**Block If:**
- A live vision backend cannot be reached at implementation time (no credentials were available when
  this story was written). Do **not** stub a passing verdict to make the suite green. Build the full
  client, validation, preflight and fault suite; leave the live sensitivity run as an explicitly
  unmet, operator-gated step and say so plainly in the report. Decision 010 is the precedent:
  "Exit-green offline means the machinery is correct, not that the assistant passes."

**Never:**
- Never let the actor inspect its own render as a verdict source.
- Never report a sensitivity or false-alarm number that was not measured over real judge calls.
  `not_scored` with a reason is the honest record.
- Never treat a missing image, a timeout, or a transport error as a pass.
- Never implement the designer loop (4.5) or the parameter façade (4.6).
- Never commit a captured judge response as a fixture expectation without recording that it came
  from a model, not from an analytic derivation.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | full visual set + spec checklist, geometry passing | `{pass, findings}` validated, wrapped as `visual.judge` in the report | N/A |
| Judge unreachable | transport error or no credentials | `visual.unavailable`; part not done | Audit-logged; never a pass |
| Malformed verdict | model returns no `pass` field | `VerdictSchemaError`; part not done | Error surfaced, not swallowed |
| Same model as actor | judge id == actor id and context | Preflight refuses before any call | `INVALID_INPUT`, exit 2 |
| Geometry already failed | assertions failed this iteration | Judge is not called at all | No wasted repair budget |
| Callout mismatch | judge flags a dimension vs spec | Blocking finding; re-checked against `verify_*` | Geometry stays authoritative |
| Image below floor | page raster < 2048 px | Refuse to judge; `visual.unavailable` | Never judge an illegible image |
| Operator waiver | explicit waiver flag set | Part may proceed, waiver audit-logged with reason | Waiver recorded, never implicit |

</frozen-after-approval>

## Code Map

- `benchmarks/g3/judge.py` -- the seam to implement behind. `CHECK_ID = "visual.judge"`,
  `UNAVAILABLE_CODE`, `SEVERITIES`, `VIEWS`, `MIN_PAGE_WIDTH_PX = 2048`, `validate_verdict`,
  `JudgeUnavailable`, `VerdictSchemaError`. The schema already exists — do not redefine it.
- `benchmarks/g3/gate.yaml:37-44` -- the `visual_judge:` block: model, context, temperature,
  implementation, verdict schema, check id, min page width.
- `benchmarks/g3/fault-injection/visual-judge/` -- 8 cases (5 planted, 3 controls) authored before
  the judge existed. These are what measure it; do not edit them to fit the implementation.
- `benchmarks/harness/actor.py` -- the `Backend` seam epic 2 used to keep live model calls out of
  CI. Reuse this pattern rather than inventing a second one.
- `benchmarks/g1/grader.py` + `benchmarks/g1/actor_run.py` -- the working precedent for
  operator-gated live runs with a deterministic double in CI.
- `docs/decisions/010-claude-backend-live-eval-out-of-ci.md` -- the governing decision; read it
  before choosing where the live call lives.
- `src/freecad_buddy/adapters/` -- where an external-process model client belongs (third-party deps
  are legal here, never in `usecases/`).
- `src/freecad_buddy/adapters/audit_log.py` -- where the waiver record is written.
- `benchmarks/_registry/validators.yaml` -- the `visual_judge` row story 4.1 created, currently
  `not_scored` with a stated reason. This story either measures it or updates the reason.
- `benchmarks/g3/fault-injection/score_g3_validators.py` -- the scorer that reads the suite.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/adapters/visual_judge_client.py` -- the vision client behind the seam:
      builds the request from the standard visual set, temperature 0, reads credentials from the
      environment only, and maps transport failure to `JudgeUnavailable`.
- [x] `src/freecad_buddy/usecases/verify_visual.py` -- the use case: assemble the visual set, call
      the judge through the seam, validate the verdict, wrap it as check `visual.judge` in the
      `ValidationReport`, and enforce the fail-closed rule.
- [x] `src/freecad_buddy/usecases/verify_visual.py` -- the ≥2048 px legibility gate: refuse to judge
      an image below the floor rather than judging it anyway.
- [x] preflight independence guard -- hard-fail when the judge resolves to the same model id and
      context as **any** actor descriptor; extend the existing G1-style check rather than copying it.
- [x] `src/freecad_buddy/contracts/` -- the verdict wire type and its schema, regenerated.
- [x] `benchmarks/harness/` -- a deterministic judge double for CI, replaying fixed verdicts so the
      wiring, the fail-closed path and the report shape are all provable without credentials.
- [x] `tests/external/test_verify_visual.py` -- every matrix row: unreachable, malformed verdict,
      same-model refusal, geometry-already-failed skip, below-floor refusal, waiver audit record.
- [x] `_registry/validators.yaml` -- record the measured sensitivity if a live run was possible, or
      an updated `not_scored` reason naming exactly what is missing.
- [x] `docs/decisions/017-visual-judge-live-run-gating.md` -- record where the live call runs, why it
      is out of CI, and what an operator must do to produce a citable sensitivity number.

**Acceptance Criteria:**
- Given no credentials, when `verify_visual` runs, then the check reports `visual.unavailable`, the
  part is not done, and no test asserts a passing judge verdict.
- Given a judge configured with the actor's model id and context, when preflight runs, then it
  refuses with `INVALID_INPUT` before any model call is made.
- Given a malformed verdict, when it is received, then `VerdictSchemaError` is raised and the part is
  not done.
- Given an iteration whose geometry assertions failed, when the loop reaches the visual leg, then the
  judge is not called.
- Given an operator waiver, when a part proceeds without a judge verdict, then the audit log carries
  the waiver and its stated reason.
- Given the full suites, when run, then the in-FreeCAD and external baselines do not regress.

## Implementation Notes

**The ≥2048 px floor did not need the user-facing render cap raised.** The G3 README recorded two
caps as blockers (`usecases/screenshot.py:34` `_MAX_DIM = 1920` and `hosts/tool_catalog.py:202-203`).
Both are on the *user-facing* path, and AD-21 puts judge images outside that budget because they
travel to the judge API rather than through client context. `verify_visual` therefore builds its own
`SceneSpec` at the floor width and hands it to the `RenderPort` directly; `RenderPort.render` takes
the scene's size verbatim, so nothing was widened and the client-context budget the cap protects is
untouched. Both caps stay at 1920.

**The legibility gate measures the produced image, not the request.** `_png_width` reads the IHDR
chunk off the written file. A gate reading a requested width would pass an image a renderer silently
produced smaller, which is the failure the floor exists to prevent. An unreadable file reports width
0 and is refused.

**The drawing sheet is composed before the registry call, not inside it.** `DocumentRegistry`'s lock
is a non-reentrant `threading.Lock`, and `techdraw_for_judge` calls `with_document` itself, so
nesting the two would deadlock. The sheet is built first through its own registry call; the 3D
renders then run in a second one.

**The two independence rules differ, deliberately.** `_preflight_independence` in
`benchmarks/runner.py` is one traversal of the actor descriptors serving both guards: `grader`
collides on the model id alone (NFR1 — a different context does not make the same model an
independent grader of its own text), while `visual_judge` collides only when model **and** context
both match (AD-21 — the judge is independent with "a separate model id *or* a separate context").

**`validate_verdict` exists twice, and a test holds the two together.** The ring rule forbids
`usecases/` importing `benchmarks/`, and the entry-gate seam must keep its own copy — it is the
artifact the fault cases were authored against. `test_Should_accept_and_reject_identically_When_both_validators_see_one_verdict`
runs both implementations over one 13-member corpus and asserts they agree, so a divergence breaks a
test rather than splitting the schema silently. The test was confirmed falsifiable by mutating one
validator.

**The judge's `validator_sha` covers three files**, in both `runner.py` and
`score_g3_validators.py`: the entry-gate seam, the use case, and the client. AD-19 requires a rubric
edit to stale the recorded sensitivity, and the rubric is a module constant in the client, so the
client's bytes must be in the digest. This was observed working — adding the two files changed the
digest and `test_g3_gate.py` failed until the registry row was re-scored.

## Spec Change Log

## Review Triage Log

## Design Notes

**No credentials were available when this story was specified.** That was measured, not assumed: the
environment carries no Anthropic or OpenAI key. The story is therefore scoped so everything except
the live call is provable offline — client construction, schema validation, the independence guard,
the fail-closed path, the waiver record, and the report shape. The one thing that cannot be faked is
the sensitivity number, and per decision 010 it must not be.

**Why the judge cadence is pinned.** Running the judge on an iteration whose geometry already failed
cannot change the conjunctive verdict, and each judge failure costs one of only three repair
iterations. Calling it there burns budget for no information.

## Verification

**Commands:**
- `uv run pytest tests/external/test_verify_visual.py -q` -- expected: all matrix rows pass
- `uv run pytest tests/external -q` -- expected: no regression
- `python tests/run_tests.py` (H1 `fcb` env) -- expected: no regression
- `uv run python -m benchmarks.runner faults G3` -- expected: `visual_judge` either scores from a
  real operator run or records an honest `not_scored` reason
- `python scripts/check_imports.py` -- expected: exit 0 (no third-party client imported in `usecases/`)
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift
