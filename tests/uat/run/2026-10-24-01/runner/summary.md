# Scripted UAT run

72 scenarios: 5 PASS, 1 FAIL, 66 ESCALATE.

| Scenario | Title | Launch | Verdict | Capture |
|----------|-------|--------|---------|---------|
| TC-02-01 | Create, list, save, close round trip | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-01.png |
| TC-02-02 | Open a golden model and read its tree | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-02.png |
| TC-02-03 | Save-as writes a new path and rebinds the handle | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-03.png |
| TC-02-04 | Two open documents stay isolated | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-04.png |
| TC-02-06 | query_object returns properties and error state for a Pad | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-06.png |
| TC-02-12 | query_dependencies max_edges truncation and rejection | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-12.png |
| TC-02-13 | Unicode, spaces, and a long label round-trip | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-13.png |
| TC-02-15 | Unknown or stale handle is refused by every document-taking tool | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-15.png |
| TC-02-16 | Double document_close is refused, not crashed | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-16.png |
| TC-02-17 | Bad open paths are refused, and a missing file is distinguishable | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-17.png |
| TC-03-02 | sketch_create inside a Body | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-02.png |
| TC-03-03 | sketch_create on a planar face | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-03.png |
| TC-03-05 | All four geometry kinds | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-05.png |
| TC-03-06 | All 16 constraint types | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-06.png |
| TC-03-07 | sketch_set_datum drives a downstream Pad | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-07.png |
| TC-03-08 | sketch_toggle_construction on and back | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-08.png |
| TC-03-10 | sketch_remove_geometry cascades its constraints | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-10.png |
| TC-03-11 | sketch_remove_constraint by id and by name | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-11.png |
| TC-03-12 | A fully redundant constraint is a hard fail and rolls back | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-12.png |
| TC-03-13 | sketch_add_external_geometry projects a model edge | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-13.png |
| TC-03-14 | Axis references -1 and -2 resolve as operands | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-14.png |
| TC-03-16 | Conflicting constraints name the offending ids | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-16.png |
| TC-03-18 | Wrong unit on a datum is a schema reject | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-18.png |
| TC-03-20 | A moved external-geometry source is flagged and rolled back | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-20.png |
| TC-03-21 | Unknown key anywhere is a hard reject | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-21.png |
| TC-04-01 | feature_body_create empty and adopting a base | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-01.png |
| TC-04-02 | feature_pad Length with analytic volume | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-02.png |
| TC-04-03 | feature_pad midplane straddles the sketch plane | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-03.png |
| TC-04-08 | feature_hole thread_type before cut_type | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-08.png |
| TC-04-09 | feature_fillet on named edges | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-09.png |
| TC-04-11 | feature_pattern linear and polar | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-11.png |
| TC-04-12 | feature_mirror across datum, base plane and face | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-12.png |
| TC-04-14 | feature_set_parameters edits a Pad length | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-14.png |
| TC-04-18 | feature_pattern occurrences and conditional requirements | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-18.png |
| TC-04-20 | Omitted radius and size take FreeCAD's 1 mm default | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-20.png |
| TC-05-03 | post_verify runs its four checks in order | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-05-03.png |
| TC-05-08 | Undo unavailable is recorded, not misread as the #6031 defect | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-05-08.png |
| TC-05-14 | A cross-tag fingerprint comparison raises, never returns "not equal" | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-05-14.png |
| TC-05-15 | TNP reports CLEAN on a healthy mutation | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-05-15.png |
| TC-06-03 | include and exclude select the right objects | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-06-03.png |
| TC-06-04 | styles transparency and color are honored | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-06-04.png |
| TC-06-05 | focus and highlight frame and accent the target | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-06-05.png |
| TC-06-07 | camera custom requires exactly four numbers | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-06-07.png |
| TC-07-01 | verify_shape covers the whole closed assertion vocabulary | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-07-01.png |
| TC-07-02 | verify_shape with no checks is measurement-only | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-07-02.png |
| TC-07-03 | verify_sketch PASS is equivalent to FullyConstrained, both directions | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-07-03.png |
| TC-08-03 | A preview_id authorizes exactly that apply | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-03.png |
| TC-08-04 | A preview of a failing operation is still a successful preview | FREECAD_BUDDY_AUTO_APPROVE=0 | FAIL | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-04.png |
| TC-08-07 | A token is single-use | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-07.png |
| TC-08-08 | A token is bound to the tool that minted it | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-08.png |
| TC-08-09 | A token is bound to the arguments it was minted for | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-09.png |
| TC-08-10 | A token is bound to the document it was minted on | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-10.png |
| TC-08-11 | A token is bound to the document state it measured | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-11.png |
| TC-08-13 | A refused call does not spend its token | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-13.png |
| TC-08-14 | Tampered, malformed and foreign tokens produce distinct messages | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-14.png |
| TC-08-15 | An undeclared confirm field is refused, never silently dropped | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-15.png |
| TC-08-16 | An elicitation_action other than accept is refused | FREECAD_BUDDY_AUTO_APPROVE=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-16.png |
| TC-09-03 | A missing schema-required field is a protocol rejection, not an envelope | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-03.png |
| TC-09-06 | Empty arrays are rejected where `minItems` applies | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-06.png |
| TC-09-12 | An unknown doc handle returns INVALID_INPUT | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-12.png |
| TC-09-17 | A broken recompute returns RECOMPUTE_ERROR, not a false OK | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-17.png |
| TC-09-18 | A broken reference surfaces the failing object and its status string | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-18.png |
| TC-11-01 | script_exec is registered by default (GUI proxy part) | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-11-01.png |
| TC-11-17 | A script_exec call while it is off is refused and never runs (GUI proxy part) | FREECAD_BUDDY_SCRIPT_EXEC=0 | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-11-17.png |
| TC-12-07 | A GUI-side recompute agrees with the bridge | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-12-07.png |
| TC-13-04 | Geometry parity — mass properties agree with the drawn shape | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-13-04.png |
| TC-13-06 | Render parity — the MCP render matches the live viewport | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-13-06.png |
| TC-14-02 | A fit on a framed document returns OK and reports the camera it recorded | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-02.png |
| TC-14-06 | A handle naming a document the viewport is not showing is refused, naming both | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-06.png |
| TC-14-07 | An unknown, stale, or missing handle is INVALID_INPUT before any viewport work | default | PASS | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-07.png |
| TC-14-08 | An unknown key is hard-rejected | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-08.png |
| TC-14-16 | The fit does not alter geometry | default | ESCALATE | D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-16.png |

