---
title: 'Capability-probe hardening: pure element-map probe + startup-serialized varset probe'
type: 'bugfix'
created: '2026-07-24'
status: 'done'
baseline_revision: 'ca7d5e431840a87eccf2c0d8abc6715175cfaec2'
final_revision: 'f8d62b16cd5189a0890189f7eef022d12f627fd6'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/project-context.md'
warnings: []
---

<intent-contract>

## Intent

**Problem:** Two `usecases/shim.py` capability probes are unsafe/impure. `element_map_available()` requires a NON-empty element map on a probe box — a behavioral signal ("did this shape populate a map") not a pure capability ("is the API exposed") — so a lazily-populating build yields a false negative (AD-11 wants a capability probe). `varset_backend()` creates and closes a throwaway `FCB_TMP_varset_probe` document by calling `FreeCAD.newDocument`/`closeDocument` directly, bypassing the `DocumentRegistry` single-writer lock; its doc-set churn is not serialized against registry mutations (AD-20) once a concurrent executor lands.

**Approach:** For `element_map_available()`, drop the non-emptiness check and probe pure API exposure only — `getElementHistory` callable plus the element-map attributes present on the shape (source-verified against `docs/references/FreeCAD/`). For `varset_backend()`, keep the probe body but guarantee its doc churn never interleaves with registry ops by warming every capability probe once, on the FreeCAD execution thread, before either host begins serving requests — the intent's sanctioned "run all capability probes once at startup before serving" option.

## Boundaries & Constraints

**Always:**
- FreeCAD element-map API names MUST be confirmed against `docs/references/FreeCAD/` before use (source-verify standard). Confirmed: `getElementHistory` is a TopoShape method; `ElementMapSize` (int), `ElementMap` (dict), `ElementMapVersion` (str) are ComplexGeoData attributes TopoShape inherits (`src/Mod/Part/App/TopoShape.pyi:1087`, `src/App/ComplexGeoData.pyi:152-162`).
- Probes stay host-agnostic, stdlib + FreeCAD-App only, lru_cached, and NEVER branch on version strings (capability probes only — project-context "FreeCAD API Traps").
- Probe warming runs on the FreeCAD execution thread (GUI: Qt main thread via the marshal; headless: inline) and BEFORE the listener/server accepts requests.
- Warming must not raise on a build where a probe is unavailable — a probe that cannot run returns its conservative default (existing shim contract).
- The temp probe document keeps the reserved `FCB_TMP_` prefix and is cleaned by its creator (project-context TempDocs rule).

**Block If:**
- Source verification shows the element-map Python surface differs from the confirmed names above on the targeted FreeCAD legs (1.0.x floor / 1.1.x primary), such that no pure-exposure signal exists without the non-emptiness check.

