---
title: 'DW-60: make build_broken_docs import side-effect-free via explicit opt-in'
type: 'bugfix'
created: '2026-07-30'
status: 'done'
baseline_revision: '0f94b795d748cf8812d8c63c6703d99899ebce29'
final_revision: '8a53b94'
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

### 2026-07-30 — Review pass (follow-up)
- intent_gap: 0
- bad_spec: 0
- patch: 6: (high 0, medium 3, low 3)
- defer: 1: (high 0, medium 1, low 0)
- reject: 8: (high 0, medium 3, low 5)
- addressed_findings:
  - `[medium]` `[patch]` the import-safety test spoofed `sys.argv` and was named for an argv barrier, but the generator no longer reads `sys.argv` or `__name__` at all (verified: `grep` for both returns nothing) — so the argv half of the test could not fail and nothing covered the non-enabling *values*. Retitled to the behavior actually guarded and widened to re-import under `None`/`"0"`/`""`, each with a full sha256 re-check.
  - `[medium]` `[patch]` `_restore_argv_and_flag` wrote an ambient `FREECAD_BUDDY_BUILD_BROKEN_DOCS=1` back into the process environment on cleanup (reproduced in a standalone probe), re-arming the rebuild trigger for whatever ran next and directly contradicting the sibling test that declares such an environment unfit — cleanup now drops an enabling value instead of restoring it.
  - `[medium]` `[patch]` the ambient-flag guard sampled `os.environ` *after* the flag-value test had set and popped `"1"` (unittest orders `..._enables_only_...` before `..._is_not_set_...` alphabetically — confirmed), so it could only ever observe a self-cleaned environment. Now asserts a module-import-time snapshot (`_AMBIENT_BUILD_FLAG`), taken before any test mutates the environment.
  - `[low]` `[patch]` `BROKEN_DIR.rglob("fixture.FCStd")` recursed without bound under a fixture root the G1 README documents as containing SEALED `heldout/` content — narrowed to `glob("*/fixture.FCStd")`, which matches the documented `<case>/fixture.FCStd` layout and cannot drift.
  - `[low]` `[patch]` the count guard's message read `"no fixtures to compare against"` but fires on any mismatch, so a 29- or 31-fixture tree would report a false cause — message now states expected vs found.
  - `[low]` `[patch]` `$env:VAR=1` in the README assigned an integer that worked only by PowerShell coercion, the README omitted the POSIX form the docstring carried, and it cited a test name that this pass renamed — both docs now use `$env:VAR="1"`, carry both shells, and cite the test *file* rather than a method name.
- rejected (verified against source, not taken): re-adding an `argv[0]`/`__file__` conjunct to the build guard (would reintroduce the exact coupling DW-60 removed); making `base_dir` mandatory or staging the build through a temp dir (spec **Never** forbids changing `build_all`'s signature); normalizing `" 1 "`/`"true"`/case (strict `"1"` is the deliberate documented contract, rejected in the prior pass too); moving the ambient check into `setUpModule` (the module-scope snapshot already samples pre-mutation state); private-name access across the test boundary (`_BUILD_FLAG`/`_build_requested` *are* the contract under test); the double `read_bytes()` cost (sha256 over 30 dev fixtures is not a real cost); a stderr warning when the flagless command is run (contradicts the minimum-code boundary).

### 2026-07-30 — Review pass (follow-up 2)
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 1, medium 3, low 1)
- defer: 1: (high 0, medium 1, low 0)
- reject: 11: (high 0, medium 3, low 8)
- addressed_findings:
  - `[high]` `[patch]` both reviewers found independently that nothing executed the module with the flag *on* — the prior pass's `test_build_flag_enables_only_...` only called `_build_requested()` directly, so the module-level `if _build_requested(): build_all()` had no automated witness and Acceptance Criterion 3 rested on a hand-run probe. A mistyped guard would make the documented generator a permanent silent no-op with the suite green. Added `test_enabling_flag_runs_the_build_at_module_level`, which runs a byte-identical copy of the generator from a temp dir (so the module's own `HERE = Path(__file__).parent` points there and a build cannot reach the commits) with the flag set, then asserts all 30 cases were written into that dir and the committed tree is unchanged. Falsification: sabotaging the comparison to `== "1x"` turns the suite `FAILED (failures=2)`; the pre-patch suite passed that same sabotage.
  - `[medium]` `[patch]` `test_build_flag_enables_only_...` wrote `"1"` into the *real* shared-process environment (all infc modules share one FreeCADCmd process), the exact state its own sibling test declares unfit — any fresh import during that window rebuilds the fixtures. `_build_requested()` is a pure function of a mapping, so the real environment was never needed: added `_build_requested_in(env)` to the generator and the value test now asserts against injected dicts, touching `os.environ` not at all.
  - `[medium]` `[patch]` the sha256 witness keyed a *fixed* path set (`before` computed from a `glob` snapshot), so it proved "these 30 files unchanged" rather than the spec Boundary "must never write, create, or mutate any file" — a created `.FCStd1` backup or lock file was invisible by construction. Replaced with a whole-tree digest over `rglob("*")`. Falsification probe: creating `oc-bracket-plate/fixture.FCStd1` is missed by the fixed-key witness and caught by the tree witness.
  - `[medium]` `[patch]` the test name and its argv scaffolding were dead weight — the generator reads neither `sys.argv` nor `__name__`, so deleting the spoof and `_restore_argv` could not make the test fail. Renamed to `test_import_without_the_enabling_flag_does_not_rebuild` and dropped the inert argv machinery, leaving the flag-value dimension as the real axis.
  - `[low]` `[patch]` the README and module docstring claimed import never rebuilds "for any `sys.argv`", which nothing asserts and which argv-independence makes meaningless — both now say "without that flag", matching what the suite proves.