## Escalation queue

### TC-02-01: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: handle is not the FreeCAD Name (doc != name) (comparison op); save-as writes a non-empty file (ls -l) (file check); saved file still exists after the close (ls -l) (file check).

### TC-02-02: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: every property value is JSON-safe, no repr of a live FreeCAD pointer (comparison op).

### TC-02-03: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: the save-as target does not exist before the save (file check); new file written, non-empty (ls -l) (file check); golden file mtime and size unchanged (file check); reopen yields a handle different from the first (comparison op).

### TC-02-04: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: query on A returns Box while B is active after a sphere tree-item click (GUI action); handle A and handle B are different strings (comparison op).

### TC-02-06: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: healthy state captured before the break (tc-02-06-before.png) (GUI action).

### TC-02-12: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button before and after the refused calls, which the runner cannot press; click Fit All, capture the window and judge that the model is the same picture with no dialog and no document added or closed. The script does not check these Thens; check each one in the gate run: Given: whole-document query_dependencies total_edges >= 2 (not encoded) (comparison op); Given: model framed with GUI Fit All and a before capture (GUI action).

### TC-02-13: ESCALATE

- agent check: The test case reads the Unicode label off a window capture taken before the save, which the runner does not take: create a document with the same label, capture the window and judge that both CJK runs and the wrench emoji are drawn as real glyphs in the model tree, the spaces kept and a long label shown in full or elided by the widget; then judge the final capture: the tree entry reads tc-02-13-uat-unicode and no dialog is open. The reopened document is empty, so there is no model to frame. The script does not check these Thens; check each one in the gate run: Given: the save-as target does not exist (file check).

### TC-02-15: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button, which the runner cannot press; click Fit All, capture the window and judge its visual Then. The script does not check these Thens; check each one in the gate run: query_tree_summary refusal carries schema and detail.code (text only on the wire) (raw RPC or second client); addon.log has no access violation, segfault or swig line (log or audit read); Given: baseline framed with GUI Fit All and a before capture (GUI action).

