---
title: 'Story 1.6 — Verification Core: Fingerprint, Shape, Recompute, Sketch'
type: 'feature'
created: '2026-07-22'
status: 'done'
baseline_revision: '3a814cbc8d2a3fc3d54ac376433f013ac86f46be'
review_loop_iteration: 0
followup_review_recommended: false
final_revision: '5191be0'
context:
  - '{project-root}/_bmad-output/project-context.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** Story 1.5 shipped read-only `query_*` observation, but nothing yet *grades* a shape, sketch, or recompute deterministically. Every G0 exit criterion (G0.3 golden-model verify, G0.5 STEP round-trip) and every later phase's "the bridge says PASS" claim depends on a verify core proven against the golden models and the fault suite that Story 1.3 landed and left `last_run: null` (NFR1/2, AD-6/8/13, verification-design §2/4/5).

**Approach:** Add one `fingerprint()` implementation (`usecases/fingerprint.py`, §2) and three read-only validators to `usecases/verify.py` — `verify_shape` (§5, binding the forward-declared assertion fns `expect_volume`/`expect_bbox`/`expect_solid_count`/`expect_valid`/`expect_watertight`), `verify_sketch` (§4, `FullyConstrained` PASS after recompute), and `verify_recompute` (AC5, failing objects + `getStatusString()`). Each returns a contracts-owned `ValidationReport` (banner = FreeCAD version + `element_map_version` + validator sensitivity) wrapped in a `ResultEnvelope`. Register the three verify tools as `mutating=False`. Add a FreeCAD-free `stats` helper (Wilson CI) and an in-FreeCAD fault scorer that runs `verify_shape` over the G0 fault suite, computes sensitivity/false-alarm, and writes the current `validator_sha` + `last_run` into `_registry/validators.yaml`.

## Boundaries & Constraints

**Always:**
- Ring discipline (AD-1/AD-12): impls live in `usecases/` (stdlib + FreeCAD App API only; FreeCAD imported lazily inside functions). `fingerprint()` uses the shim serializer probe (`shim.serializer_tag`/`shim.export_binary_available`) — never a version string. `check_imports.py` stays green.
- Exactly one `fingerprint()` (AD-6): SHA-256 over per-object shape bytes (objects sorted by immutable `Name`), plus a quantized (Q=1e-6) mass-property tuple as independent cross-oracle. Every record carries its serializer tag; comparison is `contracts.fingerprints_equal` (already raises on cross-tag). Null/absent-`Shape` objects are skipped, not hashed.
- Sketch PASS ⇔ `sk.FullyConstrained == True` read *after* `doc.recompute()` (AD-8). HARD FAIL on non-empty `conflicting`/`malformed`, `evaluateConstraints()`, `dof<0`, `dof>0`, `degenerate_geometry_count>0`. `redundant`/`partially_redundant` = WARN only (never fail, never auto-remove). `solve()` codes are logging-only, never the DoF signal.
- `verify_shape` binds the closed forward-declared assertion vocabulary from `benchmarks/g0/fault-injection/README.md`: `expect_volume` (rel/abs tol vs `Shape.Volume`), `expect_bbox` (`[X,Y,Z]` extents), `expect_solid_count` (`len(Shape.Solids)`), `expect_valid` (`Shape.isValid()`), `expect_watertight` (single closed solid: `is_solid ∧ Shape.isClosed()`). Each maps to one `Check{id,measured,expected,tolerance,passed,detail}`. No assertion tighter than `Shape.getTolerance` — surface the floor, don't silently override.
- Every `ValidationReport` carries the banner: `freecad_version` (`shim.freecad_version()`), `element_map_version` (int or None), and — for the fault scorer's citable report — `validator_sensitivity`/`wilson_ci`. Verdict is DERIVED via `contracts.derive_verdict`, never asserted.
- Strictly read-only for the verify tools: `verify_sketch`/`verify_recompute` call `doc.recompute()` (a *read-refresh* the design mandates, not a mutation of intent) but open no transaction and write no property; `verify_shape` never recomputes. Reads run under `registry.with_document(doc, fn)` (single-writer lock). `ActiveDocument` never targeted; objects resolved by `Name`.
- Fault-suite scoring (AC2): a scorer runs `verify_shape` over every `g0/fault-injection/*/case.yaml` (planted `expectation: DETECT` must fail the reference assertion; `clean_control` `PASS_CLEAN` must pass all), computes `sensitivity = detected/planted`, `false_alarm = flagged/controls`, hashes the validator source → `validator_sha`, and writes `last_run` to `benchmarks/_registry/validators.yaml` in the design §6 shape. Stats (Wilson CI) live in a FreeCAD-free helper.
- In-FreeCAD behavior tested under FreeCADCmd in `tests/infc/` (stdlib `unittest`); surface/registration/schema and FreeCAD-free stats/fingerprint-comparison tested in `tests/external/` under pytest.

