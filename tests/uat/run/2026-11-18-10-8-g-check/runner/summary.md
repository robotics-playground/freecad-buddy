# Scripted UAT run

7 scenarios: 0 PASS, 0 FAIL, 7 ESCALATE.

| Scenario | Title | Launch | Verdict | Capture |
|----------|-------|--------|---------|---------|
| TC-02-15 | Unknown or stale handle is refused by every document-taking tool | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-02-15.png |
| TC-02-17 | Bad open paths are refused, and a missing file is distinguishable | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-02-17.png |
| TC-03-03 | sketch_create on a planar face | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-03-03.png |
| TC-03-20 | A moved external-geometry source is flagged and rolled back | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-03-20.png |
| TC-07-03 | verify_sketch PASS is equivalent to FullyConstrained, both directions | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-07-03.png |
| TC-09-12 | An unknown doc handle returns INVALID_INPUT | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-09-12.png |
| TC-13-04 | Geometry parity — mass properties agree with the drawn shape | default | ESCALATE | /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-13-04.png |

## Escalation queue

### TC-02-15: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button, which the runner cannot press; click Fit All, capture the window and judge its visual Then. The script does not check these Thens; check each one in the gate run: the query_tree_summary refusal is one isError text line `INVALID_INPUT: unknown or stale document handle: fcb-doc:not-a-real-handle` with no schema, detail or structuredContent (mcp-tools-design.md:60), and the other eleven tools carry schema and detail.code (raw RPC or second client); addon.log has no access violation, segfault or swig line (log or audit read); Given: baseline framed with GUI Fit All and a before capture (GUI action).

### TC-02-17: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button, which the runner cannot press; click Fit All, capture the window and judge its visual Then. The script does not check these Thens; check each one in the gate run: Given: not-fcstd.txt and corrupt.FCStd prepared with printf (README.md stands in for the first) (file check); corrupt zip refused with 'document_open failed for ...corrupt.FCStd' (file check); non-FCStd file and corrupt zip messages start `Invalid project file <path>:` after the product prefix and their FreeCAD texts are equal once the path is replaced (platform text recorded, not required) (file check); addon log records no unhandled traceback (log or audit read); Given: baseline framed with GUI Fit All and a before capture (GUI action).

### TC-03-03: ESCALATE

- agent check: The visual Then needs Sketcher edit mode, which the runner does not open: open BossProfile in edit mode (script_exec setEdit, test case Preconditions), press the `Isometric` push button by its element token, press the Fit All toolbar button, wait 8 s (edit mode looks straight at the sketch plane, which cannot show the plate's thickness), capture the window and judge it: a shaded wide thin plate with the sketch axis cross on its top surface, raised above the plate's bottom by the plate thickness, not sunk inside or floating below; no second sketch, no error dialog.

### TC-03-20: ESCALATE

- agent check: The runner takes no before capture (the test case takes it in edit mode with the Isometric view, in the Given, and again presses Isometric after reopening edit mode, because closing edit mode restores the earlier camera), and the projected external curve is drawn only in Sketcher edit mode: judge the capture as one whole thin plate (5 mm, not 30 mm), no torn, missing or black face, with the BossProfile circle on its top face; then open BossProfile in edit mode (test case Preconditions), press the `Isometric` push button by its element token and the Fit All toolbar button, wait 8 s, and judge the circle at radius 4 and the external curve along a real plate edge, not hanging in space; no error dialog or red error marker. The script does not check these Thens; check each one in the gate run: Given: whole-document query_dependencies has edge BossProfile -> PlatePad (encoded as the object form) (comparison op); Given: intact state captured (tc-03-20-before.png) (GUI action); some finding is REPOINTED, owner BossProfile, prop AttachmentSupport (checked at findings.0 only) (comparison op).

### TC-07-03: ESCALATE

- agent check: The final state is a sketch, so the pixel check cannot judge it. If the scripted view_fit_viewport did not return OK, frame with the GUI Fit All toolbar button. Then open Sketch in Sketcher edit mode (script_exec setEdit, as in the test case), press the Fit All toolbar button, wait 8 s, and judge the capture: one straight horizontal segment beginning at the origin marker, with constraint glyphs drawn on it, drawn in FreeCAD's fully-constrained colour rather than the under-constrained white. The script does not check these Thens; check each one in the gate run: failed check ids include sketch.fully_constrained (checked at checks.0 only) (comparison op).

### TC-09-12: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: untouched window captured after the fit (tc-09-12-before.png) (GUI action); query_tree_summary unknown handle: the text line starts `INVALID_INPUT:` and names the handle, with no status or detail field (mcp-tools-design.md:60) (raw RPC or second client).

### TC-13-04: ESCALATE

- agent check: Visual Thens of TC-13-04. The runner frames with view_fit_viewport, which leaves an isometric camera; when you frame by the GUI instead, press the `Isometric` push button by its element token first, then the Fit All toolbar button, so the window camera equals the render's camera `iso`. Read the window capture first and describe the solid: a flat square plate 40 x 40 x 10 mm (about four times wider than tall, not a cube) with one circular hole through it. Then read the MCP render (step 'render', structured_content.render.resource_link) and confirm the same silhouette, hole position and camera, with no extra or missing body. Where they disagree the window wins and the difference is a finding against the bridge.

## Agent review

Sample seed 3186507788 (drawn). The agent reads these captures (tests/uat/test-plan.md §9); the scripted pixel check grades the rest.

- TC-02-15 (escalate): /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-02-15.png
- TC-02-17 (escalate): /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-02-17.png
- TC-03-03 (escalate): /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-03-03.png
- TC-03-20 (escalate): /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-03-20.png
- TC-07-03 (escalate): /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-07-03.png
- TC-09-12 (escalate): /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-09-12.png
- TC-13-04 (escalate): /repo/tests/uat/run/2026-11-18-10-8-g-check/runner/captures/TC-13-04.png