### TC-02-16: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button, which the runner cannot press; click Fit All, capture the window and judge its visual Then. The script does not check these Thens; check each one in the gate run: no orphan MDI child in the window after the double close (GUI action); addon log records no traceback for the second close (log or audit read); sphere-r10.FCStd size unchanged (ls -l) (file check); reopen returns a handle different from the released one (comparison op).

### TC-02-17: ESCALATE

- agent check: The test case frames the model with the GUI Fit All toolbar button, which the runner cannot press; click Fit All, capture the window and judge its visual Then. The script does not check these Thens; check each one in the gate run: Given: not-fcstd.txt and corrupt.FCStd prepared with printf (README.md stands in for the first) (file check); corrupt zip refused with 'document_open failed for ...corrupt.FCStd' (file check); non-FCStd file and corrupt zip share one refusal tail (file check); addon log records no unhandled traceback (log or audit read); Given: baseline framed with GUI Fit All and a before capture (GUI action).

### TC-03-02: ESCALATE

- agent check: If the fit step did not return OK (a document whose sketches carry no edge has no shape-bearing object to frame), frame with the GUI Fit All toolbar button first. The visual Then needs Sketcher edit mode, which the runner does not open: open PlateProfile in edit mode (script_exec setEdit, test case Preconditions), capture the window and judge it: one sketch axis cross seen from the top (XY plane), no shaded solid anywhere, no second sketch, no error dialog; the model tree shows PlateProfile indented under PlateBody.

### TC-03-03: ESCALATE

- agent check: The visual Then needs Sketcher edit mode, which the runner does not open: open BossProfile in edit mode (script_exec setEdit, test case Preconditions), capture the window and judge it: a shaded wide thin plate with the sketch axis cross on its top surface, raised above the plate's bottom by the plate thickness, not sunk inside or floating below; no second sketch, no error dialog.

### TC-03-05: ESCALATE

- agent check: The visual Then needs Sketcher edit mode, which the runner does not open: open MixedProfile in edit mode (script_exec setEdit, test case Preconditions), capture the window and judge it: a horizontal line running right from the sketch origin, a small closed circle, an open quarter arc to the right and one isolated dot upper left, all four green; no ellipse or fifth shape, nothing clipped, no error dialog.

### TC-03-06: ESCALATE

- agent check: The visual Then needs Sketcher edit mode, which the runner does not open: open ConstraintBed in edit mode (script_exec setEdit, test case Preconditions), capture the window and judge it: five lines, three circles and two points, all green, with constraint glyphs; a horizontal line from the origin, a vertical one, a parallel one, a short perpendicular one, one at 45 degrees; two equal circles that touch; two points mirrored about the V axis; labels including 60, 2.5, 5 and 45; count the glyph and label marks; nothing clipped, no orange or red geometry, no error dialog.

### TC-03-07: ESCALATE

- agent check: The runner takes no before capture and does not open Sketcher edit mode: judge the capture as a shaded slab about two-thirds as wide as it is long (25 x 40, not the narrow 10 x 40 tab), no hole, gap or broken face; then open TabProfile in edit mode (test case Preconditions) and judge one closed green rectangle under the solid with the TabWidth label reading 25; no error dialog. The script does not check these Thens; check each one in the gate run: Given: starting state captured (tc-03-07-before.png) (GUI action).

### TC-03-08: ESCALATE

