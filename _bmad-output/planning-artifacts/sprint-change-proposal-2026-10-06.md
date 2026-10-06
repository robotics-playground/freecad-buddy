# Sprint Change Proposal — Lean Agent Loop (2026-10-06)

Mode: batch. Author: Architect agent (Winston), for TanNT.

## 1. Issue Summary

**Trigger.** The MCP bridge works, but an agent that builds a real part with it uses too many calls and fills its context window too fast. Evidence: three Claude Code sessions that built the kiwibox drawer in the project `D:/Work/3D Printers/Ender 3V2 - Klipper` on 2026-10-06 (`eacac40d`, `ff604ce5`, `0320ba38`).

**Category.** Failed approach in shipped behaviour: the result envelope and the confirm protocol work correctly, but their cost per call makes long builds impractical. Part of it is drift: the code does not follow the spine.

**Evidence (measured from the session transcripts).**

| Measure | `eacac40d` | `ff604ce5` | `0320ba38` |
|---|---|---|---|
| FreeCAD tool calls | 98 | 107 | 310 |
| of which `preview_dry_run` | 36 | 39 | 77 |
| FreeCAD share of all tool output text | 75 % | 82 % | 84 % |
| Peak context (tokens) | 818K | 797K | 820K |
| Context compactions | 0 | 0 | 8 |

- **Output size.** Over all 3 sessions, FreeCAD output was 6.89M chars. Of that, `fingerprint_before` and `fingerprint_after` were 57 %, and the TNP finding lists (`post_verify.tnp_audit.findings` and `diff.tnp_precheck.findings`) were 29 %. 11,794 findings were `PASS` and 12 were `REPOINTED`. One `sketch_add_geometry` result averaged 32,003 chars, of which `sketch_state` was 230. On a 130-object document one `feature_set_parameters` result was 109K chars. 22 results went over the Claude Code size limit, were saved to file, and cost the agent extra reads.
- **No reader.** No caller reads the per-object fingerprint data or the `PASS` findings from the response. The agent passed digests only. Benchmarks read only `status` and non-PASS verdicts. `adapters/audit_log.py:136-137` stores digests only.
- **Drift.** Spine Tool-results convention (`ARCHITECTURE-SPINE.md:378`): "Text payloads are summarized, never raw dumps … so no result can blow the client's context by size alone." `data-contracts-design.md` §7 already defines `tnp_precheck` as `{status, flagged:[…]}`. The code returns every finding (`usecases/preview.py:587`) and echoes the full request args (`usecases/preview.py:579`).
- **Steps.** Every one of the 153 confirmed mutations had a preview call first. One feature costs 6 calls: `DRY(sketch_create) > sketch_create > DRY(sketch_add_geometry) > sketch_add_geometry > DRY(feature_pocket) > feature_pocket`. The preview never stopped a bad change. In `0320ba38`, call 301, the preview returned `SPEC_FAILED`, the agent confirmed anyway, and the AD-5 rollback refused the change. The sessions ran in `bypassPermissions` mode, so no human saw the `preview_id` token.
- **Time.** Model time is larger than tool time: 27 min against 0.9 min (`ff604ce5`), 120 min against 28 min (`0320ba38`). Each extra call costs one model turn over a large context.
- **Server work.** One live mutation computes 3 full-document fingerprints. The gate fingerprint (`usecases/confirm.py:332`) and `fp_before` (`usecases/transaction.py:604`) hash the same state one after the other. `snapshot_references` reads every property before the type filter (`usecases/tnp_guard.py:322`). On the 130-object document: `preview_dry_run` median 4.9 s, `feature_set_parameters` median 14.2 s.
- **Skills.** `skills/verification-thinking/SKILL.md:68-72` asks for a screenshot for "every part whose geometry changed", which the agent applied per feature (44 screenshots, 21 `verify_sketch`, 11 `verify_shape` after mutations that already reported the same checks in `post_verify`). The repo skills reference two tools that do not exist, `verify_references` and `verify_fingerprint`, 19 times in 9 files. In `0320ba38` the agent edited the live model through headless scripts 31 times, which caused 14 close/open pairs and 18 save-debugging calls.
- **Accuracy gap (confirmed).** `massprops_equal` is the identity check in 4 of 5 comparison sites (`transaction.py:361`, `preview.py:505`, `screenshot.py:194`, `documents.py:212`). A headless probe on a copy of `kiwibox-drawer.FCStd` found `principal_moments: [0, 0, 0]` on 74 of 144 hashed objects, all `Compound` shapes without `PrincipalProperties`; the solid inside has real moments. Principal moments are eigenvalues, so even real values cannot detect a rotation or mirror about the centre of mass; the inertia tensor about the centre of mass can.
- **GUI freeze (measured, headless, copy of `kiwibox-drawer.FCStd`, 184 objects).** Every FreeCAD call runs on the Qt main thread (AD-2), so the GUI is blocked for the whole tool call. One `fingerprint()` takes 4.5 s (mass properties 3.6 s); `saveCopy` 1.2 s; preview TempDoc open 1.1 s; FreeCAD's recompute after one `duct_pilot` change 14.6 s for 23 objects. Estimated per change: about 65 s with preview (7 fingerprints, 2 recomputes), of which FreeCAD's recompute is 29 s. Three print-split `Part::Common` objects take 7.5 s of each recompute.
- **Rollback proof defect (measured).** FreeCAD's `abortTransaction` + recompute restored the geometry exactly (mass properties equal on every object), but 33 objects had new B-rep bytes. The abort-path proof compares digests (`usecases/transaction.py:356`), so on this document every failed mutation falls through to the snapshot restore, which closes and reopens the document.