**Block If:**
- The installed FreeCAD build exposes neither `exportBinary` nor an `exportBrep`-to-stream path on `Part.TopoShape`, so `fingerprint()` cannot serialize a shape to deterministic bytes — HALT with the probed serializer surface (do not hash FCStd/tessellation, banned per AD-6).
- Running the fault scorer yields `verify_shape` sensitivity <95% or false-alarm >5% on the committed G0 fault suite, AND investigation shows the miss is a genuine validator defect (not a fixture/assertion bug) that cannot be resolved by tightening the validator within this story's scope — HALT with the per-case detection table so the tolerance/fixture question goes to a human (AD-13/AD-19).

**Never:**
- No mutation protocol wrapper (`run_mutation`, §1) and no TNP guard (`snapshot_references`/`audit_references`, §3) — those bind to mutation tools that do not exist until later stories; §1/§3 are out of scope (story references are §2/4/5 only).
- No `verify_export_*` (§6 = Story 1.7), no Phase-3 assertion primitives beyond the five forward-declared fault fns (`hole_*`, `distance_between`, `angle_between`, anchor frames = Phase 3), no `verify_visual` (§7a).
- No new contract wire types or `jsonschema/` files: reuse `FingerprintRecord`, `ValidationReport`, `ResultEnvelope`. The per-tool `outputSchema` stays the shared envelope schema; the report shape is validated by tests, not a new wire schema.
- No live-bridge gate runner rewrite: the stub runner (`benchmarks/runner.py`) stays stub-only. The fault scorer is a separate in-FreeCAD entry, not a new `--criterion faults` branch of the stub runner.
- Fingerprint scope is representation identity only — two independently rebuilt but geometrically equal shapes MAY hash differently; that is correct, do not "fix" it.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| fingerprint stable | `fingerprint(doc)` twice, no change | identical `digest`; `serializer` tag set; `fingerprints_equal(a,b)` True | — |
| fingerprint sensitive | box vs box +1µm length / added hole / mirror | different `digest` | — |
| fingerprint cross-tag | two records, different `serializer` | `fingerprints_equal` raises `ValueError` | by contract |
| verify_shape golden | `verify_shape{doc,object,checks:[expect_volume…]}` on a golden model | `verdict=OK`; every field within ±0.1%; banner present | — |
| verify_shape defect | fault fixture vs reference assertion | ≥1 check `passed=false`; `verdict=SPEC_FAILED` | — |
| verify_shape no shape | object with null/absent `Shape` | `INVALID_INPUT` | fail-closed |
| verify_sketch pass | fully-constrained sketch | `verdict=OK`, `fully_constrained=true`, `dof=0` | — |
| verify_sketch underconstrained | `dof>0` sketch | `verdict=SPEC_FAILED`, HARD-fail check | — |
| verify_sketch redundant | redundant-but-constrained sketch | `verdict=OK`; redundant listed in `warnings`, never fails | — |
| verify_sketch not a sketch | non-`Sketcher::` object | `INVALID_INPUT` | fail-closed |
| verify_recompute broken | doc with a deliberately invalid object | failing object `Name` + `getStatusString()` in a failed check; banner present | verdict per class |
| verify_recompute clean | all-valid doc | `verdict=OK`, no failed checks | — |
| bad handle | any verify tool, missing/stale/unknown `doc` | `INVALID_INPUT` | fail-closed |
| fault scorer | scorer over committed suite | writes `validator_sha`+`last_run{sensitivity,false_alarm,…}`; sensitivity ≥0.95 ∧ FA ≤0.05 | HALT if defect (Block If) |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/fingerprint.py` -- NEW. `fingerprint(doc) -> FingerprintRecord` (§2.2): serializer probed via `shim`, per-object `{name, brep_sha256, massprops}` sorted by `Name`, `digest = sha256(repr(entries))`, `serializer` tag. `_serialize(shape) -> bytes` (`exportBinary(io.BytesIO())` else `exportBrep`), `_massprops(shape) -> MassProps` (Q=1e-6 quantized volume/area/bbox/com/principal_moments). Stdlib + FreeCAD only; FreeCAD imported lazily.
- `src/freecad_buddy/usecases/verify.py` -- NEW. `verify_shape(registry, doc, object, checks) -> ResultEnvelope`, `verify_sketch(registry, doc, sketch) -> ResultEnvelope`, `verify_recompute(registry, doc) -> ResultEnvelope`. Each resolves via `registry.with_document`, builds a `ValidationReport` (banner from `shim`), derives verdict, wraps in an envelope. `verify_shape` dispatches the five assertion fns over `obj.Shape`; raise `ValidationError` for unknown object / null shape / non-sketch. Reuse local `_ok_envelope`/`_report_envelope`/`_banner` helpers (mirror `queries.py`). `_tol_close(measured, expected, tol)` shared with the golden/fault paths.
- `src/freecad_buddy/usecases/stats.py` -- NEW (FreeCAD-free). `wilson_ci(k, n, z=1.96) -> WilsonCI` closed form; `sensitivity(detected, planted)`, `false_alarm(flagged, controls)`. No FreeCAD import (importable from `tests/external`).
- `benchmarks/g0/fault-injection/score_verify_shape.py` -- NEW in-FreeCAD scorer (run under FreeCADCmd). Loads every `case.yaml`, opens each `fixture.FCStd`, runs `verify_shape` with the case's reference `assertions.checks`, records DETECT/PASS_CLEAN outcome per case, computes sensitivity/FA + `wilson_ci`, hashes `usecases/verify.py`+`usecases/fingerprint.py` source → `validator_sha`, and rewrites the `verify_shape` block of `_registry/validators.yaml` with `validator_sha` + `last_run{run_id,sensitivity,false_alarm,date,wilson_ci}`. Prints a per-case detection table to stderr. Exit non-zero if bars not met.
- `src/freecad_buddy/hosts/headless/entry.py` -- EXTEND `build_registry`: register `verify_shape` (`doc`,`object`,`checks` — checks optional array), `verify_sketch` (`doc`,`sketch`), `verify_recompute` (`doc`) as `RpcMethod(mutating=False)` with hand-authored `inputSchema` (`additionalProperties:false`), shared envelope `outputSchema`, one-line descriptions; handlers `marshaled` over registry-bound fns.
- `tests/infc/test_verify_tools.py` -- NEW FreeCADCmd suite: fingerprint stability + sensitivity (1µm/hole/mirror) + cross-tag raise; `verify_shape` golden pass (±0.1%) and defect fail and null-shape `INVALID_INPUT`; `verify_sketch` pass/under-constrained/redundant-warn/not-a-sketch; `verify_recompute` broken-object report + banner; bad handle `INVALID_INPUT`.
- `tests/infc/test_fault_score.py` -- NEW FreeCADCmd suite: run the scorer over the committed suite; assert sensitivity ≥0.95, false_alarm ≤0.05, and that each planted `DETECT` case is detected and the `clean_control` passes.
- `tests/external/test_mcp_surface.py` -- UPDATE: add `EXPECTED_VERIFY_TOOLS = {verify_shape, verify_sketch, verify_recompute}`; extend the exec-off exact-set assertion; assert each requires `doc` + rejects unknown keys; bad-handle dispatch of `verify_recompute` → `INVALID_INPUT`.
- `tests/external/test_stats.py` -- NEW pytest: `wilson_ci` closed-form values on known inputs; `sensitivity`/`false_alarm` arithmetic incl. zero-denominator guards.
- `tests/external/test_fingerprint_contract.py` -- NEW pytest (FreeCAD-free): `fingerprints_equal` behavior is already covered in `test_contracts`; here assert `fingerprint` module imports without FreeCAD and its helpers raise cleanly when FreeCAD is absent (or fold into existing contract test if lighter).

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` + `application-design/index.md` if present; else the `project-context.md` distillation governs.
  - Re-read `verification-design.md` §2 (fingerprint), §4 (verify_sketch), §5 (verify_shape), §8 (tolerance policy), §9 (verification obligations); `validation-harness-design.md` §6 (fault framework + `validators.yaml` shape) + §4 (Wilson CI formula); `data-contracts-design.md` (FingerprintRecord/ValidationReport/banner).
  - Re-read `project-context.md` "Architecture Ring & Import Rules", "FreeCAD API Traps" (sketch pass signal AFTER recompute; Name vs Label; ActiveDocument banned; serializer-tagged fingerprint, cross-tag compare banned), "Wire & Schema Rules", "Verification & Validation Discipline", "Units".
  - Read `benchmarks/g0/fault-injection/README.md` (the five forward-declared `fn`s + detection rule) and the committed `case.yaml`s.
  - Load `typescript-clean-code` (naming/commenting discipline, applied to Python). Load `typescript-unit-testing` (AAA/test-quality, applied to `unittest`/pytest).
  - Read the Story 1.5 spec's Design Notes + `usecases/queries.py`, `usecases/documents.py`, `usecases/shim.py`, `contracts/fingerprint.py`, `contracts/report.py`, `hosts/headless/entry.py`, `tests/infc/test_query_tools.py`, `tests/infc/test_golden_models.py`, `tests/external/test_mcp_surface.py` for the established patterns.

