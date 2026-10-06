---
id: SPEC-freecad-buddy
companions:
  - phase-gates.md
  - ../../planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md
  - ../../../docs/intent.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# FreeCAD Buddy — Phase Goals & Agent-Validatable Gates

## Why

A vision to realize plus an opportunity to capture: FreeCAD is fully scriptable and headless-capable, so an agent speaking its Python API through MCP can do — and *verify* — everything a human does. This repository ships the tools and the verification, never the agent: the design loop, the judgement and the workflow live in whatever agent drives the bridge, carried in skills. The single most likely failure mode is the agent believing it did well when it did not; therefore every phase goal in this contract is a machine-checkable gate whose validators exist and are fault-tested *before* phase implementation, and whose verdict an AI agent can compute by running deterministic checks and reading their reports — never by grading its own output.

## Capabilities

- **CAP-1** — Bridge (Phase 0)
  - **intent:** A programmatic client can drive FreeCAD (documents, geometry queries, exports) and verify resulting geometry via MCP tools, identically in-GUI and headless.
  - **success:** Gate **G0** passes (phase-gates.md), incl. ≥15 schema'd tools, 5 golden models verified ±0.1 %, ≥30 CI tests green on the FreeCAD 1.1.x CI leg.
- **CAP-2** — Assistant (Phase 1)
  - **intent:** A user can ask about the open document — feature tree, selected objects, recompute errors, next-tool guidance — and get correct answers from read-only tools.
  - **success:** Gate **G1** passes: ≥80 % on the 50-question eval graded by an independent grader against a written rubric; error diagnosis ≥8/10 at n=10 (30-case set, escalates to n=30 on 10/10); two LLM backends.
- **CAP-3** — Copilot (Phase 2)
  - **intent:** A user can issue one natural-language modeling command; the system previews a structured diff, executes on confirmation, auto-verifies, and rolls back provably on failure.
  - **success:** Gate **G2** passes: ≥85 % on the 40-command benchmark, 100 % auto-verify with rollback, undo hash-exact, TNP guard 5/5, sketches `FullyConstrained` ≥90 %.
- **CAP-4** — Spec-to-part (Phase 3)
  - **intent:** An agent turns a written part spec into a clean parametric part: it plans, builds through the mutation tools, measures the result against compiled spec assertions, looks at the rendered views, and repairs until both channels agree. The loop is the agent's, carried in the `design-loop` skill; this repository supplies the assertion primitives, the render and drawing path, and the checklist.
  - **success:** Gate **G3** passes: ≥70 % of the spec set produces a passing part within ≤3 repairs on the sealed held-out split; every part valid/watertight/DoF-0/parameter-editable; the corrupted-plan suite detects ≥9/10 spec violations.
- **CAP-5** — Unattended operation (Phase 4)
  - **intent:** An operator starts an agent against the headless bridge and leaves. The agent holds the loop and delegates by spawning subagents; the bridge makes the run safe and auditable when nobody is watching — every reported field a re-executed check, every mutation in an append-only log, every artifact reconstructable from the run workdir alone.
  - **success:** Gate **G4** passes: the spec-set rate is maintained with no human in the loop; revisions ≥70 % with the geometry diff confined to the requested change; a full build → inspect → revise → accept cycle completes without human input; every failure is a structured status, never silent.
- **CAP-6** — Skills library
  - **intent:** Any LLM harness can load curated CAD skills — Track A operating knowledge, Track B design thinking, Track W workflow (`design-loop`, `visual-review`, `spec-to-assertions`) — that measurably improve benchmark outcomes. The catalogue is 15 skills: 12 Track A+B plus the three Track W. The workflow lives here rather than in code, so this library is the load-bearing deliverable.
  - **success:** Gate **GS** passes: all 15 skills authored and dual-harness loadable; ≥8 of the 12 Track A+B show statistically significant lift under the AD-14 rules. Track W is validated by the benchmark running at all rather than by an ablation delta — without `design-loop` there is no loop to measure.
