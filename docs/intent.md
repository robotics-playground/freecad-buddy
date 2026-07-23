# FreeCAD Buddy — Project Intent

## Vision

FreeCAD is a powerful, free, parametric 3D CAD tool — but almost everything in it is manual. Every sketch, constraint, pad, pocket, and assembly step requires the user to know *which* tool to use, *where* it lives, and *how* to sequence operations correctly. The learning curve is steep and the workflow is slow even for experts.

**FreeCAD Buddy** adds AI capability to FreeCAD, evolving through clearly defined maturity levels:

1. **Assistant** — answers questions, explains the model, suggests next steps (read-only).
2. **Copilot** — executes single operations from natural language, with user confirmation.
3. **Designer** — turns a textual specification into a complete parametric part, with self-verification.
4. **Autonomous agent** — a full agentic design loop usable by both humans and other AI agents: spec in, validated manufacturable model out, including iteration, assemblies, and exports.

The core technical bet: FreeCAD is fully scriptable via its Python API (`FreeCAD`, `Part`, `Sketcher`, `PartDesign` modules) and can run headless. An AI layer that speaks this API — exposed through a tool protocol such as MCP (Model Context Protocol) — can drive everything a human can do, and can *verify* its own work by querying geometry (volumes, bounding boxes, mass properties, topological checks) rather than guessing.

The second bet: tools alone are not enough. An agent with perfect API access but no CAD judgment produces unmaintainable models and dead-end feature trees. The repo therefore ships a **skills library** — curated, versioned knowledge documents (agent skills) that teach any LLM to *think like a 3D designer*: how to decompose a complex object into sketches and features, which FreeCAD tool to use when, how to build design intent into constraints, and how to avoid FreeCAD's known traps. Tools are the hands; skills are the brain.

## Guiding Principles

- **Verify, don't trust.** Every AI-generated operation must be validated by querying the resulting geometry, not by assuming the script succeeded. A recompute error, a null shape, or an unconstrained sketch is a failure even if the code ran.
- **Parametric first.** The AI produces proper parametric feature trees (sketches with constraints, named features), not dumb mesh blobs. The output must remain editable by a human in the FreeCAD GUI.
- **Human in the loop by default, autonomy by opt-in.** Early phases require confirmation for every mutation. Autonomy is earned per phase by passing that phase's validation gates.
- **Incremental and demoable.** Each phase ships something usable on its own. No phase depends on a future phase to deliver value.
- **Topological Naming Problem (TNP) awareness.** FreeCAD's most notorious pitfall — references breaking when the model recomputes — must be handled defensively from Phase 2 onward (reference by datum planes/named features where possible, verify references after every recompute).
- **Reuse before invention.** For every capability, first survey what already exists — a FreeCAD built-in, a community addon, an established library, a published dataset, an existing agent skill — and use it. Invent only where the survey comes up empty, and record why. Novelty is a cost, not a feature; the invention budget is spent on the things nobody has built (CAD-agent validation harnesses, design-thinking skills), not on re-implementing solved problems (geometry kernels, mesh checks, MCP plumbing).

## Architecture Direction (high level)

```
┌──────────────────────┐
│  Skills Library       │  knowledge: CAD thinking, FreeCAD manual,
│  (markdown, versioned)│  decomposition patterns, tool selection
└──────────┬───────────┘
           │ loaded into context
┌──────────▼──────────┐     MCP / RPC      ┌──────────────────────┐
│  AI Agent / LLM      │ ◄────────────────► │  FreeCAD Bridge       │
│  (Claude, local LLM, │    tools:          │  (Python, runs inside │
│   or any MCP client) │    query / mutate  │   FreeCAD or headless │
└─────────────────────┘    / verify        │   FreeCADCmd)         │
                                            └──────────┬───────────┘
                                                       │ Python API
                                            ┌──────────▼───────────┐
                                            │  FreeCAD kernel       │
                                            │  (Part, Sketcher,     │
                                            │   PartDesign, Assembly)│
                                            └──────────────────────┘
```

