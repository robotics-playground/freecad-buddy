# Verify Story 10-8-g: smoke-run test-case defects

Verifier: verifier-10-8-g. Head `56e746b3da56ca8516c8c9604652d2d173a3e043`, base `ffd131d`. Date 2026-11-18.
Live run folder: `tests/uat/run/2026-11-18-10-8-g-verify/` (uncommitted). Builder outputs not read before the live check.

**Verdict: PASS.** Two low findings (deferred-work text), no product defect, no test-case fix made.

## 1. Gates (detached worktree at `56e746b`, now removed)

| Gate | Command | Result |
|------|---------|--------|
| Runner tests | `.venv\Scripts\python.exe -m pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` | `186 passed in 9.76s` |
| Lint | `.venv\Scripts\python.exe -m ruff check .` | `All checks passed!` |
| Scenarios load | `scenario.load()` over `tests/uat/scenarios/*.json` | `loaded 72 of 72` |
| Slice boundary | `git diff --stat ffd131d 56e746b -- src tests/uat/runner tests/close-loop scripts tests/uat/run/2026-11-18-01` | empty: no change |
| Trailing spaces | added `Given/When/Then/And` lines without two trailing spaces | `0` |

Full diff stat: 34 files; only `tests/uat/testcases/` (5 files), 7 scenario `agent_check` strings, `deferred-work.md`, spec, build report, new run folder `2026-11-18-10-8-g-check/`.

## 2. AC map Q1-Q10

| Q | Evidence | Result |
|---|----------|--------|
| Q1 | `TC-02-document-ingestion-and-handles.md:628`, `:630`; `TC-09-error-contract-and-fault-injection.md:503-506`. Live: `query_tree_summary {doc:"fcb-doc:not-a-real-handle"}` returned the isError text `INVALID_INPUT: unknown or stale document handle: fcb-doc:not-a-real-handle`; `query_object {doc:"fcb-doc:does-not-exist"}` returned an envelope with `schema fcb.result-envelope/1`, `detail.code INVALID_INPUT`. Matches `mcp-tools-design.md:60`. | PASS |
| Q2 | `TC-02-...md:707`: prefix `Invalid project file <path>:` and equal non-empty tails stay hard; platform literal recorded only. Live: both tails `basic_ios::clear: iostream error`; missing file tail `File '...' does not exist!` differs. | PASS |
| Q3 | TC-03-03 `TC-03-sketch-authoring.md:131-132`; TC-03-20 `:875`, `:897-898`; TC-13-04 `TC-13-gui-mcp-parity.md:274-279`; TC-13-10 `:542-549`. Live TC-03-20 and TC-13-10 below. | PASS |
| Q4 | TC-07-03 `TC-07-verification-and-export-pairing.md:147-148`; the visual Then text after the lead-in is word for word the old one. Not run live by me (builder record only). | PASS (diff), live NOT RUN |
| Q5 | TC-07-05 Given `TC-07-...md:195`; Then `:213` unchanged. Live below. | PASS |
| Q6 | See section 3. | PASS |
| Q7 | No TC-02-13 hunk in the diff; `deferred-work.md:2126-2130` has no `resolution` line. | PASS |
| Q8 | 9 entries carry `resolution:`; SHA is a placeholder (L1); one stale file name (L2). | PASS with 2 low |
| Q9 | Section 1. | PASS |
| Q10 | Section 1, slice-boundary row. | PASS |

## 3. Q6 diff review: Then expectations

Changed Then expectations (all corrections to the design, none weaker in what they prove):

- TC-02-15 `:628`, `:630`: `query_tree_summary` moves from "envelope with `schema`/`detail.code`" to "exact text line `INVALID_INPUT: unknown or stale document handle: fcb-doc:not-a-real-handle`, isError, no `schema`/`detail`". The full message is still checked exactly. The other eleven tools keep the envelope check. Source: `mcp-tools-design.md:60`.
- TC-09-12 `:503-506`: same correction for `query_tree_summary`; the three envelope calls keep `status`, `detail.message`, `detail.code`.
- TC-02-17 `:707`: the MSVC literal `ios_base::failbit set: iostream stream error` is dropped. Kept as hard checks: `status`/`detail.code INVALID_INPUT`, the `Invalid project file <path>:` prefix, non-empty tails, tails equal after path replace. This is the only loss of strictness (no fixed tail literal); it is required because `documents.py:499` passes FreeCAD's platform text through. Accepted.
- TC-03-03 `:132`, TC-03-20 `:898`, TC-07-03 `:148`: only a lead-in clause added ("with the sketch still open in edit mode and the view Isometric" or "with the sketch open in edit mode"). The judged picture text is unchanged. TC-03-03 adds a camera read-back check (`[0.425, 0.176, 0.34, 0.82]` within 0.01): stricter.

