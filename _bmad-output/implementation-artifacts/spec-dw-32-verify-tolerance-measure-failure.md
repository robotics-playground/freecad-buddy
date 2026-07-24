---
title: 'Distinguish a genuine measurement failure from a real result in verify.py watertight/tolerance-floor (DW-32)'
type: 'bugfix'
created: '2026-07-24'
status: 'done'
baseline_revision: 'c7236322b319fa5593f963b54e19e50cb2587e8c'
final_revision: 'e7c092265550bb55e2ec71ff400dcbe9557005a1'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** In `usecases/verify.py`, `_is_watertight` (l163-166) and `_shape_floor` (l264-266) swallow *every* exception into a false "not watertight" / floor `0.0`. A solid whose `getTolerance()`/`isClosed()` genuinely raises (an OCC measurement failure on a non-null shape) silently disables the B-rep tolerance-floor clamp, so a `verify_shape` comparison could assert tighter than the shape's own tolerance — the exact thing the floor exists to prevent (verification-design.md l339).

**Approach:** Split "cannot measure" from a real negative result. When `getTolerance(1)`/`isClosed()` *raise*, surface it as a `ValidationError` (the dispatch boundary maps that to `INVALID_INPUT`) instead of returning a false `0.0` / `not watertight`. The legitimate "this shape type has no `getTolerance`/`isClosed` attribute" path (getter is `None`) is NOT a failure and keeps its current benign default.

## Boundaries & Constraints

**Always:**
- A raised `getTolerance(1)` or `isClosed()` (non-null shape that genuinely cannot be measured) surfaces as `ValidationError` → `INVALID_INPUT`, never a silent `0.0` floor or false "not watertight".
- The attribute-absent path stays benign: `getattr(shape, "getTolerance", None) is None` → floor `0.0` (a shape with no tolerance concept, not a failure). `_is_watertight`'s solid-count gate (`len(shape.Solids) != 1`) stays a real `False`, not an error.
- `verify.py` stays stdlib + FreeCAD-App only (usecases ring, AD-1/AD-12). No new imports beyond the existing `ValidationError` already imported from `usecases.documents`.
- `verify_shape` still never recomputes and never grades itself; the change only alters how an unmeasurable shape is reported.

**Block If:**
- The FreeCAD source shows `getTolerance(1)`/`isClosed()` on a *valid non-null* shape can raise for a routine, expected reason (making `INVALID_INPUT` wrong for a normal shape) — HALT `blocked`, the swallow may be load-bearing.

**Never:**
- Do not catch-and-default the *raise* case back to `0.0` / `False` anywhere on the measurement path.
- Do not change the tolerance-floor clamp math in `_tol_close`, the assertion vocabulary, or any verdict-derivation logic.
- Do not add try/except around `shape.Solids`, `shape.Volume`, `shape.isValid()`, or other already-unguarded measurements (out of scope; not part of DW-32).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal solid | 1 closed solid, measurable tolerance | floor = real `getTolerance(1)`; watertight = `True` | none |
| No tolerance attr | shape without `getTolerance` | floor `0.0` | none (benign default) |
| No isClosed attr | shape without `isClosed`, but 1 solid | AttributeError path removed — attr-absent yields `False` watertight only via solid-count gate; missing `isClosed` on a 1-solid shape surfaces as `ValidationError` | INVALID_INPUT |
| Multi/zero solids | `len(shape.Solids) != 1` | watertight = `False` (real result) | none |
| `getTolerance(1)` raises | non-null shape, OCC failure | `ValidationError` | INVALID_INPUT |
| `isClosed()` raises | 1-solid non-null shape, OCC failure | `ValidationError` | INVALID_INPUT |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/verify.py` -- `_is_watertight` (l159-166, the `isClosed()` swallow), `_shape_floor` (l258-266, the `getTolerance(1)` swallow), `ValidationError` already imported (l17), used by `verify_shape` (l280) and `_measured_facts` (l269-277).
- `src/freecad_buddy/adapters/rpc_dispatch.py` -- maps `ValidationError` → `INVALID_INPUT` envelope (l97-98); the boundary this fix relies on.
- `docs/references/FreeCAD/src/Mod/Part/App/TopoShapePyImp.cpp` -- `isClosed` (l1585, raises `RuntimeError` on failure), `getTolerance` (l2155, raises `Part.OCCError`/`Standard_Failure` on OCC failure; `mode` arg is `i|O!`).
- `tests/infc/test_verify_tools.py` -- in-FreeCAD `unittest` verify-core tests; `VerifyShapeTest`, `_verify_dispatch` helper (l264) already exercises the `INVALID_INPUT` boundary.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/verify.py` -- In `_shape_floor`: keep the `getter is None → 0.0` benign default, but replace the `try/except → 0.0` around `float(getter(1))` so a raise re-raises as `ValidationError` (e.g. `raise ValidationError(f"cannot measure shape tolerance: {exc}") from exc`). In `_is_watertight`: keep the `len(shape.Solids) != 1 → False` gate, but remove the `except → False` so an `isClosed()` raise propagates as `ValidationError`; call `isClosed` via `getattr` so an absent method also raises `ValidationError` rather than `AttributeError`. -- Distinguishes "cannot measure" from a real negative; a solid that genuinely can't be measured surfaces INVALID_INPUT instead of silently voiding the floor clamp.
- [x] `tests/infc/test_verify_tools.py` -- Add tests to `VerifyShapeTest` covering the I/O matrix rows: a stub/fake shape whose `getTolerance` raises yields `INVALID_INPUT` via `_verify_dispatch`; a fake shape whose `isClosed` raises yields `INVALID_INPUT`; a real box still passes (floor real, watertight True) and the checkless `_measured_facts` path still reports watertight True. Use a lightweight fake `Shape` (duck-typed object) injected via a `Part::Feature` whose `.Shape` is monkeypatched, or drive `_shape_floor`/`_is_watertight` directly with a fake exposing `Solids`, `getTolerance`, `isClosed`. -- Locks the swallow-vs-raise distinction against regression.