- **Bridge**: a Python component exposing FreeCAD operations as typed tools (MCP server). Runs inside the FreeCAD GUI process (Workbench/addon) *and* headless (`FreeCADCmd`) for CI and agent use.
- **Tool taxonomy**: `query.*` (read model state, geometry properties, screenshots), `sketch.*` / `feature.*` / `assembly.*` (mutations), `verify.*` (recompute checks, geometry assertions, export validation).
- **Skills library**: agent-agnostic knowledge documents (markdown skills in the Claude Code / MCP skill format) that any agent loads before designing — see the dedicated section below.
- **Validation harness**: golden-model test suite — each capability is proven by scripted scenarios whose resulting geometry is asserted programmatically (volume within tolerance, watertight solid, constraint count, degrees of freedom = 0).

---

## Reuse Map — Existing Things to Stand On

Standing inventory of existing software, libraries, datasets, and skills that candidate-solve parts of this project. Each phase's Validation Design Gate includes a reuse survey that confirms, updates, or rejects the relevant rows (versions and viability checked at that time — this table is a starting map, not a commitment). Anything adopted is wrapped, not forked, unless there is a written reason.

| Need | Existing candidates (evaluate first) | Invent only if |
|------|--------------------------------------|----------------|
| MCP server plumbing | Official MCP Python SDK (FastMCP); existing community FreeCAD MCP servers on GitHub (study/adapt — several exist) | Existing servers lack the verify-first tool taxonomy — likely partial reuse: their transport/embedding patterns, our tool layer |
| Geometry validity checks | FreeCAD/OCCT built-ins: `Shape.isValid()`, `Shape.check()`, BRepCheck, mass properties (`Volume`, `CenterOfMass`, `BoundBox`) | Never — kernel-level checks are a solved problem; we only compose them into `verify.*` tools |
| Mesh/export validation (STL/3MF) | `trimesh`, `admesh`, Open3D (watertight, manifold, self-intersection checks); FreeCAD Mesh workbench | Never for the checks themselves |
| Headless FreeCAD in CI | Community Docker images / conda-forge FreeCAD packages / AppImage in CI runners | Only thin CI glue scripts |
| Benchmark specs & golden models | Published CAD-generation datasets (e.g. Fusion 360 Gallery, DeepCAD, ABC, text-to-CAD benchmark sets); FreeCAD official manual/tutorial models; printables/community part libraries | Phase-specific assertion layers on top — the *specs with machine-checkable acceptance criteria* mostly don't exist and are our invention |
| Agent harness & skill format | Claude Code skills / Agent SDK; MCP client ecosystem; plain system-prompt injection for other LLMs | Never for the harness; skills *content* (Tracks A–C) is largely our invention |
| Eval/ablation runner | pytest as the runner; existing LLM eval frameworks evaluated before building | Only the CAD-specific fault-injection + sensitivity reporting, if no framework fits |
| FreeCAD knowledge source | FreeCAD wiki/manual, forum, existing community tutorials; context7/doc-query tooling for retrieval | Distillation into skills is our work; raw knowledge is not |
| Printability / DFM checks (Phase 4+) | Slicer CLIs (e.g. PrusaSlicer console mode) for overhang/thickness analysis; FreeCAD FEM workbench + CalculiX/gmsh for stress checks | Only the rule layer mapping analysis output to pass/fail design rules |
| TNP mitigation | FreeCAD 1.x built-in TNP mitigation; datum-based modeling practice (documented community pattern) | Our re-resolve guard tooling on top — the *automated post-mutation reference audit* appears not to exist |
| Robot-description export (URDF/SDF) — Phase 5 | CROSS addon (Common Robotic-Oriented Sensor System — authors URDF/SDF from FreeCAD assemblies); FreeCAD native Assembly workbench (kinematic tree) + native solid inertials (`TopoShapeSolidPy` mass properties) | Only the verify-first export layer (paired re-parse + schema + kinematic-tree sanity) if CROSS is adopted; the whole XML emit if it isn't. Note: the in-tree FreeCAD `Robot` workbench is a 6-axis trajectory tool, **not** a URDF exporter |
| Off-the-shelf part sourcing — Phase 5 | FreeCAD native STEP import (`ImportOCAF`/`ReaderStep`); external part catalogs (step.parts and similar) for search | Never for the import/placement (native); the catalog search adapter only, if a catalog is integrated |
| Implicit / SDF-kernel modeling | — | **Not adopted** — FreeCAD is OCCT B-rep; F-rep/implicit is a different kernel and out of scope (recorded to avoid re-litigation) |