- **CAP-7** — Validation harness
  - **intent:** For every phase, an executable gate exists — benchmark + assertions + fault-injection suite + report schema — that an AI agent can run to compute the phase verdict.
  - **success:** Each phase's entry gate (AD-19) lands before its implementation: benchmark fails honestly against a stub; validator sensitivity ≥95 % and false-alarm ≤5 % proven on planted faults.
- **CAP-8** — Robot-description export & part sourcing (Phase 5)
  - **intent:** A parametric assembly exports to URDF and SDF — links, joints, limits, inertials from native mass properties, collision and visual meshes — and off-the-shelf STEP parts are sourced and placed through the bridge with their mating frames measured rather than assumed.
  - **success:** Gate **G5-robot** passes: every export completes only through a paired re-parse + schema + kinematic-tree sanity check; the mm/deg→m/kg/rad conversion is explicit and every origin records its frame.
- **CAP-9** — Viewport & render correctness
  - **intent:** When the bridge reports that the human can see the model, the human can see it; when it cannot, the agent is handed a measured number rather than a success it must not trust. A render from any camera shows the part rather than a white rectangle, and the bridge leaves no files behind.
  - **success:** Framing verdicts come from one shared projection that the fit factor and the verdict both use; `fitted: true` requires the post-fit verdict to agree; every named camera renders a face tone separable from the background; temp files are created inside the session workdir the sweep can reach.

## User journeys

Four people touch this system. Each journey names the real tools and skills it uses, then the
failures it must survive — a journey that cannot fail is not telling you anything.

In every journey the agent reaches the tools only through MCP. There is no in-process path into the
use-case layer.

### J1 — CAD user, FreeCAD open

They open FreeCAD. The addon starts the RPC listener and spawns the MCP proxy; that is the entire
setup. In a side window they talk to their agent, which loads the skills library, calls
`query_tree_summary` to orient itself in the open document, and answers or acts. When the ask is a
change, the agent calls `preview_dry_run`, shows the structured diff, and applies it on confirmation
through a typed `sketch_*`/`feature_*` tool. When the operator has set auto-approve, the agent
applies the typed tool directly; the same checks and rollback run, and the preview stays available.
When the ask is a whole part, the same conversation runs
longer: the agent plans, builds, measures with `verify_*`, looks at the rendered views, and repairs —
`design-loop` tells it how, and `visual-review` tells it what to look for. Asking a question,
executing one command, and building a part are one continuum, not three products.

*Failures it must survive:* an operation that runs without error and produces the wrong geometry —
caught because `verify_*` re-measures the artifact rather than trusting the agent's account; a fast
FreeCAD restart leaving a stale proxy on the port, which must surface as an error and never as a
silent reuse; the agent calling a part done without ever looking at it, which only the evidence in
the run workdir reveals.

*Exercises:* CAP-1, CAP-2, CAP-3, CAP-6.

### J2 — Operator, unattended

They start an agent against the headless bridge and walk away. Nothing in this repository schedules,
supervises, or parallelizes that run: the agent holds the loop, and spawns subagents itself if the
work fans out. They come back to a part, exports, an audit log of every mutation, and a run workdir
that reconstructs the whole run without the agent's context.

*Failures it must survive:* a crash in the geometry kernel taking down the process the agent drives —
this repository ships no isolation boundary of its own, so the operator's environment is the
boundary and the audit log is what makes the failure legible; a long run accumulating memory with no
recycle point; a plausible-looking report over a bad part, which is why every field in a validation
report is a re-executed check rather than an echoed claim.

*Exercises:* CAP-1, CAP-6, CAP-7.

### J3 — Skill author

They write or revise a skill, then run a benchmark with and without it and read the per-skill delta.
Because the workflow lives in skills rather than in code, this is the loop by which the system
actually improves — a better `design-loop` is a better product, with no release.

