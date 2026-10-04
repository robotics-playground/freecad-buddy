# Sprint Change Proposal — UAT Gate 1 Green (2026-10-04)

Mode: batch. Author: Developer agent, for TanNT.

## 1. Issue Summary

**Trigger.** The first complete UAT run, `tests/uat/run/2026-10-03-04/report.md` (HEAD `bece7ac`, FreeCAD 1.1.4 GUI, evidence commit `972b6f1`), left Gate 1 red.

| Gate 1 (TC-01..TC-14) | Scenarios | PASS | PARTIAL | FAIL | BLOCKED | SKIP |
|---|---|---|---|---|---|---|
| Total | 251 | 190 | 24 | 34 | 2 | 1 |

Critical: 74.7 % pass (the gate needs 100 %). High: 79.1 % (needs ≥ 95 %).

**Category.** Defects found in shipped code (Epics 1–3, 8, 9), plus test-case drift. No earlier run covered all 14 test cases: run `2026-09-13-01` left 10 of them unrun.

**Evidence.**
- 29 of the 34 FAILs trace to product defects F-01..F-33 (report section "Suspected product defects", each with request, output and `file:line`).
- 5 FAILs are disputed (TC-02-17, TC-08-14, TC-10-06, TC-10-11, TC-13-06).
- Gate 2 (TC-99): 03, 04, 05 and 07 fail differently than documented.
- The G3 live-GUI replay passed in full (4/4 controls, 10/10 reverted builds, 10/10 planted defects detected).

**User decisions (2026-10-04).**
1. Add a new epic, "UAT Gate 1 Green", with stories grouped by area. Build each with `bmad-build`, then re-run the full UAT. Story 4.3 waits until this epic is done.
2. Disputed TC-02-17, TC-08-14, TC-10-06: keep the product behaviour and update the test cases.
3. TC-10-11: `design/integration-mcp-freecad.md` §2.4 makes the method registry the single source of per-method `timeout_s`, and AD-27 defines the quarantine after a `TIMEOUT`. A headless host that bounds only `debug_exec` deviates from the design, so this is a product defect.
4. F-29 / TC-06-01 / TC-13-06: AD-34 and `design/integration-mcp-freecad.md:328` set the render lighting by the tone band, not by matching the viewport. Update the test cases, and record the headlight intensity 0.80 (commit `eb72dbb`) in the design.
5. Add Story 10.7b, "Scripted UAT runner and FreeCAD probe", before the Gate 1 re-run. The run took about 10 h of active work for 251 scenarios: an LLM agent reasoned through every scenario, FreeCAD was relaunched 31 times, and the session limit stopped the run twice. Deterministic Thens move to a scripted runner with an independent in-FreeCAD measurement probe. `cua-driver` keeps every window capture and becomes the re-check and troubleshooting path.
6. Test plan §9 visual rule: the agent reads the capture for every FAIL, every probe/MCP disagreement, the first scenario of each test case, and a random 20 % sample of the rest. Every other scenario is graded by the scripted pixel check against its stored capture. A scripted pass never stands without its capture.

## 2. Impact Analysis

**Epics.** One new epic (Epic 10) with 9 stories. No epic is removed, reopened or renumbered. Like Epic 9, Epic 10 corrects shipped behaviour, so it opens no gate and every closed gate stays closed (AD-19). Epic 4 is paused after Story 4.2: Story 4.3 starts only when Epic 10 is done.

**Requirements (SPEC.md, phase-gates.md).** No change. The defects contradict requirements and ADs that already exist. The MVP is not affected.

**Architecture.** One documentation correction: the lighting rig in `design/integration-mcp-freecad.md` §6 still shows the light at default intensity. No AD changes. The fixes restore conformance with AD-5, AD-13, AD-17, AD-20, AD-25, AD-26, AD-27, AD-30, AD-31 and AD-34.

**UX.** None (no UX document).

**Other artifacts.**
- The UAT test cases (TC-01..TC-14, TC-99) need updating.
- The GUI harness standard needs updating (`.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md`).
- `scripts/automation/uat_watchdog.py` needs a fix.
- `tests/uat/test-plan.md` §9 changes its visual rule (decision 6), and the suite gains executable scenario files, a scripted runner and a test-only FreeCAD probe (Story 10.7b).