**Acceptance Criteria:**
- Given a shape whose `getTolerance(1)` raises, when `verify_shape` runs through dispatch, then the envelope status is `INVALID_INPUT` (not a report with a silently-zeroed floor).
- Given a 1-solid shape whose `isClosed()` raises, when `expect_watertight` is checked (or the checkless facts path runs), then the envelope status is `INVALID_INPUT` (not a `watertight=False` report).
- Given a shape with no `getTolerance` attribute, when `_shape_floor` runs, then it returns `0.0` and no error is raised.
- Given a normal box, when `verify_shape` runs with the golden watertight/volume/bbox checks, then the verdict is `OK` — unchanged from before (no regression in `tests/infc/test_verify_tools.py`).

## Design Notes

The two swallows differ in what "failure" means, so the fix is asymmetric:

- `_shape_floor`: `getter is None` is a *legitimate* absence (some shape types have no tolerance) → keep `0.0`. Only the `getter(1)` *call raising* is the failure → re-raise as `ValidationError`.
- `_is_watertight`: `len(Solids) != 1` is a *real* answer (`False`), not a failure. The `isClosed()` call raising is the failure → let it propagate as `ValidationError`.

Per FreeCAD source (TopoShapePyImp.cpp): `isClosed()` raises `RuntimeError("check failed, shape may be empty")` and `getTolerance` raises `Part.OCCError` on `Standard_Failure`. `_require_shape` (l113) already rejects a null `Shape` upstream, so what reaches these helpers is a non-null shape that genuinely can't be measured — precisely the DW-32 case that must not be swallowed.

Sketch of the intended shape:

```python
def _shape_floor(shape: object) -> float:
    getter = getattr(shape, "getTolerance", None)
    if getter is None:
        return 0.0
    try:
        return float(getter(1))
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"cannot measure shape tolerance: {exc}") from exc

def _is_watertight(shape: object) -> bool:
    if len(shape.Solids) != 1:
        return False
    is_closed = getattr(shape, "isClosed", None)
    if is_closed is None:
        raise ValidationError("shape does not support closure measurement")
    try:
        return bool(is_closed())
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"cannot measure shape closure: {exc}") from exc
```

## Verification

**Commands:**
- `python -c "import ast; ast.parse(open('src/freecad_buddy/usecases/verify.py').read())"` -- expected: parses clean (syntax check without FreeCAD).
- `python scripts/check_imports.py` -- expected: clean (no ring violation; no new imports).
- `ruff check src/freecad_buddy/usecases/verify.py tests/infc/test_verify_tools.py` -- expected: clean.
- `FreeCADCmd tests/run_tests.py` (in-FreeCAD runner) -- expected: `test_verify_tools.py` green, including the new raise→INVALID_INPUT cases and the unchanged golden-pass.

**Manual checks (if no CLI):**
- `grep -nE "except Exception.*return (False|0\.0)" src/freecad_buddy/usecases/verify.py` on the measurement path returns nothing (no swallow-to-default left on `getTolerance`/`isClosed`).

## Spec Change Log

_No spec amendments — all review findings were resolved as in-diff patches._

## Review Triage Log

