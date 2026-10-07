# Epic 11 Context: Lean Agent Loop

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Let an agent build a part with fewer calls and a small context, while every mutation still runs every check. A result reports what changed and what failed, not every value that passed. With operator auto-approve, attended GUI work applies a mutation in one call. Skills stop asking for checks the mutation result already reports. On a large document, a change freezes the GUI only for FreeCAD's own recompute, not for bridge overhead. Trigger: three kiwibox-drawer build sessions on 2026-10-06 (`eacac40d`, `ff604ce5`, `0320ba38`) used 98-310 FreeCAD calls and reached 797K-820K context tokens. 86 % of FreeCAD output was full fingerprints and PASS findings that no caller reads. One change on a copy of `kiwibox-drawer.FCStd` costs about 65 s with preview, of which FreeCAD's recompute is 29 s. Two correctness defects also surfaced: compound shapes record zero principal moments, and the abort-path rollback proof fails on new B-rep bytes, so every failed mutation closes and reopens the document. The epic opens no gate and reopens no epic (AD-19). Epic 10 Story 10.7 starts only after Stories 11.1-11.4.

## Stories

- Story 11.1: Mass Properties That Tell Shapes Apart
- Story 11.2: Quiet Result Envelope
- Story 11.3: One Call per Mutation
- Story 11.4: Cheap, Correct Rollback Proof and Fingerprints
- Story 11.5: Build-Loop Skills
- Story 11.6: Measured Build Session

## Requirements & Constraints