**User decisions (2026-10-06).**
1. Direction approved: quiet result envelope, one call per mutation, remove repeated server work, skill fixes, and check the moments gap first.
2. The operator turns on `FREECAD_BUDDY_AUTO_APPROVE=1` for attended GUI work. `preview_dry_run` stays available.
3. A new Epic 11 holds the work. Epic 10 scope does not change.
4. Epic 11 Stories 11.1-11.4 finish before Story 10.7 starts, so the UAT test cases and the scripted runner are updated once, on the new envelope.
5. Automatic rollback stays. It is made cheap and correct: the abort-path proof uses mass properties when the digest differs, fingerprints are cached per object, and the mass properties gain the inertia tensor. An agent-decides `on_failure: "keep"` option is not added.
6. Skills keep derived pieces (print splits) out of the edit loop.

## 2. Impact Analysis

**Epics.** One new epic (Epic 11) with 6 stories. No epic is removed or renumbered. Epic 10 changes only its sequencing: Story 10.7 starts after Stories 11.1-11.4. Epic 4 stays paused after Story 4.2 (unchanged). Epic 6 (skills library, backlog) is not opened: Story 11.5 edits shipped skill text only and keeps the AD-15 shape rules. Epic 11 opens no gate and reopens no epic (AD-19).

**Requirements (SPEC.md, phase-gates.md).**
- CAP-3 is unchanged: preview, confirm, auto-verify and provable rollback all stay available.
- Journey J1 (`SPEC.md:61`) describes the agent previewing every change. It needs one sentence for the operator auto-approve posture.
- Gate G2.3 ("Hash-identical in 100 % of cases") is unchanged: digests are still computed and compared on the server.
- The MVP is not affected.

**Architecture.** Rule changes in AD-6, AD-7 and AD-10, and in the Tool-results convention. AD-17 and AD-28 do not change text: the projection lives in `usecases/` (one envelope shape for every surface, AD-17), and the type changes take a major schema bump under the existing AD-28 rule (`fcb.mutation/2`, `fcb.geometry-diff/2`). Design documents: `data-contracts-design.md` §7 and §9, `mcp-tools-design.md` §1.4, `verification-design.md` §3.3, `integration-mcp-clients.md` §4.

**UX.** None (no UX document).

**Other artifacts.**
- UAT test cases that read full fingerprints or full findings: TC-05 and TC-08 (updated in Story 10.7, which now runs after Epic 11).
- Tests that assert the old envelope: `test_contracts.py`, `test_mutation_contract.py`, `test_framing_envelope.py`; generated schemas `mutation.schema.json` and `geometry-diff.schema.json`.
- Skill copies installed in user projects must be re-copied after Story 11.5 (operator step).
- The deferred-work ledger is not edited by this proposal. Deferred items are listed in §4.6.

**Technical impact.** `contracts/` (mutation, diff, fingerprint), `usecases/` (transaction, preview, confirm, tnp_guard, fingerprint, documents, features), `adapters/mcp_server.py`, `hosts/tool_catalog.py`, `skills/`. Validator sources change, so G2 scores that use `run_mutation`, `audit_references` and `fingerprint()` are re-run.

## 3. Recommended Approach

