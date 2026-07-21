# 004 — Driving-Dimension Facade: VarSet with Spreadsheet Fallback

## Decision

The driving-dimension facade prefers `App::VarSet` for storing named parametric dimensions,
falling back to a `Spreadsheet::Sheet` when VarSet is not usable via Python. The choice is
gated behind `usecases/shim.varset_available()`. Spreadsheet is the safe default until VarSet
external (Python) exposure is confirmed on FreeCAD 1.1 (tracked upstream as issue #12531).

## Drives

- Parametric editability facade (story 4.6).

## Runtime-confirm

- Is `App::VarSet` creatable and its properties settable via Python on the **1.1.0** build (issue #12531)?
- To be confirmed on the CI headless 1.1.0 leg via `shim.varset_available()`.
- If unusable, the Spreadsheet fallback remains authoritative and the facade never emits VarSet objects.
