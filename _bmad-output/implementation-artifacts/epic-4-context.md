# Epic 4 Context: Spec-to-Part (Phase 3 · gate G3)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

A user gives a written part spec. A driving agent returns an editable parametric part that measurably meets it: geometry assertions pass, and the agent has looked at the rendered views. This repository supplies only three things: what the agent measures with (assertion primitives in a declared anchor frame), what it looks at (iso/focus renders plus a dimensioned drawing sheet), and the parameter façade that keeps the part editable. The plan → execute → measure → repair loop lives in the agent and in the Track W skills (`design-loop`, `visual-review`, `spec-to-assertions`), never in shipped code. An earlier implementation put a designer loop, a judge and actor plans in the repo; it was reverted. Do not rebuild any part of it.

## Stories

- Story 4.1: Entry Gate G3.E — Spec Set, Assertions & Fault Suite
- Story 4.2: Assertion Primitives
- Story 4.3: Drawing Generator
- Story 4.4: Parametric Editability
- Story 4.5: Gate G3 Exit

## Requirements & Constraints

- **No loop in any shipped artifact.** `src/`, `benchmarks/` and skill helper scripts hold no planner, repair strategy, iteration count, judge, model client or credential. Test: would the repo behave differently depending on which model talks to it? If yes, the logic belongs in a skill body.
- **No done-predicate.** `verify_*` and assertions return measurements and per-check pass/fail. No code aggregates them into "part is done" or defines convergence.
- **Agent reaches tools only through MCP.** No in-process path into `usecases/` for any caller, the gate runner included.
- **Dual-channel done is the agent's verdict:** all geometry assertions pass AND the agent wrote per-part visual findings (view, observation, severity) to the run workdir. Enforcement is the evidence trail plus the ≥20 % human spot-audit, not a runtime check.
- **G3.E stays open until every entry item lands.** Items: spec set failing honestly against a stub and corrupted-plan suite with all four threats countered (4.1, landed); anchor frame resolves identically on 1.0.x and 1.1.x legs, and suite scored at sensitivity ≥95 % / false-alarm ≤5 % with `validator_sha` (4.2); render and drawing path at the ≥2048 px floor (4.3); the three Track W skills exist (6.5); reuse survey (4.1, landed). An item whose story has not landed reports `INVALID_INPUT`.
- **Exit criteria G3.1–G3.6:** ≥70 % of the spec set passes within ≤3 repairs at R≥10 on the sealed held-out split, dev/held-out gap ≤15pp; passing parts are valid, watertight, recompute-clean, all sketches `FullyConstrained`; ≥90 % recompute clean with one driving parameter changed and the change reflected; ≥9/10 corrupted plans detected with zero silent bad parts; visual findings present per passing part; ≤10 min median wall-clock per part, model time included.
- **Citability:** a number is citable only if a party that did not produce the work can recompute it from stored measurements. "Count of parts whose assertions passed" is citable; "mean repairs to convergence" is not. A cited rate is valid only for the actor model id in the banner.
- **Specs are commercial-clean,** derived from documented real-world parts, never reverse-fit to the agent. Each spec and fault case carries a provenance manifest. Any post-hoc spec edit adds a requirement the prose states, relaxes none, and is disclosed.

## Technical Decisions