**Option 1: Direct adjustment (selected).** Add Epic 11, build it before Story 10.7, then continue Epic 10.
- Effort: medium (6 stories, one of them a contract change).
- Risk: medium. Story 11.2 changes a wire contract that tests and UAT read. Story 11.4 touches the mutation bracket. Each story keeps the full check set, and its acceptance criteria prove that.
- Timeline: Gate 1 (Story 10.8) waits for Stories 11.1-11.4.

**Option 2: Rollback.** Not viable. No recent change caused the cost; it is the shipped design of Epics 3 and 8.

**Option 3: MVP review.** Not viable. Nothing in the MVP scope must drop. The fix reduces cost without removing a check.

**Principle for every story:** the server checks everything, and the response reports what changed and what failed. No check is removed or weakened.

## 4. Detailed Change Proposals

### 4.1 Epics — `_bmad-output/planning-artifacts/epics.md`

**Edit A — Epic 10, "Sequencing" paragraph.**

OLD:
> **Sequencing:** corrects shipped behaviour in Epics 1-3, 8 and 9. **Opens no gate and reopens no epic** (AD-19). 10.2 -> 10.3 are ordered (both edit post-verify); 10.7 -> 10.7b (the runner encodes the corrected test cases); the other stories are parallel-eligible; 10.8 is last.

NEW:
> **Sequencing:** corrects shipped behaviour in Epics 1-3, 8 and 9. **Opens no gate and reopens no epic** (AD-19). 10.2 -> 10.3 are ordered (both edit post-verify); Epic 11 Stories 11.1-11.4 -> 10.7 (the test cases are written once, against the new envelope); 10.7 -> 10.7b (the runner encodes the corrected test cases); the other stories are parallel-eligible; 10.8 is last.

Rationale: user decision 4.

**Edit B — append the new epic after Epic 10.**

