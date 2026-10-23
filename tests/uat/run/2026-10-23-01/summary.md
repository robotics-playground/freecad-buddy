# Scripted UAT run

45 scenarios: 21 PASS, 1 FAIL, 23 ESCALATE.

| Scenario | Title | Launch | Verdict | Capture |
|----------|-------|--------|---------|---------|
| TC-02-01 | Create, list, save, close round trip | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-01.png |
| TC-02-02 | Open a golden model and read its tree | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-02.png |
| TC-02-03 | Save-as writes a new path and rebinds the handle | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-03.png |
| TC-02-04 | Two open documents stay isolated | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-04.png |
| TC-02-06 | query_object returns properties and error state for a Pad | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-06.png |
| TC-02-12 | query_dependencies max_edges truncation and rejection | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-12.png |
| TC-02-13 | Unicode, spaces, and a long label round-trip | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-13.png |
| TC-02-15 | Unknown or stale handle is refused by every document-taking tool | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-15.png |
| TC-02-16 | Double document_close is refused, not crashed | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-16.png |
| TC-02-17 | Bad open paths are refused, and a missing file is distinguishable | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-17.png |
| TC-03-05 | All four geometry kinds | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-05.png |
| TC-03-06 | All 16 constraint types | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-06.png |
| TC-03-07 | sketch_set_datum drives a downstream Pad | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-07.png |
| TC-03-13 | sketch_add_external_geometry projects a model edge | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-13.png |
| TC-03-20 | A moved external-geometry source is flagged and rolled back | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-20.png |
| TC-04-02 | feature_pad Length with analytic volume | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-04-02.png |
| TC-04-03 | feature_pad midplane straddles the sketch plane | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-04-03.png |
| TC-04-09 | feature_fillet on named edges | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-04-09.png |
| TC-05-03 | post_verify runs its four checks in order | FREECAD_BUDDY_AUTO_APPROVE=0 | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-05-03.png |
| TC-05-08 | Undo unavailable is recorded, not misread as the #6031 defect | FREECAD_BUDDY_AUTO_APPROVE=0 | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-05-08.png |
| TC-05-14 | A cross-tag fingerprint comparison raises, never returns "not equal" | FREECAD_BUDDY_AUTO_APPROVE=0 | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-05-14.png |
| TC-05-15 | TNP reports CLEAN on a healthy mutation | FREECAD_BUDDY_AUTO_APPROVE=0 | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-05-15.png |
| TC-06-03 | include and exclude select the right objects | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-06-03.png |
| TC-06-04 | styles transparency and color are honored | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-06-04.png |
| TC-06-05 | focus and highlight frame and accent the target | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-06-05.png |
| TC-06-07 | camera custom requires exactly four numbers | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-06-07.png |
| TC-07-01 | verify_shape covers the whole closed assertion vocabulary | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-07-01.png |
| TC-07-02 | verify_shape with no checks is measurement-only | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-07-02.png |
| TC-07-03 | verify_sketch PASS is equivalent to FullyConstrained, both directions | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-07-03.png |
| TC-08-03 | A preview_id authorizes exactly that apply | FREECAD_BUDDY_AUTO_APPROVE=0 | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-08-03.png |
| TC-08-08 | A token is bound to the tool that minted it | FREECAD_BUDDY_AUTO_APPROVE=0 | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-08-08.png |
| TC-08-13 | A refused call does not spend its token | FREECAD_BUDDY_AUTO_APPROVE=0 | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-08-13.png |
| TC-08-14 | Tampered, malformed and foreign tokens produce distinct messages | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-08-14.png |
| TC-09-03 | A missing schema-required field is a protocol rejection, not an envelope | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-09-03.png |
| TC-09-12 | An unknown doc handle returns INVALID_INPUT | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-09-12.png |
| TC-09-17 | A broken recompute returns RECOMPUTE_ERROR, not a false OK | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-09-17.png |
| TC-09-18 | A broken reference surfaces the failing object and its status string | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-09-18.png |
| TC-11-01 | script_exec is registered by default (GUI proxy part) | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-11-01.png |
| TC-11-17 | A script_exec call while it is off is refused and never runs (GUI proxy part) | FREECAD_BUDDY_SCRIPT_EXEC=0 | FAIL | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-11-17.png |
| TC-12-07 | A GUI-side recompute agrees with the bridge | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-12-07.png |
| TC-13-04 | Geometry parity — mass properties agree with the drawn shape | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-13-04.png |
| TC-13-06 | Render parity — the MCP render matches the live viewport | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-13-06.png |
| TC-14-02 | A fit on a framed document returns OK and reports the camera it recorded | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-14-02.png |
| TC-14-07 | An unknown, stale, or missing handle is INVALID_INPUT before any viewport work | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-14-07.png |
| TC-14-16 | The fit does not alter geometry | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-14-16.png |

