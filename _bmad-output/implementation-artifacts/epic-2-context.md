# Epic 2 Context: Read-Only Model Assistant

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Epic 2 delivers Phase 1: a read-only assistant that lets a FreeCAD user ask natural-language questions about their open model — tree explanation, error diagnosis, next-tool guidance — and receive graded-correct, cited answers with zero mutation risk. It proves the bridge is genuinely model-agnostic by running the same assistant on two LLM backends (a Claude backend and a fully local model), plus a text-parse ReAct fallback over the identical tool surface. The epic exists to establish, on top of Epic 1's verified bridge, that answer quality can be decided mechanically by a validated independent grader — never by the assistant itself — and to lock the eval/rubric/grader machinery that all later phases reuse. Gate G1 is passed only when a sealed held-out eval runs green under statistical discipline with human sign-off tokens present.

## Stories

- Story 2.1: Entry Gate G1.E — Eval Set, Rubric & Grader Validation
- Story 2.2: Assistant on the Claude Backend
- Story 2.3: Local Backend + ReAct Fallback Adapter
- Story 2.4: Gate G1 Exit

## Requirements & Constraints

- **Read-only guarantee.** The assistant answers exclusively through `query_*` and read-only `verify_*` tools. The Phase 1 registry profile must expose zero mutation tools; introspection of what the assistant can call is itself a gate check.
- **Two backends + fallback.** The assistant must complete the eval through an identical tool surface on at least two backends: a Claude backend and a local model (pinned llama.cpp + Qwen3-30B-A3B-Instruct, constrained decoding ON, over streamable HTTP). A ReAct text-parse adapter must drive the same tool registry against any OpenAI-compatible endpoint, proving model-agnosticism twice.
- **No self-grading (hard invariant).** Pass/fail comes from deterministic code or an independent grader model only. The producing agent never grades itself. The grader config must resolve to a different model/context than the actor; preflight hard-fails on actor/grader identity.
- **Entry gate before implementation.** The eval set, rubric, and a fault-tested grader must exist and fail honestly against a stub assistant before any assistant code is written. No tool is ever graded by an untested validator.
- **Grader must prove sensitivity.** The grader is itself a validator: it must clear sensitivity ≥95% / false-alarm ≤5% on a planted confident-wrong answer suite before its scores are citable. A rubric edit invalidates prior grader sensitivity runs (source-hash staleness).
- **Held-out sealing.** The dev/held-out eval split is sealed (age-encrypted archive + `SEAL.json` manifest, human-held key). Only the exit run unseals it; a failed exit burns the held-out set (new cases required for re-exit).
- **Statistics discipline.** Dev runs at R=3; exit runs on the sealed held-out set at R≥10 with majority-of-R scoring. Every reported rate carries a Wilson 95% CI. Dev/held-out gap must be ≤15pp or exit is blocked (overfitting).
- **Latency budget.** Median response ≤15 s over the eval set. This depends on summarized-tree queries — tools must return summarized trees, never raw dumps (load-bearing for both large-tree handling and local-model throughput).
- **CI matrix.** All suites run headless on the FreeCAD 1.0.x (Py 3.11) + 1.1.x (Py 3.12) blocking matrix. Version-sensitive calls stay behind the capability-probe shim.
- **In-FreeCAD purity.** In-FreeCAD code imports stdlib + FreeCAD API only; all third-party deps (grader client, harness, MCP libs) live in the uv-managed external process.

### G1 Exit Criteria (what "done" means for the epic)

- G1.1 Answer quality: 50-question eval, R=3 dev, grader-scored per rubric, pass rate ≥80%.
- G1.2 Error diagnosis: 30-case broken-recompute fixture set; grade n=10 first (grader checks *the* failing object + cause named), n=10 ≥8/10 to pass; only 10/10 escalates to full n=30.
- G1.3 Large-tree handling: 50+-feature docs, no context overflow, summarized queries used, median latency ≤15 s.
- G1.4 Model-agnostic bridge: G1.1 sample re-runs on the second (local) backend through the identical tool surface.
- G1.5 Skills drafted + loaded: `freecad-fundamentals` and `freecad-troubleshooting` present (4-section shape, CI shape-check green), load recorded in run logs — drafted in Epic 6 Story 6.2.
- G1.6 Read-only guarantee: zero mutation tools registered in the assistant profile.
- Human tokens required at exit: `rubric_review` + `spot_audit`, run-bound.