Added steps are actions, not checks:

- TC-03-03 `:131`, TC-03-20 `:897`, TC-07-03 `:147`: `And (visual)` lines in the Then block. Content: `setEdit`, Isometric press, Fit All, wait. TC-03-03 `:131` also holds the camera read-back (a check, and an extra one). Placement in the Then block: accepted per leader note; the MCP Thens before them need edit mode closed.
- TC-03-20 `:875` (Given), TC-07-05 `:195` (Given; it states `framing.fits true`, an extra check), TC-13-04 `:274` (When), TC-13-10 `:542` (When).
- Cleanup `resetEdit` added in TC-03-03, TC-03-20, TC-07-03.
- 7 scenario `agent_check` strings mirror the case text; `expect` blocks unchanged.

## 4. Live check in `fcb-desktop`

FreeCAD 1.1.4 in the container, image `fcb-desktop:local` built 2026-11-17T17:06Z, after the last `src/` commit `bc23a38`. MCP only at `http://127.0.0.1:18765/mcp`; GUI through `cua-driver-docker`. No host FreeCAD.

### Runner on the 7 changed scenario files

`docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/runner/run.py <7 files> --out /repo/tests/uat/run/2026-11-18-10-8-g-verify/runner` → exit 0, `7 scenarios: 0 PASS, 0 FAIL, 7 ESCALATE`, run errors 0. ESCALATE is the agent-check queue (GUI steps the runner cannot do), as designed. All 7 captures read: TC-03-03, TC-03-20 iso plate (no edit mode, as the runner does not open it); TC-07-03 black segment outside edit mode (expected, agent check opens edit mode); TC-13-04 iso 40x40x10 plate with hole; TC-09-12 iso box; TC-02-15, TC-02-17 unframed box corner (agent check frames by GUI Fit All).

### Cases run end to end as written