- agent check: The runner takes no before capture and no capture between the toggles: capture the rectangle with its diagonal before the first toggle and after the second (the test case's before/after pair), and judge five lines in both, the diagonal drawn with the same solid style and colour as the four rectangle edges in the after image, none deleted, no error dialog; if the intermediate construction state is captured too, say whether the diagonal looked different there.

### TC-03-10: ESCALATE

- agent check: The runner takes no before capture and does not open Sketcher edit mode: capture the intact rectangle before the removal and, after it, open PlateProfile in edit mode (test case Preconditions) and capture again; judge four edges joined at four corners, no open side where the fourth edge was removed, the fully-constrained green, the dimension labels still drawn, the after image matching the before image edge for edge, no error dialog.

### TC-03-11: ESCALATE

- agent check: The visual Then needs Sketcher edit mode and a before capture, which the runner does not take: open PlateProfile in edit mode (test case Preconditions) before the first removal and after the second, capture both and judge the rectangle still closed in the fully-constrained colour, not shifted, the two reference labels (SpareWidth among them, in the reference colour) drawn before and gone after, the driving labels 60 and 40 still drawn, no error dialog.

### TC-03-12: ESCALATE

- agent check: The visual Then needs Sketcher edit mode and a before capture, which the runner does not take: open PlateProfile in edit mode (test case Preconditions) before the redundant call and after it, capture both and judge the same closed rectangle at the same size and place, edges in the fully-constrained green and not the redundant orange, no extra horizontal glyph on the bottom edge, no 'Redundant constraints' notice, no modal error dialog.

### TC-03-13: ESCALATE

- agent check: External geometry is drawn only in Sketcher edit mode, which the runner does not open, and the runner takes no before capture: open BossProfile in edit mode (test case Preconditions), capture the window and judge one projected curve in the external-geometry colour lying along a 60 mm boundary edge of the shaded plate, on the plate and not offset; the solid unchanged; no error dialog. The script does not check these Thens; check each one in the gate run: Given: pre-projection state captured (tc-03-13-before.png) (GUI action); tnp_audit counts.PASS >= 1 (not encoded) (comparison op); whole-document query_dependencies has edge BossProfile -> PlatePad (encoded as the object form, out_list equals [PlatePad]) (comparison op).

### TC-03-14: ESCALATE

- agent check: The visual Then needs Sketcher edit mode, which the runner does not open: open AxisProfile in edit mode (test case Preconditions), capture the window and judge one closed green rectangle whose bottom edge lies on the horizontal axis and whose left edge lies on the vertical axis, point-on-object markers at the two pinned corners, not collapsed or inverted, no orange or red geometry, no error dialog.

### TC-03-16: ESCALATE

- agent check: The visual Then needs Sketcher edit mode and a before capture, which the runner does not take: open PlateProfile in edit mode (test case Preconditions) before the conflicting call and after it, capture both and judge one closed rectangle at the original width and depth (not shrunk toward 45), edges in the fully-constrained green and not conflict red, exactly one width label reading 60, no error dialog left open.

### TC-03-18: ESCALATE

- agent check: The runner takes no before capture and does not open Sketcher edit mode, which draws the dimension labels: capture the profile before the four refused calls and, after the RibAngle edit, open BracketProfile in edit mode (test case Preconditions) and capture again; judge no new circle in the profile, the HoleSpacing label still 40 over an unchanged distance, the RibAngle label 30 with the rib swung closer to the base line as the only difference, nothing collapsed or exploded, no error dialog.

### TC-03-20: ESCALATE

- agent check: The runner takes no before capture, and the projected external curve is drawn only in Sketcher edit mode: judge the capture as one whole thin plate (5 mm, not 30 mm), no torn, missing or black face, with the BossProfile circle on its top face; then open BossProfile in edit mode (test case Preconditions) and judge the circle at radius 4 and the external curve along a real plate edge, not hanging in space; no error dialog or red error marker. The script does not check these Thens; check each one in the gate run: Given: whole-document query_dependencies has edge BossProfile -> PlatePad (encoded as the object form) (comparison op); Given: intact state captured (tc-03-20-before.png) (GUI action); some finding is REPOINTED, owner BossProfile, prop AttachmentSupport (checked at findings.0 only) (comparison op).

### TC-03-21: ESCALATE

- agent check: The runner takes no before capture: capture the window before the four rejected calls (after the first fit) and compare it with the runner's capture; judge the same PlateProfile geometry and nothing else, no second sketch axis cross, no isolated dot, no extra horizontal glyph, no projected external curve, the two images indistinguishable apart from framing, no error dialog or disconnected-server notice.

### TC-04-03: ESCALATE

- agent check: Visual Then of TC-04-03: the solid straddles the XY plane, half above and half below. The origin planes are hidden in the capture, so the plane is not drawn; the 2026-10-03-04 run judged this with FreeCAD View > Toggle axis cross. Toggle the axis cross, capture, and confirm the origin sits at mid-height of the 20 x 30 x 10 block.

### TC-04-08: ESCALATE

- agent check: The scripted pixel check does not see the hole's shape: judge the capture as a plate with one counterbored hole, two concentric circular diameters at the hole (a wide shallow step narrowing to the threaded bore), not a single plain bore.

### TC-04-09: ESCALATE

- agent check: The capture also shows OtherBody, the refusal fixture of the 'base outside the Body' Then, as a separate 20 x 20 x 5 block at x = 80..100, y = 10..30. Judge the visual Then on the 60 x 40 x 5 plate only: all four vertical corners carry a visible 2 mm round and none is sharp. The script does not check these Thens; check each one in the gate run: Given: topology oracle lists the four 5 mm Z-parallel edges as Edge1/2/5/8 (comparison op).

### TC-04-11: ESCALATE

- agent check: The scripted pixel check does not count holes: count them on the capture, exactly two on the plate 40 mm apart along its long axis and exactly six evenly spaced on the disc; three on the plate, or five or seven on the disc, is a defect.

### TC-04-14: ESCALATE

- agent check: The runner takes no capture before the edit or right after it, and its capture follows the later parameter Thens (Length 12, Reversed, Midplane), so it shows a 20 x 30 x 12 block on the sketch midplane: capture the 10 mm block after the first fit and the 25 mm block right after the edit, and judge the same 20 x 30 footprint grown visibly taller, no second solid.

### TC-04-18: ESCALATE

- agent check: The runner takes no before capture: capture the plate after the first fit, before the refused calls, and compare it with the runner's capture; the hole count must be one in both, any extra bore means a refused pattern partly ran.

### TC-04-20: ESCALATE

- agent check: The scripted pixel check does not see edge dress-ups: judge the capture as the 60 x 40 plate with one small rounded corner and one small flat bevel, both about 1 mm, on different edges.

### TC-05-03: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: pre-mutation window framed and captured (tc-05-03-before.png) (GUI action).

### TC-05-08: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: pre-mutation window framed and captured (tc-05-08-before.png) (GUI action).

### TC-05-14: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: a second FreeCAD build with the other serializer (process kill or relaunch; not applicable on a single-build run; record N/A); Given: pre-attempt window framed and captured (tc-05-14-before.png) (GUI action); CONDITIONAL two-build: a cross-build comparison raises (process kill or relaunch; not applicable on a single-build run; record N/A).

### TC-05-15: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: query_dependencies shows Fillet depends on Pad (comparison op); Given: pre-mutation window framed and captured (tc-05-15-before.png) (GUI action); every tnp_audit finding is RE_BASELINED (encoded as the other counts absent) (comparison op); tnp_audit counts.PASS >= 1 (encoded as present) (comparison op).

### TC-06-03: ESCALATE

- agent check: Read the renders the keep step copied to the run folder. tc-06-03-include-a.png must show one solid (PadA) and tc-06-03-exclude-a.png the rest (BoxB); neither may show a datum plane. tc-06-03-include-body.png must show the Tip solid of BodyA (the 20 x 20 x 10 PadA block), not a blank image. Then say what the window capture shows (count the solids; name any datum plane, origin marker or sketch line) and judge tc-06-03-default.png against it: the same two solids, no datum plane. The window wins on any disagreement.

### TC-06-04: ESCALATE

- agent check: Read the renders the keep step copied to the run folder. tc-06-04-red.png: BoxA (front, 10 mm cube) is red and BoxB (behind it, larger) keeps its own grey. tc-06-04-red-t80.png: BoxB is visible through the red BoxA, and it is not in tc-06-04-red.png. tc-06-04-t0.png and tc-06-04-t100.png must differ where BoxA is drawn, and in tc-06-04-t0.png BoxA keeps its own colour (not red). In the window capture BoxA must still carry its original colour, not red: the window and the red render must disagree on colour. The runner takes no before capture; judge the after capture alone. A red window is a finding. The script does not check these Thens; check each one in the gate run: Given: untouched viewport captured (tc-06-04-before.png) (GUI action); viewport capture after the second call shows ObjectA in its own colour (GUI action).

### TC-06-05: ESCALATE

- agent check: Read the renders the keep step copied to the run folder. tc-06-05-focused.png must fill more of the frame with BoxA than tc-06-05-unfocused.png. tc-06-05-highlight.png must draw BoxA in the accent orange while BoxB keeps its own colour. Then say what the window capture shows (shape, framing, the colour of every face: no face is accent orange) and judge tc-06-05-unfocused.png against it. The window wins on any disagreement.

### TC-06-07: ESCALATE

- agent check: Read the renders the keep step copied to the run folder: tc-06-07-custom.png must be visually the same view as tc-06-07-iso.png. Then say what the window capture shows (how many faces are visible, which way is up, which corner faces the viewer) and judge tc-06-07-custom.png against it: a three-quarter view of the same box. The window wins on any disagreement.

### TC-07-01: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: checks holds the named id set (encoded as a fixed index order) (comparison op).

### TC-07-02: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: checks holds exactly the named ids (encoded as a fixed index order) (comparison op).

### TC-07-03: ESCALATE

- agent check: The final state is a sketch, so the pixel check cannot judge it. If the scripted view_fit_viewport did not return OK, frame with the GUI Fit All toolbar button. Then judge the capture: one straight horizontal segment beginning at the origin marker, with constraint glyphs drawn on it, drawn in FreeCAD's fully-constrained colour rather than the under-constrained white. The script does not check these Thens; check each one in the gate run: failed check ids include sketch.fully_constrained (checked at checks.0 only) (comparison op).

### TC-08-03: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: framed fit and before capture before the pad (GUI action).

### TC-08-04: FAIL

- expect preview.structured_content.diff.validity.explanation: expected "regex \bFillet\b", observed "recompute left 1 object(s) invalid: Fillet: BRep_API: command not done"
- agent check: The runner takes no before capture: capture the framed pad before the preview and compare it with the runner's capture; the two must be identical by eye, sharp edges, no rounded edge, no error-state colouring.

### TC-08-07: ESCALATE

- agent check: The runner takes no before capture: capture the window before the replay and compare it with the runner's capture, stating what is on screen and in the model tree in each; the refused replay must leave the window identical by eye, the same geometry, no duplicated body, no error dialog (the runner's capture also follows the Probe2 apply, which adds an empty body).

