---
title: 'DW-60: make build_broken_docs import side-effect-free via explicit opt-in'
type: 'bugfix'
created: '2026-07-30'
status: 'done'
baseline_revision: '0f94b795d748cf8812d8c63c6703d99899ebce29'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-automation-verification.md'
warnings: []
---

<intent-contract>

## Intent

**Problem:** `benchmarks/g1/dev/broken-docs/build_broken_docs.py` decides whether to run `build_all()` by comparing `sys.argv[1]` against `__file__` (`_is_top_level_script`), a workaround for FreeCADCmd setting `__name__` to the file stem instead of `"__main__"`. Any harness that imports the module for `gen.CASES` while `argv[1]` happens to be the generator's own path would silently rebuild and overwrite all 30 committed fixtures.

**Approach:** Replace the argv heuristic with an explicit opt-in an importer cannot trip: build only when the environment flag `FREECAD_BUDDY_BUILD_BROKEN_DOCS=1` is set. Import is then always side-effect-free regardless of `argv`/`__name__`, while the documented FreeCADCmd build invocation still works. Add an in-FreeCAD test proving import writes nothing.

## Boundaries & Constraints

**Always:**
- Import of the module must never write, create, or mutate any file, for any `sys.argv` and any `__name__`.
- The 30 committed `fixture.FCStd` files and their `case.yaml` files stay byte-identical — this change regenerates nothing.
- Module stays stdlib + FreeCAD App only (`benchmarks/` is outside the `src/` rings but follows the same no-third-party rule for in-FreeCAD code).
- Update the module docstring and `benchmarks/g1/README.md` generator invocation so the documented command matches the new opt-in.
- `tests/infc/` tests use stdlib `unittest` only, run under `FreeCADCmd tests/run_tests.py`.

**Block If:**
- Regenerating fixtures would be needed to make any test pass (would change committed binary fixtures — not in scope).
- FreeCAD is unavailable locally so the infc suite cannot be run at all; report the unverified command rather than claiming success.

**Never:**
- Do not touch `tests/run_tests.py`'s own `_is_top_level_script` (different file, different concern, out of scope for DW-60).
- Do not regenerate or re-save any fixture.
- Do not change `CASES`, the break-kind builders, `_save`, or `build_all`'s signature.
- Do not add a CLI-argument parser, config file, or any abstraction beyond the single flag check.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Intended build | `FREECAD_BUDDY_BUILD_BROKEN_DOCS=1` set, run under `FreeCADCmd build_broken_docs.py` | `build_all()` runs, 30 fixtures written, one `wrote <path>` line each | `_save` still raises `RuntimeError` if an object is not in error |
| Import for `CASES` (self-check) | Module imported by `tests/infc/test_broken_docs_g1.py`, flag unset, `argv[1]` = `tests/run_tests.py` | No build, no file written; `gen.CASES` available | No error expected |
| Import with generator path as `argv[1]` (DW-60 case) | Module imported while `sys.argv[1]` is the generator's own path, flag unset | No build, no file written | No error expected |
| Flag set to a non-enabling value | `FREECAD_BUDDY_BUILD_BROKEN_DOCS` unset, empty, or `0` | No build | No error expected |

</intent-contract>

## Code Map

- `benchmarks/g1/dev/broken-docs/build_broken_docs.py` -- the generator; `_is_top_level_script` (lines 146-159) is the argv heuristic to replace; module-level `if _is_top_level_script(): for path in build_all(): print(...)` at lines 159-161 is the side-effect site.
- `tests/infc/test_broken_docs_g1.py` -- existing in-FreeCAD self-check; does `sys.path.insert(0, BROKEN_DIR)` then `import build_broken_docs as gen` for `gen.CASES`. Must stay green; new import-safety test goes here.
- `tests/run_tests.py` -- the FreeCADCmd runner that discovers `tests/infc/`; has its own copy of the argv heuristic (out of scope).
- `benchmarks/g1/README.md` (line ~21) -- documents `build_broken_docs.py` as the deterministic generator; update if it states the invocation.
- `benchmarks/g1/actor_run.py` -- reads the committed fixtures (`BROKEN_DOCS = HERE / "dev" / "broken-docs"`); does not import the generator. No change.

## Tasks & Acceptance

