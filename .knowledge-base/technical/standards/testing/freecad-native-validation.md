# FreeCAD Native Validation — Check a Built Part with FreeCAD's Own Tools

How an agent proves that a part built through the bridge is correct, using FreeCAD's own
measurement instead of the freecad-buddy MCP results. The MCP results come from the code under
test. FreeCAD's own tools do not, so their numbers are the trusted evidence.

Read [freecad-gui-e2e-harness](freecad-gui-e2e-harness.md) first. It covers preflight, launch,
the MCP calls that build the part, and shutdown. This guide starts when the part exists in the
running FreeCAD window.

Reference run with every artifact: `tests/uat/run/2026-10-03-02/` (report, evidence, scripts).

## Evidence layers

Use all three. Each layer catches what the others cannot.

| Layer | Tool | Gives | Code path |
|-------|------|-------|-----------|
| A | Part > Check Geometry (native task panel) | validity, BOP errors, solid count, face count, volume, area | FreeCAD GUI only |
| B | Kernel macro run from Macro > Macros > Execute | volume, bounding box, each cylinder's diameter, axis and centre | FreeCAD API (`App`, `Part`), no `freecad_buddy` import |
| C | Viewport screenshot after FreeCAD's own Fit all | shape, proportions, which face a feature is on | FreeCAD GUI only |

Layer A has no positions. A position defect (feature on the wrong face, mirrored, offset datum)
builds at the correct volume, so layer B or C must show it.

## Scripts

All in `tests/uat/run/2026-10-03-02/evidence/`:

| Script | Role |
|--------|------|
| `cg_native.sh` | Layer A for one document: activate, select `Body`, Check Geometry, Run check, read result, screenshot `cg-<tag>.png` |
| `ui.py` | UIA locator used by `cg_native.sh`: tree row, `Body` under a document, task button, Shape Content text |
| `fc_measure.py` | Layer B macro: writes `fc_measure.json` (one row per open document) |
| `replay_g3.py` | Builds G3 corrupted-plan parts over MCP. An example of the build step, not part of the check |

## cua-driver basics for FreeCAD

- Pass JSON on stdin: `echo '{...}' | cua-driver <tool>`. The positional form fails on Windows
  backslashes.
- `get_window_state {pid, window_id}` returns the UIA tree. Each element has `role`, `label`,
  `value`, `actions` and `frame`. `frame` is in **screen pixels** (2560 x 1440 on the reference
  machine, 125 % scale).
- A window screenshot (`--screenshot-out-file`) is downscaled to 1568 px on the long side. Its
  pixels are window coordinates for a `{pid, window_id, x, y}` click.
- A desktop click (`{"target":{"kind":"desktop","display_id":"primary"},"x":..,"y":..}`) uses
  screen pixels. Use it with UIA `frame` centres. It is delivered as foreground input.
- `get_desktop_state` returns the full screen as `screenshot_png_b64`. Decode it to a PNG. Use it
  when a modal dialog blocks the window UIA route.
- Qt tree rows and keys need foreground delivery. A background or UIA `invoke` on a tree row does
  not select it.
- Verify every action in a second domain: window title (`list_windows`), UIA text, or pixels.

Menu paths confirmed on FreeCAD 1.1.1 with `invoke_menu {pid, window_id, path}`:

| Path | Notes |
|------|-------|
| `["View","Workbench","Part"]` | Check Geometry is a Part-workbench toolbar button |
| `["View","Panels","Python Console"]` | Capital C. Resolves only while no task dialog is open |
| `["View","Overlay Docked Panel","Toggle Right"]` | Restores a hidden right-side overlay (Tasks) |
| `["Windows","<N> <document label> : 1*"]` | Activates a document. Read the exact label from the expanded Windows menu |
| `["Macro","Macros"]` | Opens the modal Execute Macro dialog. The UIA call blocks until the dialog closes, so run it in the background |

## Procedure

### 1. Prepare

1. Confirm the part's document is open: MCP `document_list`, or the window title.
2. Switch to the Part workbench: `invoke_menu ["View","Workbench","Part"]`.
3. Make room for the task panel: close the Python console panel if it is open.
4. Record `PID` (FreeCAD process) and `WIN` (main window id from `list_windows`).

**Done when:** title reads `... - FreeCAD 1.1.1`, the menu bar shows `Part`, and no task dialog
is open (UIA has no `Button` labelled `Run check`).

### 2. Layer A — Check Geometry on each part

```bash
PID=<pid> WIN=<window_id> bash tests/uat/run/2026-10-03-02/evidence/cg_native.sh <document label> <tag>
```

It prints one JSON line:

```json
{"tag": "...", "rows": ["<doc>.Body"], "solids": "1", "volume": "28229.8",
 "status": ["1 processed out of 1 selected\n0 invalid shapes. ...", "No errors"]}
```

What the script does, so you can repeat a step by hand:

1. Closes any open task dialog with the task `Close` button. A Check Geometry task binds to the
   document that was active when it opened, so a new document needs a new task.
2. Presses Ctrl+Tab (foreground) until the window title names the document.
3. Clicks the document's `Body` tree row. If the row is collapsed, it clicks the document row and
   presses Right first.