### TC-08-08: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: framed fit and before capture before the preview (GUI action).

### TC-08-09: ESCALATE

- agent check: The runner takes no before capture and no capture right after the refused 60 mm call: capture before it, right after it and after the authorized apply, and state the solid's height in each; the refused image must be identical to the before image (a flat sketch, no solid), the after image a solid 30 mm tall against its 20 mm base, not double.

### TC-08-10: ESCALATE

- agent check: The runner takes no before capture and no capture right after the refused call: capture TC0810B framed before the refused apply and right after it, and state what is on screen and which document's title the window carries in each; the two must be identical by eye, TC0810B still a flat sketch with no pad, TC0810A not activated into the viewport (the runner's capture follows the authorized apply on TC0810A and must still show TC0810B).

### TC-08-11: ESCALATE

- agent check: The runner takes no before capture and no capture right after the refused stale-token call: capture before the datum change and right after the stale call, and state the sketch's proportions and whether a solid is present in each; the after image must show the rectangle visibly wider (40 x 20, the confirmed datum change) and no extruded solid (the runner's capture follows the recovery apply, a 40 x 20 x 30 pad).

### TC-08-13: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: framed fit and before capture before the preview (GUI action).

### TC-08-14: ESCALATE

- agent check: The final state is a sketch, so the pixel check cannot judge it, and the runner takes no before capture. If the scripted view_fit_viewport did not return OK, frame with the GUI Fit All toolbar button. Then judge the capture: a flat 20 x 20 mm sketch, no extruded solid, and no error dialog left open by any variant. The script does not check these Thens; check each one in the gate run: Given: framed fit and before capture before the variants (GUI action).