**Execution:**
- [x] `src/freecad_buddy/usecases/fingerprint.py` -- implement `fingerprint()` + `_serialize`/`_massprops`; serializer via shim; skip null/absent `Shape`. -- AD-6 single fingerprint oracle.
- [x] `src/freecad_buddy/usecases/stats.py` -- `wilson_ci`/`sensitivity`/`false_alarm`, FreeCAD-free. -- rate reporting (AD-14/§4).
- [x] `src/freecad_buddy/usecases/verify.py` -- `verify_shape`/`verify_sketch`/`verify_recompute`, banner + derived verdict, `ValidationError` on bad object/shape/sketch. -- AD-8/§4/§5 validators.
- [x] `src/freecad_buddy/hosts/headless/entry.py` -- register the three verify tools (`mutating=False`, per-tool inputSchema, `additionalProperties:false`, description). -- surface exposure / G0.2 count.
- [x] `benchmarks/g0/fault-injection/score_verify_shape.py` -- in-FreeCAD scorer writing `validator_sha`+`last_run` to `validators.yaml`; per-case table; exit non-zero if bars unmet. -- NFR2 citable-score binding.
- [x] `tests/infc/test_verify_tools.py` -- FreeCADCmd coverage of every verify tool + fingerprint stability/sensitivity/cross-tag (golden values analytic, never captured from the impl). -- AC coverage.
- [x] `tests/infc/test_fault_score.py` -- scorer over the committed suite meets ≥95%/≤5% bars with per-case detection. -- AC2.
- [x] `tests/external/test_mcp_surface.py` -- add verify tools to the exact-set + schema + bad-handle assertions. -- surface regression guard.
- [x] `tests/external/test_stats.py` -- Wilson CI + rate arithmetic + zero-denominator guards. -- stats unit coverage.

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- rings clean (verify/fingerprint stay in usecases; no mcp/Qt leak; stats FreeCAD-free). -- `check_imports OK`.
- [x] `uv run ruff check .` -- clean (T201 honored; scorer stderr table via `sys.stderr`, not `print` in server code — the scorer is a benchmark script, confirm its ruff scope). -- `All checks passed!`.
- [x] `uv run ruff format` (changed files) -- formatted.
- [x] `uv run pytest tests/external -q` -- all green (surface + stats). -- 121 passed.
- [x] `"FreeCADCmd" tests/run_tests.py` -- verify + fault-score suites + prior infc suites green (local FreeCAD 1.1). -- Ran 47 tests, OK, exit 0. Scorer: sensitivity 1.000, false_alarm 0.000.