## Technical Decisions

- **One server, transport is a flag.** A single FastMCP server object serves every client; clients differ only in transport, confirmation mechanism, skills delivery, and image handling — no client-specific logic leaks into use cases. Claude uses stdio (headless) or streamable HTTP (GUI-attached); the local backend uses streamable HTTP; the ReAct adapter is in-process (no MCP transport).
- **Independent grader wiring.** `g1/gate.yaml` declares `actor:` and `grader:` model configs. Grader input = question + the actor's final answer (not its scratch reasoning) + the human-authored `g1/rubric.md` + the case's expected findings (`{object, cause}`; G1.2 requires *the* object). Grader output = schema-validated `{pass, matched_expected, rationale}` at temperature 0; transcript stored for audit. The grader registers in `_registry/validators.yaml`.
- **Benchmark layout.** `benchmarks/g1/` holds `dev/` (50-question eval + broken-doc cases), `heldout/` (sealed: `heldout.tar.age` + `SEAL.json` only), `fault-injection/` (planted confident-wrong answers), and `rubric.md`. Fault suites sit beside the dev/held-out split and never count toward pass rates.
- **Gate runner is a pure verdict function.** The runner re-executes checks and emits one contracts-owned `ValidationReport` per case×repeat with the banner (FreeCAD version, ElementMapVersion, validator sensitivity, Wilson CI). `gate verdict g1 --run <id>` recomputes the verdict from stored reports + tokens alone — re-runnable by an auditing agent without re-executing cases.
- **Local stack constraints.** llama-server registers the bridge as an MCP server over HTTP; JSON-Schema-constrained sampling is mandatory for tool calls (drives format-error rate to ~0). An unconstrained local run is diagnostic only, never an eval configuration.
- **ReAct adapter contract.** Renders tool names + JSON schemas (sourced from `contracts/`, single source of truth) into the system prompt; loop parses a fenced JSON tool-call block, dispatches through the same tool registry the FastMCP server uses, appends the ResultEnvelope text mirror, repeats. Malformed JSON → one structured re-prompt then typed `INVALID_INPUT`, never silent retry loops. It is a client like any other: typed tools only, explicit document handles, confirmation posture per the matrix.
- **Confirmation posture (read-only phase).** No mutations exist in Phase 1, but the adapter's confirmation posture must already match the no-elicitation matrix row (token fallback / fail-closed) so it is correct when mutations arrive in Epic 3.
- **Image delivery.** Renders (if any) go to the Claude client as `resource_link` (never inline base64 except tiny thumbnails); to the local/ReAct leg as `resource_link` only — local context is the scarcest resource, the image is for the human not the model.

## Cross-Story Dependencies

- **Depends on Epic 1** in full: the read-only `query_*`/`verify_*` tool surface, the summarized-tree queries (G1.1/G1.3 groundwork), the version shim, the contracts-owned `ValidationReport`/envelope schemas, the audit sink, and the gate runner all ship in Epic 1.
- **G1.5 consumes Epic 6, Story 6.2:** the two skills `freecad-fundamentals` and `freecad-troubleshooting` are authored in the parallel skills track and must be present + shape-checked for the G1 eval runs. Epic 6's `freecad-troubleshooting` ablation (GS.4) re-runs the same G1.2 tiered error-diagnosis fixtures.
- **Story ordering within the epic:** 2.1 (entry gate: eval + rubric + validated grader, must fail honestly vs a stub) precedes 2.2/2.3 (implementation); 2.4 (sealed held-out exit run + human tokens) is last. Gate-sequential: Epic 1 must be fully green before Epic 2 starts, and Epic 2 before Epic 3.