- **Assertion vocabulary is closed (11 functions):** `is_valid_solid`, `count_cylindrical_holes`, `hole_diameter`, `hole_position`, `hole_spacing`, `hole_through`, `distance_between`, `angle_between`, `expect_bbox`, `expect_extent`, `expect_volume`. Names and signatures go in `contracts/` (stdlib only). Measurements use the `Face.Surface` typed-geometry path. Each check returns `(passed, measured, expected, tolerance, detail)` inside a `ValidationReport`. Hole counting follows the normative rules (hole vs boss, coaxial grouping, fillet filtering, countersink/counterbore).
- **Anchor frame** is declared per spec from {`named_datum` | `base_sketch_plane` | `largest_planar_face`} and resolved by one shared implementation. Each member is total and deterministic, or it raises. `largest_planar_face` tie-break: largest area, then lowest centroid Z, then lowest sorted mapped name. The resolved face's mapped name goes in the report banner. A frame that resolves differently across legs is a broken spec, not a failing part.
- **Banned in specs:** sub-element index selectors (`Face6`); feature metadata (`PartDesign::Hole.Diameter`) as a verdict (diagnostic hint only); whole-shape similarity (Chamfer/IoU) as a primary metric. An unevaluable assertion is a failing `INVALID_INPUT` check, never a silent skip.
- **Tolerances** start at linear ±0.05 mm, angle ±0.1°, volume ±1 %, calibrated by the fault suite, never tighter than `Shape.getTolerance`.
- **Corrupted plan = recorded plan.** Each fault case is an ordered list of `{tool, args}` MCP steps with one planted step marked (controls have none). Story 4.2 replays plans through the mutation tools and grades the part with the referenced spec's assertions. G3.4 uses the same path at exit. No builder script.
- **Drawing sheet:** front/top/right `DrawViewPart` projections on one `TechDraw::DrawPage`, built on a reserved-prefix (`FCB_TMP_`) TempDoc copy; the part document stays byte-identical. Dimensions come from the driving parameters and the spec assertions, not from picked view geometry. One sheet-wide scale, stated as a ratio. ≥2048 px page width. Without render or drawing, the visual set is incomplete and the part is not done.
- **Image budgets differ:** user-facing renders cap at 1920 px. Review images are workdir artifacts with the ≥2048 px floor. The current screenshot path and its schema cap at 1920 px, so the review set needs its own entry point.
- **Driving parameters** go through the shim's VarSet façade with Spreadsheet fallback, selected by `shim.varset_available()`.
- **Gate runner** spawns an external agent harness as a separate process; options carry the MCP endpoint, allowed tools and skills only. The runner re-executes assertions against stored artifacts and computes stats (majority-of-R, Wilson CI, gap). Held-out is age-encrypted with `SEAL.json`; only `gate run --exit` unseals. Sensitivity scores are current only while `validator_sha` matches.
- **Mutations** during a build use the existing typed `sketch_*`/`feature_*` tools under the AD-5 protocol. Visual review is per part, never per mutation.

## Cross-Story Dependencies

- **Prerequisite:** gate G2 green (Epic 3 done). Story 4.1 is landed (in review).
- **4.2 owns the deferred 4.1 work:** the anchor-frame resolver, the six primitives the G2 grader lacks (`hole_diameter`, `hole_position`, `distance_between`, `angle_between`, `expect_bbox`, `expect_extent`), the plan replayer, the cross-leg frame check and the sensitivity score. Open points to settle there:
  - `expect_bbox`/`expect_extent` axis order (sorted extents or frame-axis order); `g3-dev-009` on `XZ_Plane` depends on it.
  - The replayer binds `'$doc'` to the handle from `document_create`, runs preview/confirm, and must confirm plan assumptions: body plane `XY_Plane`, `select: {diameter, axis}` selector syntax, `largest_planar_face` origin at the face centroid.
  - Planted plans for specs 003, 007, 008, 010 and 011 have no control. Each must grade clean with its planted step reverted before its detection counts toward sensitivity.
- **One resolver only.** The partial G2 grader lives in `benchmarks/harness/assertions.py`; the design places measurements in `usecases/`. Decide placement in 4.2. The spec set, the G3.3 re-check (4.4) and the exit grader (4.5) all use the same resolver.
- **4.3** owns the ≥2048 px render and drawing path, a headless TechDraw SVG/PNG export spike under the render-leg environment, and drawing-generator fault cases (a planted wrong-callout sheet).
- **Story 6.5** must land `design-loop`, `visual-review` and `spec-to-assertions`. None is in `skills/` today.
- **4.5 depends on 4.1–4.4 and 6.5.** It needs a run-bound `spot_audit` token. G3.5 reads visual findings from the run workdir, but `run_id` threading is Story 5.4 (Phase 4). This ordering conflict needs a decision before 4.5 starts.
- **Operator items before exit:** countersign the agent-attested license checks on the 16 G3 fault-case manifests; review the sealed 7-case held-out split for weak assertions (reading it spends an unseal event); decide whether `g3-dev-007`'s blind bore is flat-bottomed (a `feature_hole` drill point fails its volume check).
- **Doc drift to ignore:** the harness design says per-part timing includes "judge" time. No judge exists. Time spans agent thinking, tool calls and TechDraw generation.
