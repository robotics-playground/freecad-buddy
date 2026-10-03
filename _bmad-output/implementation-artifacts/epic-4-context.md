# Epic 4 Context: Spec-to-Part (Phase 3 · gate G3)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

A user gives a written part spec. A driving agent returns an editable parametric part that measurably meets it: geometry assertions pass, and the agent has looked at the rendered views. This repository supplies only three things: what the agent measures with (assertion primitives in a declared anchor frame), what it looks at (iso/focus renders plus a dimensioned drawing sheet), and the parameter façade that keeps the part editable. The plan → execute → measure → repair loop lives in the agent and in the Track W skills (`design-loop`, `visual-review`, `spec-to-assertions`), never in shipped code. An earlier implementation put a designer loop, a judge and actor plans in the repo; it was reverted. Do not rebuild any part of it.

## Stories

- Story 4.1: Entry Gate G3.E — Spec Set, Assertions & Fault Suite (landed)
- Story 4.2a: Assertion Primitives, Anchor-Frame Resolver, `verify_shape` `anchor_frame` input (done)
- Story 4.2b: Cross-Leg Frame Check (G3.E.3) & Corrupted-Plan Replay Scoring (G3.E.4)
- Story 4.3: Drawing Generator
- Story 4.4: Parametric Editability
- Story 4.5: Gate G3 Exit

## Requirements & Constraints

- **No loop in any shipped artifact.** `src/`, `benchmarks/` and skill helper scripts hold no planner, repair strategy, iteration count, judge, model client or credential. Test: would the repo behave differently depending on which model talks to it? If yes, the logic belongs in a skill body.
- **No done-predicate.** `verify_*` and assertions return measurements and per-check pass/fail. No code aggregates them into "part is done" or defines convergence.
- **Agent reaches tools only through MCP.** No in-process path into `usecases/` for any caller, the gate runner included.
- **Dual-channel done is the agent's verdict:** all geometry assertions pass AND the agent wrote per-part visual findings (view, observation, severity) to the run workdir. Enforcement is the evidence trail plus the ≥20 % human spot-audit, not a runtime check.
- **G3.E stays open until every entry item lands.** Owners: E.1, E.2, E.7 → 4.1 (landed); E.3 (frame resolves identically on 1.0.x and 1.1.x legs) and E.4 (corrupted-plan suite at sensitivity ≥95 % / false-alarm ≤5 % with `validator_sha`) → 4.2b; E.5 (render and drawing path at ≥2048 px) → 4.3; E.6 (three Track W skills exist) → 6.5. An item whose story has not landed reports `INVALID_INPUT`.
- **Exit criteria G3.1–G3.6:** ≥70 % of the spec set passes within ≤3 repairs at R≥10 on the sealed held-out split, dev/held-out gap ≤15pp; passing parts are valid, watertight, recompute-clean, all sketches `FullyConstrained`; ≥90 % recompute clean with one driving parameter changed and the change reflected; ≥9/10 corrupted plans detected with zero silent bad parts; visual findings present per passing part; ≤10 min median wall-clock per part, model time included.
- **Citability:** a number is citable only if a party that did not produce the work can recompute it from stored measurements. A cited rate is valid only for the actor model id in the banner.
- **Specs are commercial-clean,** derived from documented real-world parts, never reverse-fit to the agent. Each spec and fault case carries a provenance manifest. Any post-hoc spec or case-data edit adds a requirement the prose states, relaxes none, and is disclosed.
- **Held-out split stays sealed.** Never read or sweep `benchmarks/*/heldout`; only `gate run --exit` unseals.

## Technical Decisions