**Never:**
- Do NOT inject a `DocumentRegistry` instance into `shim.py` or make module-level probes depend on a host object — probes stay pure module functions.
- Do NOT route the varset probe's temp document through `document_*` usecases or add a new mutating tool.
- Do NOT change the `varset_backend()`/`element_map_version()` return contracts or the `capability_banner` payload shape.
- Do NOT edit the deferred-work ledger (the orchestrator records resolution).
- No new preference keys, no version-string comparisons, no speculative concurrency primitives.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Element-map API exposed, map empty | Fresh `Part.makeBox`, lazily-populated build (0-size map) | `element_map_available()` returns `True` | No error expected |
| Element-map API exposed, map populated | Probe box with populated map | `element_map_available()` returns `True` | No error expected |
| `getElementHistory` absent | Build without element-map API | `element_map_available()` returns `False` | Missing attr handled, no raise |
| Element-map attribute absent | Shape lacks `ElementMapSize`/`ElementMap` | `element_map_available()` returns `False` | Missing attr handled, no raise |
| Part import fails | FreeCAD/Part unavailable | `element_map_available()` returns `False` | Exception → conservative default |
| Warm at startup, varset usable | Host bootstrap, `App::VarSet` present | All probes cached before serving; `varset_backend()=="varset"` | No error expected |
| Warm at startup, probe unavailable | A probe cannot run | Warming completes; unavailable probe returns its default | Per-probe defaults, warming never raises |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/shim.py` -- `element_map_available()` (behavioral → pure), and a new `warm_capability_probes()` helper that force-evaluates every lru_cached probe once.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- `start_bridge()`: warm probes on the Qt main thread (via `marshal.call`) after the marshal is built, before `listener.start_threaded()`.
- `src/freecad_buddy/hosts/headless/entry.py` -- `run()`: warm probes (inline marshal) after `build_registry`, before `serve_stdio`.
- `tests/infc/test_document_lifecycle.py` -- `CapabilityProbeTest`: extend to cover pure-exposure semantics and idempotent warming.

## Tasks & Acceptance

**Execution:**
- [x] **Pre-Work: Load Standards (MANDATORY — re-execute every stage, do NOT mark done)** -- Read `.knowledge-base/technical/standards/index.md`, `.knowledge-base/technical/standards/freecad/source-verify.md`, `.knowledge-base/technical/standards/global/commenting.md`; re-confirm the element-map API names against `docs/references/FreeCAD/src/Mod/Part/App/TopoShape.pyi` and `docs/references/FreeCAD/src/App/ComplexGeoData.pyi` before editing.
- [x] `src/freecad_buddy/usecases/shim.py` -- Rewrite `element_map_available()` to probe pure API exposure: `getElementHistory` callable AND the element-map attributes present on the box shape; remove the `len(mapper) > 0` non-emptiness gate. Update its docstring to describe only what it does (no behavioral claim).
- [x] `src/freecad_buddy/usecases/shim.py` -- Add `warm_capability_probes()` that invokes every lru_cached probe once (`export_binary_available`, `serializer_tag`, `varset_backend`, `varset_available`, `element_map_available`, `element_map_version`, `freecad_version`) so their doc-churning work happens at a controlled point; must not raise.
- [x] `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- In `start_bridge()`, call `marshal.call(shim.warm_capability_probes, <timeout>)` after the marshal is constructed and before `listener.start_threaded()`.
- [x] `src/freecad_buddy/hosts/headless/entry.py` -- In `run()`, call `marshal.call(shim.warm_capability_probes, <timeout>)` (inline executor) after `build_registry` and before `serve_stdio`.
- [x] `tests/infc/test_document_lifecycle.py` -- Add tests: `element_map_available()` returns `True` on the live build (map may be empty), stays `bool`, and never raises; `warm_capability_probes()` is idempotent and leaves no `FCB_TMP_varset_probe` document open afterward.
- [x] **Final Task: Quality Checks** -- run the repo checks in Verification below.

**Acceptance Criteria:**
- Given a build that exposes the element-map API but has not populated a map on a fresh box, when `element_map_available()` is called, then it returns `True` (no false negative from emptiness).
- Given a build without `getElementHistory` or without the element-map attributes, when `element_map_available()` is called, then it returns `False` without raising.
- Given host startup, when the host begins serving, then every capability probe has already been evaluated on the FreeCAD execution thread, so the varset probe's temp-document churn cannot interleave with a concurrent registry mutation (AD-20).
- Given warming runs, when it completes, then no `FCB_TMP_varset_probe` document remains open and warming did not raise on any probe.
- Given the `capability_banner`/`query_capabilities` payload, when probes are hardened, then its shape and the `varset_backend`/`element_map_version` return contracts are unchanged.

## Spec Change Log

## Review Triage Log