| Case | Result | Evidence and observations |
|------|--------|---------------------------|
| TC-03-20 | PASS | Given built by MCP (plate 12000.0, `BossProfile` dof 0, edge `BossProfile -> PlatePad`, external geometry audit CLEAN). Before: edit mode, Isometric token `s00000037:436`, Fit All `:400`, 8 s, camera `[0.425, 0.176, 0.34, 0.82]`; `evidence/tc-03-20-before.png`: iso plate with thickness, green circle R5, magenta external edge on the front plate edge. `feature_set_parameters Length 30` → `SPEC_FAILED`, `rolled_back true`, finding `REPOINTED` owner `BossProfile` prop `AttachmentSupport`, explanation `TNP audit flagged 1 reference(s): BossProfile.AttachmentSupport REPOINTED`, `element_map_version 15.70200.5`. `sketch_set_datum` → OK, CLEAN, `findings []`. Volume 12000.0; `verify_recompute` OK; `view_fit_viewport` OK. After: `evidence/tc-03-20-after.png`, same camera, plate as thin as before, circle R4, external edge on the real plate edge, no error marker. |
| TC-07-05 | PASS | Show All by `Show All Objects` leaf token; `view_fit_viewport` OK (`fits true`, ratio 0.95). AP242 `text` = `STEP export written -> /repo/tests/uat/run/2026-11-18-10-8-g-verify/evidence/tc-07-05-ap242.step.` exactly, `framing.fits true`. Both `verified false`, distinct `fcb-export:` ids, bytes 6886/6854 equal `stat`. Schema grep 1/0/1. `verify_export_step` OK for both with `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF` and `AUTOMOTIVE_DESIGN`. `ap:"AP203"` → input validation error, no file. Re-import volume 6000.0. `evidence/tc-07-05-after.png`: one closed box 1:2:3, whole. |
| TC-13-10 | PASS | Tree before: `TC13Pad`, `Body`. Isometric token `s00000040:418`, Fit All `:381`, 8 s; `evidence/tc-13-10-before.png`: iso sketch outline only. `preview_dry_run` then `feature_pad` with `confirm.preview_id` → OK, `rolled_back false`. Fit All label `Fit All` in post-pad snapshot. `evidence/tc-13-10-after.png`: iso solid with visible thickness where the before showed only the outline. `query_tree_summary` names `Pad`; bbox z 0..5. Body expanded by a foreground pixel click on its arrow (as the case says); tree then has `Origin`, `Pad` (`evidence/tc-13-10-tree-expanded.png`). Note: `feature_body_create` ran without `confirm` (auto-approve on, confirm optional). |
| TC-02-17 | PASS | Baseline open, Show All, Fit All token, `evidence/tc-02-17-before.png`. Five opens: missing → `...: File '<path>' does not exist!`; not-fcstd and corrupt → `document_open failed for '<path>': Invalid project file <path>: basic_ios::clear: iostream error`, tails equal and non-empty; empty → `document_open requires a 'path'`; directory → `document_open failed for '.../evidence': ...`. All `INVALID_INPUT`. `document_list`: baseline only. `query_capabilities` OK; `addon.log` `Traceback` count 0. `evidence/tc-02-17-after.png` equals the before picture. |
| TC-03-03, TC-07-03, TC-13-04, TC-02-15, TC-09-12 | Runner only | Scripted checks 0 FAIL; GUI agent checks NOT RUN by me (the 4 required cases cover Q3 and Q5). Q1 checked by the two live calls in section 2. |

## 5. Falsification

1. TC-03-20 after-capture without the new Isometric step: reopened edit mode, waited 8 s, camera `[0.0, 0.0, 0.0, 1.0]`. `evidence/falsify-tc-03-20-after-no-iso.png`: top view of the plate face, circle R4, no thickness visible. "As thin as in the before image" cannot be judged, the same failure as smoke run 2026-11-18-01 (`lead-grades.md:52`). After the Isometric press the Then passed. The Then is still strict, and the added step is what makes it pass.
2. TC-07-05 export after Show All without the fit: `text` = `STEP export written -> ...falsify-tc-07-05-unfitted.step.\n\nWarning: the model does not fully fit the live viewport, ...`, `framing.fits false`. The exact `text` Then fails as in the smoke run (`bugs.md:55`). After the fit in the Given it equals the line.

## 6. deferred-work.md

- 9 entries have `resolution: resolved by Story 10-8-g`; TC-02-13 (`deferred-work.md:2126-2130`) stays open.
- **L1 (low):** each resolution says `commit recorded by the leader after the commit`; SHA `56e746b` not yet written.
- **L2 (low):** `deferred-work.md:2089` (TC-03-03) cites `evidence/tc-03-03-iso-edit.png`; the check run holds `evidence/tc-03-03-after.png` (renamed per triage BH9). Stale file name.

## 7. Teardown

Container FreeCAD stopped (`fcb-freecad stop` killed pid 28220 after the window close timed out; all documents were closed first). `/healthz` empty, no FreeCAD process. Worktree `D:\Work\Personal\Sources\fcb-verify-10-8-g` removed. Bad-input and STEP files deleted per the Cleanup blocks. No file edited outside the run folder and this report.

## Re-run at df5572f

Head `df5572f471a5b32b7bcd9b82c95b408581ef7dcb` (fix round G1 on `56e746b`). Detached worktree, now removed. Live run folder `tests/uat/run/2026-11-18-10-8-g-verify-g1/` (uncommitted).

**Verdict: PASS.** RT-1 to RT-7 closed. No new finding.

### Gates

| Gate | Result |
|------|--------|
| `pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` (main venv) | `186 passed` |
| `ruff check .` | `All checks passed!` |
| `scenario.load` on `tests/uat/scenarios/*.json` | `loaded 72` |
| `git diff --stat 56e746b df5572f -- src tests/uat/runner tests/close-loop scripts tests/uat/run/2026-11-18-01` | empty |

