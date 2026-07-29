---
title: 'Correct the query_screenshot camera preset quaternions against FreeCAD Camera.cpp (DW-44)'
type: 'bugfix'
created: '2026-07-29'
status: 'done'
baseline_revision: '67c3e1a39f28ed34f35e2a42d89f31775e84cb1a'
final_revision: '46ba1f4603f86e8b53caded17162c3fae5cca1b3'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** `_CAMERA_QUATS` in `src/freecad_buddy/usecases/screenshot.py` (l65-73) hard-codes seven preset quaternions that were never checked against FreeCAD. Source-verified against `docs/references/FreeCAD/src/Gui/Camera.cpp`: `front` is `(0.5, 0.5, 0.5, 0.5)` — a verbatim copy of `right` — while `Camera::front()` (l44-48) is `{sqrt(2)/2, 0, 0, sqrt(2)/2}` = `(0.707107, 0, 0, 0.707107)`. A `front` render is therefore silently identical to a `right` render. `iso` also carries a one-digit typo: `0.17591` vs `Camera::isometric()`'s `0.17592` (l71). No test asserts any preset value, so the duplication is invisible.

**Approach:** Fix the two wrong values and add an in-FreeCAD test that asserts every preset equals its `Camera.cpp` counterpart up to quaternion sign (q and -q encode the same rotation, per `Camera::rotationsMatch`, l176-194), plus a pairwise-distinctness assertion so no preset can ever silently duplicate another again. Expected values in the test are transcribed from `Camera.cpp`, not captured from `_CAMERA_QUATS`.

## Boundaries & Constraints

**Always:**
- Every corrected value is transcribed from `docs/references/FreeCAD/src/Gui/Camera.cpp`, never derived from the current table or computed at test time from the implementation under test.
- Sign-insensitive comparison: two unit quaternions match when `|dot(a, b)|` is within tolerance of `1.0` (mirrors `Camera::rotationsMatch`). `left` stays `(0.5, -0.5, -0.5, 0.5)` — the exact negation of `Camera::left()` `{-0.5, 0.5, 0.5, -0.5}` (l61-64) — because it encodes the same rotation.
- The wire-facing preset *names* are unchanged: the `camera` enum in `hosts/tool_catalog.py` (l173-176) keeps `back`, which maps to `Camera::rear()`. Renaming an enum member would be a contract (schema) change.
- `usecases/screenshot.py` stays stdlib + FreeCAD-App only (AD-1/AD-12). The new test lives in `tests/infc/` under stdlib `unittest`; no pytest, no third-party imports.
- The new preset assertions are pure table comparisons — no GL, no render — so they must run unguarded, not behind the existing `_render_available()` skip guard.

**Block If:**
- `Camera.cpp` in `docs/references/FreeCAD/` disagrees with the values recorded in the Design Notes table below (i.e. the vendored reference has changed) — HALT `blocked`; the correction target is no longer established.

**Never:**
- Do not touch `top`, `bottom`, `right`, `back`, or `left` values — all five are source-verified correct (see Design Notes table).
- Do not add, remove, or rename preset keys; do not add `dimetric`/`trimetric` (not in the tool enum, not requested).
- Do not change `_orientation`, `_custom_orientation`, the render probe, or any framing/lighting behavior.
- Do not add a pixel-content or visual-diff assertion — orientation correctness is proven by the quaternion table, and render asserts must not enter the blocking headless gate.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| `camera: "front"` | preset lookup | `(0.707107, 0.0, 0.0, 0.707107)` | No error expected |
| `camera: "iso"` (default) | preset lookup | `(0.424708, 0.17592, 0.339851, 0.820473)` | No error expected |
| `camera: "right"` | preset lookup | `(0.5, 0.5, 0.5, 0.5)`, and NOT equal to `front` | No error expected |
| every preset vs `Camera.cpp` | full table | each matches its counterpart up to sign | test fails on mismatch |
| any two distinct presets | full table | no pair encodes the same rotation | test fails on duplication |
| `camera: "bogus"` | unknown key | `ValidationError` (`INVALID_INPUT`) — unchanged | existing behavior |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/screenshot.py` -- `_CAMERA_QUATS` (l64-73, the table to correct); `_orientation` (l277-285) reads it; unchanged.
- `docs/references/FreeCAD/src/Gui/Camera.cpp` -- authority. `top()` l34, `bottom()` l39, `front()` l44, `rear()` l50, `right()` l56, `left()` l61, `isometric()` l66, `rotationsMatch()` l176 (the sign-insensitive comparison to mirror).
- `tests/infc/test_screenshot.py` -- in-FreeCAD `unittest` screenshot suite; currently has zero camera-preset coverage. `_render_available()` (l27) guards GL-requiring asserts; the new preset test must NOT use that guard.
- `src/freecad_buddy/hosts/tool_catalog.py` -- l173-176 `camera` enum (`iso|front|top|right|left|back|bottom|custom`); read-only reference, do not edit.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/screenshot.py` -- set `front` to `(0.707107, 0.0, 0.0, 0.707107)` and `iso` to `(0.424708, 0.17592, 0.339851, 0.820473)`; leave the other five entries byte-identical -- `front` currently duplicates `right`, and `iso` has a digit typo, both against `Camera.cpp`.
- [x] `src/freecad_buddy/usecases/screenshot.py` -- update the `_CAMERA_QUATS` comment (l64) to name `Gui/Camera.cpp` as the source of the values -- a bare "fixed camera orientations" comment is what let unverified magic numbers sit undetected.
- [x] `tests/infc/test_screenshot.py` -- add a `CameraPresetTest(unittest.TestCase)` holding the expected quaternions transcribed from `Camera.cpp`, a sign-insensitive match helper, a per-preset match assertion, and a pairwise-distinctness assertion -- covers every I/O Matrix row and makes silent duplication impossible.
- [x] `tests/infc/test_screenshot.py` -- add a per-component assertion (`test_every_preset_component_matches_camera_cpp`) comparing against the closer-signed expected quaternion -- the rotation-level check alone cannot see a digit-level typo: normalized, the `iso` `0.17591`/`0.17592` error is a 9.7e-11 rotation difference, invisible at any sane tolerance.
- [x] `tests/infc/test_screenshot.py` -- normalize in `_same_rotation` and adopt FreeCAD's `1e-6` default; add unit-norm and arity assertions -- the unnormalized metric conflated norm deficit with rotation difference, which is what forced the original looser ad-hoc tolerance.

