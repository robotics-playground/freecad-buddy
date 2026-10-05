---
title: 'Restore the STEP write unit after each export'
type: 'bugfix'
created: '2026-10-05'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `export_step` pins the process-global OCC static `write.step.unit` to `MM` (`shim.py:406`) and never restores it. FreeCAD applies the user's `Mod/Part/STEP` `Unit` preference to that static only once, at Part load (`OCAF/ImportExportSettings.cpp:133-147`, from `AppPart.cpp:577`). So after one bridge export, the user's own File > Export STEP writes MM even when the preference is `M` or `INCH`. Deferred from Story 10.5 (`deferred-work.md`, last `spec-10-5` entry).

**Approach:** Read the unit with `Part.exportUnits()["write.step.unit"]` (`AppPartPy.cpp:2426-2446`) before the pin. Set it back in the same `finally` that already calls `shim.restore_step_schema()` around `shape.exportStep(path)`, also when the write raises. Unlike the schema, the unit has a getter, so the restore is exact. Probe on FreeCAD 1.1.3 (fcb env): `Part.exportUnits()` returns `{'write.iges.unit': 'MM', 'write.step.unit': 'MM'}`; after `setStaticValue("write.step.unit","INCH")` a plain `exportStep` writes `CONVERSION_BASED_UNIT('INCH',…)`.

**Tests:** an in-FreeCAD test sets the static to `INCH`, runs `export_step`, and checks that the static reads `INCH` afterwards and that a plain `Shape.exportStep` writes the `INCH` unit. A second test does the same when `exportStep` raises. The bridge file itself stays MM.

</frozen-after-approval>

## Implementation Notes

- `shim.pin_step_config(ap)` now reads `Part.exportUnits()["write.step.unit"]` before the pin and returns it. `shim.restore_step_schema()` became `shim.restore_step_config(unit)`, which sets the unit back exactly and the schema by the Story 10.5 D6 rule. `exports.export_step` passes the saved unit to it in the existing `finally`.
- Tests (`tests/infc/test_export_tools.py`): `setUp` saves the unit and `tearDown` restores it. Two new tests: a bridge export with the static at `INCH` leaves it at `INCH`, the bridge file has no `INCH` unit, and a plain `exportStep` afterwards writes `CONVERSION_BASED_UNIT('INCH'`; the same restore when `exportStep` raises (`Writing of STEP failed`). Mutation check: with the unit restore line removed, both fail; with it, the 30 export tests pass.
- `exports.py` changed, so the three export validators were re-scored (STEP leg on the fcb env, mesh leg on `uv`): sensitivity 1.0, false alarm 0.0, `validator_sha` `b9e65813…`.
- Design `verification-design.md` §6.2 now states the unit restore and its getter.
- Review patches: the pin sets the schema before the unit, so a refused schema cannot leave the unit at `MM`; the docstring and design §6.2 now say FreeCAD also applies the `Unit` preference when the STEP preferences are saved (`STEP/ImportExportSettings.cpp:99-103`).

## Review Triage Log

- Pin sets unit before schema; a raising schema set would leave the unit at `MM` — low, patched by reordering (one-line swap; the enum names are valid on every supported build, so the raise is not shown reachable).
- A raising unit restore hides the `exportStep` error and skips the schema restore — false: the restored value comes from `Part.exportUnits()`, which returns only values `setStaticValue` accepts.
- Bridge file checked only by the absence of `INCH` — rejected: an `INCH` file also carries `SI_UNIT(.MILLI.,.METRE.)`, so a positive millimetre check cannot separate the cases; the pin to `MM` is unchanged code.
- Test uses `Shape.exportStep`, not `Import.export` → `WriterStep` — rejected low: both read the same `write.step.unit` static (Story 10.5 review confirmed the same for the schema static).
- No `export_step.unit` header check in the paired verify — deferred: new capability, not caused by this change.
- Docstring and design said the `Unit` preference is applied only at Part load — low, patched: `STEP/ImportExportSettings.cpp:99-103` `setUnit` also writes the static.
- Deferred-work entry left open — rejected: `deferred-work.md` is append-only.
- Registry `run_id` identical across re-scores — rejected: pre-existing scorer rule (`er-{today}-1`); `validator_sha` binds the score to the sources and the run reproduces.
- Tests may have run against the stale built addon — false: the installed `Mod/FreeCADBuddy/freecad_buddy` is a junction to `src` (verified in Story 10.5), and `dist/` is ignored build output.