### TC-08-15: ESCALATE

- agent check: The runner takes no before capture and no capture right after the three refused calls: capture before them, right after them and after the authorized apply, and state what is on screen in each; the refused image must be identical to the before image (a flat sketch, no solid), the after image the extruded solid.

### TC-08-16: ESCALATE

- agent check: The runner takes no before capture and no capture right after the three declining calls: capture before them, right after them and after the accepted apply, and state what is on screen in each; the refused image must be identical to the before image (a flat sketch, no solid), the after image the extruded solid.

### TC-09-03: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: untouched window captured after the fit (tc-09-03-before.png) (GUI action).

### TC-09-06: ESCALATE

- agent check: The runner takes no before capture: capture the framed sketch before the refused calls and compare it with the runner's capture; the same sketch, no new line segment, the two images identical by eye, no error dialog or modal.

### TC-09-12: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Given: untouched window captured after the fit (tc-09-12-before.png) (GUI action); query_tree_summary unknown handle: status and detail.code (text prefix only on the wire) (raw RPC or second client).

### TC-09-17: ESCALATE

- agent check: Read the capture: the FreeCAD tree marks the failing object (Pad) with an error icon, and the 3D view still shows the last valid 20 x 20 x 10 block (FreeCAD keeps it on a failed recompute). If the fit step did not return OK (the test case expects the MCP fit may refuse a faulted document), the capture is unframed: click the GUI Fit All toolbar button, capture the window and judge that. A tree with no error marker on Pad is a finding. The script does not check these Thens; check each one in the gate run: at least one check recompute.object with passed false (checked at checks.0 only) (comparison op); _RECOMPUTE_ERROR_STATES in usecases/verify.py includes Touched (encoded as measured equals Touched) (file check).

