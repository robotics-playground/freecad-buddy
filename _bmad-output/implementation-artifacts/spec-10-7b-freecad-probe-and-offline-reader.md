---
title: 'Story 10.7b (part P): FreeCAD Probe and Offline Reader'
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_commit: '18a0b0fd9893202d324b330f00883672aaddeaa6'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** UAT Thens are measured through the bridge under test, or by an agent reading the window. No oracle reads FreeCAD's own kernel and GUI state independently, so a bridge defect that also corrupts its own report cannot be caught by a script.

**Approach:** Add a test-only probe under `tests/uat/probe/` that FreeCAD loads only through `-M` (module path) at a UAT launch, serves a read-only JSON snapshot of kernel and GUI state on localhost, and shares no code with `src/freecad_buddy`. Add a FreeCADCmd reader for saved `.FCStd` files, and a planted-fault set that proves the probe detects each named bad state (AD-13).

Scope is part P of Story 10.7b (epics.md AC1–AC3). Parts R (runner, AC4–7), S (§9, AC8) and V (replay, AC9) are deferred in `deferred-work.md`.

## Boundaries & Constraints

**Always:**
- Probe code imports only stdlib, `FreeCAD`, `FreeCADGui`, `Part` and `PySide`; never `freecad_buddy`.
- Every FreeCAD read runs on the Qt main thread; the HTTP thread only queues requests and waits.
- Read-only: the probe calls no setter, opens no transaction, changes no document, view or selection state.
- Listener binds `127.0.0.1` on an ephemeral port and requires a per-process token; it writes `{pid, port, token}` to `<FreeCAD user app data>/fcb-uat-probe/probe-<pid>.json` and deletes it on exit.
- Fault-set launches use a temporary `-u` user config and `--disable-addon FreeCADBuddy`, so the developer's `user.cfg` is untouched and the bridge is not loaded.

**Never:**
- Ship the probe: no change to `scripts/build_addon.py`, `pyproject.toml` or `src/`.
- Load the probe from the user `Mod` folder or any default path.
- Add a write or plant endpoint to the probe.
- Register the probe in `benchmarks/_registry/validators.yaml` (it is a UAT oracle, not a gate validator).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Snapshot | `GET /snapshot` with token, one open doc | JSON: `freecad_version`, `active_document`, per doc `name`, `label`, `modified`, objects (`name`, `type`, `visibility`, `shape: {valid, volume, bbox}` or `null`), `view: {camera, size, visible_size, clipped}` | N/A |
| No document | no open doc | `active_document: null`, `documents: []`, `view: null` | N/A |
| Bad token | wrong or missing token | HTTP 403, no read performed | N/A |
| Main thread busy | read not served in 10 s | HTTP 504 `main thread did not answer` | thread does not hang |
| Offline read | `freecadcmd read_fcstd.py --pass <in.FCStd> <out.json>` | `out.json` with the per-object fields of the snapshot (no GUI fields) | missing/corrupt file: `out.json` `{"error": "<message>"}`, exit code non-zero |
| Compare | snapshot + expectation | list of mismatches, each naming field, expected, observed; empty list when equal; volume and bbox within an absolute tolerance from the expectation | unknown expectation key: raise |

</frozen-after-approval>

## Code Map