**Acceptance Criteria:**
- Given the 5 golden models with their `expected.yaml` bands, when `verify_shape` runs each with the matching assertion checks, then volume/bbox/counts/validity all pass within ±0.1% and the report carries the banner (G0.3).
- Given the committed G0 fault-injection suite, when the fault scorer runs, then `verify_shape` shows sensitivity ≥95% and false-alarm ≤5%, and the result is recorded in `_registry/validators.yaml` with a current `validator_sha` and a `last_run` (with Wilson CI) (NFR2).
- Given one document fingerprinted twice without change, when `fingerprint()` runs (serializer probed + tagged), then digests are identical; a 1µm dimension change, an added hole, or a mirror produces a different digest; cross-tag comparison raises `ValueError` (AD-6).
- Given a sketch in any state, when `verify_sketch` runs after recompute, then the verdict follows AD-8 exactly: PASS ⇔ `FullyConstrained`; HARD FAIL on conflicting/malformed/over/under/degenerate; redundant = WARN only; `solve()` codes logging-only.
- Given a document with a deliberately broken object, when `verify_recompute` runs, then the failing object + its `getStatusString()` reason appear in the report and every report carries the banner (FreeCAD version, `element_map_version`, validator sensitivity where a rate is claimed).
- Given `tools/list` with exec off, when enumerated, then the surface additionally lists `verify_shape`/`verify_sketch`/`verify_recompute`, each with a `doc`-requiring `inputSchema` (`additionalProperties:false`), the shared envelope `outputSchema`, a description, and underscore names.
- Given any verify tool with a missing/stale/unknown `doc` (or an unknown object / null `Shape` / non-sketch), when dispatched, then the result is `INVALID_INPUT` (fail-closed) and `ActiveDocument` is never targeted.