Explicitly identified as **genuine inventions** (survey expected to come up empty, budget spent here): the verify-first tool taxonomy, machine-checkable spec-assertion benchmarks, the fault-injection validator harness, the post-mutation TNP audit, and the design-thinking skills (Track B).

---

## Skills Library — Teaching Agents to Think Like a 3D Designer

Tools give an agent the *ability* to act; skills give it the *judgment* to act well. The skills library is a first-class deliverable of this repo: a set of versioned, agent-agnostic knowledge documents (markdown skills, consumable by Claude Code, MCP clients, or any LLM harness) that encode what an experienced FreeCAD user and mechanical designer knows. Skills are developed alongside the phases and validated the same way everything else is: by their measurable effect on benchmark pass rates.

### Skill Catalog

**Track A — FreeCAD operating knowledge (the manual, distilled):**

| Skill | Teaches |
|-------|---------|
| `freecad-fundamentals` | Document structure, bodies, workbenches, recompute model, units; how the feature tree actually evaluates |
| `freecad-sketcher` | Sketch creation, geometry vs construction geometry, the constraint system, reaching DoF = 0, external references and their risks |
| `freecad-partdesign` | Pad/pocket/revolve/loft/sweep/fillet/chamfer/hole/patterns — parameters, prerequisites, failure modes of each |
| `freecad-datums-references` | Datum planes/axes/points, local coordinate systems, why datum-based referencing beats face/edge references (TNP defense) |
| `freecad-troubleshooting` | Reading recompute errors, broken sketch references, self-intersecting sketches, failed fillets, degenerate geometry — symptom → cause → fix recipes |
| `freecad-scripting-idioms` | Python API idioms and gotchas: object naming, recompute timing, property types, headless vs GUI differences |

**Track B — Design thinking (how a 3D designer reasons):**

| Skill | Teaches |
|-------|---------|
| `design-decomposition` | Breaking a complex object into an ordered feature plan: identify the base solid, choose the primary sketch plane, additive vs subtractive sequencing, when to split into multiple bodies |
| `sketch-strategy` | What belongs in one sketch vs several; simple over clever (two simple sketches beat one complex one); choosing the profile that captures design intent |
| `tool-selection` | Decision rules: pad vs revolve vs loft vs sweep; fillet vs chamfer; pattern vs mirror vs individual features; PartDesign vs Part booleans — with the *why* for each rule |
| `design-intent` | Constraints and parameters as intent: dimension what the spec states, derive the rest; symmetric constraints over mirrored numbers; naming features so the tree reads like a build plan |
| `parametric-patterns` | Master/skeleton sketch pattern, spreadsheet/VarSet-driven dimensions, feature ordering for robust edits (fillets last, references early) |
| `verification-thinking` | What to measure after each step and why; sanity checks (volume orders of magnitude, symmetry, bounding box vs spec); treating a passing recompute as necessary but not sufficient |

**Track C — Domain judgment (candidate, matures with Phases 3–5):**

| Skill | Teaches |
|-------|---------|
| `dfm-3d-printing` | Wall thickness, overhangs, bridging, hole shrinkage, orientation for strength — designing parts that actually print |
| `dfm-machining` | Internal corner radii, drill-friendly holes, tolerances that a mill/lathe can hit |
| `mechanical-conventions` | Standard sizes (metric bolts, clearance vs tapped holes, nut pockets), fits and clearances, fastener stack-ups |
| `assembly-strategy` | Part-splitting decisions, mating surface design, degrees of freedom in assemblies, tolerance-aware clearances |
| `spec-interpretation` | Reading ambiguous human specs: what to assume, what to ask, what to flag; converting vague requests into machine-checkable requirements |

### How skills are validated (the ablation rule)

