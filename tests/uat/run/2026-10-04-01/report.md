# UAT run 2026-10-04-01 — Story 10.1 targeted re-run

- **Code under test:** commit `70de526` (Story 10.1), addon junction to repo `src`.
- **FreeCAD:** 1.1.4 GUI, pid `13352`; bridge proxy spawned by the addon on `:8765`.
- **Proof the new code ran:** `document_create` to a missing folder returned `INVALID_INPUT` through `documents.py` `_check_save_target`, which exists only in `70de526`.
- **Scope:** the main scenarios that run `2026-10-03-04` failed for Story 10.1 findings, plus
  TC-02-01 as a save-as regression check. The user reduced the scope to main test cases;
  TC-12-11 (F-01 again) and TC-99-07 (F-30, needs a FreeCAD restart) were not run.
- **Environment, rules and expected behaviour:** [RUN-CONTEXT.md](RUN-CONTEXT.md).

## Results

| Scenario | Priority | Finding | Verdict | Notes |
| --- | --- | --- | --- | --- |
| TC-02-01 | Critical | F-02 | PASS | Title shows the file stem `tc-02-01-uat-roundtrip`, as AC2 requires; the Then that expects `uat-roundtrip` is a test-case defect. |
| TC-02-05 | Critical | F-01 | PASS | `types`, `name_pattern`, `renderable_only` return the Pad nested in the Body; `visible_only` drops the hidden Pad. |
| TC-02-13 | Medium | F-02 | PASS against AC2 | Reopened label `tc-02-13-uat-unicode` (file stem). Three Thens expect the Unicode label: test-case defects. CJK and emoji rendering in the tree not observed. |
| TC-02-15 | Critical | F-25, F-30 | PARTIAL | 12 tools with a fake handle return `INVALID_INPUT`. Inline host `doc: 12345` is refused by the MCP schema before the product guard (known schema-layer test-case defect, also in `2026-10-03-04`). The inline host's start sweep removed only a dead session's folder (F-30 rule holds). |
| TC-02-18 | Critical | F-03 | PASS | Read-only target, missing folder, directory: each `INVALID_INPUT` naming the path; no folder created, files and label unchanged. |
| TC-05-14 | High | F-12 | PASS | Untagged record and record without `objects` are `INVALID_INPUT`; `UndoCount` 4 before and after (GUI console). Two-build comparison NOT RUN (one FreeCAD build installed). |
| TC-12-13 | Critical | F-25 | PASS | First use of a handle to a GUI-closed document returns `INVALID_INPUT` "unknown or stale document handle", no `document_list` before it. Three test-case defects: `verify_state exists:false` cannot be satisfied; two `query_mass_properties` calls omit the required `object`. |
| TC-08-06 | Critical | F-20 | PASS | String form: `matches_pre_op:false`, text "the digest differs from the expected one on byte comparison; pass the whole FingerprintRecord…", no "did NOT restore". Record form: `true`, "restored the pre-op state". Test-case defects: string form expects `true`; `query_sketch_info` has no `fully_constrained`; `expect_fingerprint: 42` refused by the MCP schema. |

**Totals:** 8 scenarios, 7 PASS, 1 PARTIAL (test-case defect only), 0 product FAIL. Every Story
10.1 finding (F-01, F-02, F-03, F-12, F-20, F-25, F-30) shows its fixed behaviour in the GUI.

## Test-case defects for Story 10.7

- TC-02-01, TC-02-13: expect the create label after save-as; AC2 sets the file stem.
- TC-02-15: exact `INVALID_INPUT` text for a non-string `doc`; the MCP schema refuses first.
- TC-05-14: says FreeCAD 1.1.1; `query_capabilities` has no `auto_approve` field.
- TC-08-06: string form expects `matches_pre_op: true`; `query_sketch_info` has no `fully_constrained` field; `expect_fingerprint: 42` message is pre-empted by the MCP schema; `auto_approve` precondition not checkable.
- TC-12-13: `verify_state` with `exists:false` is unsupported; `query_mass_properties {doc}` lacks the required `object`; the test case does not say how to open the documents, and the golden models open with objects hidden.

## Observations

- After a successful save in TC-02-18 the window title still shows `*`. A later `view_fit_viewport` call probably marks the document modified. Not investigated.
- `%TEMP%\FCB_TMP_prev_rtoduji3` (2026-09-13, access denied) is a stray outside the workdir; AD-25 leaves OS-temp strays to the operator.
- The executor of TC-05-14 sent keys to the 3D view by mistake while targeting the Python console. The view changed, the document did not (`UndoCount` and objects unchanged); the before screenshot was retaken before the scenario ran.

## Evidence

`evidence/`: per-scenario results tables `tc-02-results.md`, `tc-05-14-results.md`,
`tc-12-13-results.md`, `tc-08-06-results.md`, with the MCP transcripts, scripts and screenshots
each table names.
