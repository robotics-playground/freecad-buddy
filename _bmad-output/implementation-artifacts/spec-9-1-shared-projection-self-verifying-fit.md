---
title: 'Story 9.1: One Projection for Fit and Verdict, and a Fit That Verifies Itself'
type: 'bugfix'
created: '2026-09-13'
status: 'done'
baseline_revision: '0b52de188bb5eec4c3f9d22d7a677dcffbe30e87'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-9-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-8-3-view-fit-viewport-tool.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-8-2-framing-read-exact-projection-test.md'
warnings: [oversized, multiple-goals] # invoked as 'epic-9' (4 stories); this spec covers story 9.1 only
deferred:
  - summary: >-
      No in-FreeCAD or live-GUI test exercises the real View3DInventor; the convergence proof runs
      against a Python model of SoCamera::viewBoundingBox.
    evidence: |-
      Every new test drives _SimulatingView / _ProjectingView, which reimplement FreeCAD's framing
      arithmetic from View3DInventorViewer.cpp:4456-4492,4840. If that derivation is wrong, fake
      and production are wrong together and the suite still passes. tests/infc/ has no view_fit
      file. Settled by running the R2-01 reproducer against FreeCAD 1.1.1 and inspecting pixels.
    location: >-
      tests/external/test_view_fit.py
    severity: medium
  - summary: >-
      _not_framed_envelope drops document and camera_recorded from structured_content though the
      camera was read and audited on that path.
    evidence: |-
      _fitted_envelope returns {fitted, document, camera_recorded}; the failure path goes through
      _refused_envelope, returning {fitted, reason}. One audit record is written before the failure
      envelope is built, so the prior camera is recoverable from the audit log but the caller
      cannot tell. The other _refused_envelope users genuinely have no camera; this one does.
    location: >-
      src/freecad_buddy/usecases/view_fit.py
    severity: low
  - summary: >-
      _measure hand-builds a FramingVerdict literal duplicating framing._unavailable.
    evidence: |-
      A second constructor for one contract type in a second module, where the checked/stale_reason
      pairing can drift. Promote framing's builder alongside measure_framing and call it.
    location: >-
      src/freecad_buddy/usecases/view_fit.py
    severity: low
  - summary: >-
      _measure's bare except Exception is wider than the single unguarded raise it documents.
    evidence: |-
      measure_framing already catches its own getSize, projection and bbox failures; the only
      unguarded raise is the document.Objects read. A catch over the whole call converts any future
      bug inside measure_framing into a bland "could not be measured" carrying only the exception
      type. Narrow the catch to the object-list read.
    location: >-
      src/freecad_buddy/usecases/view_fit.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** `view_fit_viewport` frames the model with an analytic face-diagonal estimate of the
on-screen silhouette while the framing verdict measures the real projected corner hull. The two
disagree by 1.155x on a cube down to 0.856x on a 40x40x800 bar, so compact parts are zoomed past
the edge and the tool still returns `fitted: true` beside its own `framing: {"fits": false,
"ratio": 1.0978}`. Repeated calls do not converge, because a factor derived from geometry cannot
improve by repetition.

**Approach:** Delete the analytic estimate. Measure the projected extent with the same
corner-projection routine the framing verdict already uses, then make the fit verify its own
result: measure, zoom, re-project. `fitted: true` becomes a measurement rather than a report that
the call ran — a post-fit contradiction returns `SPEC_FAILED` carrying its `framing` block.

## Boundaries & Constraints

**Always:**
- One shared corner-projection routine serves both the fit factor and the framing verdict. It
  lives in `usecases/framing.py` (the existing owner) and is imported by `usecases/view_fit.py`.
- The fit is three passes inside **one** `_animation_suspended` block: (1) orient isometric and
  project the pre-fit extent, (2) `fitAll(factor)`, (3) re-project through the written camera to
  verify.