4. Clicks the Check Geometry toolbar button (screen 1490, 215 on the reference layout; the status
   bar reads "Analyzes the selected shapes for errors" when the cursor is on it). Retries up to 3
   times, then clicks `Run check`.
5. Reads the Shape Content text: the UIA `Edit` whose `value` starts with `Checked object`. The
   newest block is last.

**Done when:** for every part, `rows` names that document's `Body`, `status` shows
`0 invalid shapes` and `No errors`, `solids` is `1`, and `volume` is inside the spec band.
Read at least one `cg-<tag>.png` yourself.

### 3. Layer B — kernel macro

1. Copy the macro into the user macro folder:
   `cp tests/uat/run/2026-10-03-02/evidence/fc_measure.py "$APPDATA/FreeCAD/v1-1/Macro/fc_measure.FCMacro"`.
2. Open Macro > Macros (in the background, see the menu table). The dialog title is
   `Execute Macro`.
3. Take `get_desktop_state`, find `fc_measure.FCMacro` in the User macros list, desktop-click it,
   then desktop-click `Execute`.
4. Wait for `fc_measure.json` to appear next to the script (its mtime is the run time).
5. Delete the copied `.FCMacro`.

**Done when:** `fc_measure.json` holds one row per open document. Volumes equal layer A to the
displayed precision. For each position defect, the cylinder `axis` and `center` show the defect.

### 4. Layer C — viewport

1. Activate the document.
2. Click FreeCAD's Fit all toolbar button (the first magnifier). Do not trust
   `view_fit_viewport` for this check (see troubleshooting).
3. Save a window screenshot and read it yourself: document name in the tree, part shape, feature
   location.

**Done when:** each screenshot shows the part the case describes, with no modal dialog.

### 5. Clean up

1. Close the task dialog, then close the test documents (`_automation/uat/close_all.py`).
2. Delete any copied macro from `%APPDATA%\FreeCAD\v1-1\Macro\`.
3. Delete screenshots that show anything other than FreeCAD (for example, a terminal window).
4. Tell the operator about any layout change you left (closed Python console, workbench).

## Subagent brief

A validation subagent needs only this brief and the running FreeCAD. Fill in the brackets.

```text
Validate parts in the running FreeCAD with FreeCAD's own tools. Follow
.knowledge-base/technical/standards/testing/freecad-native-validation.md exactly; load the
cua-driver skill first. FreeCAD pid [PID], main window id [WIN]. Documents to check: [labels].
Expected values per document: [volume and band, solids, position facts]. Do not launch or quit
FreeCAD, do not edit any repository file, do not run freecad-buddy MCP tools except
document_list. Write evidence to [absolute dir]. Report a table: document, Check Geometry
status, solids, native volume, expected, verdict; plus every step that failed and how you
recovered.
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `invoke_menu` returns `menu path segment N was not found` | Label differs on this build (`Python Console`, `Standard Views`, `Macros`), or a task dialog is open and the View menu is shorter | Expand the menu with `click {element_token, action:"expand"}`, list `MenuItem` labels, use the exact text. Close the task dialog first |
| Tree click does nothing; console shows no `Gui.Selection.addSelection` | Click went through UIA `invoke`, which does not select a Qt tree row | Click again with `delivery_mode:"foreground"` or as a desktop click at the row's `frame` centre |
| Check Geometry button click does nothing; status bar shows its tooltip | The click landed as a hover | Click again (up to 3 times) |
| `0 processed out of 0 selected` | Selection is in a different document than the active one, or nothing is selected | Close the task, activate the document (window title must match), select `Body`, start a new check |
| Run check reuses the previous part's result | The task dialog belongs to the previous document | Close the task and start Check Geometry again for this document |
| Shape Content area is empty | The Shape Content section is collapsed (its UIA `QFrame` has no frame) | Click the section's header arrow (the `QLabel` in its `TaskHeader`) |
| Task panel too short; scrolling does not move it | Tasks panel is a right-side overlay, and the bottom console takes the height | Close the Python console panel; collapse Check Geometry Results so Shape Content gets the space |
| Task panel vanished after an overlay click | `Std_DockOverlayToggleRight` hid the right overlay | `invoke_menu ["View","Overlay Docked Panel","Toggle Right"]` |
| `get_window_state` times out: `UIA provider unresponsive` | A modal dialog is open, or an earlier UIA `invoke` is still blocked on it | Use `get_desktop_state` and desktop clicks for that dialog; run modal-opening invokes in the background |
| Text typed into the Python console never runs; Enter does nothing | UIA `type_text` sets the widget value; Qt never receives key input, even with foreground Enter | Do not script through the console. Run code as a macro (layer B) |
| A locator for `Close` clicks the window title bar | The main window has a `Button` named `Close` at y = 0 | Match task buttons only below the title bar (`frame.y > 200`), as `ui.py` does |
| `view_fit_viewport` shows a grey screen, status bar about 1.8 mm wide | The fit bounds a datum or a one-point sketch, not the solid (deferred defect) | Use FreeCAD's Fit all toolbar button |
| Extents read 99.84 for a 100 mm ring | `Shape.BoundBox` is not tight on circular edges | Do not grade circular extents from `BoundBox`; compare volume and cylinder diameters |
| A desktop capture shows a terminal over FreeCAD | Another window is in front | Bring FreeCAD forward with a foreground action first; delete that screenshot from the evidence |