**Acceptance Criteria:**
- Given the corrected table, when `_orientation({"camera": "front"})` and `_orientation({"camera": "right"})` are both resolved, then they return different quaternions that do not encode the same rotation.
- Given the in-FreeCAD suite runs on both blocking CI legs with no render capability, when `CameraPresetTest` executes, then it runs and passes without being skipped (no GL dependency).
- Given a future edit sets any preset to a value not in `Camera.cpp`, when the in-FreeCAD suite runs, then `CameraPresetTest` fails naming the offending preset.

## Spec Change Log

## Review Triage Log

### 2026-07-29 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 7: (high 0, medium 4, low 3)
- defer: 1: (high 0, medium 1, low 0)
- reject: 5: (high 0, medium 2, low 3)
- addressed_findings:
  - `[medium]` `[patch]` Comparison tolerance was `1e-5` while `Camera.h` l69 defaults `1e-6`, and the `2*(1-|dot|)` metric was applied to non-unit quaternions, conflating norm deficit with rotation difference. `_same_rotation` now normalizes first and uses `1e-6`; every preset then matches at squared distance 0.0.
  - `[medium]` `[patch]` No assertion that presets are unit quaternions (`front`/`back` norm 1.0000003, `iso` 0.9999997). Added `test_every_preset_is_a_unit_quaternion`.
  - `[medium]` `[patch]` Bare `zip()` truncated silently, so a 3-component preset was invisible to the whole suite. Added explicit arity assertions; verified a 3-component `top` now fails.
  - `[medium]` `[patch]` Spec Design Notes stated the iso-typo rotation distance and tolerance headroom incorrectly. Recomputed and rewritten with measured values.
  - `[low]` `[patch]` Redundant outer `abs()` in `_same_rotation` could fold a wrongly-scaled quaternion into a passing value; removed (normalization makes it dead).
  - `[low]` `[patch]` `_aligned` sign choice undefined at `dot == 0`; documented the orthogonal case in the docstring.
  - `[low]` `[patch]` `assertNotEqual(front, right)` was exact float-tuple inequality, subsumed by the adjacent `_same_rotation` check; removed.

Rejected (with reason): parse `Camera.cpp` at test time — independent hand-transcription is the project standard for golden values, deriving them from the same file both sides read would defeat it. Assert against the `tool_catalog` camera enum, and cover the `custom` branch — already covered by `tests/external/test_render_probe.py`, and outside DW-44. Screen presets against `dimetric`/`trimetric` — not in the wire enum, and the spec forbids adding them. Stale golden PNGs from the old `front` view — no such baselines exist in the repo.

## Design Notes

Source-verified table (`docs/references/FreeCAD/src/Gui/Camera.cpp`), `(x, y, z, w)`:

| preset | `Camera.cpp` | current code | action |
|---|---|---|---|
| `iso` | `isometric()` `0.424708, 0.17592, 0.339851, 0.820473` | `..., 0.17591, ...` | fix digit |
| `front` | `front()` `{r, 0, 0, r}`, `r = sqrt(2)/2` | `(0.5, 0.5, 0.5, 0.5)` | fix — duplicates `right` |
| `top` | `top()` `{0, 0, 0, 1}` | same | leave |
| `bottom` | `bottom()` `{1, 0, 0, 0}` | same | leave |
| `right` | `right()` `{0.5, 0.5, 0.5, 0.5}` | same | leave |
| `left` | `left()` `{-0.5, 0.5, 0.5, -0.5}` | `(0.5, -0.5, -0.5, 0.5)` | leave — exact negation, same rotation |
| `back` | `rear()` `{0, r, r, 0}` | `(0.0, 0.707107, 0.707107, 0.0)` | leave |

The ledger entry (DW-44) guessed `back` was a 90° Z-rotation; that is wrong — `back` matches `rear()`. `front` is the real defect.