- **Assertion vocabulary is closed and shipped (4.2a).** Eleven primitives: `is_valid_solid`, `count_cylindrical_holes`, `hole_diameter`, `hole_position`, `hole_spacing`, `hole_through`, `distance_between`, `angle_between`, `expect_bbox`, `expect_extent`, `expect_volume`. Names and frame types live in `contracts/assertions.py` (`ASSERTION_FNS`, `AnchorFrameKind`, `DeclaredAnchorFrame{kind, ref}`, resolved `AnchorFrame`). Measurements live in `usecases/assertions.py` (one shared implementation). `benchmarks/harness/assertions.py` delegates to it, so grader and MCP tool measure the same way.
- **`verify_shape`** takes `checks` (`{fn, expect, tol?, select?, select_a?, select_b?, direction?}`) and an optional `anchor_frame {kind, ref}`; omitted frame = `global`. It returns a `ValidationReport`; a §7.2 check id is `assert.<fn>`; `banner.anchor_frame` records the resolved frame (kind, ref, entity, origin, axes).
- **Anchor frame rules.** `named_datum` / `base_sketch_plane`: `ref` matches object `Name`, else a unique `Label`; frame = its global placement. `largest_planar_face` (`ref: null`): largest area, then lowest centroid Z, then lowest mapped name (without mapped names: lowest centroid X, then Y); a surviving tie leaves the frame unresolved. Origin at face centroid, +Z into the part, in-plane X = document X projected onto the face (document Y if degenerate). The shape is measured in document coordinates.
- **`expect_bbox`** compares sorted exact extents (`optimalBoundingBox`) measured in the frame; axis order is ignored. `expect_extent` stays directional along one frame `direction`.
- **Failure codes.** Malformed input (unknown `fn`, wrong key, index selector like `Face6`, wrong `expect` arity, malformed frame) → `ValidationError`, envelope `INVALID_INPUT`. Empty selector match, unresolved frame, or a measurement that raises → that check fails with `detail.code = invalid_input.unsupported_assertion`; frame-free checks are still measured. Any other failed check → `SPEC_FAILED`. Feature metadata is a diagnostic hint only.
- **Tolerances** default linear ±0.05 mm, angle ±0.1°, volume ±1 %, never tighter than `Shape.getTolerance`.
- **Corrupted plan = recorded plan.** Each fault case is an ordered list of `{tool, args}` MCP steps with one planted step marked (controls have none). Plans replay through the mutation tools (AD-5 preview/confirm) and the part is graded with the spec's assertions. No builder script.
- **Drawing sheet:** front/top/right `DrawViewPart` projections on one `TechDraw::DrawPage`, built on a reserved-prefix (`FCB_TMP_`) TempDoc copy; the part document stays byte-identical. Dimensions come from driving parameters and spec assertions, not picked view geometry. One sheet-wide scale stated as a ratio. ≥2048 px page width.
- **Image budgets differ:** user-facing renders cap at 1920 px; review images are workdir artifacts with the ≥2048 px floor, so the review set needs its own entry point.
- **Driving parameters** go through the shim's VarSet façade with Spreadsheet fallback, selected by `shim.varset_available()`.
- **Validator currency.** Any change to a validator source stales its `validator_sha`; the four source-hash lists (runner, G0 and G2 scorers) must stay in sync, and scores must be re-run and written to `benchmarks/_registry/validators.yaml`.
- **Gate runner** spawns an external agent harness as a separate process; options carry MCP endpoint, allowed tools and skills only. It re-executes assertions against stored artifacts and computes stats (majority-of-R, Wilson CI, gap).

## Cross-Story Dependencies

- **Prerequisite:** gate G2 green (Epic 3 done). 4.1 and 4.2a landed.
- **4.2b depends on 4.2a primitives.** Decisions already taken:
  - G3.E.3: resolve frames on every part the corrupted-plan suite builds (controls and reverted planted plans) on both legs, plus a symmetric-shape tie-break test per frame kind. `gate.yaml` lists covered specs and leaves the rest as not proven. Only FreeCAD 1.1 is installed locally; the 1.0.x leg needs a new micromamba env or CI (per-leg artifact pattern).
  - G3.E.4: add `faithful_args` to the planted step of all 10 planted cases; replay each plan planted and reverted; a reverted build that does not grade clean makes the case `INVALID_INPUT`; reverted builds count as clean controls (14 controls). Disclose the data edit in `benchmarks/g3/README.md`.
  - Count detections per check: an empty-match `INVALID_INPUT` check can mask a measured `SPEC_FAILED` at part level.
  - The `largest_planar_face` mapped-name tie-break reads a `;:H<tag>` part that changes between sessions. Do not compare banner `entity` text across runs; if the step is unstable on both legs, propose an AD-13 correction.
  - Replayer binds `'$doc'` to the `document_create` handle and converts steps to `PlanStep` tuples.
- **4.3** owns the ≥2048 px render and drawing path, a headless TechDraw SVG/PNG export spike under the render-leg environment, and drawing-generator fault cases.
- **4.4** re-runs spec assertions through the same resolver after a parameter change.
- **Story 6.5** must land `design-loop`, `visual-review` and `spec-to-assertions`. None is in `skills/` today.
- **4.5 depends on 4.1–4.4 and 6.5.** It needs a run-bound `spot_audit` token. G3.5 reads visual findings from the run workdir, but `run_id` threading is Story 5.4 (Phase 4). This ordering conflict needs a decision before 4.5 starts.
- **Operator items before exit:** countersign the agent-attested license checks on the 16 G3 fault-case manifests; review the sealed 7-case held-out split for weak assertions (reading it spends an unseal event); decide whether `g3-dev-007`'s blind bore is flat-bottomed.
- **Doc drift to ignore:** the harness design says per-part timing includes "judge" time. No judge exists. Time spans agent thinking, tool calls and TechDraw generation.