### TC-09-18: ESCALATE

- agent check: Read the capture: the object named in subject.failing_objects (Pad) has an error icon in the tree and its Sketch is gone from the tree; the 3D view still shows the last valid 20 x 20 x 10 block (FreeCAD keeps it on a failed recompute). If the fit step did not return OK (the test case expects the MCP fit may refuse a faulted document), the capture is unframed: click the GUI Fit All toolbar button, capture the window and judge that. A tree with no error marker on Pad is a finding. The script does not check these Thens; check each one in the gate run: Pad's recompute.object check picked by index checks.1 (comparison op).

### TC-11-01: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: H1 tools/list length is the typed count + 1 (H1 host); script_exec listed on H1, and the proxy tools/list matches (H1 host); H1 stderr has the SECURITY script_exec ENABLED warning (H1 host); GUI addon.log has the same SECURITY warning (log or audit read); exec_enabled true on H1 query_capabilities (H1 host); script_exec on an H1 document returns value_repr '0' (the scenario runs it on the GUI box: '1') (H1 host); H1 audit has two exec lines, the second verify_verdict OK (H1 host); grep of src/ for ALLOW_EXEC, AllowExec, debug_exec finds nothing (file check); Given: addon.log operator settings line has FREECAD_BUDDY_SCRIPT_EXEC='1' (log or audit read); Given: framed baseline captured (tc-11-01-before.png) (GUI action).

### TC-11-17: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: H1 refuses with INVALID_INPUT and the exact 'script_exec is off: ...' message (H1 host); H1 audit has two exec lines, the second verify_verdict INVALID_INPUT (H1 host); H1 query_tree_summary has no Leak line (H1 host); GUI audit log line count unchanged (log or audit read); Given: addon.log has FREECAD_BUDDY_SCRIPT_EXEC='0' and no SECURITY ENABLED line (log or audit read); Given: GUI audit.jsonl line count recorded (log or audit read); Given: framed baseline captured (tc-11-17-before.png) (GUI action).

### TC-12-07: ESCALATE

- agent check: The runner takes no capture between steps: the clean-state Given (toolbar Recompute button disabled) and the dirty-state Then (tc-12-07-props.png: old 5 mm pad still drawn, touched marker on the Pad row where Body is expanded, Recompute button enabled) are not captured; the Edit > Recompute step succeeding is the only scripted sign the command was enabled. Re-run those two GUI reads by hand, then judge the capture: no touched or error marker on any tree row, Recompute button disabled again, a solid visibly taller than the 5 mm plate (20 x 10 x 8). The script does not check these Thens; check each one in the gate run: Given: toolbar Recompute button reads disabled (GUI action); GUI dirty state: Recompute enabled and the touched marker in the tree (GUI action).

### TC-13-04: ESCALATE

- agent check: Visual Thens of TC-13-04. The runner frames with view_fit_viewport, not the GUI Fit All toolbar button. Read the window capture first and describe the solid: a flat square plate 40 x 40 x 10 mm (about four times wider than tall, not a cube) with one circular hole through it. Then read the MCP render (step 'render', structured_content.render.resource_link) and confirm the same silhouette, hole position and camera, with no extra or missing body. Where they disagree the window wins and the difference is a finding against the bridge.

### TC-13-06: ESCALATE

