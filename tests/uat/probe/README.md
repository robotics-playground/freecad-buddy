# UAT probe

Test-only oracle for UAT. It reads FreeCAD kernel and GUI state directly, not through the
bridge, so a bridge defect that also corrupts the bridge's own report shows as a probe/MCP
disagreement (AD-13).

- Imports stdlib, `FreeCAD`, `FreeCADGui`, `Part` and `PySide` only. Never `freecad_buddy`.
- Read-only. No setter, no transaction, no change to document, view or selection. No write
  endpoint.
- Not shipped. `scripts/build_addon.py` does not copy it. FreeCAD loads it only through `-M`.

| File | Role |
|------|------|
| `InitGui.py` | FreeCAD runs it at GUI init; it starts the listener when the event loop runs |
| `probe_server.py` | localhost HTTP listener, token check, main-thread executor, discovery file |
| `snapshot.py` | read functions; kernel part (`read_document`) and GUI part (`take_snapshot`) |
| `read_fcstd.py` | offline reader for a saved `.FCStd` under FreeCADCmd |
| `expect.py` | comparator: snapshot + expectation → list of mismatches |
| `run_faults.py`, `faults/` | planted fault set that proves the probe detects each bad state |
| `fault_scene.py` | clean scene and done marker for the plant macros; the probe never imports it |

## Launch