- **No check is removed or weakened.** Each story proves that the AD-5 bracket, the AD-6 rollback proof, the AD-7 audit and the AD-8 sketch signal still run and still fail a bad change. The server checks everything; the response reports what changed and what failed.
- **Re-run validator scores whose sources change:** G2 scores that use `run_mutation`, `audit_references` and `fingerprint()`. The G2 fault suite (rollback-boundary #6031-pattern, TNP-provoking, dress-up silent drop) must fail or flag exactly as before. Gate G2.3 (hash-identical rollback in 100 % of cases) is unchanged: digests are still computed and compared on the server. Never open `benchmarks/*/heldout`.
- **CAP-3 unchanged:** preview, confirm, auto-verify and provable rollback all stay available. `preview_dry_run` stays.
- **Not in scope (rejected or deferred):** agent-decides `on_failure: "keep"` (rejected, automatic rollback stays); generic typed batch tool (rejected); sketch primitives, composite profile tool, clearance tool, TNP Layer 1 scoping, MCP elicitation (deferred until Story 11.4 and 11.6 numbers exist).
- **Reference document for evidence and timing:** a copy of `kiwibox-drawer.FCStd` (184 objects). Never edit the original. Timing method: median of 5, headless and in the GUI; bridge overhead = total time minus FreeCAD's recompute.
- **Epic acceptance targets (Story 11.6, against `0320ba38` baseline):**

| Measure | Baseline | Target |
|---|---|---|
| FreeCAD output chars per FreeCAD call | 9,590 | ≤ 1,440 |
| Results over the client size limit (spilled) | 15 | 0 |
| Largest FreeCAD result | 109K | ≤ 10K |
| FreeCAD calls per feature (median) | 6 | ≤ 2 |
| Bridge overhead per mutation, drawer-size document | about 15 s apply / 50 s preview + apply | ≤ 3 s |
| Checks run per mutation (AD-5/6/7/8) | all | all |

- Story 11.6 also needs a real FreeCAD screenshot visual check and a native Check Geometry pass (`freecad-native-validation` standard). Report committed under `tests/uat/run/`.

## Technical Decisions

- **AD-6 mass properties (Story 11.1):** quantized tuple is volume, area, bbox, COM, principal moments @1e-6, plus the inertia tensor about the COM. All values come from the shape's solids, so a non-empty compound never records zero moments. `MassProps.inertia` = 6 values `Ixx, Iyy, Izz, Ixy, Ixz, Iyz` about the COM in document axes, optional field added to `fcb.fingerprint/1` (additive, AD-28). Reason: principal moments are eigenvalues, so they do not change under a rotation or mirror about the COM; the tensor does. The `inertia` quantization step is calibrated so an abort + recompute on the drawer copy gives `massprops_equal == True` on every object. A solid with symmetric inertia is a documented limit.
- **`massprops_equal` invariants:** `volume`, `area`, `com`, `principal_moments`, `inertia`. `bbox` is excluded. It is the identity check in 4 of 5 comparison sites (transaction, preview, screenshot, documents).
- **AD-5 rollback proof (Story 11.4):** abort path proves rollback by digest equality, else by `massprops_equal` over the same object names, because a recompute after `abortTransaction` writes new B-rep bytes for geometry it restored. Only an invariant mismatch restores the `saveCopy` snapshot (AD-25 location rules). Snapshot-restore path proves with `massprops_equal`. Abort-path and snapshot-restore proofs compute every fingerprint entry fresh, never from cache.
- **Fingerprint work per mutation (Story 11.4):** a live mutation runs `fingerprint()` 2 times, not 3: the confirm gate record is passed into `run_mutation` as `fp_before`. The failure path reuses the rollback-proof fingerprint. A per-object entry cache reuses an entry whose shape is unchanged since its last fingerprint; a changed shape never reuses its entry. `snapshot_references` reads a property value only after its type passes the link-type filter.
- **AD-6 wire projection (Story 11.2):** the full `FingerprintRecord` never travels in a tool result. It stays in a digest-keyed in-process cache; `document_undo(expect_fingerprint=<digest>)` resolves through it. `MutationBlock` `fcb.mutation/2`: `fingerprint_before` / `fingerprint_after` = `{digest, serializer}`; `changed: [{name, volume, area, com}]` per object whose invariants differ (empty on a no-op). Failed or rolled-back mutation: each `changed` entry adds full `before` and `after` `MassProps`. `rolled_back` / `rollback_proven` unchanged.
- **AD-7 audit on the wire:** `tnp_audit` and `tnp_precheck` = `{status, element_map_version, counts: {<verdict>: n}, findings: [non-PASS only]}`. The full per-reference list is still computed and decides the aggregate verdict; only PASS entries are not serialized. Counts prove the audit ran: an empty list with `CLEAN` is a clean audit, never a skipped one. FLAGGED lists every non-PASS finding.
- **Preview diff `fcb.geometry-diff/2`:** `op` = `{tool}` only (the confirm token signs the args digest); `text` does not repeat `preview_id`.
- **Tool-results convention:** silent on pass, loud on fail. A passing check reports verdict and counts; a failing check reports its detail. No result echoes request arguments. Wire JSON is compact (no `indent=2` in `adapters/mcp_server.py`).
- **AD-17 / AD-28:** the projection is built in `usecases/` so every surface gets one envelope shape. Contract changes take a major bump (`fcb.mutation/2`, `fcb.geometry-diff/2`); `/1` is retained for audit replay. Generated JSON Schemas must pass the drift check.
- **AD-10 confirmation (Story 11.3):** `autoApprove` is an operator posture valid in every client context, attended GUI included. With `FREECAD_BUDDY_AUTO_APPROVE=1` set before FreeCAD starts, a mutation without `confirm` applies in one call under the full AD-5 bracket; the audit log records an `auto_approve` approval. A post-verify failure rolls back and returns its status exactly as with a token. Auto-approve unset: every mutation still needs a valid `preview_id`, except the display-state carve-out.
- **Display-state carve-out:** `feature_set_parameters` that writes only `Visibility` is confirm-exempt (same as `view_fit_viewport`), still runs the AD-5 bracket and is audit-logged. Any other property in the same call keeps the gate.
- **AD-15 skills (Story 11.5):** `SKILL.md` keeps 4 sections and ≤ 1,500 words (`scripts/check_skill_shape.py`); long material goes in `references/`. A body may name a sibling skill in prose only. AD-21 review floor (≥ 2048 px for review-directed images) still applies where it applies; 800 px is the default user-facing screenshot size.
- **AD-35:** workflow, checklists and visual review live in skills, never in shipped code. The Story 11.6 metrics script is a repo tool in `scripts/automation/`, not shipped bridge code.
- **AD-1 rings:** imports point inward only, `contracts/` ← `usecases/` ← `adapters/` ← `hosts/`.

## Cross-Story Dependencies

- 11.1 before 11.2 and before 11.4: 11.2 makes mass properties the visible change record, and 11.4 makes them the abort-path rollback proof.
- 11.3 and 11.4 are parallel-eligible with 11.2. 11.4 edits `usecases/transaction.py`, so it merges after 11.2.
- 11.5 is parallel-eligible. It must match the 11.2 field names (`changed`, `post_verify.tnp_audit`, `mutation.fingerprint_*`) and the 11.3 auto-approve posture.
- 11.6 is last: needs 11.1-11.5 done, auto-approve set and the updated skills installed. It closes the epic.
- Epic 10: Stories 11.1-11.4 finish before Story 10.7, so UAT test cases (TC-05, TC-08 read full fingerprints and findings) and the 10.7b runner are written once, on the new envelope.
- Tests that assert the old envelope change with 11.2: `test_contracts.py`, `test_mutation_contract.py`, `test_framing_envelope.py`, generated `mutation.schema.json` and `geometry-diff.schema.json`.
- Operator: re-copy updated skills into user projects after 11.5; set `FREECAD_BUDDY_AUTO_APPROVE=1` for attended GUI work. Setup documented in `README.md` and the GUI harness standard (11.3).