**Execution:**
- [x] `benchmarks/g1/dev/broken-docs/build_broken_docs.py` -- replace `_is_top_level_script()` with a `_build_requested()` helper reading `os.environ.get("FREECAD_BUDDY_BUILD_BROKEN_DOCS")` and returning True only for an enabling value (`"1"`); guard the module-level build with it; drop the now-unused `sys` import if nothing else uses it -- an importer cannot set the flag by accident, so import is side-effect-free by construction.
- [x] `benchmarks/g1/dev/broken-docs/build_broken_docs.py` -- update the module docstring's run line to the flag-prefixed invocation (`FREECAD_BUDDY_BUILD_BROKEN_DOCS=1 FreeCADCmd build_broken_docs.py`) -- the documented command must be the one that works.
- [x] `tests/infc/test_broken_docs_g1.py` -- add a test that re-imports the generator module fresh with `sys.argv` spoofed to `[<generator path>, <generator path>]` and the flag absent from `os.environ`, and asserts every `fixture.FCStd` mtime + size is unchanged and `_build_requested()` is False; restore `sys.argv`/`os.environ`/`sys.modules` in a `finally` -- covers the DW-60 edge case and the flag-off matrix rows.
- [x] `benchmarks/g1/README.md` -- state the generator's opt-in invocation so a reader does not reach for the bare `FreeCADCmd` command -- keeps docs consistent with the guard.

**Acceptance Criteria:**
- Given the 30 committed fixtures on disk, when the whole infc suite runs via `FreeCADCmd tests/run_tests.py`, then it passes and `git status --porcelain benchmarks/g1/dev/broken-docs` reports no modified fixture.
- Given `FREECAD_BUDDY_BUILD_BROKEN_DOCS` is unset, when the module is imported by any harness under any `sys.argv`, then no filesystem write occurs and `CASES` is importable.
- Given the flag is set to `1`, when the module is executed under FreeCADCmd, then `build_all()` runs (build path preserved).

## Spec Change Log

## Review Triage Log

### 2026-07-30 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 7: (high 1, medium 5, low 1)
- defer: 1: (high 0, medium 1, low 0)
- reject: 6: (high 0, medium 2, low 4)
- addressed_findings:
  - `[high]` `[patch]` `os.environ.clear()` + `update()` in the test's `finally` rebuilt the whole process environment mid-suite (all infc modules share one FreeCADCmd process), risking loss of vars FreeCAD/OCC set after the snapshot — replaced with `addCleanup` restoring only `_BUILD_FLAG` and `sys.argv`.
  - `[medium]` `[patch]` `assertEqual(before, after)` over an `rglob` result passed vacuously (`{} == {}`) if no fixture was on disk — added `assertEqual(len(fixtures), EXPECTED_COUNT)` before snapshotting.
  - `[medium]` `[patch]` mtime+size was a weak witness for "nothing written" (a deterministic `saveAs` is the same-size case) — switched to `hashlib.sha256` over the bytes; a falsification probe confirms the stat witness misses a same-size same-mtime rewrite the hash catches.
  - `[medium]` `[patch]` nothing asserted the positive path, so a typo in the flag name or comparison would make the documented build a silent permanent no-op — added `test_build_flag_enables_only_on_the_documented_value` covering `"1"`/`"0"`/`""`/`"true"`/unset through the module's own `_BUILD_FLAG`.
  - `[medium]` `[patch]` an enabling flag already exported in the ambient environment would let any in-process import rewrite the fixtures — added `test_build_flag_is_not_set_while_the_suite_runs`.
  - `[medium]` `[patch]` the test mutated process-global `sys.modules` and left the module-level `gen` alias bound to a stale object — now loads an isolated module via `importlib.util.spec_from_file_location` + `exec_module` under a throwaway name, touching no global state.
  - `[low]` `[patch]` docstring/README documented only POSIX `VAR=1 cmd`, a parse error in the repo's primary PowerShell shell — both forms now documented, and the README cites the asserting test.
- deferred (not written to the ledger — this run was invoked with "do NOT edit the deferred-work ledger"; the orchestrator records it):
  - source_spec: `spec-dw-60-broken-docs-import-guard.md`
    summary: `benchmarks/g0/export-fault-injection/build_export_fault_fixtures.py` still carries the identical argv-based rebuild-on-import hazard DW-60 was filed for, so the defect class is closed in only one of two generators.
    evidence: `_is_top_level_script` at lines 549-562 matches `Path(sys.argv[1]).resolve()` against `__file__`, and line 564 runs `build_all()` at module level, overwriting committed export fixtures. Verified present at review time; pre-existing and outside DW-60's stated scope (the intent names only the G1 broken-doc generator). Same one-line env-flag opt-in applies.

## Design Notes

Env flag over a self-defined CLI argument: FreeCADCmd passes its own argv through to the script, so an argument-based opt-in would still be argv-coupled — exactly the class of accident DW-60 records. An environment variable is set only by a deliberate invocation and is invisible to `import`.