```markdown
## Epic 11: Lean Agent Loop

An agent builds a part with fewer calls and a small context: every mutation still runs every check, and its result reports what changed and what failed, not every value that passed. The operator can run attended GUI work with one call per mutation. The skills stop asking for checks the mutation result already gives. A change on a large document freezes the GUI only for FreeCAD's own recompute, not for bridge overhead.

**Why now:** three build sessions on 2026-10-06 (`eacac40d`, `ff604ce5`, `0320ba38`) used 98-310 FreeCAD calls, reached 797K-820K context tokens, and compacted 8 times in the longest one. 86 % of FreeCAD output was full fingerprints and PASS findings that no caller reads. The spine Tool-results convention already forbids raw dumps. On a copy of `kiwibox-drawer.FCStd` one change costs about 65 s with preview, of which FreeCAD's recompute is 29 s and the rest is bridge overhead (`sprint-change-proposal-2026-10-06.md` §1).

**Sequencing:** 11.1 -> 11.2 and 11.1 -> 11.4 (11.2 makes mass properties the visible change record, and 11.4 makes them the abort-path rollback proof, so they must be right first). 11.3 and 11.4 are parallel-eligible with 11.2; 11.4 edits `usecases/transaction.py`, so it merges after 11.2. 11.1-11.4 finish before Story 10.7. 11.5 is parallel-eligible. 11.6 is last. **Opens no gate and reopens no epic** (AD-19).

**Acceptance for the epic:** Story 11.6: a measured build session meets the targets in its acceptance criteria.

**Rules for every story:** no check is removed or weakened. Each story proves that the AD-5 bracket, the AD-6 rollback proof, the AD-7 audit and the AD-8 sketch signal still run and still fail a bad change. Re-run any validator score whose sources change.

### Story 11.1: Mass Properties That Tell Shapes Apart

> **As** the bridge, **I want** every fingerprint's mass properties computed from the shape's solids and sensitive to orientation, so that `massprops_equal`, the identity check in 4 of 5 comparison sites, sees a rotation or mirror about the centre of mass.

**Evidence (2026-10-06, headless probe on a copy of `kiwibox-drawer.FCStd`):** `principal_moments` is `[0, 0, 0]` on 74 of 144 hashed objects, all `Compound` shapes without `PrincipalProperties`; the solid inside has real moments, for example `(3.4e8, 1.9e8, 1.8e8)`. Principal moments are eigenvalues of the inertia tensor, so even real values do not change under a rotation or mirror about the centre of mass.

**Acceptance Criteria:**

1. **Given** a compound of solids, **When** `fingerprint()` runs, **Then** `principal_moments` come from its solids and are non-zero for any non-empty solid; a unit test under `tests/infc/` fails on zero moments for a non-empty compound.
2. **Given** any shape, **Then** `MassProps` carries `inertia`: the 6 components of the inertia tensor about the centre of mass in document axes (`Ixx, Iyy, Izz, Ixy, Ixz, Iyz`), computed from the solids, as an optional field added to `fcb.fingerprint/1` (additive, AD-28); `massprops_equal` compares it.
3. **Given** an asymmetric solid rotated 90° about its centre of mass, and the same solid mirrored through a plane through its centre of mass, **When** `massprops_equal(before, after)` runs, **Then** it returns `False` for both (regression tests). A solid with symmetric inertia is a documented limit.
4. **Given** a copy of `kiwibox-drawer.FCStd`, **When** one feature is changed inside a transaction, aborted and recomputed, **Then** `massprops_equal(before, after)` is `True` on every object; the quantization step for `inertia` is set so that this holds, and the story records the step and the measured jitter.

### Story 11.2: Quiet Result Envelope

> **As** an agent, **I want** a mutation or preview result that carries the digest, the changed objects and the non-PASS findings, so that one result costs about 2K chars instead of 30-110K.

**Acceptance Criteria:**

1. **Given** any successful mutation, **When** the result returns, **Then** `mutation.fingerprint_before` and `mutation.fingerprint_after` are digest strings with their serializer tag, and `mutation.changed` lists `{name, volume, area, com}` for each object whose mass-property invariants differ (empty on a no-op).
2. **Given** a mutation that fails or rolls back, **When** the result returns, **Then** `changed` also carries the full before and after `massprops` of each object that differs, and `rolled_back` / `rollback_proven` are as today.
3. **Given** any `tnp_audit` or `tnp_precheck` block, **Then** it is `{status, element_map_version, counts: {<verdict>: n}, findings: [non-PASS only]}`; a FLAGGED audit lists every non-PASS finding.
4. **Given** a preview, **Then** `diff.op` is `{tool}` and `text` does not repeat `preview_id`.
5. **Given** any result, **Then** `adapters/mcp_server.py` writes compact JSON (no `indent=2`).
6. **Given** the full `FingerprintRecord`, **Then** it stays on the server in an in-process cache keyed by digest; `document_undo(expect_fingerprint=<digest>)` uses it for the mass-property comparison, and the hint at `usecases/documents.py:166-168` is removed.
7. **Given** the projection, **Then** it is built in `usecases/` (AD-17), the contracts are `fcb.mutation/2` and `fcb.geometry-diff/2` with `/1` retained for audit replay (AD-28), and the generated schemas pass the drift check.
8. **Given** the 529 recorded results from the three sessions, **When** a replay script projects them through the new code path, **Then** total size drops by ≥ 85 % and no result is over 10K chars.
9. **Given** the G2 fault suite (rollback-boundary, TNP-provoking, dress-up silent drop), **When** it runs, **Then** every case fails or flags exactly as before.

### Story 11.3: One Call per Mutation

> **As** an operator, **I want** attended GUI work to apply a mutation in one call when I have set auto-approve, so that the agent does not spend a preview round trip on every change.

**Acceptance Criteria:**

1. **Given** `FREECAD_BUDDY_AUTO_APPROVE=1` set before FreeCAD starts, **When** an agent calls `feature_pad` without `confirm`, **Then** the pad applies under the full AD-5 bracket and the audit log records an `auto_approve` approval for it.
2. **Given** the same posture and a mutation that fails post-verify, **Then** it rolls back and returns its failure status exactly as with a token.
3. **Given** `feature_set_parameters` that writes only `Visibility`, **When** called without `confirm` and without auto-approve, **Then** it applies (display state, same carve-out as `view_fit_viewport`) and is audit-logged; any other property in the same call keeps the gate.
4. **Given** auto-approve unset, **Then** every other mutation still needs a valid `preview_id` (no regression).
5. The operator setup is documented in `README.md` and in the GUI harness standard.

### Story 11.4: Cheap, Correct Rollback Proof and Fingerprints

> **As** the bridge, **I want** each mutation to do whole-document work only as often as its guarantees need, and to prove a FreeCAD abort without a needless snapshot restore, so that a change on a large document freezes the GUI for FreeCAD's recompute and not for bridge overhead.

**Evidence (2026-10-06, headless, copy of `kiwibox-drawer.FCStd`, 184 objects):** one `fingerprint()` takes 4.5 s (mass properties 3.6 s, B-rep bytes 0.9 s); `saveCopy` 1.2 s; FreeCAD's recompute after one `duct_pilot` change 14.6 s for 23 objects. A live mutation runs 3 fingerprints and a preview 4. After `abortTransaction` + recompute, mass properties matched on every object, but 33 objects had new B-rep bytes. So the digest proof at `usecases/transaction.py:356` fails, and every failed mutation restores the snapshot, which closes and reopens the document.

**Acceptance Criteria:**

1. **Given** a successful live mutation, **When** it runs, **Then** `fingerprint()` runs 2 times, not 3: the gate record (`usecases/confirm.py:332`) is passed into `run_mutation` and used as `fp_before` (`usecases/transaction.py:604`). A test counts the calls.
2. **Given** the abort path, **Then** rollback is proven by digest equality, else by `massprops_equal` over the same object names (Story 11.1 invariants); only an invariant mismatch restores the snapshot. **Given** a mutation on the drawer copy that fails post-verify, **Then** it returns `rolled_back_verified` and the document is never closed or reopened.
3. **Given** the failure path, **Then** the fingerprint computed for the rollback proof is reused at `usecases/transaction.py:692`, not recomputed.
4. **Given** a fingerprint, **Then** an object whose shape is unchanged since its last fingerprint reuses its cached entry. The story chooses the unchanged-shape test, and a test proves that a changed shape never reuses its entry. The abort-path and snapshot-restore proofs compute every entry fresh.
5. **Given** `snapshot_references`, **Then** a property value is read only after its type passes the link-type filter (`usecases/tnp_guard.py:322-326`).
6. **Given** the drawer copy and one leaf change (`duct_pilot.Length`), **When** the live mutation is timed (median of 5, headless and in the GUI), **Then** bridge overhead (total time minus FreeCAD's recompute) is ≤ 3 s, from about 15 s today; the timings are recorded in the story file.
7. **Given** the G2 fault suite, **Then** the rollback-boundary (#6031-pattern) cases still escalate to the snapshot restore and pass, and all `test_mutation_protocol.py`, `test_tnp_guard.py` and fingerprint tests pass.

### Story 11.5: Build-Loop Skills

> **As** an agent, **I want** skills that use the checks the mutation result already reports, so that I verify per milestone and not per feature.

**Acceptance Criteria:**

1. `verification-thinking` adds a build-loop rule: per feature, read `post_verify`, `sketch_state` and `changed`, with no `verify_*` call and no screenshot; per milestone (a finished part or feature group), one `verify_shape` with every spec check and one screenshot packet; call `verify_*` again after any change made outside the typed tools. `SKILL.md:68-72` keeps "even when every deterministic check passed" and changes "every part whose geometry changed" to "every milestone".
2. `freecad-sketcher` states that `sketch_state.fully_constrained` and `dof` in the mutation result are the AD-8 signal, and that a separate `verify_sketch` is for a sketch changed outside the typed tools.
3. `freecad-scripting-idioms` forbids editing the live model through headless scripts while the bridge serves it.
4. `design-decomposition` states the CAD plan shape: a parameter table and milestones, one commit per milestone, no per-step checkboxes and no hand-predicted volumes.
5. All 19 references to `verify_references` and `verify_fingerprint` in 9 files point to `post_verify.tnp_audit` and `mutation.fingerprint_*` digests.
6. `verification-thinking/references/snapshot-packet-sizing.md` sets 800 px as the default screenshot size and keeps the AD-21 review floor where it applies.
7. `design-decomposition` states that derived pieces (print splits, `Part::Common` cuts of a master body) stay out of the edit loop: in a separate document, or rebuilt only at milestones. Evidence: on `kiwibox-drawer.FCStd`, 3 split `Part::Common` objects take 7.5 s of the 14.6 s recompute after one change to the master body.
8. `scripts/check_skill_shape.py` passes (4 sections, ≤ 1,500 words per `SKILL.md`).

### Story 11.6: Measured Build Session

> **As** the team, **I want** one real build measured against the 2026-10-06 baseline, so that the epic is closed on numbers.

**Acceptance Criteria:**

1. A transcript metrics script lands in `scripts/automation/` and reports, per session: FreeCAD calls, `preview_dry_run` calls, FreeCAD output chars, largest result, spilled results, peak context, compactions.
2. **Given** Stories 11.1-11.5 done, auto-approve set and the updated skills installed, **When** an agent builds a part of the same size class as the kiwibox drawer (about 100+ objects) in the FreeCAD GUI, **Then** the script reports: FreeCAD output ≤ 15 % of the `0320ba38` value per FreeCAD call, 0 spilled results, no result over 10K chars, and FreeCAD calls per feature ≤ 2 (median).
3. **Given** the same session, **Then** the median bridge overhead per mutation, measured by the Story 11.4 timing method, is ≤ 3 s.
4. The agent visually checks the finished part against a real FreeCAD screenshot, and a native Check Geometry passes (`freecad-native-validation` standard).
5. The report, with the baseline numbers beside the new numbers, is committed under `tests/uat/run/`.
```