**Technical impact.** Changes in `usecases/` (documents, queries, sketches, features, transaction, verify, exports), `adapters/` (render_probe, rpc_listener, rpc_client, marshal, audit), and `hosts/gui_addon/bootstrap.py`. Several validator sources change, so their scores are re-run (G0 `verify_shape`, G2 `assertions`/`verify_sketch`/`audit_references`/`run_mutation`, G3 `spec_assertions`).

## 3. Recommended Approach

**Option 1 — Direct adjustment (selected).** Add Epic 10, build its stories, then re-run the UAT. Effort: high (8 stories). Risk: medium, because several fixes touch the mutation protocol and the rollback proof. Timeline: Epic 4 waits for Epic 10.

**Option 2 — Rollback.** Not viable. The defects are spread across Epics 1–3; nothing recent caused them.

**Option 3 — MVP review.** Not viable. Each defect breaks an AD the MVP depends on (verify-first, rollback proof, TNP guard).

## 4. Detailed Change Proposals

### 4.1 Epics — `_bmad-output/planning-artifacts/epics.md`

**C1. Append Epic 10 after Epic 9** (full text in Appendix A).

### 4.2 Sprint status — `_bmad-output/implementation-artifacts/sprint-status.yaml`

**C2. Add Epic 10 entries** after `epic-9-retrospective`:

```yaml
  epic-10: backlog
  10-1-documents-and-queries: backlog
  10-2-sketch-and-verify-correctness: backlog
  10-3-feature-tools-and-mutation-protocol: backlog
  10-4-render-and-framing: backlog
  10-5-step-export-schema: backlog
  10-6-session-transport-and-bounded-execution: backlog
  10-7-uat-suite-and-harness-maintenance: backlog
  10-7b-scripted-uat-runner-and-freecad-probe: backlog
  10-8-uat-gate-1-rerun: backlog
  epic-10-retrospective: optional
```

**C3. Add a header comment** after the Epic 9 comment block:

```yaml
# - Epic 10 corrects shipped behaviour found by the first complete UAT run (2026-10-03-04), so it
#   opens no gate and reopens no epic (AD-19). Epic 4 is paused after story 4-2: story 4-3 starts
#   only when epic-10 is done. Ordering: 10-1..10-6 are parallel-eligible except 10-2 -> 10-3
#   (both edit post-verify in usecases/transaction.py and usecases/verify.py); 10-7 runs alongside;
#   10-7 -> 10-7b (the runner encodes the corrected test cases); 10-8 (full UAT re-run, Gate 1
#   green, using the 10-7b runner) is last and closes the epic.
```

### 4.3 Architecture — `design/integration-mcp-freecad.md` §6, Lighting rig

**C4.** In the code block, after `light.direction.setValue(...)`, add `light.intensity.setValue(0.80)`.

**C5.** Replace the bullet "**Ambient is set by the band ceiling, not by viewport match.** …" with:

> - **Ambient and headlight intensity are set by the band ceiling, not by viewport match.** The ceiling comes from the brightest default material: FreeCAD's stock diffuse `(0.8, 0.8, 0.9)` (`App/Material.cpp`), which every fresh profile and CI renders with. An axis-aligned view takes most of its tone from the headlight and `iso` much less, so dimming the headlight to 0.80 pulls the brightest views down about twice as fast as `iso`. Measured on llvmpipe, FreeCAD 1.1.3: the brightest camera (`right`) reads 205.3 and `iso` reads `rgb(127,127,136)`. The MCP render is a constructed scene; its face shading is not required to match the live viewport.

Rationale: the design must state the shipped rig, as Story 9-3 required. This also records decision 4.

## 5. Implementation Handoff

**Scope: Moderate.** It reorganises the backlog (new epic; Epic 4 paused), and a Developer agent can implement every story with `bmad-build`.

**Recipients.**
- Developer agent (this session): apply C1–C5, then build stories 10.1–10.7b in order with `bmad-build`.
- UAT runner: Story 10.8.