Sign-insensitive comparison, mirroring `Camera::rotationsMatch` (l188-193):

```python
def _same_rotation(lhs, rhs, tolerance=1e-5):
    dot = sum(a * b for a, b in zip(lhs, rhs))
    return abs(2.0 * (1.0 - abs(dot))) <= tolerance
```

The `2 * (1 - |dot|)` identity measures rotation only for *unit* quaternions, and the stored presets are 6-decimal roundings (`front`/`back` norm 1.0000003, `iso` norm 0.9999997). Compared unnormalized, the metric conflates norm deficit with rotation difference — `iso` against its own exact counterpart reads 1.24e-6 despite being the same rotation. `_same_rotation` therefore normalizes first, which makes the metric meaningful and lets the test adopt FreeCAD's own default tolerance of `1e-6` (`Camera.h` l69) instead of a looser ad-hoc value. Normalized, every preset matches its `Camera.cpp` counterpart at squared distance 0.0, and the closest distinct preset pair sits at 0.239.

A rotation-level check alone cannot catch digit-level transcription drift: normalized, the `iso` `0.17591`/`0.17592` typo is a 9.7e-11 rotation difference — invisible at any sane tolerance. That is why the per-component assertion exists alongside the rotation assertion; the two cover different defect classes.

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: exit 0, no ring violation from the changed files.
- `FreeCADCmd tests/run_tests.py` (or the repo's documented in-FreeCAD runner) -- expected: whole `tests/infc/` suite green, `CameraPresetTest` reported as run (not skipped).
- `uv run pytest tests/external/test_render_probe.py` -- expected: green; the `custom` orientation paths are untouched.
- `uv run ruff check src tests` and `uv run ruff format --check src tests` -- expected: clean.

**Manual checks (if no CLI):**
- If `FreeCADCmd` is unavailable in this environment, state that the in-FreeCAD leg was not executed; do not claim it passed.

## Auto Run Result

Status: done

**Implemented change.** Corrected two `_CAMERA_QUATS` entries in `usecases/screenshot.py` against `Gui/Camera.cpp`: `front` was `(0.5, 0.5, 0.5, 0.5)` — a verbatim duplicate of `right`, so a `front` render was silently identical to a `right` render — and is now `(0.707107, 0.0, 0.0, 0.707107)`; `iso`'s `0.17591` typo is now `0.17592`. The other five presets were source-verified correct and left byte-identical. Added `CameraPresetTest` to the in-FreeCAD suite pinning every preset to its `Camera.cpp` counterpart.

The ledger's own accusation was wrong: DW-44 claimed `back` was a 90° Z-rotation. `back` matches `Camera::rear()` exactly. `front` was the real defect.

**Files changed.**
- `src/freecad_buddy/usecases/screenshot.py` — two corrected quaternions; comment now cites `Gui/Camera.cpp` and names the counterpart for all seven presets.
- `tests/infc/test_screenshot.py` — new `CameraPresetTest` (6 tests): per-preset rotation match, per-component match, unit-norm/arity guards, pairwise distinctness, front-vs-right separation, unknown-preset rejection.
- `_bmad-output/implementation-artifacts/deferred-work.md` — one appended entry (end-to-end render orientation unverified).

**Review findings.** 7 patched, 1 deferred, 5 rejected; 0 intent_gap, 0 bad_spec. The substantive patch: the comparison used FreeCAD's `2*(1-|dot|)` identity on non-unit quaternions (6-dp roundings), which conflates norm deficit with rotation difference — `iso` read 1.24e-6 against its own exact counterpart. `_same_rotation` now normalizes first, which let the tolerance tighten from an ad-hoc `1e-5` to FreeCAD's own `1e-6` default with every preset matching at 0.0.

**Verification.** All run in this environment against `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`:
- `freecadcmd tests/run_tests.py` — `Ran 115 tests ... OK (skipped=1)`. All 6 `CameraPresetTest` tests reported `ok`, not skipped. The single skip is the pre-existing render-unavailable case (this machine has a render context).
- Falsifiability proven by reverting each defect class and re-running: iso digit typo → 1 failure; `front` duplicating `right` → 4 failures; 3-component `top` → 2 failures + 2 errors; non-unit `back` → 2 failures. Table restored after each.
- `python scripts/check_imports.py` — `check_imports OK`.
- `uv run pytest tests/external/test_render_probe.py tests/external/test_mcp_surface.py` — `53 passed`.
- `uv run ruff check src tests` — 1 error, `tests/external/test_check_imports.py:302` E501, confirmed pre-existing by stashing. `ruff format --check` — the only hunks on the touched files reproduce identically on the unmodified baseline; left alone per surgical-changes rule.

**Residual risks.** The tests verify table-to-`Camera.cpp` transcription, not rendered orientation — a correct table plus a wrong axis/sign convention in the offscreen path would still pass. Deferred to the ledger, to close when FR13's visual judge depends on a specific non-iso view. Pyright reports pre-existing diagnostics in both files (unresolvable `FreeCAD`/`Part` imports outside the FreeCAD interpreter, untyped document handles); none originate from this change.