- The binding axis is AD-32's: `max` of the two `extent / viewport_extent` quotients — the same
  quantity `hull_ratio` returns. Never `fitAll`'s sphere radius.
- `_FILL_FRACTION` (0.95) stays the target fill on that binding axis.
- `fitted: true` requires pass 3 to return `fits: true`.
- The post-fit `SPEC_FAILED` carries a top-level `framing` key holding the freshly computed
  verdict. This is AD-32's single carve-out to the omit-on-non-OK rule.
- `usecases/view_fit.py` keeps its no-`FreeCADGui`/no-Qt property; the view stays duck-typed.
- Preserve every shipped behaviour the existing tests pin that this story does not name: audit of
  the prior camera, the host-installed sink, the `fitAll` arity fallback, animation restoration on
  raise, and the unavailable/refused envelopes.

**Never:**
- Do not change `hull_ratio`, `containment`, `corners`, `union_bbox` or `_IMPLAUSIBLE_FACTOR`
  semantics. This story reuses them; story 8.2 pinned them and its tests must stay green.
- Do not retry or loop the fit. One contradiction is an honest failure, not a second pass.
- Do not touch the wrong-document guard (`_require_same_document`) — that is story 9.2, which
  edits this same file next. Keep the diffs separable.
- Do not hand-write `ratio` into the prose `text` or the `detail.message`. The number reaches the
  caller through the `framing` block only.