### RT-1, RT-2: independent reproduction

Script in the session scratchpad (`v_rt12.py`). It imports the worktree `src/freecad_buddy/adapters/mcp_server.py` and `tests/uat/runner/run.py` (paths printed). Each case builds `_invalid_input_envelope(message)`, wraps it with `_to_call_result` (`structured=False` for `query_tree_summary`, default for `document_open`), converts it with `mcp_client.to_result`, then runs `run.check_expect` on every `expect` of that step.

| Scenario, step | Output | Checks | Finding |
|----------------|--------|--------|---------|
| tc-09-12 `unknown_tree` | `INVALID_INPUT: unknown or stale document handle: fcb-doc:does-not-exist` (correct) | 2 | none |
| tc-09-12 `unknown_tree` | `INVALID_INPUT: internal error while resolving fcb-doc:does-not-exist` | 2 | yes (`equals`) |
| tc-09-12 `unknown_tree` | `INVALID_INPUT: stale handle fcb-doc:does-not-exist (unknown or stale document handle)` | 2 | yes |
| tc-02-17 `not_fcstd` | `... Invalid project file /repo/tests/uat/README.md: basic_ios::clear: iostream error\n` (correct) | 2 | none |
| tc-02-17 `not_fcstd` | `... Invalid project file <path>: ` (empty tail) | 2 | yes (regex `\S`) |
| tc-02-17 `not_fcstd` | `... Invalid project file <path>:  ` (space-only tail) | 2 | yes |
| tc-02-17 `not_fcstd` | `document_open failed for '<path>': something else` | 2 | yes |

`tc-09-12.json:124` now `equals` the exact line. `tc-02-17.json:78` regex now ends `Invalid project file \S+README\.md: \S`. Both `agent_check` strings now carry the exact line (TC-09-12) and `status`/`detail.code`, non-empty and equal tails, and the difference from the missing-file text (TC-02-17).

Live runner in `fcb-desktop` (FreeCAD stopped first): `run.py tc-02-17.json tc-09-12.json --out .../2026-11-18-10-8-g-verify-g1/runner` → exit 0, `2 scenarios: 0 PASS, 0 FAIL, 2 ESCALATE`, run errors 0, 0 findings. Observed: `unknown_tree` text `INVALID_INPUT: unknown or stale document handle: fcb-doc:does-not-exist`; `not_fcstd` message `... Invalid project file /repo/tests/uat/README.md: basic_ios::clear: iostream error\n`. Both captures read: TC-09-12 iso box; TC-02-17 unframed box corner (its GUI Fit All stays an agent check, unchanged).

### RT-6

`TC-03-sketch-authoring.md:31` now names one exception: a read-only `script_exec` (camera read-back) may run with edit mode open. In TC-03-03 the only MCP call between `setEdit` (`:131`) and the Cleanup `resetEdit` (`:136`) is the `:131` read `[round(x, 3) for x in G.ActiveDocument.ActiveView.getCameraOrientation().Q]`, which reads only. `:132` is a `cua-driver` capture, not MCP. TC-03-20 closes edit mode before the next MCP call (`:875`), and after `:897` only a capture runs before Cleanup. The first live run (section 4) ran this same read with edit mode open: `OK`, and edit mode stayed open. Closed.

### RT-3, RT-4, RT-5, RT-7

- RT-3: `tc-03-03.json:457` `agent_check` now has the camera read-back (each component within 0.01 of `[0.425, 0.176, 0.34, 0.82]`). Closed.
- RT-4 (my L2): `deferred-work.md:2089` no longer cites `tc-03-03-iso-edit.png` (0 matches); it cites `tc-03-03-after.png`. Closed.
- RT-5 (my L1): 9 resolution lines name commit `56e746b`; 0 lines say `commit recorded by the leader`. The TC-02-13 entry still has no `resolution`. Closed.
- RT-7: `TC-07-verification-and-export-pairing.md:195` now cites `envelope.py:124`, which is `return f"{text}\n\n{sentence}" if sentence else text`. Closed.

### Teardown

The runner tore down its FreeCAD. `fcb-freecad status` shows no pid, and `/healthz` cannot be reached. Worktree removed.
