# 017 — The Visual Judge's Live Call Is Operator-Gated, Out of CI

## Decision

The visual leg's **live vision-model call is operator-gated and skipped in unattended CI**, the
same boundary decision 010 drew for the G1 actor and decision 011 for the local ReAct eval.

The judge client (`src/freecad_buddy/adapters/visual_judge_client.py`) **injects its transport**,
exactly as the ReAct adapter injects its chat transport. The repo therefore carries no model SDK,
no HTTP dependency, and no credential. The client reads `FREECAD_BUDDY_JUDGE_API_KEY` from the
environment and nowhere else; with the variable unset, `available()` reports the absent credential
and `verify_visual` reports `visual.unavailable` — the part is **not done**.

CI exercises every deterministic part of the leg against `benchmarks/harness/judge_double.py`'s
`ScriptedJudge`: the request build, the temperature-0 pin, the schema validation, the fail-closed
path, the ≥2048 px legibility gate, the geometry-already-failed skip, the waiver record, and the
report shape. It never asserts a passing judge verdict.

The G3.7 sensitivity number is a **measured operator run**, never a green CI job.
`benchmarks/_registry/validators.yaml` records `visual_judge` as `not_scored` with a reason naming
both gaps until that run happens.

## Rationale

- **The key cannot be a CI secret.** Harness-design §6 makes API keys human-only. A live vision
  call needs one, so a green unattended job can never be the thing that asserts the judge works.
  This is the identical constraint decision 010 resolved for the actor.
- **Never fake the number.** The scripted judge replays whatever verdict its script carries,
  including `pass: True`. That deliberately does **not** stand in for model quality: a green
  offline run means the machinery is correct, not that a model passed a part. Reporting a
  sensitivity measured over a double would be the exact fabrication AD-19 forbids.
- **Injected transport keeps one code path.** A bespoke SDK client would be a second path the
  operator's run does not exercise, and it would pull a model dependency into a repo that has
  deliberately avoided one twice already (decisions 010, 011).
- **The rubric is part of the validator.** AD-19's staleness rule says editing the rubric or
  checklist invalidates prior sensitivity runs. The rubric is a module constant in the client, and
  the client's bytes are folded into `visual_judge`'s `validator_sha` by both
  `benchmarks/runner.py` and `score_g3_validators.py`, so a rubric edit stales the score
  mechanically rather than by anyone remembering to.

## Where the live call lives

| Leg | Runs where | Needs a key |
| --- | --- | --- |
| Request build, schema validation, fail-closed path, legibility gate, report shape | CI, against `ScriptedJudge` | no |
| The model call itself | an operator's machine, `FREECAD_BUDDY_JUDGE_API_KEY` set, transport wired | yes |
| The recorded sensitivity | written to `_registry/validators.yaml` from that operator run | yes |

## What an operator must do to produce a citable sensitivity number

1. Set `FREECAD_BUDDY_JUDGE_API_KEY` in the environment. Never in a file in the repo.
2. Set `FREECAD_BUDDY_JUDGE_MODEL` to the exact vision model id used. It must not match any
   `actor*` descriptor's model **and** context in `benchmarks/g3/gate.yaml` — the preflight guard
   (`_preflight_independence`) refuses with `INVALID_INPUT`, exit 2, before any call is made.
3. Construct `VisualJudgeClient` with a transport that reaches that model.
4. Drive the 8 `g3/fault-injection/visual-judge/` cases — 5 planted defects, 3 clean controls.
   Each needs a driveable fixture, which means a part built through the designer loop (story 4.5);
   until that exists the cases stay `fixture: pending` and the run is not possible.
5. Re-run `score_g3_validators.py`. It writes the measured sensitivity and false-alarm with a
   Wilson CI, replacing the `not_scored` reason.

Both gaps must close. Driveable fixtures without a live call measures nothing; a live call without
fixtures has nothing to measure.

### Correction (2026-09-14): this decision governs the IN-LOOP judge, not every judge

As originally written this note was read — by several implementation stories and by the orchestrating
agent — as meaning the 8-case fault suite could not be graded at all without an API credential. That
is wrong, and the operator corrected it.

Two different things were conflated:

- **The in-loop judge.** `usecases/verify_visual.py` is called automatically inside the designer
  loop, which runs headless in the benchmark harness with no agent attached. It genuinely needs a
  programmatic client and therefore a credential. Everything above applies to it unchanged.
- **Grading the fault suite.** That is 8 images — 5 planted defects, 3 controls — inspected **once**,
  offline, against a fixed rubric. A vision-capable agent can look at a rendered PNG directly. No
  client, no credential, no CI involvement. Nothing in this decision forbids it, and the "measured
  operator run, never a green CI job" rule is satisfied: an agent inspecting images under operator
  direction *is* the operator run, and it is not a CI job.

The precedent already existed in this epic: DW-121 (judge-sheet callouts paired with views that
cannot display their axis) was found by rendering a sheet and looking at it, after every automated
assertion in that story had passed.

**Independence caveat that must travel with any number produced this way.** AD-13 requires the judge
not be the actor. An agent that also drove the designer loop is not a fully independent judge. For
the fault suite the exposure is limited — the planted parts were authored before any judge existed,
and the grading is of planted defects against a fixed rubric rather than of the agent's own output —
but the caveat is recorded beside the score rather than glossed. A fully independent number still
requires a separate model or a separate context.

## Boundaries

- No API key or model secret ever enters CI, an env file, a fixture, a test, or the repo.
- Temperature is pinned at 0 in the client and is not a parameter. A caller able to raise it could
  make the same part pass on a re-run, which would make G3.7 unreproducible.
- The judge never validates its own output: `VisualJudgeClient.judge` returns the parsed mapping
  untouched, and `usecases/verify_visual.validate_verdict` is what rejects a malformed verdict.
  A client that validated would be free to repair a broken verdict into a passing one.
- The judge is never the actor. `_preflight_independence` checks the `visual_judge:` block against
  **every** actor descriptor — the `actor:` key, any additional `actor*` key, and every `actors:`
  list entry.

## The two independence rules differ, on purpose

| Guard | Collides when | Why |
| --- | --- | --- |
| `grader` (NFR1, harness §8) | the **model id** matches | a different context does not make the same model an independent grader of its own text |
| `visual_judge` (AD-21, verification-design §7a) | the model id **and** the context both match | the judge is independent with "a separate model id **or** a separate context"; it reads images, not its own prose, and a fresh context with no build history is the separation that buys |

Both are enforced by one traversal of the actor descriptors in
`benchmarks/runner.py::_preflight_independence`, so a second backend cannot slip a collision past
either guard by declaring itself under a different key.

## Drives

- `adapters/visual_judge_client.py` (injected transport, env-only credential, temperature 0).
- `usecases/verify_visual.py` (fail-closed rule, legibility gate, `visual.judge` report).
- `benchmarks/harness/judge_double.py` (the CI double).
- The `visual_judge` row in `_registry/validators.yaml`, `not_scored` until an operator run.