A skill earns its place by moving a number, not by sounding wise. The standing test: run a phase benchmark **with and without** the skill loaded; the skill must improve the pass rate (or a named sub-metric, e.g. "fully constrained sketch rate") by a measurable margin on the same model. Skills that show no measurable effect are rewritten or cut.

### SMART goal — Skills Track (runs alongside Phases 1–4)

**Specific.** Author, version, and validate the Track A and Track B catalogs (12 skills) in a standard skill format under `skills/`, each with: scope statement, decision rules, worked examples, and anti-patterns. Wire them into the agent harness so benchmarks can run with any skill subset.

**Measurable — exit criteria:**
- [ ] All 12 Track A + B skills authored and loadable by at least 2 different agent harnesses (e.g. Claude Code skill + plain system-prompt injection for other LLMs).
- [ ] Ablation harness exists: any benchmark can run with a declared skill subset, and reports per-skill deltas.
- [ ] ≥ 8 of 12 skills demonstrate a measurable benchmark improvement (pass-rate or named sub-metric) in ablation on Phase 2 or Phase 3 benchmarks; the rest are revised or removed.
- [ ] `design-decomposition` specifically: Phase 3 benchmark first-plan success rate (plan needs no structural rework) improves by ≥ 15 percentage points with the skill loaded vs without.
- [ ] `freecad-troubleshooting` specifically: Phase 1 error-diagnosis cases pass rate with skill ≥ 9/10 (vs the baseline 8/10 criterion).
- [ ] Each skill has an owner-reviewed accuracy pass against current FreeCAD documentation (version-pinned, same versions as CI matrix).

**Achievable.** Source material exists (FreeCAD wiki/manual, community best practices, own benchmark failures — every Phase 2/3 failure analysis feeds a skill). Ablation reuses the existing benchmark harness.

**Relevant.** Directly attacks the biggest quality risk: an agent that can call tools but designs badly. Also the most portable artifact — the skills are useful to any FreeCAD-driving agent, even outside this repo's bridge.

**Time-bound.** Track A drafts during Phases 1–2; Track B drafts during Phases 2–3; all 12 validated by Phase 3 exit. Track C is scoped as part of Phase 4/5 planning.

---

## Validation-First Discipline

The single most likely failure mode of this project is not "the agent can't do it" — it is **the agent believing it did well when it did not**. LLM agents systematically over-grade their own work: the script ran, so the part must be right; the shape recomputed, so the spec must be met. If validation is designed after (or by) the thing being validated, the metrics will be flattering and false.

Therefore every phase begins with a mandatory **Validation Design stage**: the testing and validation method is designed, implemented, and *itself tested* before phase implementation starts. Implementation may not begin until the validation gate below is passed.

### Principles

1. **The actor never grades itself.** Pass/fail is decided by deterministic code (geometry queries, assertions, diff checks) or by an independent grader that did not produce the work. The designing agent's opinion of its output is diagnostic input, never a result.
2. **Validate the validator.** A validation method is only trusted after it proves it can catch failures. Standing technique: **fault injection** — deliberately wrong outputs (wrong dimension, missing hole, mirrored part, unconstrained sketch, silently-swallowed error) are fed through the validator, which must flag them. A validator that passes everything is measured as broken, not lucky.
3. **Measure both error directions.** Every validator reports *sensitivity* (% of planted faults caught — target ≥ 95%) and *false-alarm rate* (% of known-good references wrongly failed — target ≤ 5%). A benchmark score is only reportable alongside its validator's current sensitivity number.
4. **Held-out sets.** Each benchmark splits into a *development set* (visible during implementation, used for iteration) and a *held-out set* (sealed until phase exit, run once). Phase exit criteria are judged on the held-out set. A large dev/held-out gap (> 15 points) means overfitting to the benchmark — phase does not exit.
5. **Realism over convenience.** Benchmark specs and golden models come from real-world parts (printed brackets, published FreeCAD tutorials, community models, actual user requests) — not from specs reverse-engineered to fit what the agent already does well. Each benchmark documents its provenance.
6. **End-artifact checks, not process checks.** "All steps executed" is not success. Success is measured on the final artifact: geometry assertions against the spec, re-import round-trips, opening cleanly in the FreeCAD GUI, surviving a parameter edit. Process logs explain failures; they never define success.
7. **Human audit sampling.** Every phase exit includes a human spot-audit of a random sample (≥ 20%) of "passing" benchmark results. Any audit finding a false pass invalidates the run: fix the validator, re-run, re-audit.