## Spec Change Log

## Review Triage Log

### 2026-07-22 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 0, medium 1, low 4)
- defer: 5
- reject: 8
- addressed_findings:
  - `[medium]` `[patch]` `verify.py` `_report_envelope` set `detail: None` on every verdict; a non-`OK` result (`SPEC_FAILED`/`RECOMPUTE_ERROR`) then violated the `ResultEnvelope` contract (`detail` required non-null unless status `OK`). Added `_failure_detail` building an `ErrorDetail{code, message, objects}` from the failed checks; `detail` is now null only when `OK`. New infc assertion pins the non-null detail on a defect.
  - `[low]` `[patch]` `verify.py` `verify_shape` `expect_bbox` with an expect list of length ≠ 3 raised `IndexError` → `RECOMPUTE_ERROR` (not fail-closed `INVALID_INPUT`), and a non-dict `check` raised `AttributeError` → `RECOMPUTE_ERROR`. Both now raise `ValidationError` → `INVALID_INPUT`. New infc test covers the bbox-length case.
  - `[low]` `[patch]` `verify.py` `_tol_close` collapsed the band to the (often 0) shape-tolerance floor when a `tol` dict was present but carried neither `rel` nor `abs`, demanding exact equality and spuriously failing. Added `_has_band`; `_check_expect_volume`/`_check_expect_bbox` fall back to their default band unless `tol` has a usable `rel`/`abs`.
  - `[low]` `[patch]` `fingerprint.py` a degenerate shape's `nan`/`inf` mass property flowed through `round()` into the record and made `mirror_text` emit invalid-JSON `NaN`. `_quantize` now floors non-finite values to `0.0`. Also corrected the module docstring, which described the mass-prop tuple as an "independent cross-oracle" though the impl (per spec §68) folds it into the primary digest.
  - `[low]` `[patch]` `score_verify_shape.py` `_score_case` opened each fixture twice (raw `App.openDocument` + `registry.document_open`) and closed only the raw handle, leaking registry handles across cases. Now opens once via the registry, reads the object name through `with_document`, and closes via `registry.document_close`; the now-unused `FreeCAD` import was dropped.