### 4.2 Sprint status — `_bmad-output/implementation-artifacts/sprint-status.yaml`

Add after `epic-10-retrospective: optional`:

```yaml
  epic-11: backlog
  11-1-mass-properties-that-tell-shapes-apart: backlog
  11-2-quiet-result-envelope: backlog
  11-3-one-call-per-mutation: backlog
  11-4-cheap-correct-rollback-proof-and-fingerprints: backlog
  11-5-build-loop-skills: backlog
  11-6-measured-build-session: backlog
  epic-11-retrospective: optional
```

Add to the comment block, after the Epic 10 ordering note:

```yaml
# - Epic 11 (sprint-change-proposal-2026-10-06) cuts agent calls, result size and bridge time.
#   11-1 -> 11-2 and 11-1 -> 11-4; 11-3 is parallel-eligible; 11-4 merges after 11-2; 11-1..11-4 finish before
#   10-7 starts; 11-5 runs alongside; 11-6 is last.
```

### 4.3 Requirements — `_bmad-output/specs/spec-freecad-buddy/SPEC.md`

**J1, line 61.**

OLD:
> When the ask is a change, the agent calls `preview_dry_run`, shows the structured diff, and applies it on confirmation through a typed `sketch_*`/`feature_*` tool.

NEW:
> When the ask is a change, the agent calls `preview_dry_run`, shows the structured diff, and applies it on confirmation through a typed `sketch_*`/`feature_*` tool. When the operator has set auto-approve, the agent applies the typed tool directly; the same checks and rollback run, and the preview stays available.