- `docs/references/FreeCAD/src/App/FreeCADInit.py:101,153-154,276-286` -- each `-M` path is one module folder; its `InitGui.py` runs from `Gui/FreeCADGuiInit.py:333-341` before the event loop starts (`Gui/StartupProcess.cpp:459-478`), so defer start with `QTimer.singleShot`
- `docs/references/FreeCAD/src/App/Application.cpp:2214,2218,2221,2389-2396` -- `-u`, `-M`, `--disable-addon <folder name>`; `-u` does not move the user `Mod` folder
- `docs/references/FreeCAD/src/App/Application.cpp:2835-2849,2893-2899` -- a `.py` argument is imported (`__name__` = stem, no main guard); `.FCMacro` runs via `runFile`; `--pass` args reach `sys.argv`
- `docs/references/FreeCAD/src/Gui/View3DPy.cpp:138-166,198,337-339` -- `getCamera`, `getCameraOrientation`, `getSize`, `graphicsView()`; visible area = `graphicsView().visibleRegion().boundingRect()`
- `docs/references/FreeCAD/src/Gui/Document.pyi:229,247` -- `ActiveView`, `Modified`; `obj.Visibility` mirrors `ViewObject.Visibility`
- `tests/uat/run/2026-10-03-02/evidence/fc_measure.py` -- precedent: FreeCAD-API-only measurement, no `freecad_buddy` import
- `tests/run_tests.py:24,34-35` -- FreeCADCmd imports scripts and hides stdout: write results to a file
- `tests/external/test_session_metrics.py:9-12` -- pattern for importing a non-package module in pytest
- `benchmarks/g0/golden-models/` -- known-good `.FCStd` with hand-computed volumes for controls
- `C:\Program Files\FreeCAD 1.1\bin\{freecad,freecadcmd}.exe` -- default executables; override with `FREECAD_EXE` / `FREECADCMD_EXE`

## Tasks & Acceptance

**Execution:**
- [x] `tests/uat/probe/InitGui.py` + `tests/uat/probe/probe_server.py` -- start the listener after the main window is up; main-thread executor (`QTimer` poll or queued signal); `/snapshot` and `/health`; discovery file lifecycle -- AC1
- [x] `tests/uat/probe/snapshot.py` -- pure read functions over FreeCAD objects (kernel and GUI parts separated so the offline reader reuses the kernel part) -- AC1, AC2
- [x] `tests/uat/probe/read_fcstd.py` -- FreeCADCmd entry: parse args after `--pass`, open the file read-only, write JSON, exit code -- AC2
- [x] `tests/uat/probe/expect.py` -- stdlib comparator from the I/O matrix -- AC3
- [x] `tests/uat/probe/faults/` -- one plant `.FCMacro` per case and `cases.json`: 5 planted defects (wrong visibility, wrong volume, modified flag, wrong active document, clipped view via a non-maximized 3D subwindow pushed partly outside the MDI area) and 2 clean controls (clean scene; clean scene queried twice, proving the query changed nothing) -- AC3
- [x] `tests/uat/probe/run_faults.py` -- per case: launch FreeCAD with `-M <probe>`, temp `-u`, `--disable-addon FreeCADBuddy`, the plant macro; wait for the discovery file; snapshot; compare; terminate the process it started; print sensitivity and false-alarm counts; exit non-zero below 5/5 detected or above 0 false alarms -- AC3
- [x] `tests/uat/probe/README.md` -- launch command, discovery file, endpoints, offline reader, fault set -- AC1–3
- [x] `tests/external/test_uat_probe.py` -- comparator matrix rows; snapshot JSON shape from fake objects; static check that no file under `tests/uat/probe/` imports `freecad_buddy` and that `scripts/build_addon.py` output contains no `probe` path -- AC1, AC3

**Acceptance Criteria:**
- Given FreeCAD 1.1.4 launched with `-M tests/uat/probe`, when `/snapshot` is queried, then it returns the matrix fields and the document `Modified` flag is unchanged after the query.
- Given FreeCAD launched without `-M`, when it starts, then no `probe-<pid>.json` appears.
- Given `run_faults.py`, when it runs on the live machine, then 5/5 planted defects are detected and 0/2 controls are flagged.
- Given `benchmarks/g0/golden-models/box-10-20-30.FCStd`, when the offline reader runs, then the volume is 6000 within 1e-6 and the bbox is 10×20×30.

## Implementation Notes

- A `.FCStd` saved without a GUI (all `benchmarks/g0/golden-models/`) opens in the GUI with every object hidden; the probe reports `visibility: false`, which matches the window. Each plant macro first shows the box and sets `Modified = False` to build the clean scene.
- `getSize()` is device pixels and truncates: on FreeCAD 1.1.4 at device pixel ratio 1.25, a 1534 x 799 widget reports 1917 x 998. `read_view` scales `visibleRegion()` by the ratio with `int()`; rounding gave a 1 px false `clipped`. Measured at ratio 1.25 only, so a difference of 1 px or less per dimension is not clipped. A hidden or minimized view (empty region) gives `visible_size` and `clipped` `null`.
- FreeCAD processes command-line macros in `MainWindow::delayedStartup`, after the probe's `singleShot(0)` start, so the discovery file can appear before the plant is done. Each macro calls `fault_scene.mark_planted()` last, which writes the file named by `FCB_PROBE_PLANT_DONE` (text = plant error, empty on success); `run_faults.py` waits for it and the discovery file, and reports a plant error as the case failure.
- A fault counts as detected only when its named `field` in `cases.json` mismatches, not any field. The comparator treats `documents` as the exact set of open documents.