- agent check: Visual Thens of TC-13-06. The runner cannot press the Standard Views or Fit All toolbar buttons, so the window keeps FreeCAD's default camera and is framed by view_fit_viewport; record that camera and compare against the matching MCP camera (the test case's own fallback). Read the window capture first and describe it, then read the MCP render (step 'render', structured_content.render.resource_link): same plate outline and through hole in the same relative position, same visible face count and up direction, a flat 40 x 40 x 10 plate in both, nothing in the window missing from the render and no Body, Sketch or Origin child in the render. AD-34 tone band: no render face is black or white, each face is separable from the background (mean interior tone at least 24/255 from it on one channel, every channel within [20, 235]). The tone order is NOT compared with the window. The script does not check these Thens; check each one in the gate run: scene.rendered_objects contains BoxHole (encoded as index 0 equals BoxHole) (comparison op).

### TC-14-06: ESCALATE

- agent check: The window title bar and the document tabs are outside the 3D view the pixel check reads: judge on the capture that DocB's name is in the title bar, its tab is active (DocA was not brought forward), and DocB's model sits at the size and place of the fit before the refusal.

### TC-14-08: ESCALATE

- agent check: The runner takes no capture after the Given fit: capture the box right after the first fit and compare it with the runner's capture; the model at the same size, position and orientation, no dialog raised by either reject.

### TC-14-16: ESCALATE

- agent check: The script does not check these Thens; check each one in the gate run: Modified state unchanged across the fit, read from the window title (GUI action).

## Agent review

Sample seed 3815675731 (drawn). The agent reads these captures (tests/uat/test-plan.md §9); the scripted pixel check grades the rest.

- TC-02-01 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-01.png
- TC-02-02 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-02.png
- TC-02-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-03.png
- TC-02-04 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-04.png
- TC-02-06 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-06.png
- TC-02-12 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-12.png
- TC-02-13 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-13.png
- TC-02-15 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-15.png
- TC-02-16 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-16.png
- TC-02-17 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-02-17.png
- TC-03-02 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-02.png
- TC-03-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-03.png
- TC-03-05 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-05.png
- TC-03-06 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-06.png
- TC-03-07 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-07.png
- TC-03-08 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-08.png
- TC-03-10 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-10.png
- TC-03-11 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-11.png
- TC-03-12 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-12.png
- TC-03-13 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-13.png
- TC-03-14 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-14.png
- TC-03-16 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-16.png
- TC-03-18 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-18.png
- TC-03-20 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-20.png
- TC-03-21 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-03-21.png
- TC-04-01 (first of TC-04): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-01.png
- TC-04-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-03.png
- TC-04-08 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-08.png
- TC-04-09 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-09.png
- TC-04-11 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-11.png
- TC-04-12 (no pixel check): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-12.png
- TC-04-14 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-14.png
- TC-04-18 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-18.png
- TC-04-20 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-04-20.png
- TC-05-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-05-03.png
- TC-05-08 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-05-08.png
- TC-05-14 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-05-14.png
- TC-05-15 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-05-15.png
- TC-06-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-06-03.png
- TC-06-04 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-06-04.png
- TC-06-05 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-06-05.png
- TC-06-07 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-06-07.png
- TC-07-01 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-07-01.png
- TC-07-02 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-07-02.png
- TC-07-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-07-03.png
- TC-08-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-03.png
- TC-08-04 (fail): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-04.png
- TC-08-07 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-07.png
- TC-08-08 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-08.png
- TC-08-09 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-09.png
- TC-08-10 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-10.png
- TC-08-11 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-11.png
- TC-08-13 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-13.png
- TC-08-14 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-14.png
- TC-08-15 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-15.png
- TC-08-16 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-08-16.png
- TC-09-03 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-03.png
- TC-09-06 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-06.png
- TC-09-12 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-12.png
- TC-09-17 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-17.png
- TC-09-18 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-09-18.png
- TC-11-01 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-11-01.png
- TC-11-17 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-11-17.png
- TC-12-07 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-12-07.png
- TC-13-04 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-13-04.png
- TC-13-06 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-13-06.png
- TC-14-02 (first of TC-14): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-02.png
- TC-14-06 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-06.png
- TC-14-07 (sample): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-07.png
- TC-14-08 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-08.png
- TC-14-16 (escalate): D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-24-01\runner\captures\TC-14-16.png