Rationale: user decision 2. CAP-3 and G2 are unchanged.

### 4.4 Architecture — `ARCHITECTURE-SPINE.md`

**AD-6 — append to Rule.**

ADD:
> The full `FingerprintRecord` stays on the server. Tool results carry the `digest` and serializer tag, plus a `changed` list of the objects whose mass-property invariants differ; a failed or rolled-back mutation adds the before and after mass properties of those objects. A digest-keyed in-process cache holds the full records that `document_undo` and the mass-property comparisons need.

**AD-5 — Rule, rollback proof.**

OLD:
> **re-hash and compare to prove rollback**; on mismatch, restore from the pre-mutation `saveCopy` snapshot

NEW:
> **re-hash and compare to prove rollback**: digest equality, else equal mass-property invariants over the same object names, because a recompute after abort writes new B-rep bytes for geometry it restored; on an invariant mismatch, restore from the pre-mutation `saveCopy` snapshot

**AD-6 — Rule, mass-property tuple.**

OLD:
> (volume, area, bbox, COM, principal moments @1e-6)

NEW:
> (volume, area, bbox, COM, principal moments @1e-6, and the inertia tensor about the COM on a calibrated step), computed from each shape's solids,

**AD-6 — new obligation (after the Rule).**

ADD:
> mass properties come from the shape's solids, so a non-empty compound never records zero moments. The tuple includes the inertia tensor about the centre of mass in document axes: principal moments alone cannot detect a rotation or mirror about the centre of mass, because eigenvalues do not change under either.

**AD-7 — append to Rule.**

ADD:
> Tool results report the audit as `status`, `element_map_version`, `counts` per verdict and the non-PASS findings only. The counts prove the audit ran; an empty finding list with `CLEAN` is a clean audit, never a skipped one.

**AD-10 — replace the sentence on confirmation.**

OLD:
> Confirmation: MCP elicitation (`accept`/`decline`/`cancel`) with client-confirm fallback; headless is fail-closed unless an explicit `autoApprove` flag, and every auto-approval is audit-logged.

