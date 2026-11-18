# Findings — run 2026-11-18-01

Each finding: id, scenarios, cause class (`uat-run-practices.md` §7), request, raw output, `file:line`.

## Run hygiene

### R-1 — A phase replay script drove a FreeCAD on the Windows host; developer `user.cfg` changed

- Phase: R0b-1 (agent `aca2b0b4e8ffc3338`), scenario TC-05-03, first replay. Cause class: agent execution fault.
- Request: the agent's scratch replay script used its MCP client default URL `http://127.0.0.1:8765/mcp` (the host bridge port) instead of the container relay `http://127.0.0.1:18765/mcp`.
- Raw: the calls were answered once and created a document `tc-05-03` in the FreeCAD that served host `:8765`; later calls were refused (phase report F1). Host `addon.log` (`%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log`): host FreeCAD GUI bridge started 20:15:26 (line 2793), stopped 20:55:18 (line 2801); a second host FreeCAD started 21:04:23 and stopped 21:04:27 (lines 2803-2810, proxy pinned to pid 24476). No run agent reports a host launch; the lead started none.
- Effect: developer `user.cfg` SHA-256 changed from `b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a0` (decision 8) to `63fa48cfe55eb515b30113b21e4732da70a1aa0b877c51dab3b8a4e979b9bd2a`, file time 2026-11-18 21:04:27 (the exit of the 21:04 host FreeCAD). No copy of the old file exists. New run baseline recorded in `evidence/user-cfg-sha256.txt` (`uat-run-practices.md` §5).
- Graded run: the second TC-05-03 replay, on `:18765`. Rule added to `lead-notes/RULES.md` watch items.


## FAILs of this run

Line numbers refer to `tests/uat/testcases/TC-xx-*.md` at commit `2db195c`. Each FAIL has one new entry in `_bmad-output/implementation-artifacts/deferred-work.md` (spec D2). No product defect.

### B-11 — `query_tree_summary` refusal is text only; two Thens read an envelope

- Scenarios: TC-02-15 (Critical, R0a-1), TC-09-12 (Critical, R0b-3). Cause class: test-case defect.
- Request: `query_tree_summary {doc: "fcb-doc:not-a-real-handle"}` (TC-02-15); `query_tree_summary {doc: "fcb-doc:does-not-exist"}` (TC-09-12), over `http://127.0.0.1:18765/mcp`.
- Raw: `isError: true`, `structuredContent: null`, text `INVALID_INPUT: unknown or stale document handle: fcb-doc:not-a-real-handle`. Every other tool in both scenarios returned the envelope with `detail.code` `INVALID_INPUT`.
- Then: `TC-02-document-ingestion-and-handles.md:630` "each response carries `schema` `fcb.result-envelope/1` and `detail.code`"; `TC-09-error-contract-and-fault-injection.md:505-506`. Design: `query_tree_summary` sends one text block by design (`mcp-tools-design.md` §1.3).
- Fix direction: the Thens exempt `query_tree_summary` and check its text line instead.

### B-12 — Expected MSVC iostream text on Linux

- Scenario: TC-02-17 (Critical, R0a-1). Cause class: test-case defect.
- Request: `document_open {path: "/repo/tests/uat/run/2026-11-18-01/evidence/tc-02-17-not-fcstd.txt"}` and the corrupt `.FCStd`.
- Raw: `INVALID_INPUT` `document_open failed for '<path>': Invalid project file <path>: basic_ios::clear: iostream error`; both tails equal apart from the path.
- Then: `TC-02-document-ingestion-and-handles.md:707` expects `ios_base::failbit set: iostream stream error` (MSVC wording). The bridge passes FreeCAD's text through (`usecases/documents.py:496-499`).
- Fix direction: accept the platform libstdc++ or MSVC text, or check only that both tails are equal apart from the path.

### B-13 — Thickness or elevation judged in a top-down Sketcher edit view

