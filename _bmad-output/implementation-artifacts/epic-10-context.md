# Epic 10 Context: UAT Gate 1 Green

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Make the bridge do what the design says when a real agent drives it through the real FreeCAD 1.1.4 window: queries return what matches, mutations that should fail do fail, rollback is proven, and every report states what actually happened. Bring the UAT suite and harness in line with the shipped product, and make a full UAT run cheap (scripted runner plus independent probe) so Gate 1 can be re-run. Trigger: UAT run `2026-10-03-04` (HEAD `bece7ac`) left Gate 1 red: 34 of 251 scenarios FAIL, 29 on product defects F-01..F-33 (Critical 74.7 %, needs 100 %; High 79.1 %, needs ≥ 95 %). Epic 4 is paused: Story 4.3 starts only when Epic 10 is done.

## Stories

- Story 10.1: Documents and Queries
- Story 10.2: Sketch and Verify Correctness
- Story 10.3: Feature Tools and the Mutation Protocol
- Story 10.4: Render and Framing
- Story 10.5: STEP Export Schema
- Story 10.6: Session, Transport and Bounded Execution
- Story 10.7: UAT Suite and Harness Maintenance
- Story 10.7b: Scripted UAT Runner and FreeCAD Probe
- Story 10.8: UAT Gate 1 Re-run

## Requirements & Constraints

**Rule for every story.** Each finding is a hypothesis. Reproduce it first (report `tests/uat/run/2026-10-03-04/report.md`, "Findings", gives request and output). Fix it with a regression test. A finding that does not reproduce is closed with evidence, not fixed. Re-run every validator score whose sources change (G0 `verify_shape`; G2 `assertions`, `verify_sketch`, `audit_references`, `run_mutation`; G3 `spec_assertions`). Never open `benchmarks/*/heldout`.

**Findings per story** (paths under `src/freecad_buddy/`; line numbers are from HEAD `bece7ac`, re-locate before editing):

| Story | Finding | Defect | Location |
|---|---|---|---|
| 10.1 | F-01 | Tree filters (`types`, `name_pattern`, `renderable_only`) drop matching children of a non-matching container | `usecases/queries.py:352-358` |
| 10.1 | F-02 | `document_save` to new path loses Unicode label (file stem used) | `usecases/documents.py:319` (`saveAs`) |
| 10.1 | F-03 | Save to missing folder creates it; dir path writes `<dir>.FCStd`; read-only target gives catch-all `RECOMPUTE_ERROR`. Must be `INVALID_INPUT` naming path | `adapters/rpc_dispatch.py:128` |
| 10.1 | F-12, F-20 | `document_undo`: malformed `expect_fingerprint` not refused before undo; string form says false "did NOT restore" | `usecases/documents.py:163-176` |
| 10.1 | F-25 | Stale handle after GUI close gives `RECOMPUTE_ERROR`, must be `INVALID_INPUT` | `usecases/documents.py:212-222`; purge only at `:493`, `:511` |
| 10.1 | F-30 | `sweep_temp_dir` removes non-`FCB_TMP_` entries; H1 start swept live GUI's shared workdir | `usecases/documents.py:59-95` |
| 10.2 | F-04 | `kind:"point"` reads `center`, not `start` | `usecases/sketches.py:203-204` |
| 10.2 | F-05 | Single-point `DistanceX`/`DistanceY` wrongly requires `second`/`second_pos` | `usecases/sketches.py:442-445` |
| 10.2 | F-06 | Verdict depends on constraint order; redundancy must only warn | `usecases/verify.py:333,352` |
| 10.2 | F-17 | DoF read after `recompute()` without `solve()` on file-opened sketch | `usecases/verify.py:331-333` |
| 10.2 | F-19 | `post_verify.recompute_clean:true` while sketch is in error | post-verify |
| 10.2 | F-22, F-23 | Nested `fn` dict gives `unhashable type`; `object:""` treated as omitted | `usecases/verify.py:252`, `:238` (guard `:102-103`) |
| 10.3 | F-07 | `second_length` ignored; `TwoLengths` refused | `usecases/features.py:483-484` |
| 10.3 | F-08 | Wrong-typed `feature_set_parameters` value refused only inside transaction | `usecases/features.py:1660` |
| 10.3 | F-09 | Post-verify checks only sketches in `touched`; pad reports `[feature, body]` | `usecases/transaction.py:246-266`, `features.py:491` |
| 10.3 | F-10 | `brep_sha256` changes after snapshot reopen, so `rolled_back_via_snapshot` never reached | rollback proof, `usecases/transaction.py` |
| 10.3 | F-11 | `fingerprint()` skips null shapes; broken Tip reported `rolled_back_verified` | `fingerprint` |
| 10.3 | F-13 | TNP audit reports `CLEAN` when it did not run or a reference broke | `usecases/transaction.py:195-201` |
| 10.3 | F-21 | Auto-approve audit: approval and mutation `params_digest` differ; `fingerprint_before` null | `features.py:1633` vs `adapters/mcp_server.py:213/221`; join promised at `audit_log.py:94-96` |
| 10.4 | F-14 | `include:["BodyA"]` renders blank PNG with `empty_scene:false` | `adapters/render_probe.py:221-231` |
| 10.4 | F-15 | `include` of hidden object changes live visibility and modified flag | `render_probe.py:187` vs `:226` |
| 10.4 | F-16 | `transparency` without colour has no effect | `_wrap_style` |
| 10.4 | F-27 | Framing measures widget, not visible area; clipped part reported `fits:true` | `framing.py` `_viewport_size` |
| 10.4 | F-28 | Fit on datum-plane-only doc returns `OK ratio:0.0`; sketch/mesh-only gives `SPEC_FAILED` | viewport fit |
| 10.5 | F-18 | `ap:"AP242"` and default write AP214 `FILE_SCHEMA`; pinned preference not read by `shape.exportStep` | `usecases/shim.py:412-426`, `usecases/exports.py:150` |
| 10.6 | TC-10-11 | H1 bounds only `debug_exec`; every tool must honour registry `timeout_s` and quarantine | `marshal.py:57-62`, `hosts/tool_catalog.py:1427-1468` |
| 10.6 | F-33 | After `debug_exec` TIMEOUT, next call waits on abandoned body's registry lock | `adapters/marshal.py:57-62` |
| 10.6 | TC-99-07 | Second RPC client must get AD-26 busy error, never hang | `adapters/rpc_listener.py` |
| 10.6 | F-26 | Relaunched addon adopts orphan or foreign server on `:8765`; must verify `/healthz` session identity | bootstrap spawn guard, `hosts/gui_addon/bootstrap.py` |
| 10.6 | F-24, F-31 | Dropped in-flight call not logged by proxy; malformed first frame not logged; clean exit logs `ERROR` traceback | `adapters/rpc_client.py:252-254`, `adapters/rpc_listener.py:269-271` |
| 10.6 | F-32 | Comment claims discovery file read-only on Windows; `chmod` is a no-op there | `adapters/rpc_listener.py:197-198` |