- rejected (verified against source, not taken): the bare `assert spec is not None` (kept — `assertIsNotNone` does not narrow for the type checker, and the next line raises regardless); `before` snapshotted outside the subTest loop (comparing all iterations to one baseline is correct for an invariant); `_restore_flag` dropping an ambient `"1"` (deliberate, added last pass — restoring it would re-arm the trigger); making the ambient guard an allowlist instead of `assertNotEqual(..., "1")` (it defends today's exact comparison; a loosened comparison is the hypothetical, and the value test now pins strictness); normalizing `" 1 "`/`"TRUE"`/`"yes"` (strict `"1"` is the documented contract, rejected in both prior passes); moving `_BUILD_FLAG` up beside `HERE` (cosmetic); adding a cmd.exe README form (POSIX + PowerShell cover the documented shells); a stderr hint on flagless invocation (spec **Never**: no abstraction beyond the flag check); partial-write handling inside `build_all` (spec **Never** freezes its signature); wrapping `read_bytes` OSError (a raw traceback already names the path); varying `sys.argv` across shapes (argv is not an input to the guard); changing `tests/run_tests.py`'s heuristic (spec **Never** excludes it explicitly).

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

**Follow-up review pass (2026-07-30):**
- `micromamba run -n fcb FreeCADCmd tests/run_tests.py` — **Actual:** `Ran 137 tests in 13.752s` / `OK (skipped=1)`, exit 0. Same test count as the prior pass, so the test restructure lost no case; all three flag/import tests present in the run log.
- `git status --porcelain benchmarks/g1/dev/broken-docs` — **Actual:** only `M build_broken_docs.py`; zero `fixture.FCStd` modified by the suite run.
- `uv run ruff check` + `ruff format --check` on both changed files — **Actual:** `All checks passed!` / `2 files already formatted`.
- `uv run ruff check .` — **Actual:** `Found 10 errors.` — same count as the pre-existing baseline, so no regression.
- Falsification probes for this pass: (1) reproduced the cleanup re-arm — with `FREECAD_BUDDY_BUILD_BROKEN_DOCS=1` ambient, the old `_restore_argv_and_flag` wrote `"1"` back after the test; (2) confirmed `unittest`'s alphabetical ordering runs the flag-setting test before the ambient guard, so the guard could only read a self-cleaned environment; (3) confirmed by `grep` that the generator now references neither `sys.argv` nor `__name__`, which is what made the old test's argv spoofing unfalsifiable.

**Follow-up review pass 2 (2026-07-30):**
- `micromamba run -n fcb FreeCADCmd tests/run_tests.py` — **Actual:** `Ran 138 tests in 14.054s` / `OK (skipped=1)`, exit 0. One test more than the prior pass (137), the added positive-path build test; all four flag/import tests `ok` in the run log.
- `git status --porcelain benchmarks/g1/dev/broken-docs` — **Actual:** only `M build_broken_docs.py`; zero `fixture.FCStd` modified, confirming the new build test's temp-dir redirection never reaches the commits.
- `uv run ruff check` + `ruff format --check` on both changed files — **Actual:** `All checks passed!` / `2 files already formatted`.
- `uv run ruff check .` — **Actual:** `Found 10 errors.` — identical count on clean `HEAD` (re-verified this pass by stashing `benchmarks/` + `tests/`), so pre-existing and unrelated.
- Falsification probes for this pass: (1) sabotaged the guard comparison to `env.get(_BUILD_FLAG) == "1x"` and re-ran the suite — `FAILED (failures=2, skipped=1)`, with `test_enabling_flag_runs_the_build_at_module_level` among the failures; the pre-patch suite passed that same sabotage, proving the positive path previously had no witness. Generator restored and re-verified at `== "1"`. (2) Created a stray `oc-bracket-plate/fixture.FCStd1` and compared witnesses: the prior fixed-key sha256 map reports no change (`False`), the whole-tree digest reports a change (`True`), confirming the tree witness covers the spec's "must never write, create, or mutate any file" where the fixed-key one did not. Probe file removed; tree digest confirmed restored.

## Auto Run Result

Status: done

**Implemented change.** `build_broken_docs.py` builds fixtures only on the explicit opt-in `FREECAD_BUDDY_BUILD_BROKEN_DOCS=1`, replacing an `argv[1]`-vs-`__file__` heuristic that let any importer silently overwrite all 30 committed fixtures. Import is now side-effect-free by construction, independent of `argv` and `__name__`. This follow-up review pass added the missing witness for the *enabling* path and strengthened the "nothing written" witness.

**Files changed.**
- `benchmarks/g1/dev/broken-docs/build_broken_docs.py` — argv heuristic replaced by `_build_requested()` over the env flag; `_build_requested_in(env)` extracted so the predicate is testable without mutating the shared process environment; docstring documents the POSIX and PowerShell invocations.
- `tests/infc/test_broken_docs_g1.py` — `test_import_without_the_enabling_flag_does_not_rebuild` (re-imports under unset/`"0"`/`""`, whole-tree sha256 witness), `test_enabling_flag_runs_the_build_at_module_level` (runs a copy of the generator from a temp dir with the flag on, asserts 30 cases written there and commits untouched), `test_build_flag_enables_only_on_the_documented_value` (injected-mapping value matrix), `test_build_flag_was_not_ambiently_set_when_the_suite_started`.
- `benchmarks/g1/README.md` — documents the opt-in invocation for both shells and cites the asserting test file.

**Review findings this pass.** 5 patches applied (1 high, 3 medium, 1 low): the untested enabling path, the shared-environment mutation, the fixed-key witness, and the dead argv scaffolding plus its overclaiming docs. 1 deferred as new ledger entry DW-66 (argv-heuristic modules reachable from the live infc process — distinct from the existing DW-65; no existing entry was modified). 11 rejected, each checked against source and against the spec's **Never** boundaries.

**Verification.** `FreeCADCmd tests/run_tests.py`: `Ran 138 tests` / `OK (skipped=1)`, exit 0. Zero committed fixtures modified. ruff check + format clean on both changed files; repo-wide count unchanged from HEAD at 10 pre-existing errors. Two falsification probes confirm both new witnesses fail when the behavior they guard is broken.

**Residual risks.** The ambient-flag guard asserts a module-import-time snapshot, so it cannot observe an enabling flag exported mid-suite by code outside this module; no in-repo caller does that today. Four copies of the retired argv heuristic survive elsewhere in `benchmarks/` plus one in `tests/run_tests.py`, which the spec places out of scope — tracked as DW-65 and DW-66.

## Auto Run Result

Status: done

**Implemented change:** the G1 broken-doc fixture generator builds only when `FREECAD_BUDDY_BUILD_BROKEN_DOCS=1` is in the environment, so importing it for `gen.CASES` is side-effect-free under any `argv` and any `__name__`. This follow-up pass hardened the *tests* that prove it: they no longer leave an enabling flag armed behind them, no longer assert on a self-cleaned environment, and now cover every non-enabling flag value on the real import path.

**Files changed:**
- `benchmarks/g1/dev/broken-docs/build_broken_docs.py` — `_is_top_level_script()` replaced by `_build_requested()` reading `_BUILD_FLAG`; `import sys` dropped for `import os`; docstring documents both shells with PowerShell's correct `="1"` quoting.
- `tests/infc/test_broken_docs_g1.py` — import-safety test now re-imports under `None`/`"0"`/`""` with a sha256 witness over all 30 fixtures and a bounded `glob("*/fixture.FCStd")`; cleanup split into `_restore_argv`/`_restore_flag`, the latter refusing to re-arm `"1"`; the ambient-flag guard asserts a module-import-time snapshot taken before any test mutates the environment.
- `benchmarks/g1/README.md` — states both the POSIX and PowerShell invocations and cites the asserting test file rather than a method name.

**Review findings:** 6 patches applied (3 medium, 3 low), 1 deferred as DW-65 (medium), 8 rejected. The three medium patches were all in the test file and compounded: the suite added to prove "import never rebuilds" was itself re-arming the rebuild trigger on cleanup, while the test meant to catch that condition could not observe it.

**Residual risks:**
- The identical argv hazard survives in `benchmarks/g0/export-fault-injection/build_export_fault_fixtures.py` — deferred as DW-65, outside DW-60's scope.
- The module-level `if _build_requested():` branch is covered only for the non-taken direction. Guard *inversion* is caught (the import-safety test would rebuild and fail the hash check), but a guard reduced to a permanent no-op — wrong flag name at the module level, `if False:` — leaves all tests green and makes the documented build silently do nothing. Accepted: the generator is a dev-only tool whose output is committed and independently self-checked by `test_each_committed_fixture_is_broken_on_its_named_object`.
- Verified on FreeCAD 1.1.0 only; the 1.0.x leg is CI's. Nothing in the change is version-sensitive (stdlib `os.environ` + `importlib`).
- `_build_requested()` accepts only the literal `"1"`, so a mis-set flag (`true`, trailing space) is a silent no-op rather than a loud error — deliberate, asserted in-suite, and both documented invocations use `1`.