## Escalation queue

### TC-02-12: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button before and after the refused calls, which the runner cannot press; click Fit All, capture the window and judge that the model is the same picture with no dialog and no document added or closed.

### TC-02-13: ESCALATE

- agent check: The test case reads the Unicode label off a window capture taken before the save, which the runner does not take: create a document with the same label, capture the window and judge that both CJK runs and the wrench emoji are drawn as real glyphs in the model tree, the spaces kept and a long label shown in full or elided by the widget; then judge the final capture: the tree entry reads tc-02-13-uat-unicode and no dialog is open. The reopened document is empty, so there is no model to frame.

### TC-02-15: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button, which the runner cannot press; click Fit All, capture the window and judge its visual Then.

### TC-02-16: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button, which the runner cannot press; click Fit All, capture the window and judge its visual Then.

### TC-02-17: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button, which the runner cannot press; click Fit All, capture the window and judge its visual Then.

### TC-03-05: ESCALATE

- agent check: The visual Then needs Sketcher edit mode, which the runner does not open: open MixedProfile in edit mode (script_exec setEdit, test case Preconditions), capture the window and judge it: a horizontal line running right from the sketch origin, a small closed circle, an open quarter arc to the right and one isolated dot upper left, all four green; no ellipse or fifth shape, nothing clipped, no error dialog.

### TC-03-06: ESCALATE

- agent check: The visual Then needs Sketcher edit mode, which the runner does not open: open ConstraintBed in edit mode (script_exec setEdit, test case Preconditions), capture the window and judge it: five lines, three circles and two points, all green, with constraint glyphs; a horizontal line from the origin, a vertical one, a parallel one, a short perpendicular one, one at 45 degrees; two equal circles that touch; two points mirrored about the V axis; labels including 60, 2.5, 5 and 45; count the glyph and label marks; nothing clipped, no orange or red geometry, no error dialog.

### TC-03-07: ESCALATE

- agent check: The runner takes no before capture and does not open Sketcher edit mode: judge the capture as a shaded slab about two-thirds as wide as it is long (25 x 40, not the narrow 10 x 40 tab), no hole, gap or broken face; then open TabProfile in edit mode (test case Preconditions) and judge one closed green rectangle under the solid with the TabWidth label reading 25; no error dialog.

### TC-03-13: ESCALATE

- agent check: External geometry is drawn only in Sketcher edit mode, which the runner does not open, and the runner takes no before capture: open BossProfile in edit mode (test case Preconditions), capture the window and judge one projected curve in the external-geometry colour lying along a 60 mm boundary edge of the shaded plate, on the plate and not offset; the solid unchanged; no error dialog.

### TC-03-20: ESCALATE

- agent check: The runner takes no before capture, and the projected external curve is drawn only in Sketcher edit mode: judge the capture as one whole thin plate (5 mm, not 30 mm), no torn, missing or black face, with the BossProfile circle on its top face; then open BossProfile in edit mode (test case Preconditions) and judge the circle at radius 4 and the external curve along a real plate edge, not hanging in space; no error dialog or red error marker.

### TC-04-03: ESCALATE