**Success criteria.**
- Every story's reproducers (named by finding id and test case) pass against its regression test.
- CI stays green.
- Every touched validator score is current.
- Story 10.7b: the probe detects every planted bad state in its own fault set, and the scripted runner reproduces the 2026-10-03-04 verdicts for every deterministic Then it covers.
- Story 10.8: a full UAT run with Gate 1 green (Critical 100 %, High ≥ 95 %), Gate 2 matching its updated documented deviations, and the G3 live replay unchanged.

## Appendix A — Epic 10 text for `epics.md`

```markdown
## Epic 10: UAT Gate 1 Green

The bridge does what the design says when a real agent drives it through the real FreeCAD window: queries return what matches, mutations that should fail do fail, rollback is proven, and every report states what actually happened. The UAT suite and its harness describe the product as it is.

**Why now:** UAT run `2026-10-03-04` (HEAD `bece7ac`, FreeCAD 1.1.4) was the first to execute all of TC-01..TC-14. Gate 1 is red: 34 of 251 scenarios fail, 29 of them on product defects F-01..F-33 (`tests/uat/run/2026-10-03-04/report.md`, "Findings"). Most are the spine already being right and the code not matching it. The user requires Gate 1 green before Story 4.3.

**Sequencing:** corrects shipped behaviour in Epics 1-3, 8 and 9. **Opens no gate and reopens no epic** (AD-19). 10.2 -> 10.3 are ordered (both edit post-verify); 10.7 -> 10.7b (the runner encodes the corrected test cases); the other stories are parallel-eligible; 10.8 is last.

**Acceptance for the epic:** Story 10.8 — a full UAT run with Gate 1 green.

**Rules for every story:** treat each finding as a hypothesis: reproduce it first (the report gives the request and the output), then fix with a regression test. A finding that does not reproduce is closed with evidence, not fixed. Re-run any validator score whose sources change.

### Story 10.1: Documents and Queries

> **As** an agent, **I want** document and query tools to report exactly what is in the document, **so that** I never act on a silently filtered tree or a stale handle.

**Acceptance Criteria:**

1. **Given** a Pad inside a Body
   **When** `query_tree_summary` runs with `types`, `name_pattern` or `renderable_only` filters
   **Then** matching children of a non-matching container are returned (F-01, `usecases/queries.py:352-358`; TC-02-05, TC-12-11)
2. **Given** `document_save` to a new path
   **When** the file is reopened
   **Then** the document label is preserved (F-02, TC-02-13)
3. **Given** `document_save` to a missing folder, to a directory, or to a read-only file
   **When** it runs
   **Then** each case returns `INVALID_INPUT` naming the path, never a catch-all `RECOMPUTE_ERROR` and never a silent folder creation (F-03, TC-02-18)
4. **Given** `document_undo` with a malformed `expect_fingerprint`, or with the string form
   **When** it runs
   **Then** a malformed fingerprint is refused before the undo, and the string form never states a false "did NOT restore" (F-12, F-20; TC-05-14, TC-08-06)
5. **Given** a document closed in the GUI
   **When** a stale handle is used
   **Then** it returns `INVALID_INPUT`, not `RECOMPUTE_ERROR` (F-25, TC-12-13)
6. **Given** `sweep_temp_dir`
   **When** it runs
   **Then** it removes only `FCB_TMP_` entries under its own session workdir, never a non-prefixed sibling and never the live GUI's files (F-30; TC-02-15, TC-99-07)

### Story 10.2: Sketch and Verify Correctness

> **As** an agent, **I want** sketch tools and `verify_*` to accept what FreeCAD accepts and report what FreeCAD measures, **so that** a verdict can be trusted.

**Acceptance Criteria:**

1. **Given** `sketch_add_geometry {kind:"point", start:[x,y]}`
   **When** it runs
   **Then** the point is created (F-04, TC-03-05)
2. **Given** a single-point `DistanceX`/`DistanceY` constraint
   **When** it is added
   **Then** it is accepted as FreeCAD accepts it (F-05, TC-03-05/06)
3. **Given** the same constraint set added in any order
   **When** the sketch is verified
   **Then** the verdict is the same; redundancy warns and never fails by itself (F-06, `verification-design.md:213`)
4. **Given** an under-constrained sketch opened from a file
   **When** `verify_sketch` runs
   **Then** the reported DoF is the solver's value after solving (F-17, TC-07-03)
5. **Given** a sketch that FreeCAD marks in error
   **When** a mutation's post-verify runs
   **Then** `recompute_clean` is false (F-19)
6. **Given** `verify_shape` with a nested `fn` mapping or `object: ""`
   **When** it runs
   **Then** both return `INVALID_INPUT` with the closed-vocabulary message (F-22, F-23; TC-09-10, TC-09-13)

### Story 10.3: Feature Tools and the Mutation Protocol

> **As** an agent, **I want** a mutation either to commit verified or to roll back with proof, **so that** AD-5 holds on every path.

**Acceptance Criteria:**

1. **Given** `feature_pad` with `second_length`, or the `TwoLengths` type
   **When** it runs
   **Then** the pad builds both lengths, or the input is refused before the transaction (F-07, TC-04-04)
2. **Given** `feature_set_parameters` with a wrong-typed value
   **When** it runs
   **Then** it is refused before a transaction opens (F-08, TC-04-21)
3. **Given** a pad on an under-constrained sketch
   **When** it runs
   **Then** post-verify covers the sketch the feature consumes, and the mutation is refused (F-09, AD-8; TC-04-23, TC-05-03)
4. **Given** a failed mutation restored from its snapshot
   **When** the rollback is proven
   **Then** the proof compares a representation that survives reopening, and `rolled_back_via_snapshot` is reached (F-10, TC-05-06)
5. **Given** UndoMode 0 and a broken feature
   **When** the rollback is verified
   **Then** null shapes are part of the fingerprint, and a broken Tip is never reported `rolled_back_verified` (F-11, TC-05-08)
6. **Given** a TNP audit that did not run, or a reference that broke
   **When** the mutation reports
   **Then** the audit status is never `CLEAN` (F-13, TC-05-15..18)
7. **Given** auto-approve
   **When** the audit log is written
   **Then** approval and mutation lines share one `params_digest` and carry `fingerprint_before` (F-21; TC-08-18, TC-11-08)

### Story 10.4: Render and Framing

> **As** an agent, **I want** a render and a framing verdict that describe what the window shows, without changing the document.

**Acceptance Criteria:**

1. **Given** `query_screenshot` with `include` naming a Body
   **When** it renders
   **Then** the PNG shows the Body, or the envelope reports `empty_scene: true` (F-14, TC-06-03)
2. **Given** an `include` naming a hidden object
   **When** it renders
   **Then** the live document's visibility and modified state are unchanged (F-15, TC-13-03)
3. **Given** a style with `transparency` and no colour
   **When** it renders
   **Then** the transparency applies (F-16, TC-06-04)
4. **Given** a window whose visible area is smaller than the widget
   **When** framing is measured
   **Then** the verdict uses the visible area, and a clipped part is `fits: false` (F-27, TC-14-13)
5. **Given** a document whose only geometry is a datum plane, a sketch or a mesh
   **When** `view_fit_viewport` runs
   **Then** it fits that geometry or reports why it cannot, never `OK` with `ratio: 0.0` (F-28; TC-02-08, TC-04-12/13)

### Story 10.5: STEP Export Schema

> **As** an agent, **I want** `export_step {ap:"AP242"}` to write AP242.

**Acceptance Criteria:**

1. **Given** `export_step` with `ap: "AP242"`, and with the default
   **When** the file is written
   **Then** its `FILE_SCHEMA` names AP242, and the paired verify checks it (F-18; TC-07-05, TC-09-08)

### Story 10.6: Session, Transport and Bounded Execution

> **As** an operator, **I want** the bridge to bound every call, own its port and log what happens, as AD-26 and AD-27 state.

**Acceptance Criteria:**

1. **Given** any tool in the headless host
   **When** it runs past its registry `timeout_s`
   **Then** it returns `TIMEOUT` and the session is quarantined per AD-27 (TC-10-11, `design/integration-mcp-freecad.md` §2.4)
2. **Given** a `debug_exec` that timed out
   **When** the next call arrives
   **Then** it is refused or served without waiting on the abandoned body's registry lock (F-33)
3. **Given** a second RPC client
   **When** it connects while a session is active
   **Then** it gets the AD-26 busy error, never a hang (TC-99-07)
4. **Given** an unclean FreeCAD kill
   **When** FreeCAD relaunches
   **Then** the addon does not adopt an orphan or foreign server on `:8765`; it verifies `/healthz` session identity (F-26; TC-01-14, TC-10-12, TC-12-15, TC-99-08)
5. **Given** a malformed first frame, a clean exit, or an in-flight call dropped by a kill
   **When** the listener and proxy log
   **Then** each event is logged once at the right level, with no traceback on a clean exit (F-24, F-31)
6. **Given** the discovery file on Windows
   **When** it is written
   **Then** the code comment states the ACL protection actually applied (F-32)

### Story 10.7: UAT Suite and Harness Maintenance

> **As** a tester, **I want** the UAT test cases and harness to describe the shipped product and run without human rescue.

**Acceptance Criteria:**

1. **Given** the test-case defects in the report
   **When** the test cases are updated
   **Then** they read the build version and the tool count from the live bridge, use current field names, accept the MCP schema-layer refusal where the input is still refused, show golden models before fitting, use FreeCAD 1.1.4 edge numbering and menu labels, and build fixtures the bridge allows
2. **Given** disputed TC-02-17, TC-08-14, TC-10-06, and TC-06-01 / TC-13-06 (render shading)
   **When** the test cases are updated
   **Then** they assert the shipped behaviour, citing the decision in the sprint change proposal of 2026-10-04
3. **Given** TC-99-03/04/05 (AD-25 partly implemented)
   **When** the test cases are updated
   **Then** the implemented parts are promoted to Gate 1 and only the remaining gap stays expected-fail
4. **Given** the harness findings
   **When** the GUI harness standard is updated
   **Then** it forbids opening modal dialogs through `invoke_menu`, requires FreeCAD to run at the agent shell's integrity level, and documents the background-input routes that work on 1.1.4
5. **Given** `scripts/automation/uat_watchdog.py --since` with an offset-aware timestamp
   **When** it runs
   **Then** it does not crash
6. **Given** TC-06-10 and TC-13-17 (BLOCKED: no route to a Touched document)
   **When** the test cases are updated
   **Then** they build the Touched state through a route the bridge offers, or are retired with the reason

### Story 10.7b: Scripted UAT Runner and FreeCAD Probe

> **As** a tester, **I want** the deterministic Thens measured by scripts through a channel independent of the bridge, with `cua-driver` kept for captures, re-checks and troubleshooting, **so that** a full UAT run takes minutes of scripted work plus targeted agent review instead of about 10 hours, without losing accuracy.

**Why:** UAT run `2026-10-03-04` took about 10 h of active work for 251 scenarios. An LLM agent reasoned through every scenario, FreeCAD was relaunched 31 times (`evidence/launch-log.tsv`), the session limit stopped the run twice, UIA automation timed out and froze on modal dialogs, and desktop use forced background-only input.

**Acceptance Criteria:**

1. **Given** a running FreeCAD GUI
   **When** the test-only probe is queried
   **Then** it returns, read-only and from FreeCAD's own kernel and GUI state, each object's type, visibility, `Shape` validity, volume and bounding box, the document's modified flag, the active document, the camera and the visible view size; the probe shares no code with `src/freecad_buddy`, is not shipped in the addon, and loads only under the UAT launch profile
2. **Given** a saved document
   **When** it must be checked offline
   **Then** a FreeCADCmd reader measures it from the `.FCStd` file without loading the bridge
3. **Given** the probe's own fault set (planted wrong visibility, wrong volume, modified flag, wrong active document, clipped view)
   **When** the probe runs against each planted state
   **Then** it detects every one (the AD-13 sensitivity discipline applied to the oracle)
4. **Given** a test-case scenario
   **When** it is encoded as an executable scenario file (request, expected envelope fields, probe assertions, pixel checks)
   **Then** the runner executes it with no LLM call, and the test-case markdown stays the human-readable source
5. **Given** a window capture taken through `cua-driver` at a fixed window size and DPI
   **When** it is graded
   **Then** a scripted pixel check measures the non-background extent against the frame and colour samples at points projected from the probe's geometry, and compares against a golden capture where one exists
6. **Given** a scripted check that fails, or a probe measurement that disagrees with the MCP output
   **When** the runner reports it
   **Then** the scenario goes to the escalation ladder: re-check through `cua-driver` (property panel or tree read, Part > Check Geometry, agent-read capture), then troubleshoot by driving FreeCAD with `cua-driver`; a disagreement is a finding, never a retry, and a scripted pass never stands without its capture
7. **Given** scenarios that need different launch settings (auto-approve, exec, audit-log path)
   **When** the runner schedules them
   **Then** it groups them by launch configuration, launches FreeCAD non-elevated with a dedicated UAT profile (`-u`) so the developer's `user.cfg` is untouched, and never opens a modal dialog through `invoke_menu`
8. **Given** `tests/uat/test-plan.md` §9
   **When** it is updated
   **Then** the agent reads the capture for every FAIL, every probe/MCP disagreement, the first scenario of each test case, and a random 20 % sample of the rest; every other scenario is graded by the scripted pixel check against its stored capture
9. **Given** the 2026-10-03-04 run
   **When** the runner replays every deterministic Then it covers
   **Then** it reproduces the recorded verdicts, and any difference is explained

### Story 10.8: UAT Gate 1 Re-run

> **As** the team, **I want** a full UAT run that proves Gate 1 green before Epic 4 resumes.

**Acceptance Criteria:**

1. **Given** Stories 10.1-10.7b done and CI green
   **When** the full suite TC-01..TC-14, TC-99 and the G3 live replay run on FreeCAD 1.1.4 through the Story 10.7b runner, with agent review per the updated §9 and the desktop free (or the GUI lane in an isolated Windows session)
   **Then** Gate 1 is green (Critical 100 %, High ≥ 95 %), Gate 2 matches its documented deviations, and the G3 replay is unchanged; the report is committed under `tests/uat/run/`
```