### The Validation Design Gate (per phase)

Before implementation of phase *N* starts, a dedicated job produces and lands:

- [ ] **Threat list**: written enumeration of the ways the agent could *appear* to succeed while failing in this phase (the phase-specific self-deception modes), each mapped to the check that catches it.
- [ ] **Benchmark + assertions implemented and runnable** (dev + held-out split, provenance documented) — before any phase code exists, the benchmark runs against a stub and fails honestly.
- [ ] **Fault-injection suite**: ≥ 10 planted-failure cases for this phase's validators; validator sensitivity ≥ 95%, false-alarm rate ≤ 5% on known-good references.
- [ ] **Grading spec**: for any criterion needing judgment (e.g. Phase 1 answer quality), a written rubric with worked pass/fail examples, gradeable by a human or an independent grader model — never by the acting agent.
- [ ] **Reuse survey**: a short build-vs-reuse note for this phase's new components — what existing software/library/dataset/skill was found (see Reuse Map), what is adopted, and for anything built from scratch, why nothing existing fits.

The gate itself is timeboxed to ~20% of the phase timebox (e.g. ~1 week of a 6-week phase); it is part of the phase, not an addition to it.

### Phase-specific self-deception modes (the threat lists start here)

| Phase | How the agent fools itself | Primary counter |
|-------|---------------------------|-----------------|
| 1 | Fluent, plausible, wrong answers; diagnosis names *an* object, not *the* object | Grading rubric keyed to exact expected findings; independent grader; wrong-but-confident cases planted in eval set |
| 2 | Operation runs without error but produces wrong geometry; verification checks recompute success instead of intent ("a pocket exists" vs "the right pocket, right place, right depth") | Per-command geometry assertions written with the benchmark, before implementation; fault-injected wrong-parameter runs |
| 3 | Plan looks professional but final part deviates from spec; self-repair loop declares convergence by iteration cap, not by measurement; measures what it built instead of what was asked | Spec assertions authored independently of the plan; convergence = assertions pass, never "loop finished"; corrupted-plan fault suite (already in Phase 3 criteria) |
| 4 | Service returns HTTP 200 + well-formatted report for a bad part; revision "succeeds" by breaking an unrelated feature silently | Validation report fields backed by re-executed checks, not echoed agent claims; geometry diff on revisions confined to requested change |
| Skills | Skill sounds authoritative, measures nothing | Ablation rule (already standing): no measurable lift, no skill |

---

## Phases

Each phase has a SMART goal: **S**pecific scope, **M**easurable exit criteria, **A**chievable within the phase timebox, **R**elevant to the vision ladder, **T**ime-bound. A phase is *done* only when every exit criterion is checked — judged on the held-out benchmark set, with validator sensitivity reported, per the Validation-First Discipline above. **Each phase starts with its Validation Design Gate; implementation is blocked until the gate lands.** Timeboxes assume part-time solo development and start when the phase starts (they are durations, not calendar dates).

---

### Phase 0 — Foundation: FreeCAD Bridge & Test Harness

> *Make FreeCAD programmatically drivable and verifiable. No AI yet.*

**Specific.** Build the Python bridge exposing FreeCAD via MCP: document lifecycle (new/open/save), object tree inspection, Python execution sandbox, geometry queries (volume, area, bounding box, mass properties, shape validity), screenshot capture, and export (STEP, STL). Works both inside the FreeCAD GUI and headless via `FreeCADCmd`. Set up the golden-model test harness in CI.