- agent check: Visual Then of TC-04-03: the solid straddles the XY plane, half above and half below. The origin planes are hidden in the capture, so the plane is not drawn; the 2026-10-03-04 run judged this with FreeCAD View > Toggle axis cross. Toggle the axis cross, capture, and confirm the origin sits at mid-height of the 20 x 30 x 10 block.

### TC-04-09: ESCALATE

- agent check: The capture also shows OtherBody, the refusal fixture of the 'base outside the Body' Then, as a separate 20 x 20 x 5 block at x = 80..100, y = 10..30. Judge the visual Then on the 60 x 40 x 5 plate only: all four vertical corners carry a visible 2 mm round and none is sharp.

### TC-06-03: ESCALATE

- agent check: Read the renders the keep step copied to the run folder. tc-06-03-include-a.png must show one solid (PadA) and tc-06-03-exclude-a.png the rest (BoxB); neither may show a datum plane. tc-06-03-include-body.png must show the Tip solid of BodyA (the 20 x 20 x 10 PadA block), not a blank image. Then say what the window capture shows (count the solids; name any datum plane, origin marker or sketch line) and judge tc-06-03-default.png against it: the same two solids, no datum plane. The window wins on any disagreement.

### TC-06-04: ESCALATE

- agent check: Read the renders the keep step copied to the run folder. tc-06-04-red.png: BoxA (front, 10 mm cube) is red and BoxB (behind it, larger) keeps its own grey. tc-06-04-red-t80.png: BoxB is visible through the red BoxA, and it is not in tc-06-04-red.png. tc-06-04-t0.png and tc-06-04-t100.png must differ where BoxA is drawn, and in tc-06-04-t0.png BoxA keeps its own colour (not red). In the window capture BoxA must still carry its original colour, not red: the window and the red render must disagree on colour. The runner takes no before capture; judge the after capture alone. A red window is a finding.

### TC-06-05: ESCALATE

- agent check: Read the renders the keep step copied to the run folder. tc-06-05-focused.png must fill more of the frame with BoxA than tc-06-05-unfocused.png. tc-06-05-highlight.png must draw BoxA in the accent orange while BoxB keeps its own colour. Then say what the window capture shows (shape, framing, the colour of every face: no face is accent orange) and judge tc-06-05-unfocused.png against it. The window wins on any disagreement.

### TC-06-07: ESCALATE

- agent check: Read the renders the keep step copied to the run folder: tc-06-07-custom.png must be visually the same view as tc-06-07-iso.png. Then say what the window capture shows (how many faces are visible, which way is up, which corner faces the viewer) and judge tc-06-07-custom.png against it: a three-quarter view of the same box. The window wins on any disagreement.

### TC-07-03: ESCALATE

- agent check: The final state is a sketch, so the pixel check cannot judge it. If the scripted view_fit_viewport did not return OK, frame with the GUI Fit All toolbar button. Then judge the capture: one straight horizontal segment beginning at the origin marker, with constraint glyphs drawn on it, drawn in FreeCAD's fully-constrained colour rather than the under-constrained white.

### TC-08-14: ESCALATE

- agent check: The final state is a sketch, so the pixel check cannot judge it, and the runner takes no before capture. If the scripted view_fit_viewport did not return OK, frame with the GUI Fit All toolbar button. Then judge the capture: a flat 20 x 20 mm sketch, no extruded solid, and no error dialog left open by any variant.

### TC-09-17: ESCALATE

- agent check: Read the capture: the FreeCAD tree marks the failing object (Pad) with an error icon, and the 3D view still shows the last valid 20 x 20 x 10 block (FreeCAD keeps it on a failed recompute). If the fit step did not return OK (the test case expects the MCP fit may refuse a faulted document), the capture is unframed: click the GUI Fit All toolbar button, capture the window and judge that. A tree with no error marker on Pad is a finding.

### TC-09-18: ESCALATE