- deferred_findings:
  - `verify_sketch` gates `evaluateConstraints()` behind `bool(MalformedConstraints)`; AD-8/design §4 list `evaluateConstraints()` as an independent hard-fail trigger. On FreeCAD 1.1 the method returns `True` for a healthy fully-constrained sketch (a build divergence, documented inline), so it cannot be used unconditionally — but a genuinely malformed sketch whose `MalformedConstraints` property is empty could slip past. Not demonstrated reachable on 1.0/1.1 (bad-index constraints raise at `addConstraint`), real forward gap.
  - The fault scorer full-clobbers `validators.yaml` from a fixed template; if a second validator block is ever added it would be dropped on the next run. Only `verify_shape` exists now.
  - The scorer's hand-rolled `case.yaml` parser (`_CHECK_RE` greedy match, `.replace('rel'/'abs')` before `ast.literal_eval`) is brittle to check text containing those substrings or multi-line flow mappings; works on the committed fixtures only.
  - `_is_watertight`/`_shape_floor` swallow any exception → "not watertight"/floor `0.0`; a solid whose `getTolerance()` genuinely raises would silently disable the tolerance-floor clamp. Not a Phase-0 path.
  - `fingerprint._serialize` aborts the whole fingerprint if `exportBinary` raises on a specific shape (no per-shape `exportBrep` fallback); the serializer is process-global probed and tested, so this needs a shape that supports the probe but fails the call.
  - rejected (noise / by-design / not reachable): mass-prop "cross-oracle" not independently comparable (spec §68 defines the digest as `sha256(repr(entries))` including massprops — impl follows the spec; massprops remain on each `objects[]` entry for diff use); `test_harness_g0` asserts the score from the committed `validators.yaml` rather than a fresh run (correct AD-12 split — the fresh in-FreeCAD run is `tests/infc/test_fault_score.py`; the external test validates the stored binding artifact); `test_checkless_call` "tautological" (it also asserts the measured volume within ±0.1% of the analytic value — a real check); `wilson_ci` negative-`z` guard (`z` is the fixed internal constant `Z_95`, never caller-supplied); `verify_recompute` `"Invalid" in list(State)` substring risk (FreeCAD `State` is always a status-string tuple, never a bare string); `object` param shadows builtin (matches the schema key; the 1.4/1.5 pattern); dof<0 "not reported as over-constrained" (verdict is correct; the detail carries the dof value); non-numeric `expect`/`tol` "not mapped to INVALID_INPUT" (dispatch maps `TypeError`/`ValueError`/`KeyError` → `INVALID_INPUT`, so `float(None)`/`float("x")` already fail closed).

## Design Notes