NEW:
> Confirmation: MCP elicitation (`accept`/`decline`/`cancel`) with client-confirm fallback; headless is fail-closed unless an explicit `autoApprove` flag, and every auto-approval is audit-logged. `autoApprove` is an operator posture valid in every client context, attended GUI work included: when set, a mutation applies in one call under the full AD-5 bracket, and `preview_dry_run` stays available. A write of only `Visibility` is display state and is confirm-exempt, as `view_fit_viewport` is.

**Conventions table — Tool results row.**

OLD:
> `structuredContent` validated by per-tool `outputSchema` + text mirror; images per AD-10 budget rules. Text payloads are summarized, never raw dumps — a tree query on a ≥50-feature document returns a summary, so no result can blow the client's context by size alone.

NEW:
> `structuredContent` validated by per-tool `outputSchema` + text mirror; images per AD-10 budget rules. Text payloads are summarized, never raw dumps — a tree query on a ≥50-feature document returns a summary, so no result can blow the client's context by size alone. **Silent on pass, loud on fail:** a check that passes reports its verdict and counts; a check that fails reports its detail. Mutation and diff blocks follow the same rule (AD-6, AD-7). No result echoes the request arguments. JSON on the wire is compact.

AD-17 and AD-28: no text change (see §2).

### 4.5 Design documents (under `architecture-freecad-buddy-2026-07-21/design/`)

**`data-contracts-design.md` §7 `GeometryDiff`.**

OLD:
```python
    schema: Literal["fcb.geometry-diff/1"]
    op: dict                        # echo of the proposed typed operation (tool + params)
```
```python
    tnp_precheck: dict              # required: {"status": "CLEAN"|"FLAGGED"|"UNSUPPORTED",
                                    #  "flagged": [{"object": str, "reference": Selector,
                                    #               "kind": "re_point"|"drop"|"marker"}]}
```

NEW:
```python
    schema: Literal["fcb.geometry-diff/2"]
    op: dict                        # {"tool": str} — the args are not echoed; the confirm
                                    #   token signs their digest
```
```python
    tnp_precheck: dict              # required: {"status": "CLEAN"|"FLAGGED"|"UNSUPPORTED",
                                    #  "element_map_version": str,
                                    #  "counts": {<verdict>: int},
                                    #  "findings": [non-PASS findings only, §3.3 shape]}
```

Add after the code block: "The shipped code returned every finding, PASS included (`usecases/preview.py:587`); `/2` restores the summarized shape."

**`data-contracts-design.md` §9 — `MassProps` gains `inertia: [6]` (from the solids, optional, additive); `principal_moments` come from the solids; the invariant list adds `inertia`; the abort-path rollback verdict becomes digest equality, else `massprops_equal`, with the 2026-10-06 measurement as its reason.**

**`verification-design.md` §1.2 and §2.2 — the abort-path pseudocode accepts `massprops_equal` when the digest differs; `_massprops` adds `inertia_tensor(shape)`.**

**`data-contracts-design.md` §9 — add subsection "Wire projection".**

ADD:
> The full `FingerprintRecord` never travels in a tool result. A `MutationBlock` (`fcb.mutation/2`) carries `fingerprint_before` / `fingerprint_after` as `{"digest": str, "serializer": str}`, and `changed: [{name, volume, area, com}]` for each object whose invariants (`volume`, `area`, `com`, `principal_moments`) differ. On a failed or rolled-back mutation each `changed` entry adds `before` and `after` `MassProps`. The server keeps full records in a digest-keyed in-process cache; `document_undo` resolves `expect_fingerprint` digests through it. `/1` stays for audit replay (AD-28).

**`mcp-tools-design.md` §1.4 — mutation block example.**

OLD:
```json
{ "mutation": {
  "transaction_id": "string",
  "fingerprint_before": { "hash": "sha256…", "serializer": "exportBinary|exportBrep", "mass_props": {} },
  "fingerprint_after":  { "hash": "…", "serializer": "…", "mass_props": {} },
  "post_verify": { "recompute_clean": true, "is_valid": true,
                   "fully_constrained": true,
                   "tnp_audit": { "status": "CLEAN|FLAGGED|UNSUPPORTED", "element_map_version": "string", "findings": [] } },
  "rolled_back": false, "rollback_proven": null
}}
```