**Story 10.7 (test cases, harness).** Update TC-01..TC-14, TC-99 for these test-case defects: read build version (1.1.4, not `1.1.1`) and tool count (45, not 44) from the live bridge; current field names (`geo_ids` not `geometry`, `label` not `name` in `document_create`; drop stale `dof`, `auto_approve`, `transient`, `path` in `document_list`, `geometry_count`); accept the MCP schema-layer refusal (`Input validation error: …`) where input is still refused; Show All Objects on golden models before fitting; FreeCAD 1.1.4 edge numbering, Edit > Undo text and menu labels; FreeCAD keeps the last valid shape on failed recompute (TC-09-17/18); build fixtures the bridge allows (no unconstrained sketches, no JSON Infinity); fix fixture assumptions (900 mm pocket commits, open shell is one face, `two-box-compound` holds one object, golden Box is static `Part::Feature`). Disputed FAILs keep product behaviour and the TC asserts it, citing the 2026-10-04 sprint change proposal: TC-02-17 (non-FCStd and corrupt zip share one message), TC-08-14 (3 distinct token messages, signature checked first), TC-10-06 (one process-wide document registry), TC-06-01 / TC-13-06 / F-29 (render shading is set by tone band, not viewport match). TC-99-03/04/05: promote implemented AD-25 parts to Gate 1, keep only the remaining gap expected-fail. TC-06-10, TC-13-17 (BLOCKED, no route to a Touched document): build Touched state through a bridge route, or retire with reason. Harness standard `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md`: forbid modal dialogs via `invoke_menu`; FreeCAD must run at the agent shell's integrity level; document working background-input routes on 1.1.4 (`invoke_menu` refuses sub-menu items such as `["View","Fit All"]`, toolbar button by `element_token` works; `right_click`/`double_click` by token route through `global_input`; `Stop-Process` and `kill_app` are refused for FreeCAD). Fix `scripts/automation/uat_watchdog.py --since` crash on offset-aware timestamp (`TypeError: can't compare offset-naive and offset-aware datetimes`).

**Story 10.7b (runner, probe).** Test-only probe reads, read-only from FreeCAD kernel and GUI state: per-object type, visibility, `Shape` validity, volume, bounding box; document modified flag; active document; camera; visible view size. Probe shares no code with `src/freecad_buddy`, is not shipped in the addon, loads only under the UAT launch profile. A FreeCADCmd reader measures saved `.FCStd` offline without the bridge. Probe must detect every planted fault in its own fault set (wrong visibility, wrong volume, modified flag, wrong active document, clipped view). Scenarios become executable files (request, expected envelope fields, probe assertions, pixel checks) run with no LLM call; TC markdown stays the human source. Runner groups scenarios by launch configuration, launches FreeCAD non-elevated with a dedicated `-u` UAT profile, never opens a modal through `invoke_menu`. A failed scripted check or a probe/MCP disagreement is a finding, never a retry; it goes to the `cua-driver` escalation ladder. A scripted pass never stands without its capture. Update `tests/uat/test-plan.md` §9: agent reads the capture for every FAIL, every probe/MCP disagreement, the first scenario of each TC, and a random 20 % of the rest; the scripted pixel check grades the others. Runner must reproduce the 2026-10-03-04 verdicts for every deterministic Then it covers, with any difference explained.

**Story 10.8 (epic acceptance).** Full TC-01..TC-14, TC-99 and G3 live replay on FreeCAD 1.1.4 through the 10.7b runner, desktop free or GUI lane in an isolated Windows session. Gate 1 green (Critical 100 %, High ≥ 95 %); Gate 2 matches its updated documented deviations; G3 replay unchanged (4/4 controls, 10/10 reverted builds, 10/10 planted defects detected). Report committed under `tests/uat/run/`. CI stays green throughout.

## Technical Decisions

- **AD-5 (mutation protocol).** Snapshot, `openTransaction`, op, `recompute()`, post-verify (recompute clean, `Shape.isValid()`, `FullyConstrained` where sketches are involved, TNP audit), commit. On failure: abort, recompute, re-hash to prove rollback; on mismatch restore the `saveCopy` snapshot and re-verify. Rollback is measured, never assumed. Binds 10.3 (F-09, F-10, F-11, F-13) and 10.2 (F-19).
- **AD-6 (fingerprint).** One `fingerprint()` in usecases: SHA-256 over per-object shape bytes sorted by `Name`, plus quantized mass-property tuple as cross-oracle; hashes tagged by serializer id, never compared across tags. FCStd/document-XML hashing banned as identity oracle. Relevant to F-10 (proof must survive reopen) and F-11 (null shapes must count).
- **AD-7 (TNP audit).** No element map means `UNSUPPORTED`, never clean. Binds F-13.
- **AD-8 (sketch pass).** PASS iff `FullyConstrained == True` read after `doc.recompute()`. Redundant constraints warn, never fail. Binds F-06, F-09, F-17.
- **AD-13.** Pass/fail is decided by deterministic code or an independent grader, never by the producing agent. Applies to the 10.7b probe: it is an independent oracle and must pass its own sensitivity fault set.
- **AD-17.** Closed status set `OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`. Input faults are `INVALID_INPUT`, not catch-all `RECOMPUTE_ERROR` (F-03, F-25). Audit records are append-only and must be joinable (F-21).
- **AD-19.** Epic 10 corrects shipped behaviour: it opens no gate and reopens no epic.
- **AD-20.** Every call carries an explicit document handle; documents open and close only through `document_*` use cases. A handle to a document closed in the GUI is invalid input (F-25).
- **AD-25.** Every bridge file lives under a session-scoped workdir (`snap/`, `exports/`, `audit.log`, `tmp/`). Sweeps touch only the bridge's own prefixed entries in its own session (F-30).
- **AD-26.** One client session at a time; a second client is refused with `-32000` busy detail, never left hanging.
- **AD-27.** `TIMEOUT` quarantines the session: further calls refused with `TIMEOUT` until the in-flight op returns and its transaction is aborted with rollback proved. No automatic retry of mutations. The method registry is the single source of per-method `timeout_s` (`design/integration-mcp-freecad.md` §2.4), so the headless host must bound every tool, not only `debug_exec`.
- **AD-30.** Framing `fits` is false iff any of the 8 union-bbox corners projected through `getPointOnViewport` falls outside the viewport; F-27 requires the visible area, not the full widget.
- **AD-31.** `view_fit_viewport` is view-only: changes no geometry or fingerprint, `mutating=True`, no `confirm` property.
- **AD-34.** Render rig: exactly one off-axis `SoDirectionalLight` plus ambient; every camera renders a face tone separable from background. Ambient and headlight intensity (0.80, commit `eb72dbb`) are set by the tone-band ceiling, not by viewport match; the MCP render need not match live viewport shading. A render must be distinguishable from an empty scene (F-14).
- Ring rule (AD-1): imports point inward only, `contracts/` ← `usecases/` ← `adapters/` ← `hosts/`. Qt and `FreeCADGui` only in `hosts/` (and Qt in `render_probe`, `marshal`). The 10.7b probe lives outside `src/freecad_buddy`.

## Cross-Story Dependencies

- 10.1 to 10.6 are parallel-eligible, except 10.2 before 10.3: both edit post-verify in `usecases/transaction.py` and `usecases/verify.py`.
- 10.7 runs alongside the product stories. 10.7 before 10.7b: the runner encodes the corrected test cases.
- 10.8 is last and needs 10.1 to 10.7b done and CI green. It closes the epic.
- Epic 4: Story 4.3 is blocked until Epic 10 is done.