## Checklist Record

| Item | Status | Note |
|---|---|---|
| 1.1 Trigger story | [x] | UAT run 2026-10-03-04 after Story 4.2b and the 1.1-only change |
| 1.2 Problem | [x] | Defects in shipped code and test-case drift |
| 1.3 Evidence | [x] | Report with findings F-01..F-33, captures in `evidence/` |
| 2.1 Current epic (4) | [x] | Paused after 4.2; 4.3 waits for Epic 10 |
| 2.2 Epic-level change | [x] | Add Epic 10 |
| 2.3 Future epics | [x] | No change; Epic 10 must close first |
| 2.4 Obsolete or new epics | [x] | One new epic |
| 2.5 Order | [x] | Epic 10 before Story 4.3 |
| 3.1 PRD/SPEC | [x] | No change |
| 3.2 Architecture | [x] | C4, C5 (lighting rig) |
| 3.3 UX | [N/A] | No UX document |
| 3.4 Other artifacts | [x] | Test cases, harness standard, `uat_watchdog.py` (Story 10.7); test-plan §9, scripted runner and probe (Story 10.7b) |
| 4.1 Direct adjustment | Viable | Selected |
| 4.2 Rollback | Not viable | — |
| 4.3 MVP review | Not viable | — |
| 5.x Proposal | [x] | This document |
| 6.4 sprint-status | [!] | C2, C3 on approval |

## Approval and Execution

- Approved by TanNT on 2026-10-04 (batch mode), with Story 10.7b and the test-plan section 9 sampling rule added at review.
- Applied the same day: C1 (Epic 10 appended to `epics.md`), C2 and C3 (`sprint-status.yaml`), C4 and C5 (`design/integration-mcp-freecad.md` lighting rig).
- Next: Story 10.1 with `bmad-build`.
