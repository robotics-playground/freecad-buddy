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

A vision to realize plus an opportunity to capture: FreeCAD is fully scriptable and headless-capable, so an AI layer speaking its Python API through MCP can do — and *verify* — everything a human does, maturing from read-only assistant to autonomous design service. The single most likely failure mode is the agent believing it did well when it did not; therefore every phase goal in this contract is a machine-checkable gate whose validators exist and are fault-tested *before* phase implementation, and whose verdict an AI agent can compute by running deterministic checks and reading their reports — never by grading its own output.

## Capabilities

- **CAP-1** — Bridge (Phase 0)
  - **intent:** A programmatic client can drive FreeCAD (documents, geometry queries, exports) and verify resulting geometry via MCP tools, identically in-GUI and headless.
  - **success:** Gate **G0** passes (phase-gates.md), incl. ≥15 schema'd tools, 5 golden models verified ±0.1 %, ≥30 CI tests green on the 1.0/1.1 matrix.
- **CAP-2** — Assistant (Phase 1)
  - **intent:** A user can ask about the open document — feature tree, selected objects, recompute errors, next-tool guidance — and get correct answers from read-only tools.
  - **success:** Gate **G1** passes: ≥80 % on the 50-question eval graded by an independent grader against a written rubric; error diagnosis ≥8/10; two LLM backends.
- **CAP-3** — Copilot (Phase 2)
  - **intent:** A user can issue one natural-language modeling command; the system previews a structured diff, executes on confirmation, auto-verifies, and rolls back provably on failure.
  - **success:** Gate **G2** passes: ≥85 % on the 40-command benchmark, 100 % auto-verify with rollback, undo hash-exact, TNP guard 5/5, sketches `FullyConstrained` ≥90 %.
- **CAP-4** — Designer (Phase 3)
  - **intent:** The system turns a written part spec into a clean parametric part, measuring the result against spec assertions and self-repairing until they pass.
  - **success:** Gate **G3** passes: ≥70 % of 20 specs within ≤3 repairs on the sealed held-out set; every part valid/watertight/DoF-0/parameter-editable; corrupted-plan detection ≥9/10.
- **CAP-5** — Autonomous service (Phase 4)
  - **intent:** Any agent or human submits a spec to a headless job API and receives a validated model, exports, and a validation report; revisions preserve unrelated geometry.
  - **success:** Gate **G4** passes: Phase 3 rate maintained headless; revisions ≥70 % with confined diffs; agent-to-agent cycle without human input; 50-job soak clean.
- **CAP-6** — Skills library
  - **intent:** Any LLM harness can load curated CAD-judgment skills (Track A operating knowledge + Track B design thinking) that measurably improve benchmark outcomes.
  - **success:** Gate **GS** passes: 12 skills authored and dual-harness loadable; ≥8/12 show statistically significant lift under the AD-14 rules.
- **CAP-7** — Validation harness
  - **intent:** For every phase, an executable gate exists — benchmark + assertions + fault-injection suite + report schema — that an AI agent can run to compute the phase verdict.
  - **success:** Each phase's entry gate (AD-19) lands before its implementation: benchmark fails honestly against a stub; validator sensitivity ≥95 % and false-alarm ≤5 % proven on planted faults.

## Constraints

- The architecture spine's AD-1..AD-20 bind all implementation (adopted companion); load-bearing here: typed-tools-only mutation (AD-4), uniform mutation protocol with hash-proven rollback (AD-5/6), TNP audit (AD-7), `FullyConstrained` as the sketch pass signal (AD-8), Validation Design Gate ordering (AD-19).
- Pass/fail is computed by deterministic harness code or an independent grader — the producing agent's self-assessment is never a result (AD-13).
- A phase may not start until the previous phase's gate is fully green; phase implementation may not start until its entry gate lands (AD-19).
- All gate runs execute headless in CI on the FreeCAD 1.0.x + 1.1.x matrix (AD-11); a check that only passes in-GUI does not count.
- Statistics rules (AD-14): majority-of-R scoring, Wilson 95 % CI beside every rate, exact McNemar for ablations, dev/held-out gap >15pp blocks exit.
- Benchmark artifacts only from commercial-clean, documented real-world provenance (AD-16).
- Solo part-time development; phase timeboxes are durations, not dates.

## Non-goals

- Training or fine-tuning custom ML models — existing LLMs via API/local inference only.
- CAM/toolpath generation, photorealistic rendering, cloud multi-tenant SaaS.
- Phase 5 topics (assemblies, TechDraw, FEM loops, vision feedback, reverse engineering) until scoped after the Phase 4 retrospective.
- Fully removing humans from gate verdicts — audit sampling and rubric authorship stay human (see phase-gates.md §Global protocol).

## Success signal

An external MCP-client agent completes a full submit-spec → receive validated model + report → request revision → accept cycle against the headless service with zero human input, while the sealed held-out Phase 3 benchmark holds ≥70 % — the exact moment "FreeCAD as an autonomous design tool usable by AI agents" becomes demonstrable, not claimed.

## Assumptions

- Gate check runners live in `benchmarks/` and emit the contracts-owned `ValidationReport` (AD-17); exact runner CLI shape is an implementation detail downstream stories fix.
- Phase 1's "cite FreeCAD documentation" capability resolves at the Phase 1 entry gate (deferred in spine) without changing gate G1's criteria.

## Open Questions

- Should intent.md's n=10 criteria (G1.2 error diagnosis 8/10; GS.4 troubleshooting 9/10) be enlarged to n≈20–30 for statistical confidence, or kept as soft targets with CI reported? Gates currently keep them flagged low-confidence per AD-14.