**Measurable — exit criteria:**
- [ ] MCP server starts inside FreeCAD (as addon/workbench) and headless; an MCP client (e.g. Claude Code) can list and call its tools.
- [ ] ≥ 15 tools implemented across `query.*`, `document.*`, `export.*`, each with a JSON schema and docstring.
- [ ] `verify.shape` tool reports: is-valid-solid, watertight, volume, bounding box, face/edge counts — verified against 5 hand-made reference models with known values (±0.1% tolerance).
- [ ] CI pipeline (GitHub Actions) runs the full tool test suite headless on every push; suite ≥ 30 tests, all green.
- [ ] Round-trip test passes: create doc → run script → export STEP → re-import → geometry matches (volume ±0.1%).

**Achievable.** Pure Python + FreeCAD API + existing MCP SDK; no ML work. Known prior art (existing community FreeCAD MCP experiments) confirms feasibility.

**Relevant.** Every later phase calls these tools; the verification harness is what makes AI output trustworthy.

**Time-bound.** 4 weeks.

---

### Phase 1 — Assistant: Read-Only AI Helper

> *AI that understands the open document and the user's question — but touches nothing.*

**Specific.** Chat interface (FreeCAD panel and/or external MCP client) where an LLM answers questions using read-only bridge tools: explain the feature tree, describe a selected object, diagnose recompute errors, recommend which FreeCAD tool/workbench to use next, and cite relevant FreeCAD documentation. Zero mutation tools exposed in this phase.

**Measurable — exit criteria:**
- [ ] Assistant answers correctly on a curated evaluation set of 50 questions (model-tree comprehension, error diagnosis, "how do I…" guidance) with ≥ 80% pass rate, graded against written expected answers.
- [ ] Given a document with a deliberately broken recompute (e.g. dangling sketch reference), assistant identifies the failing object and the cause in ≥ 8 of 10 test cases.
- [ ] Feature-tree explanation works on documents with ≥ 50 features without exceeding context limits (uses summarized tree queries, not raw dumps).
- [ ] Response latency ≤ 15 s median on the evaluation set.
- [ ] Runs against at least 2 LLM backends (e.g. Claude API + one local model) to prove the bridge is model-agnostic.
- [ ] Skills: `freecad-fundamentals` and `freecad-troubleshooting` drafted and loaded during the evaluation runs (Track A drafting starts here).

**Achievable.** Read-only tools already exist from Phase 0; work is prompting, tree summarization, and the eval set.

**Relevant.** Builds the "AI understands CAD state" muscle and the evaluation discipline that every mutation phase depends on.

**Time-bound.** 4 weeks after Phase 0.

---

### Phase 2 — Copilot: Single-Step Operations from Natural Language

> *"Add a 5 mm fillet to the top edges" — AI proposes one operation, user confirms, bridge executes and verifies.*

**Specific.** Expose mutation tools (`sketch.*`, `feature.*`: create sketch, add geometry + constraints, pad, pocket, fillet, chamfer, hole, mirror, pattern). The AI maps one natural-language command to one operation (or one small atomic group), shows a preview/diff (before/after screenshot + parameter list), executes on confirmation, then runs automatic post-verification: recompute succeeded, shape still valid, sketch DoF, and no broken references (TNP check). Undo restores the exact prior state.

**Measurable — exit criteria:**
- [ ] Command benchmark: 40 scripted natural-language commands across 8 operation types on reference models; ≥ 85% execute correctly (resulting geometry matches expected assertions) on first attempt.
- [ ] 100% of executed operations run post-verification automatically; any failed verification triggers automatic rollback and a human-readable explanation.
- [ ] Undo after any AI operation restores previous document state exactly (verified by geometry hash) in 100% of benchmark cases.
- [ ] TNP guard: after each mutation, all existing feature references re-resolve; benchmark includes 5 TNP-provoking scenarios and the guard flags all of them.
- [ ] Sketch operations produce fully constrained sketches (DoF = 0) in ≥ 90% of sketch benchmark cases.
- [ ] Skills: remaining Track A skills (`freecad-sketcher`, `freecad-partdesign`, `freecad-datums-references`, `freecad-scripting-idioms`) drafted; `tool-selection` and `sketch-strategy` (Track B) drafted; command benchmark runs with skills loaded and the ablation harness reports their deltas.

**Achievable.** One operation per confirmation keeps the action space small; verification tooling from Phase 0 catches errors deterministically.