- Do not relax the non-OK omission rule for any other tool or any other status.
- Do not add a `confirm` property or route the tool through the mutation wrappers.
- Do not widen `NEAR_MISS_TOLERANCE` in `contracts/envelope.py` to make a test pass.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fit converges | 40 mm cube, live view, 800x600 | `OK`, `fitted: true`; pass-3 `fits: true`; binding-axis ratio within the band | No error expected |
| Aspect sweep | 40 cube, 20x20x30, 40x40x80, 40x25x15, 40x40x800 | Every one fits after one call; none clips | No error expected |
| Post-fit contradiction | Pass 3 returns `fits: false` | `SPEC_FAILED`, `fitted: false`, top-level `framing` present with `checked: "computed"` and the real `ratio` | Code `view_fit.not_framed`; `ratio` absent from `text` |
| Animation cannot suspend | `setAnimationEnabled` raises | `SPEC_FAILED`, no `framing` block (nothing was measured), camera untouched | Code `view_fit.animation`; reason names the precondition |
| Unmeasurable pre-fit extent | Every corner implausible, or no readable bbox, or `getSize` unreadable | Plain `fitAll` still runs (a lost model must be recoverable), then pass 3 decides the status | Falls back to factor 1.0 |
| Repeat fit | Same model fitted twice | Second call also `OK` with a stable ratio in the band | No error expected |
| No viewport / view refuses fit | Port `None`, unavailable, no view, `fitAll` raises | Unchanged shipped envelopes; **no** `framing` block | Existing codes preserved |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/view_fit.py` -- the whole change lands here. `_fill_factor:168-191`
  is the analytic estimate to delete, including its comment at `:182-186` (AC8). `_fit_all:103-130`
  becomes the three-pass body. `_animation_suspended:132-165` currently swallows a failing
  `setAnimationEnabled` into `self._previous = None`; AC6 makes that a refusal, so the context
  manager must expose whether suspension succeeded. `_fitted_envelope:300` and
  `_refused_envelope:325` are the envelope builders; `_document_bounds:194` already reuses
  `union_bbox` + `is_default_renderable`.
- `src/freecad_buddy/usecases/framing.py` -- the routine to share. `_project:341` is the
  single-corner projection (`view.getPointOnViewport`), `corners:97`, `containment:103`,
  `hull_ratio:137`, `_viewport_size:329`. `_project` and `_viewport_size` are module-private today
  and must become importable (rename without the underscore, or add a public wrapper that returns
  the whole measured verdict). Prefer **one public function that measures a document through a
  view and returns a `FramingVerdict`** — `_verdict:300` is already exactly that shape and takes
  `(document, view)`. Promoting `_verdict` is the smallest reuse point; both passes 1 and 3 call
  it and pass 3's return value is the block the `SPEC_FAILED` carries.
- `src/freecad_buddy/contracts/render.py:79` -- `FramingVerdict` TypedDict (`fits` / `ratio` /
  `checked` / `stale_reason`). Read-only for this story.
- `src/freecad_buddy/contracts/envelope.py:56` -- `framing` is already an optional top-level
  `ResultEnvelope` key, so the carve-out needs no contract change. `framing_warning:82` /
  `with_framing_text:109` render the sentence; `NEAR_MISS_TOLERANCE:37` is `0.0`.
- `src/freecad_buddy/hosts/tool_catalog.py:1332-1343` -- `with_framing`. Line `:1337` short-circuits
  on non-`OK` and returns the envelope untouched. Because the usecase attaches its own block on the
  `SPEC_FAILED` path, that short-circuit **already preserves it** — verify this rather than
  assuming, and add the regression test. `:1343` spreads `{**envelope, "framing": verdict}`, so an
  `OK` fit's block is still attached by the wrapper as today (do not attach it twice).
- `tests/external/test_view_fit.py` -- 31 tests to keep green. `_ProjectingView:505` already
  projects through a caller-supplied function and records `boxZoom`; `_FactorView:604` records
  factors; `_AnimationView:703` records the toggle/write ordering pinned at `:738`.
  **`_resulting_fill:620-634` encodes `fitAll`'s real arithmetic** — the model lands at
  `silhouette / (diagonal * factor)` — and the aspect sweep at `:637-656` is the fixture set AC2
  extends. Two tests contradict this story and must be replaced, not deleted silently:
  `:659 test_should_not_read_the_camera_back_while_it_holds_the_qt_thread` (asserts the fit must
  **not** project) and `:672` (`fit_calls == 1`, no correction passes).
- `tests/external/test_framing.py` -- 32 tests pinning the projection primitives; any rename must
  keep them green. `_FakeBoundBox:24`, `_box_object:117`.
- `tests/external/test_framing_envelope.py` -- pins the attach/omit rules the carve-out touches.
- `tests/uat/run/2026-09-13-02/bugs.md` -- R2-01 is the reproducer, with the measured per-aspect
  error table this story's fixtures encode.

## Tasks & Acceptance

**Execution:**

- `src/freecad_buddy/usecases/framing.py` -- promote `_verdict(document, view)` to a public
  `measure_framing(document, view) -> FramingVerdict` and add it to `__all__`; keep `_verdict` as
  the private name only if something still calls it, otherwise rename outright -- one routine, so
  fit and verdict cannot disagree (AC1). Leave `read_framing`, the cache and the primitives alone.
- `src/freecad_buddy/usecases/view_fit.py` -- delete `_fill_factor` and its `:182-186` comment;
  replace `_fit_all` with the three-pass body that calls `measure_framing` before and after
  `_fit_all_with_factor` -- the estimate is the defect and the comment re-derives it (AC1, AC8).
- `src/freecad_buddy/usecases/view_fit.py` -- derive the factor from the pass-1 verdict's `ratio`.
  `fitAll(f)` frames the scene box's space diagonal, so the on-screen extent scales as `1/f`
  relative to `fitAll(1.0)`: measure `ratio0` through the current camera, and choose `f` so the
  post-zoom binding-axis ratio lands on `_FILL_FRACTION`. When `ratio0` is `None` (implausible
  corners, no bbox, unreadable size) fall back to factor `1.0` so a lost model is still recovered
  -- the binding axis is AD-32's, never the sphere radius (AC7).
- `src/freecad_buddy/usecases/view_fit.py` -- make animation suspension a precondition: have
  `_animation_suspended` record that `setAnimationEnabled(False)` raised, and return
  `SPEC_FAILED` instead of fitting -- with animation on, pass 3 re-reads the pre-fit camera and
  restores the defect (AC6). A view with **no** toggle at all keeps fitting (pinned at
  `test_view_fit.py:770`); only a toggle that exists and fails is a refusal. The shipped
  `__enter__:152-157` catches one `Exception` over both calls, which conflates the two — split it
  so a missing `isAnimationEnabled`/`setAnimationEnabled` attribute stays best-effort while a
  present `setAnimationEnabled(False)` that raises becomes the refusal.
- `src/freecad_buddy/usecases/view_fit.py` -- gate `_fitted_envelope` on the pass-3 verdict; add a
  `SPEC_FAILED` builder that carries the verdict as a top-level `framing` key and leaves the
  number out of `text` and `detail.message` -- `ratio` lives nowhere else in the contract (AC3,
  AC4).
- `tests/external/test_view_fit.py` -- replace `test_should_not_read_the_camera_back_...` and the
  `fit_calls == 1` assertion with the three-pass contract; extend `_ProjectingView` so its
  projection changes after `fitAll` (a pre/post projection function pair), which is what makes
  passes 1 and 3 distinguishable in a fake -- the old tests assert the behaviour this story
  reverses, so leaving them green would mean the fix did not land.
- `tests/external/test_view_fit.py` -- add the aspect-sweep fixtures **including a 40 mm cube and
  a 20x20x30 box**, plus the repeat-fit, contradiction, animation-refusal and
  `framing`-on-`SPEC_FAILED` cases from the I/O matrix (AC2, AC9).
- `tests/external/test_framing_envelope.py` -- add the one regression that `with_framing` leaves a
  usecase-attached `framing` block intact on a non-`OK` envelope, and still attaches none for any
  other non-`OK` tool -- the carve-out extends to exactly one site.

**Acceptance Criteria:**

- Given the fitted 40 mm cube, 20x20x30 box, 40x40x80 bar, 40x25x15 plate and 40x40x800 bar, when
  each is fitted once, then every one returns `OK` with a post-fit verdict of `fits: true` and a
  binding-axis ratio at `_FILL_FRACTION` within tolerance -- the cube and the 20x20x30 box are the
  two the shipped tuning never sampled.
- Given `grep -n "silhouette" src/freecad_buddy/usecases/view_fit.py`, when the change is done,
  then it returns nothing -- no analytic estimate and no comment re-deriving it survives.
- Given the same model fitted twice, when the second call returns, then its verdict is stable and
  in the band -- non-convergence was the shipped symptom.
- Given a fit whose pass-3 verdict is `fits: false`, when the caller reads the envelope, then
  `status` is `SPEC_FAILED`, `structured_content.fitted` is `false`, and `envelope["framing"]`
  holds that verdict with `checked: "computed"`; `str(ratio)` appears nowhere in `text`.
- Given the shipped `tests/external/test_framing.py` and `test_framing_contract.py`, when the
  suite runs, then every test still passes -- this story reuses story 8.2's primitives and changes
  none of their semantics.

## Design Notes

**The factor arithmetic.** `fitAll(f)` scales the scene box by `f` before framing its space
diagonal, so relative to a plain `fitAll(1.0)` the on-screen extent scales as `1/f`. The shipped
code got the *form* right and the *input* wrong: it fed an analytic silhouette where a measured
one was needed. `tests/external/test_view_fit.py:620` already encodes the ground truth
(`silhouette / (diagonal * factor)`), and `diagonal` is exact — only `silhouette` was estimated.

Pass 1 gives a ratio through whatever camera is current, which is **not** `fitAll(1.0)`'s camera,
so `ratio0` cannot be used as the post-zoom prediction directly. Two defensible shapes exist and
both satisfy every AC; pick either and pin it with the sweep test:

1. **Measure, zoom, verify, report** — compute `f` from the geometry the way the shipped code does
   but with the *measured* projected extent substituted for the estimate, then let pass 3 decide
   the status. The verification is what makes it correct; the factor only has to be close.
2. **Zoom to a known state first** — `fitAll(1.0)`, project (that is now a known camera), compute
   the exact correction `f = ratio1 / _FILL_FRACTION`, `fitAll(f)`, then verify. Costs one extra
   camera write inside the same suspended block.

Shape 2 converges in one call for any aspect and needs no analytic model of `fitAll` at all, which
is the property the whole story is about. Prefer it unless the second write proves visibly
disruptive. Either way the loop is **bounded and not retried**: at most the writes named here, and
a contradiction at the end is reported, never re-fitted.

**Why the carve-out is safe here.** `with_framing` returns non-`OK` envelopes untouched
(`tool_catalog.py:1337-1338`), so a block the usecase attached survives without editing the
wrapper. Confirm that by test rather than by reading — if the wrapper is ever changed to strip
unknown keys, this story's contract breaks silently.

**Near-miss tolerance.** `NEAR_MISS_TOLERANCE` is `0.0` today. Under a measured factor every
fixture should land at one value instead of spreading, so if the sweep shows a consistent small
overshoot, record the measured number in the test rather than widening the constant. Changing that
constant is out of scope.

## Verification

**Commands:**
- `uv run ruff check <the four changed files>` -- expected: clean. A repo-wide `ruff check .`
  reports 9 pre-existing E501 errors in files this story does not touch.
- `uv run ruff format --check <the four changed files>` -- expected: no **new** reformatting.
  `view_fit.py` and `test_view_fit.py` were already unformatted at `0b52de1`; verify by stashing
  each file and re-checking rather than reading a repo-wide result as a regression.
- `uv run pytest tests/external/test_view_fit.py -q` -- expected: all pass, including the new
  aspect sweep with the cube and the 20x20x30 box.
- `uv run pytest tests/external/test_framing.py tests/external/test_framing_envelope.py tests/external/test_framing_contract.py -q`
  -- expected: all pass unchanged; story 8.2's primitives are reused, not altered.
- `uv run pytest -q` -- expected: no new failures anywhere.
- `uv run python scripts/check_imports.py` -- expected: clean; `usecases/view_fit.py` gains no
  FreeCADGui or Qt import.
- `grep -rn "silhouette" src/freecad_buddy/usecases/view_fit.py` -- expected: no output.

**Manual checks (if no CLI):**
- The live-GUI reproducer (R2-01) is a UAT step, not part of this story's gate: a real
  `view_fit_viewport` on a 40 mm cube must return `fitted: true` with `framing.fits: true`, and
  the captured window must show the solid whole with margin on every side. Automated verification
  alone is not sufficient for that check.

## Review Triage Log

### 2026-09-13 — Review pass

- verdicts: 37 findings — high 2, medium 4, low 6, false 17, maybe-false 8
- findings:
  - `[high]` `[patch]` A measured `ratio` of exactly `0.0` skipped the correction pass and returned `OK, fitted: true` on a model reduced to a sub-pixel dot — Reproduced directly: a view projecting all 8 corners to `(400,300)` returned `status=OK, fitted=True, factors=[1.0]`. `hull_ratio` returns a genuine `0.0` there; that is a measurement, not a failure to measure. Fixed: `_correction_factor` now rejects only `None`/bool/non-finite; `factors=[1.0, 0.01]` after the fix.
  - `[high]` `[patch]` Animation left switched OFF in the human's viewer when `isAnimationEnabled()` raises but `setAnimationEnabled(False)` succeeds — Reproduced: the call ended with animation `False` after the human had `True`, contradicting the class docstring. Introduced by this diff's split of the old single handler. Fixed with a `_UNSUSPENDED` sentinel separating "nothing to restore" from "unreadable previous value"; probe now ends at `True`.
  - `[medium]` `[patch]` The unreadable-document path returned `view_fit.not_framed` claiming "the model still does not fit ... read the framing block for the measured overflow" while the verdict carried `fits: null, ratio: null` — Reproduced: the envelope made a false statement about the cause, and the path silently changed from `OK` to `SPEC_FAILED` with no test pinning it. Fixed: new code `view_fit.unverified`, reason names the measurement failure, `stale_reason` names the document not the view.
  - `[medium]` `[patch]` `test_should_fall_back_to_the_bare_call_for_a_view_whose_fitAll_takes_no_factor` never reached the `except TypeError` branch — `_FakeView.getPointOnViewport` returned a constant, so ratio was `0.0`, correction was skipped and `fit_calls == 1` held for an unrelated reason. Verified a no-factor view with a real projection lands at ratio 0.855 vs the 0.95 target. Fixed: the test now uses `_SimulatingView` arithmetic with a no-argument `fitAll` and asserts `fit_calls == 2`.
  - `[medium]` `[patch]` `_correction_factor` accepted `bool`, NaN and inf ratios (`isinstance(True, int)` passes) — Folded into the zero-ratio fix; the guard now excludes bool and non-finite values explicitly.
  - `[medium]` `[defer]` No in-FreeCAD (`tests/infc/`) or live-GUI test exercises the real `View3DInventor`; the convergence proof is against `_SimulatingView`'s model of `SoCamera::viewBoundingBox` — Real and correctly identified: if the cited derivation is wrong, fake and production are wrong together. This is the epic's UAT acceptance (`epics.md:1081`), not story 9.1's gate; TC-14 already covers the surface.
  - `[low]` `[reject]` `ruff format --check` fails on `view_fit.py` and `test_view_fit.py` — Refuted as *new*: I stashed each file and re-checked at baseline `0b52de1`; both were already unformatted before this diff. Pre-existing, and `ruff check` passes clean on all four changed files.
  - `[low]` `[defer]` `_not_framed_envelope` drops `document` and `camera_recorded` from `structured_content` though the camera was read and audited on that path — Real but cosmetic; the prior camera is recoverable from the audit log. Fix adds public surface to a failure envelope.
  - `[low]` `[defer]` `_measure` hand-builds a verdict literal duplicating `framing._unavailable` — Second constructor for one contract type in a second module. Real drift risk, not a defect today.
  - `[low]` `[reject]` No test pins that the `OK` path attaches `framing` exactly once — Verified the property holds: `_fitted_envelope` sets no `framing` key and `with_framing` attaches on `OK` only. Fix is a test for a property no code path threatens.
  - `[low]` `[defer]` `_measure`'s bare `except Exception` is wider than its documented cause — Real; `measure_framing` already catches its own `getSize`/projection/bbox failures, so only the object-list read is unguarded. Narrowing it is a follow-up.
  - `[low]` `[reject]` No test covers the "unreadable `getSize`" I/O-matrix row — The row's other two causes are covered and the third reaches the same `unavailable` verdict now pinned by the new `view_fit.unverified` test. Marginal added value.
  - `[maybe-false]` `[reject]` `_audit` fires before the verdict gate, so a `SPEC_FAILED` fit audits as a completed move — Claim is accurate about ordering, but the audit contract records the *camera move*, which did happen; AD-31 requires the prior camera be recorded for reversibility regardless of outcome. No named harm.
  - `[maybe-false]` `[reject]` Unbounded upper correction factor could overflow FreeCAD's framing — No demonstration that a reachable ratio produces such a factor; the projection discards implausible magnitudes before `hull_ratio` sees them.
  - `[false]` `[reject]` `"math" is not defined` at `view_fit.py:182` — Refuted: `import math` is present at `view_fit.py:25`. The diagnostic was a stale mid-edit snapshot.
  - `[false]` `[reject]` `measure_framing` is now public and unguarded, so any other caller raises on `document.Objects` — Refuted: `read_framing` is the only other caller and reaches it through `registry.with_document`, which resolves a live document first.
  - `[false]` `[reject]` Pyright attribute errors on `view.fitAll`, `getPointOnViewport`, `isAnimationEnabled` etc. — Refuted: the module documents deliberate duck-typing of the injected view, and no typecheck gate exists in this repo's Verification.
  - `[false]` `[reject]` Remaining 20 findings across layers (deleted `boxZoom`/`_FactorRecordingView` coverage, `_FakeDocument` gaining `Objects`, `_MIN_FIT_FACTOR` untested, three-passes-sometimes-two docstring, statement-order fragility, verdict key filtering, UAT/benchmark fixtures absent, scope of stories 9.2-9.4) — Each checked at its cited location: either the claimed bad outcome does not occur, the behaviour is the spec's stated intent, or the item is epic-level scope this story explicitly excludes. None establishes a defect in the shipped diff.

## Auto Run Result

Status: done
Story: 9.1 only. The invocation named `epic-9`; stories 9.2, 9.3 and 9.4 remain `backlog`.

**Implemented change.** The analytic silhouette estimate that framed the viewport fit is gone.
`usecases/framing.py`'s `_verdict` is promoted to public `measure_framing(document, view)`, and
`view_fit_viewport` now frames the model with that same routine: `fitAll(1.0)` to a known camera,
measure, `fitAll(ratio / _FILL_FRACTION)`, then re-measure through the camera it wrote.
`fitted: true` requires the post-fit projection to agree; a measured contradiction returns
`SPEC_FAILED` carrying its `framing` block (AD-32's single carve-out), and a fit that cannot verify
itself returns `view_fit.unverified`. Animation suspension became a precondition.

**Files changed.**
- `src/freecad_buddy/usecases/framing.py` — `_verdict` promoted to public `measure_framing`, added to `__all__`.
- `src/freecad_buddy/usecases/view_fit.py` — estimate and its comment deleted; three-pass self-verifying fit; `_AnimationRefused`; `view_fit.not_framed` and `view_fit.unverified` envelopes.
- `tests/external/test_view_fit.py` — five-aspect sweep including the 40 mm cube and 20x20x30 box; repeat-fit, contradiction, sub-pixel-dot, animation-refusal and arity-fallback cases.
- `tests/external/test_framing_envelope.py` — pins that the carve-out survives `with_framing` and extends to no other tool.

**Review findings.** 37 findings from four layers. 5 patched (2 high, 3 medium), 4 deferred,
28 rejected — every rejection recorded with its refutation in the triage log above. The two `high`
findings were both verified by direct reproduction before patching, and both re-verified as fixed
after.

**Verification performed.**
- `uv run pytest -q` — 1061 passed (1058 before the patches; 3 new tests).
- `uv run ruff check` on the four changed files — All checks passed.
- `uv run python scripts/check_imports.py` — check_imports OK.
- `grep silhouette src/freecad_buddy/usecases/view_fit.py` — no output.
- Direct reproduction probes for the zero-ratio, animation-restore and unreadable-document defects,
  re-run after patching to confirm each is fixed.
- Matrix audit: all 7 I/O rows have covering tests that collected and passed.

**Residual risks.**
- The convergence proof runs against `_SimulatingView`, a Python model of FreeCAD's
  `SoCamera::viewBoundingBox`. If that derivation is wrong, fake and production are wrong together.
  The live-GUI check against R2-01's reproducer has **not** been run and is required before this is
  called fixed in the product sense.
- No `tests/infc/` coverage: nothing exercises the real `View3DInventor`.
- The `OK`-path single-attachment of `framing` holds by construction, not by test.

Follow-up review recommended: true — two `high` entries were patched on a first pass. The specific
unverified risk is the live-GUI behaviour above: every assertion backing this story's convergence
claim is against a simulated camera.