Add `-M` with the absolute path of this folder. Use a dedicated `-u` user config, so the
developer's `user.cfg` stays unchanged:

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\freecad.exe" -M D:\path\to\repo\tests\uat\probe -u $env:TEMP\fcb-uat\user.cfg
```

`-u` does not move the user `Mod` folder, so the bridge addon still loads. Add
`--disable-addon FreeCADBuddy` to start FreeCAD without the bridge.

The listener starts after the main window is up. The Report view shows
`fcb-uat-probe listening on 127.0.0.1:<port>, <discovery file>`. Without `-M`, no listener
starts and no discovery file is written.

## Discovery file

`<FreeCAD user app data>/fcb-uat-probe/probe-<pid>.json`, on Windows
`%APPDATA%\FreeCAD\v1-1\fcb-uat-probe\probe-<pid>.json`:

```json
{"pid": 4420, "port": 51234, "token": "<32 hex>"}
```

The probe deletes the file when FreeCAD quits. A killed FreeCAD cannot delete it; the process
that killed FreeCAD deletes it.

## Endpoints

Listener binds `127.0.0.1` on an ephemeral port. Every request must send header
`X-Probe-Token: <token>`.

| Request | Answer |
|---------|--------|
| `GET /health` | `200 {"status": "ok", "pid": <pid>}`; reads no FreeCAD state |
| `GET /snapshot` | `200` snapshot JSON (below) |
| wrong or missing token | `403 {"error": "bad token"}`; no read is done |
| main thread does not run the read in 10 s | `504 {"error": "main thread did not answer"}` |
| read raises | `500 {"error": "<type>: <message>"}` |

The HTTP thread does not touch FreeCAD. It queues the read, and a Qt timer runs it on the main
thread every 50 ms. A read that times out is dropped; the main thread skips it later.

```powershell
$probe = Get-Content "$env:APPDATA\FreeCAD\v1-1\fcb-uat-probe\probe-<pid>.json" | ConvertFrom-Json
Invoke-RestMethod "http://127.0.0.1:$($probe.port)/snapshot" -Headers @{"X-Probe-Token" = $probe.token}
```

Snapshot:

```json
{
  "freecad_version": "1.1.4",
  "active_document": "box_10_20_30",
  "documents": [
    {"modified": false, "name": "box_10_20_30", "label": "box-10-20-30",
     "objects": [
       {"name": "Box", "type": "Part::Feature", "visibility": true,
        "shape": {"valid": true, "volume": 6000.0, "bbox": [0, 0, 0, 10, 20, 30]},
        "screen_center": [967, 565]}
     ]}
  ],
  "view": {"camera": "#Inventor V2.1 ascii ...", "size": [1265, 712],
           "visible_size": [1265, 712], "clipped": false, "rect": [334, 210, 1265, 712]}
}
```

- `visibility` is the object's own `Visibility` flag. A child of a hidden Body reads `true`
  although FreeCAD does not draw it.
- `shape` is `null` for an object with no shape or a null shape. `bbox` is
  `[XMin, YMin, ZMin, XMax, YMax, ZMax]`.
- `view` is the active view of the active document, or `null` when no document is open or the
  active view is not a 3D view.
- `size` is `getSize()`, in device pixels. `visible_size` is the part of the view that its
  parent does not hide, scaled to device pixels. `clipped` is `true` when the two differ by
  more than 1 px in a dimension, for example when the MDI area hides part of a small
  subwindow. The 1 px slack covers the pixel scale, which was measured only at 1.25.
- `visible_size` and `clipped` are `null` when the view is hidden or minimized (empty visible
  region): such a view says nothing about clipping.
- `rect` is `[x, y, width, height]` of the render area in global device pixels: the widget's
  global origin times the device pixel ratio, and `size`. On one monitor this is the unit of a
  window capture, before the capture is scaled.
- `screen_center` is the centre of the object's bounding box projected into the view
  (`getPointOnViewport`), in global device pixels. It is set only for an object with a shape in
  the active document while `view` is not `null`; otherwise it is `null`. The offline reader
  has no `screen_center`.
- No document open: `active_document: null`, `documents: []`, `view: null`.

A file saved without a GUI (for example `benchmarks/g0/golden-models/*.FCStd`) opens in the GUI
with every object hidden. The probe reports `visibility: false` for it, which is what the window
shows.

## Offline reader

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" tests\uat\probe\read_fcstd.py --pass <abs in.FCStd> <abs out.json>
```

`out.json` is `{"freecad_version", "documents": [{"name", "label", "objects"}]}`, with the same
per-object fields as the snapshot and no GUI fields (`modified`, `screen_center`, `view`). The
reader opens the file, reads it and closes it; it never saves. FreeCADCmd hides stdout, so the
result goes only to `out.json`. A missing or unreadable file gives `{"error": "<message>"}` and exit code 1.

## Comparator

`expect.compare(snapshot, expectation)` returns a list of
`{"field", "expected", "observed"}`, empty when the snapshot matches. The expectation names
only the fields it checks; see the docstring in `expect.py`. `documents` lists every document
that must be open, and no other. `volume` and `bbox` match within the absolute `tolerance`
(default `1e-6`). An unknown key raises `ValueError`, also under a document or view that is not
open. The comparator also reads offline-reader output; an `{"error": ...}` result raises
`ValueError` with that error.

## Fault set

```powershell
uv run python tests/uat/probe/run_faults.py
```

Each case in `faults/cases.json` starts its own FreeCAD with `-M`, a temporary `-u` config,
`--disable-addon FreeCADBuddy` and one plant macro. The macro calls `fault_scene.py`: it opens a
copy of `box-10-20-30.FCStd`, shows the box, clears the modified flag, plants its fault and
writes a done marker. A marker with text is a plant error; the runner reports it as that case's
failure. The runner waits for the discovery file and the marker, takes the snapshot, compares
it with the clean expectation, then kills that FreeCAD. It never touches a FreeCAD it did not
start. A run takes about 30 s.

Windows only: the runner finds the discovery file under `%APPDATA%`, and its default
`freecad.exe` is `C:\Program Files\FreeCAD 1.1\bin\freecad.exe`.

| Case | Kind | Planted state | Field that must mismatch |
|------|------|---------------|--------------------------|
| `wrong-visibility` | fault | box hidden | `documents.box_10_20_30.objects.Box.visibility` |
| `wrong-volume` | fault | box 31 mm high | `documents.box_10_20_30.objects.Box.volume` |
| `modified-flag` | fault | document marked modified | `documents.box_10_20_30.modified` |
| `wrong-active-document` | fault | second document open and active | `active_document` |
| `clipped-view` | fault | 3D subwindow pushed partly outside the MDI area | `view.clipped` |
| `clean` | control | nothing | none |
| `clean-queried-twice` | control | nothing; two snapshots | none, and both snapshots equal |

Output ends with `detected N/5` and `false alarms N/2`. Exit code is 0 only for `detected 5/5`
and `false alarms 0/2`. A case that fails with any error counts against the run (fault missed,
control flagged) and prints the error. A `cases.json` with fewer than 5 faults, fewer than 2
controls, or an unknown `kind` stops the run before any launch, with exit code 2. Set `FREECAD_EXE` to use another `freecad.exe`.

Tests that need no FreeCAD: `uv run pytest tests/external/test_uat_probe.py`.