**Relevant.** First mutation capability — the trust foundation (verify + rollback) for everything autonomous.

**Time-bound.** 6 weeks after Phase 1.

---

### Phase 3 — Designer: Spec-to-Part with Self-Verification

> *"Design a mounting bracket: 60×40×5 mm base plate, two M5 through-holes 40 mm apart, one perpendicular flange 30 mm tall with a 10 mm lightening slot" — AI plans, executes multi-step, checks itself, and iterates until the spec is met.*

**Specific.** The AI takes a structured or free-text part specification, produces a plan (sequence of Phase 2 operations), executes it end-to-end with per-step verification, and closes the loop: after building, it *measures* the result against the spec (dimensions, hole positions/diameters, volume sanity) and repairs discrepancies, up to N iterations. Human confirms the plan once up front, not each step. Output is a clean parametric tree with named features and a spreadsheet/VarSet of driving dimensions.

**Measurable — exit criteria:**
- [ ] Benchmark of 20 written part specs (brackets, plates, flanges, spacers, enclosure-like parts; each spec has machine-checkable acceptance assertions). ≥ 70% produce a passing part within ≤ 3 self-repair iterations, no human intervention after plan approval.
- [ ] Every generated part: valid watertight solid, recompute-clean, all sketches DoF = 0, all driving dimensions exposed as named parameters.
- [ ] Editability test: changing one driving parameter (e.g. plate length) in the generated model recomputes without errors in ≥ 90% of passing benchmark parts.
- [ ] Self-verification catches injected faults: for 10 deliberately corrupted plans, the loop detects the spec violation in ≥ 9 cases (no silent bad parts).
- [ ] Median wall-clock time per benchmark part ≤ 10 minutes.
- [ ] Skills: full Track A + B catalog (12 skills) validated per the Skills Track SMART goal — this phase's benchmark is the primary ablation testbed; every benchmark failure analyzed and, where generalizable, fed back into a skill.

**Achievable.** Composes Phase 2 verified primitives under a plan-execute-check loop; the spec-assertion harness makes "done" objective.

**Relevant.** This is the first true *design* capability — the step from tool-driver to designer.

**Time-bound.** 8 weeks after Phase 2.

---

### Phase 4 — Autonomous Agent: Full Design Loop as a Service

> *Any AI agent (or human) submits a design task; FreeCAD Buddy delivers a validated, exportable, revisable model — no GUI required.*

**Specific.** Package the Phase 3 loop as a fully headless, long-running agent service: job API (submit spec → receive model + validation report + STEP/STL/3MF exports + rendered views), revision requests against previous results ("make the flange 5 mm taller"), design-rule checks (minimum wall thickness, hole-edge distance), and printability/manufacturability heuristics for 3D-printing-oriented parts. Safety rails: resource limits, iteration caps, sandboxed execution, full audit log of every operation.

**Measurable — exit criteria:**
- [ ] End-to-end headless run: 20-spec benchmark from Phase 3 executes via the job API on CI with zero GUI, ≥ 70% pass rate maintained.
- [ ] Revision benchmark: 15 modification requests against previously generated models; ≥ 70% succeed while preserving unrelated features (geometry diff confined to the requested change).
- [ ] Every delivered job includes a machine-readable validation report (spec assertions, shape validity, design-rule check results) and at least STEP + STL exports that re-import cleanly.
- [ ] Agent-to-agent proof: an external MCP-client agent (not human-driven) completes a submit → inspect report → request revision → accept cycle without human input.
- [ ] Robustness: service survives a 50-job soak run without crash, hang, or resource leak (memory growth < 20% over the run); every failed job fails with a structured error, never silently.

**Achievable.** No new design intelligence required — Phase 3 capability hardened into a service; work is packaging, API, sandboxing, and reliability.

**Relevant.** Delivers the end-state vision: FreeCAD as an autonomous 3D design tool usable *by* AI agents.

**Time-bound.** 8 weeks after Phase 3.

---

### Phase 5 — Advanced (exploratory, scoped after Phase 4 retrospective)

Candidate directions — each will get its own SMART goal when selected:

