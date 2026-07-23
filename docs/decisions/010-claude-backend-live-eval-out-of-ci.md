# 010 — Claude Backend Is the MCP Client; Its Live Eval Is Operator-Gated, Out of CI

## Decision

The Phase-1 "Claude backend" is the **MCP client** — Claude Code / Claude Desktop driving the
registered read-only tools over MCP — not a bespoke Anthropic-SDK agent loop inside the repo.
Story 2.2 ships the read-only assistant **profile** those clients register
(`READ_ONLY_PROFILE` + `build_readonly_profile` in `hosts/tool_catalog.py`) and the **actor-run
harness** that runs the G1 eval through a `Backend` seam (`benchmarks/harness/actor.py`,
`benchmarks/g1/actor_run.py`). It hand-rolls no live model client.

The **live-model eval run is operator-gated and skipped in unattended CI.** A live run is an
operator wiring the bridge into an MCP client and running the eval; it needs an API-capable
backend + key, which cannot be an unattended-CI green (harness-design §6: keys are human-only).
CI instead exercises the read-only profile, the tiered n10→n30 escalation, the grader wiring, the
summarized-tree usage, and the report shape against a deterministic `ScriptedBackend` double. The
≥80% pass-rate is a **measured operator run**, never asserted by a green job (the hard gate is the
Story 2.4 sealed exit).

## Rationale

- **Reproducible-without-secrets, same discipline as Story 2.1.** 2.1 shipped a *deterministic*
  grader precisely so the entry gate is reproducible in CI without secrets or network. The same
  constraint binds the actor: a live Claude eval needs a key, so it cannot be the thing a green CI
  job asserts. Everything deterministic (profile, escalation, grader wiring, honest-fail) is
  CI-tested offline; only the live pass-rate is deferred to an operator.
- **Never fake the number.** The offline scripted backend replays *correct* answers so the harness
  proves escalation + report build + Wilson CI end-to-end — it deliberately does not stand in for
  model quality. Exit-green offline means "the machinery is correct", not "the assistant passes".
- **Read-only guarantee is a profile invariant (G1.6).** The profile is an explicit read-only
  allow-list, not a `mutating=False` negation: `document_open`/`close`/`list` carry
  `mutating=True` yet are the non-geometry lifecycle the assistant needs to load a fixture. The
  geometry-mutation set (`feature_*`/`sketch_*`/`preview_*`/`document_create`/`document_save`/
  `debug_exec`) is absent by construction and asserted absent by
  `tests/external/test_assistant_readonly_profile.py`.
- **Same tool surface as production.** The actor drives the profile `MethodRegistry` built by the
  shared catalog, never a private code path — the assistant sees exactly what the MCP server
  surfaces.

## Reuse survey (MCP client-as-actor vs custom loop)

- **Surveyed: a bespoke Anthropic-SDK agent loop in-repo.** Rejected as the actor: the design's
  Claude backend is the MCP client (integration-mcp-clients §2/§6), so a custom SDK loop would be
  a second, divergent code path that does not exercise the client wiring the operator actually
  runs. It would also pull a model-client dependency and a key into the harness — the exact CI
  secret the boundary forbids.
- **Surveyed: reuse Story 2.1's `DeterministicGrader` via the `GraderClient` seam.** Adopted
  wholesale — the actor-run grades every answer through `grade(question, answer, rubric, expected)`
  and maps `pass_=True→OK` / `pass_=False→SPEC_FAILED`. No new grader, no new `contracts/` type;
  the actor-run builds the same `ValidationReport` the stub path does.
- **Surveyed: reuse the existing Wilson CI + stats helpers (`usecases/stats.py`) and the tiered
  fixtures (decision 008).** Adopted — the harness computes the per-tier Wilson CI with the shared
  helper and reads the committed `tier: n10|n30` metadata; it forks none of them.

## Boundaries

- No API key or model secret ever enters CI, env files, or the repo. The live path is gated behind
  `FREECAD_BUDDY_G1_ACTOR_BACKEND=live`, which is **not wired** in this harness — it exits with a
  clean operator-gated usage error rather than a fake green.
- Grading is done only by the independent Story 2.1 grader through the `GraderClient` seam; the
  actor never grades itself (the runner's actor≠grader preflight still hard-fails on collision).

## Drives

- The read-only profile + actor-run harness + gate.yaml `actor:` pin (`claude-mcp-client`).
- The CI `arch-checks` offline actor-run + profile test (live eval skipped, no secrets).
- The Story 2.4 sealed exit is where the measured ≥80% operator run is recorded, not here.