- agent check: Read the capture: the object named in subject.failing_objects (Pad) has an error icon in the tree and its Sketch is gone from the tree; the 3D view still shows the last valid 20 x 20 x 10 block (FreeCAD keeps it on a failed recompute). If the fit step did not return OK (the test case expects the MCP fit may refuse a faulted document), the capture is unframed: click the GUI Fit All toolbar button, capture the window and judge that. A tree with no error marker on Pad is a finding.

### TC-11-17: FAIL

- pixel view: expected "a 3D view", observed null

### TC-12-07: ESCALATE

- agent check: The runner takes no capture between steps: the clean-state Given (toolbar Recompute button disabled) and the dirty-state Then (tc-12-07-props.png: old 5 mm pad still drawn, touched marker on the Pad row where Body is expanded, Recompute button enabled) are not captured; the Edit > Recompute step succeeding is the only scripted sign the command was enabled. Re-run those two GUI reads by hand, then judge the capture: no touched or error marker on any tree row, Recompute button disabled again, a solid visibly taller than the 5 mm plate (20 x 10 x 8).

### TC-13-04: ESCALATE

- agent check: Visual Thens of TC-13-04. The runner frames with view_fit_viewport, not the GUI Fit All toolbar button. Read the window capture first and describe the solid: a flat square plate 40 x 40 x 10 mm (about four times wider than tall, not a cube) with one circular hole through it. Then read the MCP render (step 'render', structured_content.render.resource_link) and confirm the same silhouette, hole position and camera, with no extra or missing body. Where they disagree the window wins and the difference is a finding against the bridge.

### TC-13-06: ESCALATE

- agent check: Visual Thens of TC-13-06. The runner cannot press the Standard Views or Fit All toolbar buttons, so the window keeps FreeCAD's default camera and is framed by view_fit_viewport; record that camera and compare against the matching MCP camera (the test case's own fallback). Read the window capture first and describe it, then read the MCP render (step 'render', structured_content.render.resource_link): same plate outline and through hole in the same relative position, same visible face count and up direction, a flat 40 x 40 x 10 plate in both, nothing in the window missing from the render and no Body, Sketch or Origin child in the render. AD-34 tone band: no render face is black or white, each face is separable from the background (mean interior tone at least 24/255 from it on one channel, every channel within [20, 235]). The tone order is NOT compared with the window.

## Agent review

Sample seed 1461316941 (drawn). The agent reads these captures (tests/uat/test-plan.md §9); the scripted pixel check grades the rest.

- TC-02-01 (no pixel check): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-01.png
- TC-02-02 (first of TC-02): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-02.png
- TC-02-03 (sample): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-03.png
- TC-02-12 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-12.png
- TC-02-13 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-13.png
- TC-02-15 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-15.png
- TC-02-16 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-16.png
- TC-02-17 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-02-17.png
- TC-03-05 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-05.png
- TC-03-06 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-06.png
- TC-03-07 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-07.png
- TC-03-13 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-13.png
- TC-03-20 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-03-20.png
- TC-04-02 (first of TC-04): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-04-02.png
- TC-04-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-04-03.png
- TC-04-09 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-04-09.png
- TC-05-03 (no pixel check): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-05-03.png
- TC-05-08 (first of TC-05): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-05-08.png
- TC-05-15 (sample): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-05-15.png
- TC-06-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-06-03.png
- TC-06-04 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-06-04.png
- TC-06-05 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-06-05.png
- TC-06-07 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-06-07.png
- TC-07-01 (first of TC-07): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-07-01.png
- TC-07-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-07-03.png
- TC-08-03 (first of TC-08): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-08-03.png
- TC-08-14 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-08-14.png
- TC-09-03 (first of TC-09): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-09-03.png
- TC-09-12 (sample): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-09-12.png
- TC-09-17 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-09-17.png
- TC-09-18 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-09-18.png
- TC-11-01 (first of TC-11): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-11-01.png
- TC-11-17 (fail): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-11-17.png
- TC-12-07 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-12-07.png
- TC-13-04 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-13-04.png
- TC-13-06 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-13-06.png
- TC-14-02 (first of TC-14): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-23-01\captures\TC-14-02.png