```python
_BUILD_FLAG = "FREECAD_BUDDY_BUILD_BROKEN_DOCS"


def _build_requested() -> bool:
    """Whether an explicit opt-in asked for a fixture rebuild (import never does)."""
    return os.environ.get(_BUILD_FLAG) == "1"


if _build_requested():
    for path in build_all():
        print(f"wrote {path}")
```

The import-safety test must force a real re-import (the module is already in `sys.modules` from the module-level import at the top of the test file), so it pops the module name from `sys.modules` before re-importing and restores it afterwards.

## Verification

**Commands:**
- `FreeCADCmd tests/run_tests.py` -- expected: whole infc suite passes, including the existing broken-doc self-check and the new import-safety tests. **Actual (FreeCAD 1.1.0, micromamba env `fcb`, Python 3.11.15):** `Ran 137 tests in 9.524s` / `OK (skipped=1)`, exit 0; all three new tests `ok`.
- `git status --porcelain benchmarks/g1/dev/broken-docs` -- expected: no `fixture.FCStd` listed as modified. **Actual:** only `M build_broken_docs.py`; zero fixtures modified.
- `uv run ruff check benchmarks/g1/dev/broken-docs/build_broken_docs.py tests/infc/test_broken_docs_g1.py` -- expected: clean. **Actual:** `All checks passed!`
- `uv run ruff format --check benchmarks/g1/dev/broken-docs/build_broken_docs.py tests/infc/test_broken_docs_g1.py` -- expected: clean. **Actual:** `2 files already formatted`.
- `uv run ruff check .` -- **Actual:** `Found 10 errors.` — identical count on clean `HEAD` (verified by stashing), so pre-existing and unrelated to this change.

**Manual checks (if no CLI):**
- Direct probe under FreeCADCmd: importing the generator with `sys.argv = [<generator path>, <generator path>]` and the flag unset left all 30 fixtures unchanged and `_build_requested()` False; the flag enables only on `"1"` (`"0"`, `""`, `"true"`, `"TRUE"`, `" 1 "` all False).
- Build path preserved: `build_all(tmpdir)` under FreeCADCmd wrote 30 fixtures into a temp directory with the committed fixtures untouched.
- Falsification probe: a same-size, same-mtime byte rewrite is invisible to an mtime+size witness but caught by the sha256 witness the test now uses.

## Auto Run Result

Status: done

**Implemented change:** the G1 broken-doc fixture generator no longer infers "am I the launched script" from `sys.argv[1]`. It builds only when `FREECAD_BUDDY_BUILD_BROKEN_DOCS=1` is in the environment, so importing the module for `gen.CASES` is side-effect-free under any `argv` and any `__name__` — closing DW-60's rebuild-on-import hole by construction rather than by luck.

**Files changed:**
- `benchmarks/g1/dev/broken-docs/build_broken_docs.py` — `_is_top_level_script()` (argv/`__file__` match) replaced by `_build_requested()` reading `_BUILD_FLAG`; `import sys` dropped for `import os`; docstring documents the POSIX and PowerShell invocations.
- `tests/infc/test_broken_docs_g1.py` — three new tests: import-with-generator-path-as-`argv[1]` writes nothing (sha256 witness over all 30 fixtures, count-guarded, isolated module load, `addCleanup` restore of only `sys.argv` + the flag); flag enables only on `"1"`; flag is not ambiently set while the suite runs.
- `benchmarks/g1/README.md` — generator line states the opt-in invocation (both shells) and cites the asserting test.

**Review findings:** 7 patches applied (1 high, 5 medium, 1 low), 1 deferred (medium), 6 rejected. Rejected as noise or scope creep: flag-value normalization (`true`/`yes`/whitespace — strict `"1"` is the deliberate documented contract); emitting a stderr note when the old flagless command is run (contradicts the spec's minimum-code boundary; docstring + README carry the invocation); ledger and spec-status findings (orchestrator-owned); README test-citation nit (folded into a patch anyway); unifying the three top-level-guard conventions across `benchmarks/g0/` generators.

**Residual risks:**
- The identical argv-based hazard survives in `benchmarks/g0/export-fault-injection/build_export_fault_fixtures.py:564` — deferred above, outside DW-60's stated scope.
- The infc suite was run on FreeCAD 1.1.0 only; the 1.0.x blocking leg is unverified locally and will be exercised in CI. Nothing in the change is version-sensitive (stdlib `os.environ` + `importlib`).
- `_build_requested()` accepts only the literal `"1"`, so a mis-set flag (`true`, trailing space) is a silent no-op rather than a loud error. Deliberate: the value is asserted in-suite and both documented invocations use `1`.
