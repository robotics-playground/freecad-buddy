# Epic 11 Context: Lean Agent Loop

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Let an agent build a part with fewer calls and a small context, while every mutation still runs every check. A result reports what changed and what failed, not every value that passed. With operator auto-approve, attended GUI work applies a mutation in one call. Skills stop asking for checks the mutation result already reports. On a large document, a change freezes the GUI only for FreeCAD's own recompute, not for bridge overhead. Trigger: three build sessions on 2026-10-06 used 98-310 FreeCAD calls and 797K-820K context tokens; 86 % of FreeCAD output was full fingerprints and PASS findings. One change on the drawer copy costs about 65 s with preview, of which recompute is 29 s. A failed mutation closes and reopens the document because the abort-path proof fails on new B-rep bytes. Opens no gate, reopens no epic (AD-19).

## Stories

- Story 11.1: Mass Properties That Tell Shapes Apart
- Story 11.2: Quiet Result Envelope
- Story 11.3: One Call per Mutation
- Story 11.4: Cheap, Correct Rollback Proof and Fingerprints
- Story 11.5: Build-Loop Skills
- Story 11.6: Measured Build Session

## Requirements & Constraints

- **No check is removed or weakened.** Each story proves that the AD-5 bracket, the AD-6 rollback proof, the AD-7 audit and the AD-8 sketch signal still run and still fail a bad change. Server checks everything; response reports what changed and what failed.
- **Re-run validator scores whose sources change** (`run_mutation`, `audit_references`, `fingerprint()`). G2 fault suite (rollback-boundary #6031-pattern, TNP-provoking, dress-up silent drop) must fail or flag exactly as before. G2.3 (hash-identical rollback, 100 %) unchanged: digests still computed and compared on the server. Never open `benchmarks/*/heldout`.
- **CAP-3 unchanged:** preview, confirm, auto-verify and provable rollback stay available; `preview_dry_run` stays.
- **Out of scope:** agent-decides `on_failure: "keep"`, generic typed batch tool (rejected); sketch primitives, composite profile, clearance tool, TNP Layer 1 scoping, MCP elicitation (deferred).
- **Reference document:** a copy of `kiwibox-drawer.FCStd` (184 objects); never edit the original. Timing: median of 5, headless and GUI; bridge overhead = total time minus FreeCAD's recompute.
- **Epic acceptance (Story 11.6, against `0320ba38`):** FreeCAD output chars per call 9,590 → ≤ 1,440; spilled results 15 → 0; largest result 109K → ≤ 10K; calls per feature (median) 6 → ≤ 2; bridge overhead per mutation about 15 s apply / 50 s preview + apply → ≤ 3 s; checks per mutation (AD-5/6/7/8) all → all. Also a real FreeCAD screenshot visual check and native Check Geometry (`freecad-native-validation`). Report under `tests/uat/run/`.

## Technical Decisions

- **AD-6 mass properties (normative, landed with 11.1):** computed from the shape's solids; each solid's tensor rebuilt from `CenterOfMass` + `PrincipalProperties` and combined by the parallel-axis rule. `MassProps.inertia` = 6 values `Ixx, Iyy, Izz, Ixy, Ixz, Iyz` about the COM, document axes. Optional field in `fcb.fingerprint/1` (additive, AD-28). Principal moments = eigenvalues by cyclic Jacobi; trigonometric closed form is banned (fails on two equal moments).
- **Quantization:** `volume`, `area`, `bbox`, `com` round to `quantum` 1e-6. `principal_moments` and `inertia` round to per-object step `10^(floor(log10(s) + 1e-9) − 9)`, `s` = largest absolute diagonal tensor component; 1e-6 when `s` is 0 or not finite. `+ 1e-9` keeps round dimensions off a step boundary. Exponent 9 calibrated on the drawer copy (recompute jitter up to 1.1e-15 of `s`); recalibrate after a FreeCAD or OCCT version change. Fixed absolute tensor step is rejected (hides a small part's rotation).
- **No-solids shapes:** use their own `MatrixOfInertia`. A compound with no solids (multi-wire or point sketch, compound of faces) records zero moments and zero tensor, so its rotation is invisible.
- **Documented limit:** record stays equal under a 180° rotation about a principal axis through the COM, a point reflection through the COM, a mirror through a COM plane normal to a principal axis, any rotation of a solid with three equal moments, and a rotation of an axisymmetric part about its axis.
- **Digest break:** mass-property tuple is digest material. Every digest changed with 11.1; a stored digest never matches a fresh one, and a stored record without `inertia` is never `massprops_equal` to anything.
- **`massprops_equal`:** compares `volume`, `area`, `com`, `principal_moments`, `inertia`; `bbox` excluded (tessellation-derived). Identity check in 4 of 5 comparison sites.
- **AD-5 rollback proof (11.4):** abort path proves by digest equality, else `massprops_equal` over the same object names; only an invariant mismatch restores the `saveCopy` snapshot (AD-25). Snapshot-restore path proves with `massprops_equal`.
- **Fingerprint cache (11.4):** a per-object entry cache reuses only unchanged shapes; rollback proofs never use it.
- **AD-6 wire projection (11.2):** full `FingerprintRecord` never travels; it stays in a digest-keyed in-process cache that `document_undo(expect_fingerprint=<digest>)` resolves through. `fcb.mutation/2`: `fingerprint_before` / `fingerprint_after` = `{digest, serializer}`; `changed: [{name, volume, area, com}]` (empty on no-op); failed or rolled-back mutation adds full `before` / `after` `MassProps`. `rolled_back` / `rollback_proven` unchanged.
- **AD-7 on the wire:** `tnp_audit` / `tnp_precheck` = `{status, element_map_version, counts: {<verdict>: n}, findings: [non-PASS only]}`. Full list still computed and decides the verdict. Counts prove the audit ran.
- **Tool-results convention:** silent on pass, loud on fail; no echo of request arguments; compact wire JSON (no `indent=2` in `adapters/mcp_server.py`).
- **AD-17 / AD-28:** projection built in `usecases/`; major bump `fcb.mutation/2`, `fcb.geometry-diff/2` (preview `op` = `{tool}` only), `/1` kept for audit replay; generated schemas pass drift check.
- **AD-10 (11.3):** `autoApprove` is an operator posture valid in every client context. With `FREECAD_BUDDY_AUTO_APPROVE=1` set before FreeCAD starts, a mutation without `confirm` applies in one call under the full AD-5 bracket; audit log records `auto_approve`. Post-verify failure rolls back as with a token. Unset: every mutation needs a valid `preview_id`, except a `feature_set_parameters` that writes only `Visibility` (confirm-exempt like `view_fit_viewport`, still bracketed and audit-logged; any other property keeps the gate).
- **AD-15 / AD-35 (11.5, 11.6):** `SKILL.md` keeps 4 sections, ≤ 1,500 words (`scripts/check_skill_shape.py`); 800 px default user-facing screenshot, AD-21 ≥ 2048 px floor where it applies. Workflow and visual review live in skills; the 11.6 metrics script is a repo tool in `scripts/automation/`.
- **AD-1 rings:** imports inward only, `contracts/` ← `usecases/` ← `adapters/` ← `hosts/`.

## Cross-Story Dependencies

- 11.1 is implemented (status: review). 11.2 and 11.4 build on its invariants: 11.2 makes mass properties the visible change record, 11.4 the abort-path rollback proof.
- 11.3 and 11.4 are parallel-eligible with 11.2; 11.4 edits `usecases/transaction.py`, so it merges after 11.2.
- 11.5 is parallel-eligible; it must match 11.2 field names (`changed`, `post_verify.tnp_audit`, `mutation.fingerprint_*`) and the 11.3 auto-approve posture.
- 11.6 is last: needs 11.1-11.5 done, auto-approve set, updated skills installed.
- Epic 10: 11.1-11.4 finish before Story 10.7, so UAT cases (TC-05, TC-08 read full fingerprints and findings) and the 10.7b runner use the new envelope.
- Open gaps from 11.1 (deferred): no G2 fault case plants a rotation or mirror about the COM; `volume` / `area` / `com` at 1e-6 can jitter on parts above about 1e9 mm³; no test detects jitter outgrowing the exponent-9 step after a kernel upgrade.
- Operator: re-copy updated skills into user projects after 11.5; set `FREECAD_BUDDY_AUTO_APPROVE=1` for attended GUI work (documented in `README.md` and the GUI harness standard by 11.3).