- Scenarios: TC-03-03 (High), TC-03-20 (Critical), runner set, R0a-2; lead regrade PASS to FAIL. Cause class: test-case defect.
- Request: the scenario steps up to the visual Then; the window is in Sketcher edit mode, which looks along the sketch normal (top view).
- Raw: `r0a2-TC-03-03-after.png` and `r0a2-TC-03-20-after.png` show the plate face from the top; no thickness or elevation is visible. The phase pass rested on an added Isometric press (`r0a2-TC-03-03-iso.png`, `r0a2-TC-03-20-iso.png`).
- Then: `TC-03-sketch-authoring.md:131` ("visibly raised above the plate's bottom by the plate's own thickness"), `:895` ("as thin as in the before image").
- Fix direction: add a camera step (Isometric toolbar button) before the capture, or judge elevation from a second capture outside edit mode.

### B-14 — Visual Then needs Sketcher edit mode; the scenario has none

- Scenario: TC-07-03 (Critical, runner set, R0b-1); lead regrade PASS to FAIL. Cause class: test-case defect.
- Raw: `runner/captures/TC-07-03.png` shows one black diagonal line in the iso view: no origin marker, no constraint glyphs, no fully-constrained colour.
- Then: `TC-07-verification-and-export-pairing.md:147`.
- Fix direction: add the Sketcher edit-mode step (Preconditions, **Sketch edit mode**) before the capture.

### B-15 — Export text "equals" the export line; the framing warning is appended

- Scenario: TC-07-05 (Critical, smoke set b, S1). Cause class: test-case defect.
- Request: `export_step {doc, path: "/repo/tests/uat/run/2026-11-18-01/evidence/tc-07-05-ap242.step", objects: ["Box"], ap: "AP242"}`; the Given does not fit the view first.
- Raw: `text` = `STEP export written -> /repo/tests/uat/run/2026-11-18-01/evidence/tc-07-05-ap242.step.\n\nWarning: the model does not fully fit the live viewport, so the human is seeing only part of it. Call view_fit_viewport to fit it, if they need to see this change.`
- Then: `TC-07-verification-and-export-pairing.md:210` "the envelope `text` equals ...". The warning is the product's framing advisory (`src/freecad_buddy/contracts/envelope.py:111`), which `TC-14-viewport-framing-and-auto-fit.md:399` requires while the model does not fit.
- Fix direction: "starts with", or fit the view in the Given.

### B-16 — Window camera and render camera cannot match

- Scenario: TC-13-04 (Critical, runner set, R0b-3). Cause class: test-case defect.
- Request: Show All, GUI Fit All toolbar button, `query_screenshot {camera: "iso"}`.
- Raw: window in Top view (`getCameraOrientation().Q` `(0.0, 0.0, 0.0, 1.0)`), 40 x 40 square, no thickness visible (`r0b3-tc-13-04-viewport2.png`); render iso (`r0b3-tc-13-04-mcp.png`).
- Then: `TC-13-gui-mcp-parity.md:287` (proportion and camera match).
- Fix direction: set the window camera to Isometric before the capture.

### B-17 — Pad thickness judged in a top view

- Scenario: TC-13-10 (Critical, smoke set b, S2). Cause class: test-case defect.
- Request: `feature_pad {doc, body: "Body", profile: "Sketch", name: "Pad", length: {value: 5, unit: "mm"}}`, then the GUI Fit All toolbar button.
- Raw: `tc-13-10-viewport.png`: a filled grey 30 x 20 rectangle in the TOP view (the pad reached the viewport); `query_mass_properties` Pad bbox z 0..5.
- Then: `TC-13-gui-mcp-parity.md:574` "the viewport solid reads as that thickness". The scenario sets no camera; the GUI Fit All route that the test case allows for GUI-side ground truth keeps the top view.
- Fix direction: add an Isometric press before the capture.

### B-18 — No emoji font in the container

- Scenario: TC-02-13 (Medium, runner set, R0a-1). Cause class: harness limit.
- Raw: U+1F527 draws as an empty box in the tree and the tab (`r0a1-TC-02-13-unicode.png`); `docker exec -u cua fcb-desktop sh -c 'fc-list ":charset=1f527"'` prints nothing. The label is intact in `document_list`.
- Then: `TC-02-document-ingestion-and-handles.md:518` (emoji drawn as real glyphs).
- Fix direction: install an emoji font (for example Noto Color Emoji) in the `fcb-desktop` image.