- **`verify_shape` assertion binding.** The `checks` param is a list of `{fn, expect, tol?}` mirroring a `case.yaml`'s `assertions.checks`. Each `fn` maps to one measurement over `obj.Shape` producing a `Check`. This lets the same code path serve (a) the golden-model check, (b) the fault scorer, and (c) a live MCP `verify_shape` call. When `checks` is omitted, return the measured shape facts (volume/bbox/counts/valid/watertight) with `passed=true` and no expected — a bare shape report, matching §5's "reported; compared when expected".
- **Tolerance floor.** `_tol_close` honors `{rel}`/`{abs}` from the case, defaulting to the §8 table, but never asserts tighter than `Shape.getTolerance` — surface the floor in `detail` when it clamps. Do not silently widen a spec's tolerance.
- **Banner `element_map_version`.** `shim.element_map_available()` is a bool; the banner wants `int | None`. Use the element-map version int where the build exposes it (probe `ElementMapVersion` on a shape), else `None` — never the string `"n/a"` (report_build precedent). If no clean int probe exists on 1.0/1.1, `None` is acceptable and the `element_map_available` bool stays in `query_capabilities`, not the report banner.
- **Fault scorer detection rule.** A planted `DETECT` case is *detected* when `verify_shape` returns a non-OK verdict against the case's reference assertions (the fixture deviates from the reference, so ≥1 check fails). A `clean_control` is a *false alarm* when it returns non-OK. `sensitivity = detected_defects / planted_defects`; `false_alarm = flagged_controls / clean_controls`. Do not hand-set any assertion to the defective value.
- **Example fingerprint record (box doc):**
  ```python
  {"schema": "fcb.fingerprint/1", "serializer": "exportBinary",
   "objects": [{"name": "Box", "brep_sha256": "…",
                "massprops": {"volume": 6000.0, "area": 2200.0, "bbox": [...],
                              "com": [5.0, 10.0, 15.0], "principal_moments": [...],
                              "quantum": 1e-6}}],
   "digest": "…"}
  ```
- **Example verify_sketch report:** `checks=[{id:"sketch.fully_constrained", measured:true, expected:true, passed:true}]`, `warnings=[{id:"sketch.redundant", measured:[…], passed:false}]`, `banner={freecad_version:"1.1.1", element_map_version:None}`, `verdict="OK"`.

## Verification

