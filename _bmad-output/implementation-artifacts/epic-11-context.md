# Epic 11 Context: Lean Agent Loop

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Let an agent build a part with fewer calls and a small context, while every mutation still runs every check. The server checks everything; a result reports what changed and what failed, not every value that passed. With the operator auto-approve posture, a mutation applies in one call. Skills stop asking for checks the mutation result already reports. On a large document a change should freeze the GUI for FreeCAD's own recompute, not for bridge overhead. Trigger: three build sessions on 2026-10-06 used 98-310 FreeCAD calls and 797K-820K context tokens; 86 % of FreeCAD output was full fingerprints and PASS findings that no caller read. Opens no gate and reopens no epic (AD-19).

## Stories

- Story 11.1: Mass Properties That Tell Shapes Apart
- Story 11.2: Quiet Result Envelope
- Story 11.3: One Call per Mutation
- Story 11.4: Cheap, Correct Rollback Proof and Fingerprints
- Story 11.5: Build-Loop Skills
- Story 11.6: Measured Build Session

## Requirements & Constraints

- **No check removed or weakened.** Each story proves that the AD-5 bracket, the AD-6 rollback proof, the AD-7 audit and the AD-8 sketch signal still run and still fail a bad change. Checks decide on full data; only the serialized result shrinks.
- **Re-run validator scores whose sources change** (`run_mutation`, `audit_references`, `fingerprint()`, `verify_shape`). The G2 fault suite (rollback-boundary #6031-pattern, TNP-provoking, dress-up silent drop) fails or flags exactly as before. G2.3 is unchanged. Never open `benchmarks/*/heldout`.
- **CAP-3 unchanged:** preview, confirm, auto-verify and provable rollback stay; `preview_dry_run` stays available.
- **Out of scope:** agent-decides `on_failure: "keep"` and a generic typed batch tool (rejected); sketch primitives, composite profile tool, clearance tool, TNP Layer 1 scoping, MCP elicitation (deferred).
- **Reference document:** a copy of `kiwibox-drawer.FCStd` (184 objects); never edit the original. Timing method: `scripts/automation/time_mutation_overhead.py`, change `duct_pilot.Length`, median of 5, warm gate, headless and GUI; bridge overhead = tool time minus FreeCAD's recompute.
- **Epic acceptance (Story 11.6, baseline session `0320ba38`):** FreeCAD output chars per call 9,590 → ≤ 1,440; spilled results 15 → 0; largest result 109K → ≤ 10K; FreeCAD calls per feature (median) 6 → ≤ 2; all AD-5/6/7/8 checks per mutation. Agent visual check against a real FreeCAD screenshot and a native Check Geometry (`freecad-native-validation`). Report with baseline beside new numbers under `tests/uat/run/`.

## Technical Decisions

- **Mass properties (AD-6):** computed from the shape's solids; a non-empty compound never records zero moments. `MassProps.inertia` = `Ixx, Iyy, Izz, Ixy, Ixz, Iyz` about the COM in document axes, optional in `fcb.fingerprint/1`. `volume`, `area`, `bbox`, `com` round to 1e-6; moments and tensor round to per-object step `10^(floor(log10(s) + 1e-9) − 9)`, `s` = largest absolute diagonal component. `massprops_equal` compares `volume`, `area`, `com`, `principal_moments`, `inertia` (not `bbox`). Documented limit: point reflection, 180° turn about a principal axis, symmetric-inertia rotations, and no-solid compounds stay equal.
- **Rollback proof (AD-5):** abort path proves by digest equality, else `massprops_equal` over the same object names; only an invariant mismatch restores the `saveCopy` snapshot, proven by `massprops_equal`. Both proofs compute every fingerprint entry fresh. The gate fingerprint is reused as `fp_before`; the proof record is reused as `fingerprint_after`.
- **Fingerprint entry cache:** per document, an object reuses its entry when the cached `TopoShape` `isEqual` the current one; at most 4 documents held.
- **Wire projection (AD-6, AD-7, AD-17):** built in `usecases/`. `fcb.mutation/2` carries `fingerprint_before` / `fingerprint_after` as `{digest, serializer}`, `changed: [{name, volume, area, com}]` (adds `before` / `after` `MassProps` on failure or rollback), `rolled_back`, `rollback_proven`. `fcb.geometry-diff/2`: `op` = `{tool}`, args not echoed. `tnp_audit` / `tnp_precheck` = `{status, element_map_version, counts: {<verdict>: n}, findings: [non-PASS only]}`; `CLEAN` with empty findings is a clean audit, never a skipped one. Full records stay in a digest-keyed in-process cache that `document_undo(expect_fingerprint=<digest>)` uses.
- **Tool-results convention:** silent on pass, loud on fail; no echo of request arguments; compact JSON on the wire. Old schema majors are retained for audit replay (AD-28).
- **Auto-approve (AD-10):** operator env var `FREECAD_BUDDY_AUTO_APPROVE`, read once at host start, never a client parameter. On by default in every host: unset or `1` is on, any other value is off. When on, a mutation without `confirm` applies in one call under the full AD-5 bracket and writes an audit `approval` with `mode: "auto_approve"`. A sent `confirm` is checked in every posture. A `feature_set_parameters` call that writes only `Visibility` is display state: confirm-exempt, still bracketed and audit-logged.
- **Skills (AD-15, AD-35):** each `SKILL.md` keeps 4 sections and ≤ 1,500 words. Workflow, checklists and visual review live in skills, never in `src/`. Default user-facing screenshot 800 px; the AD-21 review floor stays where it applies. The tools `verify_references` and `verify_fingerprint` do not exist; skills point to `post_verify.tnp_audit` and the `mutation.fingerprint_*` digests. Story 11.6's metrics script goes in `scripts/automation/`.

## Cross-Story Dependencies

- Stories 11.1-11.4 are implemented (sprint status: review). Story 11.2 replay: 89.2 % size drop on 527 parseable recorded results.
- Story 11.4 measured bridge overhead (warm gate): 17.6 s headless, 9.4 s GUI (baseline 49.4 s headless). A human decision replaced the 11.4 ≤ 3 s target with ≤ 18 s headless / ≤ 10 s GUI. Story 11.6 AC3 still states ≤ 3 s, so it needs the same decision before 11.6 runs. Remaining cost: `fingerprint` × 2, `verify_shape` `isValid`, `features._feature_state`, `saveCopy`.
- Story 11.5 must match the shipped field names (`changed`, `post_verify.tnp_audit` with `counts`, `mutation.fingerprint_*` digests, `sketch_state.fully_constrained` / `dof`) and the default-on auto-approve posture. Its AC8 needs `scripts/check_skill_shape.py`, which does not exist yet (the spine assigns it to Story 6.1); build it or get a decision.
- Story 11.6 is last: needs 11.1-11.5 done, auto-approve on, and the updated skills installed in the user project.
- Epic 10: Story 10.7 starts after 11.1-11.4; UAT cases TC-05 and TC-08 move to the `/2` shapes there.
- Operator: set `FREECAD_BUDDY_AUTO_APPROVE=0` before FreeCAD starts to require previews; re-copy updated skills into user projects after 11.5.
