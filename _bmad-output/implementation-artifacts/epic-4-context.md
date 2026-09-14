# Epic 4 Context: Spec-to-Part Designer (Phase 3 · gate G3)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Epic 4 delivers Phase 3: a user hands over a written part spec, approves one plan, and gets back an editable parametric part that is *measured* against the spec — not asserted to meet it. The loop plans, executes over Epic 3's Phase 2 mutation tools, measures the produced artifact with a closed deterministic assertion vocabulary, reads the discrepancy vector plus an independent visual judge's findings, and self-repairs within a hard cap of three iterations. "Done" is conjunctive: geometry assertions pass **and** an independent vision model passes the part against the spec. Gate G3 exits only when 20 real-world specs — whose assertions were compiled before any designer code existed — run green on the sealed held-out split, the parts stay editable, and a human spot-audit token is bound to the run.

## Stories

- Story 4.1: Entry Gate G3.E — Specs, Assertions, Judge & TechDraw Spike
- Story 4.2: Assertion Primitives
- Story 4.3: TechDraw Drawing Generator
- Story 4.4: Visual Judge (`verify_visual`)
- Story 4.5: Designer Loop
- Story 4.6: Parametric Editability
- Story 4.7: Gate G3 Exit

## Requirements & Constraints

- **Validators land before designer code.** No Phase 3 implementation begins until the entry gate is complete: 20 specs with compiled assertion sets, dev/held-out sealed, 10 corrupted-plan fault cases, a fault-tested visual judge, a written grading rubric, and a reuse survey. The entry gate is timeboxed to roughly 20 % of the phase, not added on top of it.
- **Every validator proves itself before its scores count.** The assertion layer and the visual judge each need a ≥10-case fault-injection suite reporting sensitivity ≥95 % / false-alarm ≤5 %. Planted assertion faults: missing hole, wrong diameter, mirrored pattern, 0.5 mm spacing error. Planted judge faults: mirrored part, missing flange, feature on the wrong face, grossly wrong proportions, wrong-dimension-callout drawing, plus clean controls. Editing the judge rubric or checklist invalidates prior sensitivity runs.
- **Specs have real-world provenance.** Every shipped spec derives from a documented real part or user request, from commercially clean sources only. A spec reverse-engineered to fit what the agent already does well is banned. Each benchmark artifact carries a provenance record.
- **Assertions measure the artifact, never the plan.** Assertions were authored independently of any plan and grade geometry, not tool success. Feature metadata (for example a hole feature's declared diameter) is a diagnostic hint only and never the verdict. Sub-element index selectors are banned in specs — selectors are geometric queries. Whole-shape similarity metrics are never a primary measure.
- **Convergence is the verdict, never the iteration count.** The loop declares done only when geometry ∧ visual both pass. Hitting the repair cap is a failure, not a finish. Repair input is the geometry discrepancy vector plus the judge's findings.
- **Fail-closed visual leg.** Render capability absent or judge unreachable → the part is not done. The only bypass is an explicit operator waiver, audit-logged with its reason.
- **Parts stay editable.** Driving dimensions live as named, intent-bearing parameters, every sketch reaches `FullyConstrained`, and the solid is watertight and recompute-clean.
- **Budget is pass/fail.** Median per-part wall-clock ≤10 min, measured by the harness on one basis (tool-call entry to envelope return, model time included), spanning all repair iterations including judge and drawing generation. A run that meets every assertion and blows the budget fails the gate.
- **Run traceability.** Every Phase 3 run carries a `run_id` threaded through every envelope, audit record, and validation report, and writes plan, per-iteration discrepancy vector, judge verdicts with their images, and repair decisions to the session workdir. A failed production run must be reconstructable from its workdir alone, without the agent's context.

### G3 exit criteria (what "done" means for the epic)

- G3.1 Spec benchmark: 20 specs end-to-end, one human plan approval — **≥70 % pass within ≤3 self-repairs**; dev/held-out gap ≤15pp at R≥10.
- G3.2 Artifact hygiene: **100 %** valid watertight solid, recompute-clean, all sketches `FullyConstrained`, driving dimensions exposed as named parameters.
- G3.3 Editability: change one driving parameter per passing part, recompute — **≥90 % recompute without errors**.
- G3.4 Fault catch: 10 corrupted-plan cases through the loop — **≥9/10 detected, zero silent bad parts**.
- G3.5 Throughput: **median ≤10 min** per part.
- G3.6 Skills track convergence: the parallel skills gate criteria met, including the `design-decomposition` claim on its dedicated n≥40 set.
- G3.7 Visual leg: **100 %** of passing parts carry a judge PASS from the standard visual set at temperature 0.
- A `spot_audit` human token must be bound to the run — it hashes the run's report set, covers ≥20 % of passing results, and cannot be recycled across runs. Any audit-found false pass invalidates the run.

## Technical Decisions

- **Anchor frame is declared per spec, from a closed derivation set:** named datum | base sketch plane | largest-planar-face fallback, resolved by one shared implementation. Every member must be total and deterministic — it yields exactly one frame on every supported FreeCAD leg or it raises. The largest-planar-face fallback therefore needs a mandatory tie-break (largest area, then lowest centroid along global Z, then lowest sorted mapped name), because face order differs across legs and an untied frame flips the origin on a symmetric part. The resolved face's mapped name goes in the report banner. A spec whose frame does not resolve identically on both CI legs is a broken spec, not a failing part. All measurements transform into this frame before comparison — including bounding-box extents, which are measured in frame, never as the naive global box.
- **Assertion primitive set (closed vocabulary, names and signatures owned by `contracts/`, measurements in `usecases/`):** `is_valid_solid`, `count_cylindrical_holes`, `hole_diameter`, `hole_position`, `hole_spacing`, `hole_through`, `distance_between`, `angle_between`, `expect_bbox`, `expect_extent`, `expect_volume`. Each returns `(passed, measured, expected, tolerance, detail)` inside a validation report. Measurements wrap the typed-geometry surface (`Face.Surface` → cylinder radius/center/axis) that the shipped Measure module already uses — wrapped, never forked.
- **Disambiguation rules are normative, not heuristics.** Hole vs boss: a cylindrical face is a hole wall only when material lies outside the cylinder (normal orientation or an inside-solid membership test on a point offset toward the axis). Coaxial grouping: faces sharing an axis direction with collinear centers merge into one logical hole before counting, so stepped or split walls do not inflate counts. Fillet filtering: count only faces whose bounding edges include full circles, then filter by the spec's radius band. Countersink/counterbore: a cone or larger coaxial cylinder on the same axis belongs to the same logical hole, checked only when the spec asserts it.
- **Tolerances are calibrated against planted faults, not guessed.** Starting points: linear ±0.05 mm, angle ±0.1°, volume ±1 % relative, coaxial grouping ≤0.1° axis angle and ≤0.01 mm center-line offset. No assertion may be tighter than the measured shape's own `Shape.getTolerance`.
- **Drawing generation runs on a TempDoc copy.** `techdraw_for_judge` builds a page, three orthographic projections (front/top/right), and dimensions on a transient copy under the reserved name prefix, then exports and discards it. The part document is never polluted — its fingerprint must be unchanged across the call. Dimensions are generated **from the part's named driving parameters and the spec's assertion set**, not picked from view geometry, which makes them immune to topological-naming drift. Pages export at ≥2048 px width; below that the dimension cross-check degrades to noise.
- **Judge independence is enforced at preflight**, the same separation rule as the read-only phase's grader: a separate model id or a separate context, never the acting agent. The judge runs at temperature 0 and returns a schema-validated `{pass, findings: [{view, observation, severity}]}` wrapped as the check id `visual.judge`.
- **Judge cadence is pinned:** the visual leg runs once per candidate part, at the end of each repair iteration whose geometry assertions all pass — never on an iteration geometry already failed, since the judge is conjunctive and could not change that verdict. A judge failure counts as one repair iteration against the ≤3 cap. Per-operation verification stays geometry-only.
- **Judge precedence on dimensions:** a drawing-callout-vs-spec mismatch is a finding that blocks done and triggers investigation of both the part and the assertion compilation, but geometry assertions remain the authoritative measurement — findings are re-checked against the deterministic `verify_*` measurements before any rework. The judge never overrides a passing geometric measurement with a misread callout.
- **Judge images bypass the user-facing render budget.** They travel straight to the judge API, not through client context, so the ≥2048 px legibility floor governs them instead of the user-facing size cap.
- **Driving dimensions go through the shim façade**, which prefers a VarSet and falls back to a Spreadsheet, selected by capability probe rather than version string. The façade is the single home for the parameter surface; downstream stories read and write dimensions only through it.
- **No new architectural ring for the loop itself.** The designer loop is agent-side plan/execute over the existing Phase 2 mutation tools; the new code is the assertion compiler and benchmark-runner extensions, plus the `techdraw_for_judge` and `verify_visual` use cases and an external judge client adapter.
- **Benchmark case format** declares its anchor frame and its check list in the case contract; the harness resolves assertion names to deterministic re-executed checks. Agent claims are never echoed as results.

## UX & Interaction Patterns

- The human approves the plan **once**, at the start. Everything after that is self-repair — the entire point of the epic is that the user does not supervise the build step by step.
- Failure is diagnostic, not just a verdict: the discrepancy vector and the judge's per-view findings are what the loop reads, and what a human reads when the loop gives up.

## Cross-Story Dependencies

- **Depends on Epic 3 (gate G2 green)** for the whole mutation surface the loop drives: the transaction bracket, sketch and feature tools, fingerprints, the topological-naming guard, and `verify_shape`/`verify_sketch`/`verify_recompute`. Depends on Epic 1 for the render path, the gate runner, the audit log, the envelope/validation-report contracts, and the capability-probe shim.
- **Story ordering.** 4.1 is a hard prerequisite for everything — no designer code before its specs, assertions, judge fault suite, and the headless drawing-export spike answer exist. 4.2 implements the vocabulary 4.1 compiled the specs against; a mismatch between the two is reconciled deliberately, not silently. 4.3 feeds 4.4 (drawings are part of the judge's standard input set). 4.5 consumes 4.2 and 4.4 as its convergence test. 4.6's parameter façade is also 4.3's dimension source, so the two should agree on naming before 4.3 lands. 4.7 is last and unseals the held-out split exactly once.
- **G3.6 rides the parallel skills track** (Epic 6): the skills gate criteria and the `design-decomposition` effect claim must land before G3 can exit. The ablation harness is shared infrastructure, not Epic 4 code.
- **Gate-sequential:** G3 must be green before Epic 5, whose headless service runs exactly this loop and re-executes its visual verdict in job delivery.

## Known Gaps in the Planning Artifacts

- **Judge-image render path does not exist.** The shipped render path caps at 1920 px in code, and the ≥2048 px judge carve-out the visual leg assumes needs a separate render entry point. This is recorded as a deferred item, with no design written for it — Story 4.3 or 4.4 must resolve it.
- **Headless drawing export is an unresolved spike.** Whether page export to PNG/SVG works without the GUI drawing module under the render-leg environment is an open question that Story 4.1 must answer before 4.3 is designed.
- **Conflicting record on whether dimensioned drawings belong in the judge input set.** An earlier decision note excludes them (dimension reading being the assertions' job); the adopted decision record and gate criteria include them. Treat the adopted record as authoritative and flag the stale note.
- **The parameter-edit-survives test has no design.** Editability is stated as a gate number with the parameter façade named as its enabler, but no document specifies how a driving-parameter change is chosen, applied, or judged clean. Story 4.6 defines it.
- **Corrupted-plan fault cases are named but not specified.** The 10 cases are required with a ≥9/10 catch rate; no document enumerates what a corrupted plan looks like. Story 4.1 must define the taxonomy.
