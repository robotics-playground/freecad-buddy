# Epic 11 Context: Lean Agent Loop

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Let an agent build a part with fewer calls and a small context, while every mutation still runs every check. Server checks everything; a result reports what changed and what failed, not every value that passed. With operator auto-approve, attended GUI work applies a mutation in one call. Skills stop asking for checks the mutation result already reports. On a large document a change freezes the GUI only for FreeCAD's own recompute, not for bridge overhead. Trigger: three build sessions on 2026-10-06 used 98-310 FreeCAD calls and 797K-820K context tokens; 86 % of FreeCAD output was full fingerprints and PASS findings that no caller read. One change on the drawer copy costs about 65 s with preview, of which recompute is 29 s. Every failed mutation closes and reopens the document, because recompute after abort writes new B-rep bytes and the digest proof fails. Opens no gate, reopens no epic (AD-19).

## Stories

- Story 11.1: Mass Properties That Tell Shapes Apart
- Story 11.2: Quiet Result Envelope
- Story 11.3: One Call per Mutation
- Story 11.4: Cheap, Correct Rollback Proof and Fingerprints
- Story 11.5: Build-Loop Skills
- Story 11.6: Measured Build Session

## Requirements & Constraints

- **No check removed or weakened.** Each story proves the AD-5 bracket, the AD-6 rollback proof, the AD-7 audit and the AD-8 sketch signal still run and still fail a bad change. Checks decide on full data; only the serialized result shrinks.
- **Re-run validator scores whose sources change** (`run_mutation`, `audit_references`, `fingerprint()`). G2 fault suite (rollback-boundary #6031-pattern, TNP-provoking, dress-up silent drop) fails or flags exactly as before. G2.3 unchanged: digests still computed and compared on the server. Never open `benchmarks/*/heldout`.
- **CAP-3 unchanged:** preview, confirm, auto-verify, provable rollback stay; `preview_dry_run` stays available.
- **Out of scope:** agent-decides `on_failure: "keep"` and generic typed batch tool (rejected); sketch primitives, composite profile tool, clearance tool, TNP Layer 1 scoping, MCP elicitation (deferred, decide on 11.4/11.6 numbers).
- **Reference document:** a copy of `kiwibox-drawer.FCStd` (184 objects); never edit the original. Timing: median of 5, headless and GUI; bridge overhead = total time minus FreeCAD's recompute.
- **Epic acceptance (Story 11.6, baseline `0320ba38`):** FreeCAD output chars per call 9,590 → ≤ 1,440; spilled results 15 → 0; largest result 109K → ≤ 10K; calls per feature (median) 6 → ≤ 2; bridge overhead per mutation about 15 s apply / 50 s preview + apply → ≤ 3 s; checks per mutation (AD-5/6/7/8) all → all. Plus agent visual check against a real FreeCAD screenshot and native Check Geometry (`freecad-native-validation`). Report with baseline beside new numbers under `tests/uat/run/`.

## Technical Decisions

- **Mass properties (AD-6, landed in 11.1):** computed from the shape's solids; a non-empty compound never records zero moments. A shape with no solids uses its own `MatrixOfInertia`. Principal moments = eigenvalues by cyclic Jacobi; trigonometric closed form banned (fails on two equal moments). `MassProps.inertia` = `Ixx, Iyy, Izz, Ixy, Ixz, Iyz` about the COM in document axes, optional in `fcb.fingerprint/1`. `volume`, `area`, `bbox`, `com` round to 1e-6. Moments and tensor round to per-object step `10^(floor(log10(s) + 1e-9) − 9)`, `s` = largest absolute diagonal component; 1e-6 when `s` is 0 or not finite. Exponent 9 calibrated on the drawer copy (recompute jitter about 1.1e-15 of `s`); recalibrate after a FreeCAD or OCCT upgrade. Fixed absolute tensor step rejected. The tuple is digest material, so every digest changed with 11.1; a stored record without `inertia` never equals anything.
- **Documented limit:** record stays equal under 180° rotation about a principal axis through the COM, point reflection through the COM, mirror through a COM plane normal to a principal axis, any rotation of a solid with three equal moments, rotation of an axisymmetric part about its axis. A compound with no solids records zero moments and tensor.
- **`massprops_equal`:** compares `volume`, `area`, `com`, `principal_moments`, `inertia`; `bbox` excluded (tessellation-derived). Read-only-after-render and snapshot-restore verdicts use it, never the digest.
- **Rollback proof (AD-5, 11.4):** abort path proves by digest equality, else `massprops_equal` over the same object names; only an invariant mismatch restores the `saveCopy` snapshot, then asserts `massprops_equal` on the reopened document. Snapshot location and cleanup per AD-25. Abort and snapshot-restore proofs compute every fingerprint entry fresh; the per-object cache serves only unchanged shapes.
- **Wire projection (AD-6/AD-7, landed in 11.2):** one pure stdlib projection in `usecases/` (AD-17). `fcb.mutation/2`: `fingerprint_before` / `fingerprint_after` = `{digest, serializer}` (`fingerprint_after` null on setup or commit failure); `changed: [{name, volume, area, com}]` for objects whose `massprops_equal` invariants differ, empty on no-op; failed or unproven rollback adds `before` / `after` `MassProps` (null for a missing side). `transaction_id`, `verify_verdict`, `params_digest` are off the wire; the audit log keeps them, written from the full block. `snapshot_path` only when not null. `rolled_back` / `rollback_proven` on every block. `fcb.geometry-diff/2`: `op` = `{tool}`, args not echoed (confirm token signs their digest).
- **Audit blocks on the wire:** `tnp_audit` / `tnp_precheck` = `{status, element_map_version, counts: {<verdict>: n}, findings: [non-PASS only]}`. Full list still decides the verdict. `CLEAN` with empty findings is a clean audit, never a skipped one; counts prove it ran.
- **Record cache:** full `FingerprintRecord`s live in a bounded digest-keyed in-process cache (64 records). `document_undo(expect_fingerprint=<digest>)` resolves a cached digest and compares digest, else `massprops_equal`; an unknown digest (evicted, other process) falls back to byte comparison.
- **Tool-results convention:** silent on pass, loud on fail; no echo of request arguments; compact JSON on the wire.
- **Schema evolution (AD-28):** major bump for any removal or rename; old major retained unchanged in `contracts/jsonschema/retained/<name>-<major>.schema.json`, outside the drift check. Generated schemas pass drift check.
- **Auto-approve (AD-10, 11.3):** an operator posture valid in every client context, read once at host start from env var `FREECAD_BUDDY_AUTO_APPROVE`, never a client-supplied parameter. On by default in every host: unset or `1` is on, any other value (`0`, `false`, empty) is off. When on, a mutation without `confirm` applies in one call under the full AD-5 bracket; post-verify failure rolls back as with a token. A call that sends `confirm` takes the full token check in every posture. Each auto-approval writes an audit `approval` record with `mode: "auto_approve"` and `source` = env var name. With `=0`: every mutation needs a valid `preview_id`, except `feature_set_parameters` without `confirm` that writes only `Visibility` (`mode: "display_state"` in either posture; still bracketed and audit-logged; any other property in the call keeps the gate).
- **Skills (AD-15, AD-35, 11.5):** `SKILL.md` keeps 4 sections, ≤ 1,500 words (`scripts/check_skill_shape.py`). Workflow, checklists and visual review live in skills, never in `src/`. Default user-facing screenshot 800 px; AD-21 ≥ 2048 px review floor where it applies. The 11.6 metrics script is a repo tool in `scripts/automation/` (11.2 added `replay_result_sizes.py` there).
- **AD-1 rings:** imports inward only, `contracts/` ← `usecases/` ← `adapters/` ← `hosts/`.

## Cross-Story Dependencies

- 11.1 and 11.2 implemented (status: review). 11.2 replay: 89.2 % size drop on 527 parseable recorded results.
- 11.4 builds on 11.1 invariants and edits `usecases/transaction.py`, so it merges after 11.2. 11.3 and 11.4 are parallel-eligible.
- 11.5 is parallel-eligible; it must match the shipped field names (`changed`, `post_verify.tnp_audit` with `counts`, `mutation.fingerprint_*` digests) and the 11.3 auto-approve posture.
- 11.6 is last: needs 11.1-11.5 done, auto-approve set, updated skills installed.
- Epic 10: 11.1-11.4 finish before Story 10.7. UAT cases TC-05 and TC-08 still describe the `/1` shapes (`transaction_id`, full records, PASS findings); 10.7 moves them to `/2` and uses `counts`.
- Open gaps (deferred): no G2 fault case plants a rotation or mirror about the COM; `volume` / `area` / `com` at 1e-6 can jitter above about 1e9 mm³; no test detects jitter outgrowing the exponent-9 step; no-solids face compounds hide rotation; undo on a cache-miss digest stays byte-exact (DW-97 gap); MCP text content is the whole envelope JSON, not the one-line `text` summary the tool catalog states.
- Operator: auto-approve is on by default; set `FREECAD_BUDDY_AUTO_APPROVE=0` before FreeCAD starts to require previews (documented in `README.md` and the GUI harness standard); re-copy updated skills into user projects after 11.5.