- **Assemblies:** multi-part designs with mating constraints (Assembly workbench), interference detection across parts. *(Prerequisite for robot-description export below — it supplies the kinematic link/joint tree.)*
- **Robot-description export (URDF/SDF):** export a parametric assembly to URDF and SDF — links, joints, limits, inertials (from FreeCAD's native mass properties), and collision/visual meshes — validated by re-parse, schema check, and kinematic-tree sanity, not by "the file was written." Export is our code emitting XML from the assembly tree (the CROSS addon is evaluated first as reuse); the mm/deg→metre/kg/radian conversion is an explicit boundary. *(SRDF — MoveIt planning semantics — is deferred: no native FreeCAD path; it derives from an exported URDF plus external MoveIt. Implicit CAD is rejected: FreeCAD is OCCT B-rep, implicit needs an F-rep/SDF kernel the verify stack can't validate.)*
- **Off-the-shelf part sourcing:** find and import common purchasable STEP parts (fasteners, bearings, motors, connectors) and place them under the bridge — catalog search is external, import and placement are standard FreeCAD, and an imported part's mating frames are measured, never assumed.
- **Drawings:** auto-generated TechDraw sheets with dimensions from the driving parameters.
- **Optimization loops:** FEM-in-the-loop (mass minimization under stress constraints), topology suggestions.
- **Vision feedback:** using rendered views / screenshots as a verification channel (does it *look* like the sketch/reference image).
- **Reverse tasks:** import a STEP/mesh and produce an editable parametric reconstruction.

---

## Phase Summary

| Phase | Capability level | Headline metric | Timebox |
|-------|-----------------|-----------------|---------|
| 0 | Bridge, no AI | ≥ 30 green CI tests, 5 golden models verified | 4 wk |
| 1 | Read-only assistant | ≥ 80% on 50-question eval | 4 wk |
| 2 | Confirmed single ops | ≥ 85% on 40-command benchmark, 100% auto-verify + rollback | 6 wk |
| 3 | Spec-to-part designer | ≥ 70% on 20-spec benchmark, ≤ 3 self-repairs | 8 wk |
| 4 | Autonomous headless service | Phase 3 rate maintained headless + agent-to-agent cycle | 8 wk |
| 5 | Assemblies / FEM / drawings | Scoped after Phase 4 | TBD |
| Skills track | Designer knowledge for any agent | 12 skills authored; ≥ 8 prove measurable benchmark lift in ablation | alongside Phases 1–3 |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Topological Naming Problem breaks references after recompute | Silent model corruption | TNP guard from Phase 2: reference datums/named features, re-resolve check after every mutation, benchmark includes TNP-provoking cases |
| LLM hallucinates FreeCAD API calls | Failed or wrong operations | Typed tool layer (no free-form `exec` in mutation path), per-step geometry verification, rollback on failure |
| FreeCAD version drift (API changes between 0.21/1.0+) | Bridge breakage | Pin supported versions, CI matrix across versions, thin adapter layer over version-sensitive calls |
| Agent self-grades → thinks it's doing well when it isn't | False confidence, silent bad output | Validation-First Discipline: validation designed and fault-tested before implementation, actor never grades itself, held-out sets, human audit sampling |
| Eval benchmarks too easy → inflated pass rates | False confidence | Validation Design Gate: benchmarks + assertions land before phase code; real-world provenance required; validator sensitivity ≥ 95% proven by fault injection |
| Headless vs GUI behavior differences | Works in dev, fails in service | Every phase's suite runs headless in CI from Phase 0 onward |
| Skills become stale or plausible-but-wrong lore | Agent confidently follows bad advice | Ablation rule (skill must move a metric or be cut), version-pinned accuracy review against FreeCAD docs, failure analyses feed corrections back |
| Scope creep into Phase 5 topics early | Phase slippage | Phase gates: no phase starts until previous exit criteria all checked |

## Out of Scope (for now)

- Training or fine-tuning custom ML models (the project uses existing LLMs via API/local inference).
- CAM / toolpath generation.
- Photorealistic rendering pipelines.
- Cloud multi-tenant SaaS hosting (Phase 4 service is single-tenant/local-first).
