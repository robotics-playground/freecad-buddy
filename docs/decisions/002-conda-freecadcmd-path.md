# 002 — In-FreeCAD Tests Driven via FreeCADCmd

## Decision

All in-FreeCAD tests run through `FreeCADCmd tests/run_tests.py`, never through a foreign
interpreter doing `python -c "import FreeCAD"`. Driving via the FreeCAD-bundled interpreter
sidesteps the conda PYTHONPATH edge case (conda-forge feedstock issue #21) where a foreign
python cannot reliably import the FreeCAD modules. `tests/run_tests.py` discovers the
stdlib-`unittest` suites under `tests/infc/` and runs them in a single process.

## Drives

- CI headless legs (`ci.yml` `headless` matrix): both legs invoke `FreeCADCmd tests/run_tests.py`.
- `tests/run_tests.py` design (one process, stdlib unittest, no third-party imports).
- `canary.yml` uses the same entry point.

## Runtime-confirm

- Per-leg bundled interpreter version: **3.11** on the 1.0.0 build? **3.12** on the 1.1.0 build?
- Verified on the actual conda builds during the CI headless legs (print `sys.version` from within `FreeCADCmd`).
- Confirm `FreeCADCmd tests/run_tests.py` exits 0 on an empty `tests/infc/` discovery on both legs.