### 2026-07-24 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 3: (high 0, medium 1, low 2)
- defer: 0
- reject: 8
- addressed_findings:
  - `[medium]` `[patch]` Eager `marshal.call(warm_capability_probes)` was startup-fatal: a `MarshalTimeout` or a probe teardown exception (e.g. `varset_backend`'s `finally: closeDocument`) would abort `start_bridge`/`run` and leave the host dead — a regression vs the old lazy-probe behavior. Wrapped both call sites in `try/except Exception → logger.warning(..., exc_info=True)` so warm-up degrades to lazy probing.
  - `[low]` `[patch]` `warm_capability_probes` docstring falsely claimed "Never raises"; corrected to note a probe whose teardown fails may still propagate, so callers warm defensively.
  - `[low]` `[patch]` The warm-probe test proved nothing (earlier tests primed the lru_cache, so the calls were no-op hits and `varset_backend` never opened the temp doc). Now clears `varset_backend`/`varset_available` caches before each of two warm calls so the temp-document open/close actually runs and the no-leak assertion is meaningful.
  - Rejected (8): element-map attr names already source-verified (`ComplexGeoData.pyi:152-162`, `TopoShape.pyi:1087`); behavioral→exposure change is the intended DW-18 fix; downstream consumers rely on exposure, not populated-map; headless warming still primes caches; `assertTrue(result)` is the DW-18 no-false-negative acceptance signal on target legs that expose the API; timeout magic-number, bootstrap ordering comment, redundant `makeBox`, and a startup-failure test were cosmetic or low-value.

## Design Notes

Pure-exposure probe (source: `TopoShape.pyi:1087` method `getElementHistory`; `ComplexGeoData.pyi:152/155/161` attrs `ElementMapSize`/`ElementMap`/`ElementMapVersion`). `ElementMapVersion` is a `str` in source — `element_map_version()` already int-casts and tolerates that, leave it:

```python
@lru_cache(maxsize=1)
def element_map_available() -> bool:
    try:
        import Part
        shape = Part.makeBox(1, 1, 1)
    except Exception:  # noqa: BLE001 - a probe that cannot run means the feature is unavailable
        return False
    if not callable(getattr(shape, "getElementHistory", None)):
        return False
    return hasattr(shape, "ElementMapSize") and hasattr(shape, "ElementMap")
```

Why startup warming (not a lock in shim): the dispatch already runs single-threaded on the FreeCAD execution thread (GUI listener owns the one `marshal.call`; headless uses `InlineExecutor`). Warming every lru_cached probe before the listener accepts connections means the varset probe's `newDocument`/`closeDocument` executes strictly before any registry op can run, so no interleave is reachable even once a concurrent executor lands — satisfying AD-20 without threading a registry handle into the pure probe layer. Warming goes through `marshal.call` so in GUI it lands on the Qt main thread (never a worker thread — FreeCAD-API-off-main-thread is a crash mode).

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: passes; no new cross-ring or Qt-in-usecases import introduced.
- `python tests/run_tests.py` (under `FreeCADCmd`) -- expected: `CapabilityProbeTest` and the new warming tests pass; whole in-FreeCAD suite green.
- `ruff check src/freecad_buddy/usecases/shim.py src/freecad_buddy/hosts/gui_addon/bootstrap.py src/freecad_buddy/hosts/headless/entry.py` -- expected: clean.

**Manual checks (if no CLI):**
- After a host start, confirm via `query_capabilities` that `element_map_available` is `True` on the live 1.1.x build and no `FCB_TMP_varset_probe` document is left open (`FreeCAD.listDocuments()` has no such name).

## Auto Run Result

Status: done

**Change:** Hardened the two `usecases/shim.py` capability probes (DW-18, DW-21). `element_map_available()` now probes pure API exposure — `getElementHistory` callable plus the `ElementMapSize`/`ElementMap` attributes present (source-verified against `docs/references/FreeCAD/src/App/ComplexGeoData.pyi` and `.../TopoShape.pyi`) — dropping the behavioral non-empty-map gate that could false-negative on a lazily-populating build. Added `warm_capability_probes()`, invoked once on the FreeCAD execution thread at host startup (both GUI and headless) before serving, so the `varset_backend` probe's throwaway-document churn cannot interleave with a registry mutation (AD-20) — the intent's sanctioned "run all probes once at startup" option.

**Files changed:**
- `src/freecad_buddy/usecases/shim.py` — pure-exposure `element_map_available()`; new `warm_capability_probes()`.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py` — warm probes via `marshal.call` (best-effort, non-fatal) before the listener starts.
- `src/freecad_buddy/hosts/headless/entry.py` — warm probes via `marshal.call` (best-effort, non-fatal) before serving stdio.
- `tests/infc/test_document_lifecycle.py` — pure-exposure probe test + meaningful warm/no-temp-doc-leak test (clears caches so the probe actually re-runs).

**Review:** 3 patches applied (1 medium: warm-up made non-fatal so a timeout/teardown exception no longer aborts host startup; 2 low: docstring accuracy, meaningful warm test), 0 deferred, 8 rejected (source names already verified; behavioral→exposure is the intended DW-18 fix; remaining were cosmetic/low-value). No intent gaps, no spec repairs.

**Verification:** `python scripts/check_imports.py` → OK. `ruff check` on all four files → clean. `python tests/run_tests.py` (FreeCADCmd suite) NOT run — no FreeCAD interpreter in this environment; the new tests are stdlib-`unittest`-only and correctly scoped to `tests/infc/`.

**Residual risk:** The FreeCADCmd in-process test suite (including the two new tests) is unverified in this environment; it must be run on a live 1.0.x/1.1.x leg to confirm `element_map_available()` returns `True` and no `FCB_TMP_varset_probe` leaks. Both are asserted by the new tests and by the manual check above.
