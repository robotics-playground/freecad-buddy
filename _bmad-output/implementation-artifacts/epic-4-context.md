# Epic 4 Context: Spec-to-Part (Phase 3 · gate G3)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

A user gives a written part spec. A driving agent returns an editable parametric part that measurably meets it: geometry assertions pass and the agent has looked at the rendered views. This repository supplies only what the agent measures with (assertion primitives in a declared anchor frame), what it looks at (iso/focus renders plus a dimensioned drawing sheet), and the parameter façade that keeps the part editable. The plan → execute → measure → repair loop lives in the agent and the Track W skills (`design-loop`, `visual-review`, `spec-to-assertions`), never in shipped code. An earlier implementation that put a designer loop in the repo was reverted; do not rebuild any part of it.

## Stories

- Story 4.1: Entry Gate G3.E — Spec Set, Assertions & Fault Suite
- Story 4.2: Assertion Primitives
- Story 4.3: Drawing Generator
- Story 4.4: Parametric Editability
- Story 4.5: Gate G3 Exit

## Requirements & Constraints

- **No loop in any shipped artifact.** `src/`, `benchmarks/` and skill `scripts/` hold no planner, repair strategy, iteration count, judge, model client or credential. Violation test: would the repo behave differently depending on which model talks to it? If yes, it belongs in a skill body.
- **No done-predicate.** `verify_*` and assertions return measurements and per-check pass/fail. No code aggregates them into "part is done" or defines convergence, even deterministically.
- **Agent reaches tools only through MCP.** No in-process path into `usecases/` for any caller, the gate runner included.
- **Dual-channel done (agent's verdict):** all geometry assertions pass AND the agent performed a visual review and wrote per-part findings (view, observation, severity) to the run workdir. Enforcement is the evidence trail plus the ≥20 % human spot-audit, not a runtime check.
- **Entry gate G3.E lands before any Phase 3 implementation** (timebox ~20 % of the phase): threat list, spec set with compiled assertions, benchmark that fails honestly against a stub, corrupted-plan fault suite at sensitivity ≥95 % / false-alarm ≤5 %, render and drawing path at the ≥2048 px floor, the three Track W skills present, and a recorded reuse survey.
- **Each threat needs a planted counter case** in the fault suite before the gate can be cited: plan looks professional but part deviates; agent stops from lack of patience; part never looked at; rate cited for the wrong actor model.
- **Exit criteria G3.1–G3.6:** ≥70 % of the spec set passes within ≤3 repairs at R≥10 on the sealed held-out split, dev/held-out gap ≤15pp; passing parts are valid, watertight, recompute-clean, all sketches `FullyConstrained`; ≥90 % recompute clean with one driving parameter changed; ≥9/10 corrupted plans detected with zero silent bad parts; visual findings present per passing part; ≤10 min median wall-clock per part, model time included.
- **Citability:** a number is citable only if recomputable from stored measurements by a party that did not produce the work. "Mean repairs to convergence" is not citable; "count of parts whose assertions passed" is.
- **Specs are commercial-clean** and derive from documented real-world parts or requests, never reverse-fit to what the agent does well. Each carries a provenance manifest.

## Technical Decisions

- **Assertion vocabulary** is closed: names and signatures in `contracts/` (stdlib only); measurements wrap the `Face.Surface` typed-geometry path. Primitives: `is_valid_solid`, `count_cylindrical_holes`, `hole_diameter`, `hole_position`, `hole_spacing`, `hole_through`, `distance_between`, `angle_between`, `expect_bbox`, `expect_extent`, `expect_volume`. Each returns `(passed, measured, expected, tolerance, detail)` inside a `ValidationReport`. Hole counting follows the normative disambiguation rules (hole vs boss, coaxial grouping, fillet filtering, countersink/counterbore).
- **Anchor frame:** declared per spec from the closed set {named datum | base sketch plane | largest planar face}, resolved by one shared implementation. Every member is total and deterministic or raises. `largest_planar_face` tie-break: largest area, then lowest centroid Z, then lowest sorted mapped name. The resolved face's mapped name goes in the report banner. A frame that resolves differently on the 1.0.x and 1.1.x legs is a broken spec, not a failing part.
- **Banned in specs:** sub-element index selectors (`Face6`); feature metadata (`PartDesign::Hole.Diameter`) as a verdict (diagnostic hint only); whole-shape similarity (Chamfer/IoU) as a primary metric. An unevaluable assertion is a failing `INVALID_INPUT` check, never a silent skip.
- **Tolerances** start at the defaults (linear ±0.05 mm, angle ±0.1°, volume ±1 %) and are calibrated by the fault suite. Never tighter than `Shape.getTolerance`.
- **Drawing sheet:** front/top/right `DrawViewPart` projections on one `TechDraw::DrawPage`, built on a reserved-prefix TempDoc copy (part document byte-identical afterwards). Dimensions come from the driving parameters and the spec's assertion set, not from picked view geometry. One sheet-wide scale stated as a ratio. ≥2048 px page width. If render or drawing is unavailable, the visual set is incomplete and the part is not done.
- **Image budgets differ:** user-facing renders cap at 1920 px (AD-10). Review images are workdir artifacts with the ≥2048 px floor. Today the render path caps at 1920 px in code and schema, so the review set needs its own render entry point above that cap.
- **Driving parameters** go through the shim's VarSet façade with Spreadsheet fallback, gated by `shim.varset_available()` (Spreadsheet is the safe default).
- **Gate runner:** spawns an external agent harness (Claude Agent SDK process, default Sonnet) as a separate process. Options carry the MCP endpoint, allowed tools and skills only. The runner re-executes assertions against artifacts and computes stats (majority-of-R, Wilson CI, gap). The exact actor model id goes in the banner. The grader is deterministic geometry code. Held-out cases are age-encrypted with `SEAL.json`; only `gate run --exit` unseals. Validator sensitivity runs are current only while `validator_sha` matches.
- **Mutations** during a build use the existing typed `sketch_*`/`feature_*` tools under the AD-5 protocol. Visual review is per part, never per mutation.

## Cross-Story Dependencies

- **Prerequisite:** Gate G2 is green (Epic 3 done).
- **4.1 depends on Story 6.5:** G3.E requires `design-loop`, `visual-review` and `spec-to-assertions` to exist. None is in `skills/` today.
- **4.1 and 4.3:** G3.E requires the ≥2048 px render and drawing path. It also requires a headless drawing-export spike (TechDraw SVG/PNG under the render-leg environment) and drawing-generator fault cases (a planted wrong-callout sheet).
- **4.2 resolver** is shared by the spec set (4.1), the G3.3 re-check (4.4) and the exit grader (4.5). One anchor-frame implementation only. A partial G2 grader already exists in `benchmarks/harness/assertions.py`, while the design places measurements in `usecases/`. Decide the placement in 4.2. Do not create a second implementation.
- **4.5 depends on 4.1–4.4.** It needs a `spot_audit` human token bound to the run. G3.5 reads visual findings from the run workdir, but `run_id` threading is Story 5.4 (Phase 4, after G3). This ordering conflict needs a decision before 4.5 starts.
- **Doc drift to ignore:** the harness design still says per-part timing spans "judge" time. No judge exists. Time spans agent thinking, tool calls and TechDraw generation.
