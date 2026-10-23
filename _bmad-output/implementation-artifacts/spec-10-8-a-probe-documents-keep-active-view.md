---
title: 'Story 10.8 (goal 1): Probe Documents Keep the Active Document and View'
type: 'bugfix'
created: '2026-10-23'
status: 'done'
baseline_commit: 'b4e17f032fd182a7ee45a6c3307a1e04d204d91c'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The first `query_capabilities` in a GUI session leaves FreeCAD with no active document and no active 3D view. The capability probes in `src/freecad_buddy/usecases/shim.py` open scratch documents with `FreeCAD.newDocument(name)` (`:85`, `:200`, `:227`) or `newDocument(name, hidden=True)` (`:311`, `:344`). `App::Application::newDocument` makes the new document active and restores the previous one only for a temporary document (`docs/references/FreeCAD/src/App/Application.cpp:505-516`); `closeDocument` of the active document then sets the active document to none (`:533-535`). The user's GUI loses its active document (conflicts with AD-31: no GUI change the user did not ask for), and the Critical scenario TC-11-17 fails in every scripted UAT run (`pixel view: expected "a 3D view", observed null`).

**Approach:** Open every scratch probe document in `shim.py` with `hidden=True, temp=True`, so FreeCAD creates no view and restores the previous active document itself. Add an in-FreeCAD regression test that the active document is the same before and after each probe. Prove the GUI effect live: the scripted runner's TC-11-17 scenario passes on FreeCAD 1.1.4.

</frozen-after-approval>

## Implementation Notes

- `src/freecad_buddy/usecases/shim.py`: new `_scratch_document(name)` context manager opens every probe document with `hidden=True, temp=True` and closes it on every path; `varset_backend`, `partdesign_available`, `probe_object`, `implemented_map_modes` and `property_enums` use it. The `temp=True` mechanism is stated in its docstring. `probe_object` docstring states that the caller's active document stays active.
- `tests/infc/test_document_lifecycle.py`: `test_should_keep_the_active_document_when_a_scratch_probe_runs` runs each of the 5 probes with a user document active, asserts the probe's success value, the active document and the open-document set. Without the fix: 5 errors, `App.ActiveDocument` is `None`. With it: pass. Full in-FreeCAD suite 856 OK (FreeCAD 1.1.4); `tests/external` 1691 passed; ruff clean on the changed files.
- `ruff format --check` reports 11 other files (not touched here); left as is.
- Live, FreeCAD 1.1.4 through the scripted runner (TC-11-17 alone in its `FREECAD_BUDDY_SCRIPT_EXEC=0` group, so its `query_capabilities` is the first of that FreeCAD; TC-11-01 and TC-02-02 as controls): 3 PASS, probe `view` present and not clipped in all three. Agent read of `TC-11-17.png`: one whole box framed in the 3D view, no probe document tab, no dialog. No FreeCAD left, `:8765` free.

## Review Triage Log

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | test passes when a probe fails quietly (catch-all returns the fallback) | medium | `shim.py` probes catch every exception; test checked only the active document | patch: assert each success value |
| 2 | test name and missing Arrange/Act/Assert differ from the file's newer tests | low | `test_should_..._when_...` with sections at `:477` | patch |
| 3 | test comment holds history and a scenario id | low | commenting standard forbids provenance | patch |
| 4 | no comment explains `temp=True`; FreeCAD's docstring says only "not saved" | medium | `ApplicationPy.cpp:169` vs `Application.cpp:513-516` | patch: `_scratch_document` docstring |
| 5 | create-and-close repeated at 5 sites (Shotgun Surgery, Duplicated Code) | medium | the fix needed 5 edits | patch: `_scratch_document` |
| 6 | no guard stops a new direct `newDocument` probe | low | needs a source-scanning test; the helper is the one route | reject |
| 7 | exact document-list assertion fails on leftovers from other tests | low | compare the set before and after instead | patch |
| 8 | caches cleared and not restored | low | each cache refills with the same value on its next call | reject |
| 9 | no-active-document case untested | low | ends with no active document, as before; no behaviour change | reject |
| 10 | headless test cannot prove the GUI view survives | false | not a defect of the diff; the live TC-11-17 run is the GUI proof | reject |
| 11 | caller's document is now active while `read` runs | low | no `ActiveDocument` use in `usecases/`; docstring now states the guarantee | patch (docstring) |
| 12 | test lambda returns an object from a closed document | low | returns `probe.TypeId` now | patch |