NEW:
```json
{ "mutation": {
  "schema": "fcb.mutation/2",
  "transaction_id": "string",
  "fingerprint_before": { "digest": "sha256…", "serializer": "exportBinary|exportBrep" },
  "fingerprint_after":  { "digest": "…", "serializer": "…" },
  "changed": [ { "name": "Pocket003", "volume": 47120.4, "area": 46010.2, "com": [55.2, 67.1, 19.3] } ],
  "post_verify": { "recompute_clean": true, "is_valid": true,
                   "fully_constrained": true,
                   "tnp_audit": { "status": "CLEAN|FLAGGED|UNSUPPORTED", "element_map_version": "string",
                                  "counts": { "PASS": 42 }, "findings": [] } },
  "rolled_back": false, "rollback_proven": null
}}
```

**`mcp-tools-design.md` §1.4 — lifecycle paragraph, append.**

ADD:
> A `feature_set_parameters` call that writes only `Visibility` is display state: it runs the AD-5 bracket and is audit-logged, but is confirm-exempt. A call that also writes any other property keeps the gate.

**`verification-design.md` §3.3 Verdict shape — append.**

ADD:
> On the wire (tool results) the audit is summarized per the spine Tool-results convention: `{status, element_map_version, counts: {<verdict>: n}, findings: [non-PASS only]}`. The full per-reference list is computed and used for the aggregate verdict exactly as above; only the PASS entries are not serialized.

**`integration-mcp-clients.md` §4 — Invariants line, append.**

ADD:
> The operator may set `autoApprove` for any context, attended GUI work included; a mutation then applies in one call, every approval is audit-logged, and `preview_dry_run` stays available to the agent.

### 4.6 Deferred (not in Epic 11; decide on Story 11.4 and 11.6 numbers)

| Item | Why wait |
|---|---|
| Sketch primitives (rect, circle, polygon with automatic named constraints) | Sketch payloads of up to 20K chars pass through context 3 times. Re-measure after Story 11.2. |
| Composite profile → pad/pocket tool | The 3-call chain repeats 7/9/14 times. With auto-approve it is 3 calls, so the gain is smaller. |
| Clearance and interference tool | Would remove 49 headless probe scripts. New capability, needs its own design. |
| TNP Layer 1 limited to affected objects | `snapshot_references` takes 0.02 s on the drawer document, so the gain is small; an incomplete affected set would give a false clean. |
| Agent-decides `on_failure: "keep"` (no automatic rollback) | **Rejected** (decision 5). It saves time only on failure, and failures were about 7 of 310 calls in `0320ba38`, mostly `INVALID_INPUT`, which mutates nothing. It would leave a broken model in the GUI and change gate G2.2. |
| MCP elicitation for confirmation | The design names it (AD-10); the server does not implement it. Lower priority with auto-approve set. |
| Generic typed batch tool | **Rejected.** It hides each step's result, and failures are hard to locate. |

## 5. Implementation Handoff

**Scope: Moderate.** New epic, sequencing change in Epic 10, AD rule amendments. No replan of the MVP.

| Who | Does |
|---|---|
| Architect (this proposal, on approval) | Applies §4.1-§4.5 text edits to `epics.md`, `sprint-status.yaml`, `SPEC.md`, the spine and the 4 design documents. |
| Developer agent (`bmad-build`) | Builds Stories 11.1 → 11.2, then 11.3 and 11.4, then 11.5; then Epic 10 resumes at 10.7; 11.6 runs once 11.1-11.5 are done. |
| Operator (TanNT) | Sets `FREECAD_BUDDY_AUTO_APPROVE=1` for attended GUI work; re-copies the updated skills into user projects after Story 11.5. |

**Success criteria.** Story 11.6 acceptance criteria 2-3, measured against this baseline:

| Measure (`0320ba38`) | Baseline | Target |
|---|---|---|
| FreeCAD output chars per FreeCAD call | 9,590 | ≤ 1,440 |
| Results over the client size limit | 15 | 0 |
| Largest FreeCAD result | 109K | ≤ 10K |
| FreeCAD calls per feature (median) | 6 | ≤ 2 |
| Bridge overhead per mutation, drawer-size document | about 15 s (apply) / 50 s (preview + apply) | ≤ 3 s |
| Checks run per mutation (AD-5/6/7/8) | all | all |

**Not verified in this proposal.** Timings come from a headless probe on a file copy; the GUI adds a thumbnail render on save and view updates, so it is slower. "Fewer calls means less wall-clock time" assumes model time scales with turns. FreeCAD's own recompute (14.6 s for one change on the drawer) is not reduced by Epic 11 except through the skill guidance on derived pieces.
