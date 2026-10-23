# Findings: UAT run 2026-10-23-01

## B1: TC-11-17 pixel finding `view: null` while the window shows the box framed

- **Runner result:** TC-11-17 `FAIL`, reason `pixel view: expected "a 3D view", observed null`
  (`results.json`, `findings[0]`).
- **Window:** `captures/TC-11-17.png` shows the box whole and framed inside the 3D view, with no
  dialog. The visual Then is met.
- **Cause:** not the pixel measurement. `run.check_pixel` returns the `view` finding before it
  measures, because the probe snapshot has `view: null`. TC-11-17 is the only scenario of its launch
  group (`FREECAD_BUDDY_SCRIPT_EXEC=0`), so its `query_capabilities` call is the first of that
  FreeCAD. That first call opens the capability probe documents without `hidden=True`
  (`src/freecad_buddy/usecases/shim.py`), and the probe then reads no active 3D view.
- **Status:** the open deferred product finding from part R (`deferred-work.md`, "The first
  `query_capabilities` in a GUI session leaves FreeCAD with no active document or 3D view"). The
  same scenario failed the same way in the part R pilot runs.
- **Calibration count:** 1 pixel false alarm of 32 pixel-checked scenarios (`report.md`,
  Calibration).