**Commands:**
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`.
- `uv run ruff check .` -- expected: clean.
- `uv run pytest tests/external -q` -- expected: all pass (surface + stats + fingerprint-import).
- `"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" tests/run_tests.py` -- expected: `test_verify_tools` + `test_fault_score` + prior infc suites green.
- `"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" benchmarks/g0/fault-injection/score_verify_shape.py` -- expected: sensitivity ≥0.95, FA ≤0.05; `validators.yaml` updated with `validator_sha` + `last_run`.

**Manual checks:**
- Over a running `uv run freecad-buddy serve --transport stdio --mode inline`, `tools/list` shows the three `verify_*` tools; calling `verify_shape` on an open box doc returns a banner-carrying report.

## Auto Run Result

Status: done

**Change summary:** Implemented the verify-first core (verification-design §2/4/5): a single `fingerprint()` oracle (AD-6), the `verify_shape`/`verify_sketch`/`verify_recompute` validators returning banner-carrying `ValidationReport`s with derived verdicts, their MCP registration (`mutating=False`), a FreeCAD-free Wilson-CI stats helper, and an in-FreeCAD fault scorer that ran `verify_shape` over the committed G0 fault suite and bound its citable score into `validators.yaml`. One review pass applied 5 patches (1 medium envelope-contract fix + 4 low robustness fixes), deferred 5 forward-looking gaps, and rejected 8 non-issues; no intent gap, no spec amendment.

**Files created:**
- `src/freecad_buddy/usecases/fingerprint.py` — `fingerprint(doc)`: SHA-256 over per-object serialized shape bytes (sorted by `Name`) + quantized (Q=1e-6) mass-props; serializer shim-probed/tagged; null-shape skipped; non-finite mass-props floored.
- `src/freecad_buddy/usecases/stats.py` — FreeCAD-free `wilson_ci`/`sensitivity`/`false_alarm`.
- `src/freecad_buddy/usecases/verify.py` — `verify_shape` (binds the 5 forward-declared assertion fns, tolerance-floor clamp, checkless bare-facts path, non-null failure detail), `verify_sketch` (AD-8 PASS⇔`FullyConstrained` after recompute; redundant=WARN), `verify_recompute` (failing objects + `getStatusString()`, `RECOMPUTE_ERROR` class).
- `benchmarks/g0/fault-injection/score_verify_shape.py` — in-FreeCAD fault scorer; writes `validator_sha`+`last_run`+`wilson_ci`.
- `tests/infc/test_verify_tools.py`, `tests/infc/test_fault_score.py`, `tests/external/test_stats.py`, `tests/external/test_fingerprint_contract.py`.

**Files changed:**
- `src/freecad_buddy/usecases/shim.py` — added `element_map_version() -> int | None`.
- `src/freecad_buddy/hosts/headless/entry.py` — registered `verify_shape`/`verify_sketch`/`verify_recompute` (`mutating=False`).
- `tests/external/test_mcp_surface.py` — `EXPECTED_VERIFY_TOOLS`, extended exact-set + schema + bad-handle assertions.
- `tests/external/test_harness_g0.py` — assert the scored `last_run` (sensitivity ≥0.95, FA ≤0.05, non-null `validator_sha`).
- `benchmarks/_registry/validators.yaml` — scored: sensitivity 1.0, false_alarm 0.0, Wilson [0.741, 1.0].
- `tests/run_tests.py` — additive top-level-script guard so `FreeCADCmd tests/run_tests.py` runs discovery on Windows (the `__main__` guard alone did not fire there).

**Review findings breakdown:** intent_gap 0 · bad_spec 0 · patch 5 (medium 1, low 4 — all applied) · defer 5 (appended to `deferred-work.md`) · reject 8.

**Verification performed (independently re-run after patches):**
- `uv run python scripts/check_imports.py` → `check_imports OK`.
- `uv run ruff check .` → `All checks passed!`; `uv run ruff format` applied.
- `uv run pytest tests/external -q` → 121 passed.
- `FreeCADCmd tests/run_tests.py` → Ran 48 tests, OK, exit 0 (verify + fault-score + prior infc suites).
- `FreeCADCmd benchmarks/g0/fault-injection/score_verify_shape.py` → 11/11 planted DETECTED, clean control PASS_CLEAN, sensitivity 1.000, false_alarm 0.000, `validators.yaml` written, exit 0.

**AC status:** all 7 Acceptance Criteria satisfied (golden verify_shape ±0.1% + banner; fault ≥95%/≤5% recorded with sha+last_run+Wilson; fingerprint stable/sensitive/cross-tag-raise; sketch AD-8 verdict; recompute broken-object report+banner; surface lists the 3 verify tools with doc-requiring schemas; fail-closed `INVALID_INPUT`).

**Build-specific notes (resolved in-scope, no fixture loosened):** FreeCAD 1.1 `exportBinary` takes a filename not a stream (temp-file read-back via `FCB_TMP_` prefix; verified deterministic + 1µm-sensitive); `evaluateConstraints()` returns True for a healthy sketch on 1.1 (gated behind `MalformedConstraints`, deferred as an AD-8 forward gap); `element_map_version` is `None` on 1.1 (no clean int probe on a bare shape).

**Residual risks:** the 5 deferred items (sketch `evaluateConstraints` gate; scorer full-clobber of a multi-validator `validators.yaml`; brittle in-FreeCAD `case.yaml` parser; swallowed watertight/tolerance-floor exceptions; no per-shape `exportBrep` fallback) are unreachable on well-formed Phase-0 documents but are real forward-looking gaps.