- Review patches (pass 1): findings 1-6, 10, 12, 14, 15, 17, 18, 21, 22, 27, 32 and 37 applied. New `tests/uat/probe/fault_scene.py` holds the shared plant setup and done marker; `test_uat_probe.py` grew from 22 to 52 tests. After the patches: `tests/external` 1544 passed, 4 skipped; `run_faults.py` 5/5 detected, 0/2 false alarms; offline reader volume 6000.0.

## Spec Change Log

## Review Triage Log

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | verification-gap | `run_faults.judge` scoring rule untested | medium | no test imports `run_faults`; a `bool(mismatches)` regression would still print 5/5 | patch |
| 2 | verification-gap, blind | `/snapshot` 200 and 500, `/health`, 404 untested | medium | fixture never runs `_run_queued_jobs`; deleting the `except` turns a 500 into `200 null` | patch |
| 3 | verification-gap, blind, edge | discovery write/delete untested; `_stop` raises if the file is gone and leaves the poll timer running | low | `probe_server.py:116-119` bare `os.remove`; `start()`/`_stop()` never run in tests | patch |
| 4 | verification-gap, blind | `read_fcstd.py` error path untested | medium | no test runs `main()`; manual check only | patch (fake-module test) |
| 5 | verification-gap | `view: null` for a non-3D active view untested | low | only `view=None` test has no document, so the `hasattr` guard never runs | patch |
| 6 | blind, edge | `read_fcstd.py` parses argv and writes `out.json` outside `try`; a raise at import makes FreeCAD rerun the file via `runFile` and exit 0 | medium | `read_fcstd.py:33,38-39`; `Application.cpp:2845-2847` fallback | patch |
| 7 | blind | no automated check that FreeCAD without `-M` writes no discovery file | low | checked live by the implementation agent (report); automation needs a runner flag | reject |
| 8 | blind | `--disable-addon FreeCADBuddy` not proven to keep the bridge out | low | folder is `Mod/FreeCADBuddy` (listed); `FreeCADInit.py:258` matches by folder name | reject |
| 9 | blind | stale `probe-<pid>.json` read after pid reuse | false | the new probe overwrites the file at start, before the plant marker the runner waits for | reject |
| 10 | blind, edge | `run_faults.py` is Windows-only (`APPDATA`, `freecad.exe` path) and says nothing | low | `run_faults.py:26,40`; direct doc line | patch |
| 11 | blind | Code Map names `FREECADCMD_EXE`, unused | low | fix edits this build's spec | reject |
| 12 | blind, edge | one unexpected exception in a case aborts the run with no summary | low | `run_faults.py:118-119` catches only `LaunchError, OSError` | patch |
| 13 | blind | `_reply` serializes outside `try`; a non-JSON value resets the socket | low | every snapshot value is str/float/bool/list (`getCamera` is a str); unreachable today | reject |
| 14 | blind | `visibility` is the object's own flag; README says it matches the window, false for a child of a hidden Body | medium | `snapshot.py:29` `obj.Visibility`; direct doc correction | patch (doc) |
| 15 | blind | `clipped` uses exact equality, measured at scale 1.25 only | low | 1 px rounding already caused one false `clipped` (Implementation Notes) | patch (1 px tolerance) |
| 16 | blind | "opens no transaction" has no check | low | probe calls only getters (`snapshot.py`); adding an undo field is new surface | reject |
| 17 | blind | Duplicated Code: scene setup repeated in six plant macros | low | `clean.FCMacro:7-11` and each fault macro; smell created by this diff | patch |
| 18 | blind, edge | `clipped_view.FCMacro` walks to `None` without a `QMdiSubWindow`; marker never written, 120 s wait with no cause | low | `clipped_view.FCMacro:18-20` | patch |
| 19 | blind | deferred entries use `source_spec: none`; items at `deferred-work.md:1530,1750` not reassigned | false | entries follow the step-1 split format; `:1530` is a bridge-render scenario for the runner (part R), not a probe change; ledger entries are not edited | reject |
| 20 | blind | generic module names `snapshot`, `expect` on `sys.path` | low | no collision found in `Mod` or the FreeCAD install; rename churns every file | reject |
| 21 | edge | unknown expectation keys not rejected when the document is absent or the view is `None` | low | `expect.py:104-114`; I/O matrix says unknown key raises | patch |
| 22 | edge | offline `{"error": …}` passed to `compare` loses the message | low | `expect.py:99-101`; direct raise | patch |
| 23 | edge | GUI-only fields against offline output show `observed: None` | low | reported as a mismatch, which is correct behaviour for a wrong expectation | reject |
| 24 | edge | `1 == True` passes for boolean fields | low | expectation author error only; fix adds type rules | reject |
| 25 | edge | non-number tolerant expectation raises `TypeError` | low | loud failure on an author error | reject |
| 26 | edge | one odd object's shape read fails the whole snapshot | maybe-false | no object type found whose `Shape.isValid`/`Volume` raises; settle with a document holding meshes, links and spreadsheets | reject (low if true) |
| 27 | edge | minimized or hidden window: empty `visibleRegion` reports `clipped: true` | medium | the 10.7 live checks found FreeCAD minimized; `launch_app` has `start_minimized` | patch |
| 28 | edge | a read already running past 10 s repeats on every retry | low | unlikely; fix adds state | reject |
| 29 | edge | query string answers 404 | low | no caller sends one | reject |
| 30 | edge | discovery write failure after the server started leaves it running unlisted | low | disk/permission failure in app data; fix adds branches | reject |
| 31 | edge | cleanup error in `stop()` masks the original error | low | fix adds branches; covered by finding 12's per-case catch | reject |
| 32 | edge | `cases.json` with fewer than 5 faults or an unknown `kind` still exits 0 | low | `run_faults.py:114,131`; spec bar is 5/5 and 0/2 | patch |
| 33 | edge | `queries: 0` passes a control with no snapshot | low | author error in a committed file | reject |
| 34 | edge | camera may change between the two queries of a control | maybe-false | two live runs gave 0/2; settle by repeated runs | reject (low if true) |
| 35 | edge | static no-import check misses `importlib`/`__import__` | low | no such use; fix adds parsing | reject |
| 36 | edge | partly corrupt `.FCStd` may restore with errors and exit 0 | low | unverified FreeCAD behaviour; fix adds checks | reject |
| 37 | implementation agent | harness standard says a FreeCADCmd script writes no output file | low | `read_fcstd.py` writes its file under `freecadcmd.exe` (verified); the claim holds only for a `__main__`-guarded script | patch (doc) |

## Design Notes

Clipped view: F-27 (UAT 2026-10-03-04) showed a small window where the MDI area scrolls part of the 3D view; `getSize()` stays the full widget while `visibleRegion()` shrinks. The probe reports both, and `clipped` is true when they differ.

`run_faults.py` launches its own FreeCAD windows (one per case, about 7 launches) with `subprocess`, so it runs at the agent shell's integrity level and can end each process it started. It never touches a FreeCAD it did not start.

## Verification

**Commands:**
- `uv run pytest tests/external/test_uat_probe.py` -- expected: all pass
- `uv run pytest tests/external` -- expected: no new failure
- `uv run ruff check .` -- expected: clean
- `uv run python tests/uat/probe/run_faults.py` -- expected: `detected 5/5`, `false alarms 0/2`, exit 0
- `"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" tests/uat/probe/read_fcstd.py --pass <abs>/box-10-20-30.FCStd <abs out>.json` -- expected: volume 6000

**Manual checks:**
- Launch FreeCAD with `-M`, open a golden model, query `/snapshot`, capture the window with `cua-driver`, read the capture: the snapshot's visibility and active document match what the window shows.