*Failures it must survive:* a skill that reads as authoritative and moves no number, which the
ablation cut rule exists to remove; a helper script drifting from answering one question into
deciding the next action, at which point it has become the loop wearing a script's clothes; a skill's
claims going stale against a FreeCAD version bump, which the recorded verification version catches.

*Exercises:* CAP-6, CAP-7.

### J4 — Contributor extending the tool surface

They add a typed FreeCAD operation. It goes in the ring its dependencies allow, every mutation runs
the uniform transaction protocol so it can prove its own rollback, and its entry gate lands before
the implementation it grades.

*Failures it must survive:* an import reaching across a ring boundary, which CI refuses; a mutation
that skips the protocol and cannot prove it rolled back; reasoning creeping into the source tree
because it was convenient in the moment — the test is whether the repository would behave differently
depending on which model is talking to it.

*Exercises:* CAP-1, CAP-7.

## Constraints

- The architecture spine's ADs bind all implementation (adopted companion); load-bearing here: no AI workflow in shipped code (AD-35), typed-tools-only mutation (AD-4), uniform mutation protocol with hash-proven rollback (AD-5/6), TNP audit (AD-7), `FullyConstrained` as the sketch pass signal (AD-8), Validation Design Gate ordering (AD-19).
- The agent reaches the tools only through MCP. No in-process path into the use-case layer exists, for any caller.
- Pass/fail is computed by deterministic harness code or an independent grader — the producing agent's self-assessment is never a result (AD-13).
- A phase may not start until the previous phase's gate is fully green; phase implementation may not start until its entry gate lands (AD-19).
- All gate runs execute headless in CI on the FreeCAD 1.1.x CI leg (AD-11); a check that only passes in-GUI does not count.
- Statistics rules (AD-14): majority-of-R scoring, Wilson 95 % CI beside every rate, exact McNemar for ablations, dev/held-out gap >15pp blocks exit.
- Benchmark artifacts only from commercial-clean, documented real-world provenance (AD-16).
- Solo part-time development; phase timeboxes are durations, not dates.

## Non-goals

- Training or fine-tuning custom ML models — existing LLMs via API/local inference only.
- CAM/toolpath generation, photorealistic rendering, cloud multi-tenant SaaS.
- An agent harness, a chat UI, a model client, or a job/worker service of our own. The operator brings the agent; this repository brings the tools.
- Phase 5 topics (assemblies, FEM loops, reverse engineering) until scoped after the Phase 2 retrospective.
- Fully removing humans from gate verdicts — audit sampling and rubric authorship stay human (see phase-gates.md §Global protocol).

## Success signal

An agent loaded with the skills library completes a full build → inspect → revise → accept cycle against the headless bridge with no human in the loop, while the sealed held-out spec set holds ≥70 % — measuring with `verify_*`, reading the rendered views, repairing what it finds, and stopping because the measurements say so, with no design logic anywhere in this repository. That is the moment "FreeCAD as a design tool an AI agent can drive" becomes demonstrable rather than claimed, and it is demonstrable on whatever agent the operator brings.

## Assumptions

- Gate check runners live in `benchmarks/` and emit the contracts-owned `ValidationReport` (AD-17); exact runner CLI shape is an implementation detail downstream stories fix.
- Phase 1's "cite FreeCAD documentation" capability resolves at the Phase 1 entry gate (deferred in spine) without changing gate G1's criteria.

## Open Questions

_(none open)_

## Resolved Questions

- **G1.2 / GS.4 eval size — tiered n=10→n=30 (resolved 2026-07-24).** Author a full 30-case fixture set, but gate on a two-tier run: the gate first grades **n=10**; only when the n=10 result is **100% (10/10)** does it escalate to the full **n=30** run, reporting the Wilson CI on the n=30 result. If n=10 is below 10/10 the gate concludes at n=10 (no n=30 escalation) with the n=10 Wilson CI flagged low-confidence per AD-14. This keeps the cheap path cheap and spends the extra 20 cases only when the assistant has earned statistical scrutiny.