### 2026-07-24 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 4: (high 0, medium 1, low 3)
- defer: 0
- reject: 4
- addressed_findings:
  - `[medium]` `[patch]` `_shape_floor` was computed on the checkless (`_measured_facts`) path where the floor is never consumed, so a raising `getTolerance(1)` aborted a report that never used it — moved `floor = _shape_floor(shape)` after the checkless early-return so it runs only for the per-check builders; retargeted the through-dispatch getTolerance-raise test to a `checks` call so it still exercises the floor path.
  - `[low]` `[patch]` Dead `except ValidationError: raise` clause in `_is_watertight` (a real `isClosed()` bound method raises `RuntimeError`, never `ValidationError`; the absent-attribute `ValidationError` is raised outside the `try`) — removed the unreachable clause.
  - `[low]` `[patch]` The absent-`isClosed` branch (`is None → ValidationError`) had no test coverage — added `test_absent_isclosed_raises_validation_error`.
  - `[low]` `[patch]` No test asserted the DW-32 mechanism itself (a non-zero floor still clamps a comparison, not just the error branch) — added `test_shape_floor_clamps_comparison_to_tolerance_floor` on `_tol_close`.
  - Rejected (intent-fixed, spec-forbidden, or cosmetic): mapping the OCC measurement fault to `RECOMPUTE_ERROR` instead of `INVALID_INPUT` (the intent-contract and the DW-32 ledger both mandate `INVALID_INPUT`; the no-traceback logging concern is DW-56's scope, not this change); guarding `shape.Solids`/`Volume`/`isValid` against raises (spec **Never** clause explicitly puts this out of DW-32 scope); raw OCC message text in the client `detail.message` (matches the file's existing `ValidationError` message convention); helper-class placement / docstring-emphasis / `Solids` identity style nits.

## Auto Run Result

Status: done

**Summary:** Stopped `usecases/verify.py`'s `_is_watertight` and `_shape_floor` from swallowing every exception into a false "not watertight"/floor `0.0` (DW-32). A non-null shape whose `getTolerance(1)`/`isClosed()` genuinely raises (an OCC measurement failure) now surfaces as `ValidationError` → `INVALID_INPUT` instead of silently disabling the B-rep tolerance-floor clamp (which would let a comparison assert tighter than the shape's own tolerance). The legitimate attribute-absent path (`getTolerance`/`isClosed` not present) stays benign, and `_is_watertight`'s `len(Solids) != 1 → False` gate stays a real result. `_shape_floor` is now computed only on the per-check path so a checkless facts call is never aborted by a floor value it does not consume.

**Files changed:**
- `src/freecad_buddy/usecases/verify.py` — `_is_watertight`: `getattr` `isClosed`, raise `ValidationError` when absent or when the call raises; kept the solid-count gate. `_shape_floor`: kept `getter is None → 0.0`, re-raise `ValidationError` when `getTolerance(1)` raises. `verify_shape`: moved `floor = _shape_floor(shape)` after the checkless early-return.
- `tests/infc/test_verify_tools.py` — 7 new `VerifyShapeTest` tests + `_FakeShape`/`_patched_require_shape` helpers: benign missing-tolerance-attr → 0.0, `getTolerance` raise → `ValidationError` (direct + `INVALID_INPUT` via dispatch), `isClosed` raise → `ValidationError` (direct + `INVALID_INPUT` via dispatch), absent-`isClosed` → `ValidationError`, multi-solid short-circuits to real `False`, and a `_tol_close` clamp-engaged assertion locking the floor mechanism.

**Review findings:** 4 patches applied (1 medium: over-eager floor computation on the checkless path + test retarget; 3 low: dead-clause removal, absent-`isClosed` coverage, clamp-mechanism coverage). 0 intent_gap, 0 bad_spec, 0 deferred, 4 rejected (RECOMPUTE_ERROR remap contradicts the intent/ledger-mandated `INVALID_INPUT`; guarding other measurements is spec-Never; raw-OCC-message and style nits cosmetic).

**Verification performed:**
- `python -c ast.parse` on both files: clean.
- `python scripts/check_imports.py`: `check_imports OK` (no ring violation, no new imports).
- `ruff check` both files: `All checks passed!`.
- `FreeCADCmd tests/run_tests.py` (FreeCAD 1.1, `PYTHONUTF8=1`): **106 tests OK (skipped=1)** — the authoritative in-FreeCAD leg, all new DW-32 tests green.

**Residual risk:** The OCC measurement fault is reported as `INVALID_INPUT` per the frozen intent; the reviewer's observation that `INVALID_INPUT` is logged without a traceback (so the OCC diagnostic isn't retained server-side) is a real but separate concern tracked under DW-56 (INVALID_INPUT traceback handling), not resolvable within this DW-32 scope without contradicting the intent-contract.
