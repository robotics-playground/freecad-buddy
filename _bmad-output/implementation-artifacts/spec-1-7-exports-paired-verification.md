---
title: 'Story 1.7 — Exports with Paired Verification'
type: 'feature'
created: '2026-07-22'
status: 'done'
review_loop_iteration: 0
baseline_revision: 'f9cea858cdc73544507c57211e0964b0165e9a61'
final_revision: '42d228c'
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/technical-freecad-3mf-export-fidelity-research-2026-07-20.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** The bridge has no way to emit STEP/STL/3MF and no way to prove an export is faithful; "the file was written" must never count as success (AD-9). Exports and their paired re-import verifiers are the last Phase-0 tool family before the GUI host and G0 exit.

**Approach:** Add `export_step`/`export_stl`/`export_3mf` (in-FreeCAD writers) that always report `verified: false`, and the paired `verify_export_step`/`verify_export_stl`/`verify_export_3mf` that re-read the written file with independent oracles (STEP: FreeCAD re-import round-trip; STL/3MF: trimesh + second oracle + lib3mf + FreeCAD self-read) and return a `ValidationReport`. Oracle code (third-party) lives in `adapters/`; writers and the FreeCAD self-read legs live in `usecases/` (FreeCAD-only). Land an export fault-injection suite proving each verifier at sensitivity ≥95% / false-alarm ≤5%.

## Boundaries & Constraints

**Always:**
- Ring rules: writers + FreeCAD self-read/round-trip legs are `usecases/` (stdlib + FreeCAD-App whitelist only — `Part`, `MeshPart`, `Mesh`). Oracle wrappers (`trimesh`, `lib3mf`, second STL oracle) are `adapters/export_oracle.py` (third-party allowed, NO FreeCAD import). Verdict assembly for STL/3MF is orchestrated in the host handler (`hosts/`), merging the marshaled self-read leg with the un-marshaled oracle legs (§6.1).
- One tessellation source: `MeshPart.meshFromShape(shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False)` feeds BOTH STL and 3MF (linear + angular deflection — #25311). STL and 3MF must never diverge because they share one mesh.
- STEP pins config per call: `write.step.unit=MM` via the shim (`Part.setStaticValue("write.step.unit","MM")`) AND the STEP schema (`AP242`/`AP214`) set through the shim's schema accessor (the `Mod/Part/STEP` `Scheme` preference — `write.step.schema` is NOT settable via `setStaticValue` on 1.0/1.1). Never trust ambient defaults.
- `export_*` writes and returns `{export_id, path, bytes, verified: false}`; `verified` is `const false` in its outputSchema. An export is "done" only after the paired `verify_export_*` returns verdict `PASS`/`OK`.
- Export id binds the pair: `export_*` mints an `export_id` (record path, source doc handle, format, tessellation params, source shape facts); `verify_export_*` takes `{doc, export_id}` and looks the record up. Unknown/stale `export_id` or `doc` → `INVALID_INPUT` (fail-closed).
- Independent-oracle disagreement = FAIL, never averaged. Mesh volume tolerance is derived from the tessellation deflection used, never ±0.1%. STEP volume tolerance is ±0.1% (AD-9 fixed); topology counts (faces/edges/solids) must match exactly.
- Verdict is DERIVED from checks via `derive_verdict` (never asserted); every report carries the banner (FreeCAD version, element_map_version, and validator sensitivity where a rate is claimed). Reuse the `verify.py` envelope/report helpers.
- Golden reference values in tests are hand-computed / analytic, never captured from the implementation under test. The producing agent never grades itself.
- Fault-suite scorer for the export verifiers MUST preserve the existing `verify_shape` block in `benchmarks/_registry/validators.yaml` (load-merge, never full-clobber); it writes only the `verify_export_*` blocks with `validator_sha` + `last_run` (Wilson CI).
- Reserved TempDoc prefix `FCB_TMP_` for any transient re-import document; clean up documents opened for round-trip in a `finally`.

**Block If:**
- The second STL oracle pin cannot be satisfied on the CI legs (admesh is Linux-only + dormant). If no deterministic, dependency-available second oracle can be implemented for the `SecondStlOracle` interface on the uv leg, HALT with blocking condition `stl second-oracle unresolvable`. (Default plan: a from-scratch stdlib+numpy independent STL mesh checker — parse facets, assert manifold edge-pairing / winding / non-degeneracy independently of trimesh's loader. This is glue, not a forked tool.)

**Never:**
- No slicer-acceptance smoke test and no lib3mf-as-fallback-writer — both are Phase-4 realism-gate scope (spine Deferred). This story is FreeCAD-writer + independent-oracle validation only.
- No new wire-status variants; the closed set stands. No `print()` in server/usecase code (T201); scorer diagnostics go to `sys.stderr`.
- Do not add export tools to any mutation preview/confirm gate work (Phase 2). Do not touch the render/screenshot path.
- Do not fix or refactor the Story-1.6 `score_verify_shape.py` clobber beyond what a shared merge helper strictly needs; log it as a cross-story deferral.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| STEP export happy | golden box doc, `export_step{doc,path}` | file written; `{export_id,path,bytes,verified:false}`; AP242+MM pinned | none |
| STEP verify pass | `verify_export_step{doc,export_id}` | re-import fresh doc; volume ≤0.1%, isValid, counts equal → verdict OK, banner present | none |
| STEP verify fail | export then source shape mutated / dropped solid | volume/count mismatch → verdict FAIL, non-null detail | none |
| Mesh export happy | solid doc, `export_stl`/`export_3mf` | both from one `meshFromShape`; `verified:false`; facet count recorded | none |
| STL verify pass | `verify_export_stl{doc,export_id}` | trimesh watertight/winding/volume-band + second oracle agree → OK | none |
| STL oracle disagree | trimesh OK but second oracle flags unconnected facets | verdict FAIL (disagreement = signal) | none |
| 3MF unit lie | source doc not mm / writer hardcoded-mm mismatch | lib3mf unit check fails → FAIL | none |
| 3MF type-model lie | non-watertight mesh labelled `type="model"` | lib3mf manifold-flag-vs-geometry check fails → FAIL | none |
| bad export_id | `verify_export_*{doc, export_id:"nope"}` | INVALID_INPUT (fail-closed) | ValidationError → INVALID_INPUT |
| missing/stale doc | any tool, unknown handle | INVALID_INPUT; ActiveDocument never targeted | ValidationError → INVALID_INPUT |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/exports.py` -- NEW. `export_step(registry, doc, path, objects=None, ap="AP242")`, `export_stl(registry, doc, path, objects=None, linear=None, angular=None)`, `export_3mf(...)` -- resolve via `registry.with_document`; STEP via `shim.pin_step_config(ap)` + `Shape.exportStep(path)`; mesh via `MeshPart.meshFromShape(...)` → `Mesh.Mesh(...).write(path)` (STL) / `Mesh` 3MF export from the same mesh. Each mints an `export_id`, records `{path, doc, format, tess, source_facts}` in a module-level `ExportRegistry` (or on `registry`), returns `{export_id, path, bytes, verified: false}`. NEW `verify_export_step(registry, doc, export_id)` -- pure in-FreeCAD: open the file into a `FCB_TMP_` fresh doc, `verify_shape`-style checks (volume ±0.1%, isValid, face/edge/solid counts equal to recorded source), close in `finally`, build report via shared helpers. NEW `export_self_read_stl`/`export_self_read_3mf(registry, export_id)` -- FreeCAD self-read leg: re-import mesh, return facet/vertex counts + bbox facts (no verdict). FreeCAD-only.
- `src/freecad_buddy/usecases/shim.py` -- EXTEND. `pin_step_config(ap: str) -> None` (set `Part.setStaticValue("write.step.unit","MM")` + STEP `Scheme` preference to `ap`); `step_schema() -> str` reads back the pinned scheme for the report. Version-sensitive knob isolation (AD-11).
- `src/freecad_buddy/adapters/export_oracle.py` -- NEW (third-party; NO FreeCAD). `stl_oracle(path, expected_volume, deflection) -> dict` (trimesh: is_watertight/is_winding_consistent/is_volume/volume-band/euler); `SecondStlOracle` protocol + default `StdlibStlOracle` (independent facet parse: manifold edge-pairing, winding, degeneracy); `mesh3mf_oracle(path, source_is_mm, expected_volume, deflection) -> dict` (lib3mf: parses clean, unit==millimeter, `IsManifoldAndOriented()` consistent with declared type, metadata present; trimesh geometry layer). Each returns per-oracle `{checks:[...], ok:bool}`; disagreement across oracles is surfaced, not merged.
- `src/freecad_buddy/hosts/headless/entry.py` -- EXTEND `build_registry`: register `export_step`/`export_stl`/`export_3mf` (`mutating=True`, per-tool inputSchema with `additionalProperties:false`, `verified:false` documented), `verify_export_step` (`mutating=False`, marshaled usecase), and `verify_export_stl`/`verify_export_3mf` (`mutating=False`) whose handlers MERGE the marshaled self-read leg with the un-marshaled `export_oracle` legs into one `ResultEnvelope`. One-line descriptions; shared envelope outputSchema.
- `src/freecad_buddy/adapters/export_verdict.py` -- NEW (or a function in `export_oracle.py`): `assemble_export_verdict(oracle_legs, self_read_facts, banner) -> ResultEnvelope` — combine per-leg checks, force FAIL on any leg failure OR cross-oracle disagreement, derive verdict, wrap with banner. (Banner passed in from the marshaled leg so no FreeCAD import here.)
- `benchmarks/g0/export-fault-injection/` -- NEW suite. `README.md` (§9 export faults, closed set), `build_export_fault_fixtures.py` (FreeCADCmd; writes exported files + `case.yaml` per case), planted cases: `step-dropped-solid`, `step-unit-lie`, `stl-hole` (deleted triangle), `stl-flipped-normals`, `stl-non-manifold`, `3mf-type-model-lie` (open surface labelled model), `3mf-unit-lie`, `3mf-corrupt-container`, plus `clean-control` per format. Each `case.yaml`: `targets_validator`, `format`, `expectation: DETECT|PASS_CLEAN`, reference facts.
- `benchmarks/g0/export-fault-injection/score_export_verify.py` -- NEW scorer (FreeCADCmd for self-read legs; but oracle legs need trimesh/lib3mf). Since no single leg has both FreeCAD and oracles, the scorer runs the oracle legs directly against the committed exported fixture files (which do not need FreeCAD to re-read) and the STEP/self-read legs via the registry; computes sensitivity/FA + Wilson CI per verifier; merges into `validators.yaml` preserving `verify_shape`. Hashes `usecases/exports.py`+`adapters/export_oracle.py`+`adapters/export_verdict.py` → per-verifier `validator_sha`.
- `benchmarks/_registry/validators.yaml` -- EXTEND: add `verify_export_step`/`verify_export_stl`/`verify_export_3mf` blocks (merge, preserve `verify_shape`).
- `tests/infc/test_export_tools.py` -- NEW FreeCADCmd suite: golden-model `export_step`→`verify_export_step` round-trip (volume ±0.1%, counts equal, banner); `export_stl`/`export_3mf` share one tessellation (assert equal facet count); `verified:false` on export; bad `export_id`/`doc` → INVALID_INPUT; self-read legs return facet/vertex/bbox facts.
- `tests/external/test_export_oracle.py` -- NEW pytest (trimesh+lib3mf, NO FreeCAD): `stl_oracle` on a committed clean STL passes; on a holed/flipped/non-manifold STL fails; `StdlibStlOracle` agrees on clean, flags the defects; `mesh3mf_oracle` catches unit-lie + type-model-lie + corrupt container; cross-oracle disagreement forces fail in `assemble_export_verdict`.
- `tests/external/test_export_fault_score.py` -- NEW pytest: run the oracle-side scoring over the committed export fault suite; assert sensitivity ≥0.95, FA ≤0.05 for the oracle-checkable verifiers (STL/3MF); each planted DETECT flagged, clean control passes.
- `tests/external/test_mcp_surface.py` -- UPDATE: add `EXPECTED_EXPORT_TOOLS = {export_step, export_stl, export_3mf}` and extend `EXPECTED_VERIFY_TOOLS` with the three `verify_export_*`; assert exact-set (exec off), each requires its params + rejects unknown keys, `export_*` outputSchema documents `verified`, bad-handle dispatch → INVALID_INPUT.

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `project-context.md` (Ring & Import Rules; FreeCAD API Traps — mesh single-tessellation-source #25311, STEP `write.step.unit=MM` per call, Name vs Label, ActiveDocument banned; Wire & Schema Rules; Verification & Validation Discipline; Units).
  - Re-read `verification-design.md` §6 (verify_export_* orchestration split, STEP/STL/3MF legs), §8 (tolerance policy — mesh band from deflection, STEP ±0.1%), §9 (export fault list); `mcp-tools-design.md` §3.5 (export_step/verify_export_step schemas, `verified:false`) + §2 export/verify inventory.
  - Re-read the `technical-freecad-3mf-export-fidelity-research` report: `MeshPart.meshFromShape` signature; `Shape.exportStep`; lib3mf `IsManifoldAndOriented`/unit checks; trimesh `is_watertight`/`is_winding_consistent`/`is_volume`/`volume`/`euler_number`; the type-model/unit/partial-export lies to catch.
  - Read Story 1.6 spec Design Notes + `usecases/verify.py` (envelope/report/banner helpers, `derive_verdict`, `_tol_close`), `usecases/documents.py` (registry API), `usecases/shim.py`, `hosts/headless/entry.py` (registration pattern), `benchmarks/g0/fault-injection/score_verify_shape.py` + `README.md`, `benchmarks/_registry/validators.yaml`, `tests/infc/test_verify_tools.py`, `tests/external/test_mcp_surface.py`.
  - Load `typescript-clean-code` (naming/commenting, applied to Python). Load `typescript-unit-testing` (AAA, applied to `unittest`/pytest).

**Execution:**
- [x] `src/freecad_buddy/usecases/shim.py` -- `pin_step_config(ap)` + `step_schema()`; version-sensitive STEP knob isolation. -- AD-11 / §6.2.
- [x] `src/freecad_buddy/usecases/exports.py` -- `export_step`/`export_stl`/`export_3mf` writers (one tessellation source), `export_id` record, `verified:false`; `verify_export_step` in-FreeCAD round-trip; `export_self_read_stl`/`_3mf` self-read legs. -- AC1/AC2, §6.
- [x] `src/freecad_buddy/adapters/export_oracle.py` -- trimesh + `SecondStlOracle`/`StdlibStlOracle` + lib3mf oracle wrappers; per-leg facts, no FreeCAD. -- AC3, §6.3/§6.4.
- [x] `src/freecad_buddy/adapters/export_verdict.py` -- `assemble_export_verdict`: merge legs, FAIL on any leg fail or cross-oracle disagreement, derive verdict + banner. -- AC3.
- [x] `src/freecad_buddy/hosts/headless/entry.py` -- register the 3 export + 3 verify_export tools; STL/3MF verify handlers merge marshaled self-read leg with oracle legs. -- surface / G0.2.
- [x] `benchmarks/g0/export-fault-injection/` (README + fixtures builder + `case.yaml`s) -- planted §9 export faults + clean controls. -- AC4.
- [x] `benchmarks/g0/export-fault-injection/score_export_verify.py` -- score verifiers; MERGE into `validators.yaml` preserving `verify_shape`; per-verifier `validator_sha`+`last_run`+Wilson CI; exit non-zero if bars unmet. -- AC4 / NFR2.
- [x] `benchmarks/_registry/validators.yaml` -- add `verify_export_*` blocks. -- NFR2 binding.
- [x] `tests/infc/test_export_tools.py` -- FreeCADCmd: export→verify_export_step round-trip, shared-tessellation equality, `verified:false`, bad-id/handle INVALID_INPUT, self-read facts. -- AC1/AC2 coverage.
- [x] `tests/external/test_export_oracle.py` -- pytest: oracle pass/fail on clean vs planted meshes; cross-oracle disagreement → FAIL. -- AC3 coverage.
- [x] `tests/external/test_export_fault_score.py` -- pytest: oracle-side scoring meets ≥95%/≤5% per verifier. -- AC4.
- [x] `tests/external/test_mcp_surface.py` -- add export + verify_export tools to exact-set + schema + bad-handle assertions. -- surface guard.

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- rings clean (exports/shim FreeCAD-only; oracle/verdict adapters third-party, no FreeCAD; merge in hosts). -- `check_imports OK`.
- [x] `uv run ruff check .` -- clean (T201 honored; scorer stderr via `sys.stderr`). -- `All checks passed!`.
- [x] `uv run ruff format` (changed files) -- formatted.
- [x] `uv run python scripts/gen_schemas.py --check` -- schemas byte-identical (contracts untouched). -- `gen_schemas --check OK`.
- [x] `uv run pytest tests/external -q` -- all green (oracle + fault score + surface). -- 137 passed.
- [x] `"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" tests/run_tests.py` -- export + prior infc suites green. -- Ran 59 tests, OK. Scorers: verify_export_step/stl/3mf sensitivity 1.000, false_alarm 0.000.

**Acceptance Criteria:**
- Given a golden model, when `export_step` (AP242, unit=MM pinned per call) then `verify_export_step` run, then re-import into a fresh document shows volume within ±0.1%, `isValid`, and face/edge/solid counts equal to the source; the report carries the banner (G0.5).
- Given the same solid, when `export_stl` and `export_3mf` run, then both consume one `MeshPart.meshFromShape` tessellation (linear + angular deflection — identical facet count), and each `export_*` result carries `verified: false` until its paired verify passes.
- Given the mesh exports, when `verify_export_stl` (trimesh + second oracle) and `verify_export_3mf` (lib3mf + trimesh + FreeCAD self-read) run, then any oracle disagreement forces verdict FAIL, the mesh volume tolerance derives from the deflection used (never ±0.1%), and the 3MF unit-lie and `type="model"`-on-open-surface faults are caught.
- Given the export fault cases (dropped solid, unit lie, hole, flipped normals, non-manifold, corrupt container), when the fault scorer runs, then each `verify_export_*` shows sensitivity ≥95% / false-alarm ≤5%, recorded in `validators.yaml` with a current `validator_sha` + `last_run` (Wilson CI), and the `verify_shape` block is preserved.
- Given any export/verify tool with a missing/stale/unknown `doc` or `export_id`, when dispatched, then the result is `INVALID_INPUT` (fail-closed) and `ActiveDocument` is never targeted.

## Spec Change Log

## Review Triage Log

### 2026-07-22 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 0, medium 3, low 2)
- defer: 3
- reject: 15
- addressed_findings:
  - `[medium]` `[patch]` `verify_export_step` did not check the resolved `export_id`'s format, so an STL/3MF id ran the STEP reader on a mesh file (spurious FAIL / reader crash) instead of fail-closed `INVALID_INPUT` — inconsistent with the mesh self-read leg, which already guards `entry["format"]`. Added the `format != "step"` guard mirroring `_self_read`; new infc test `test_verify_export_step_rejects_non_step_export_id`.
  - `[medium]` `[patch]` The STL/3MF mesh-verify handler in `entry.py` called the third-party oracle legs OUTSIDE any try/except: a missing/corrupt/deleted export file or a 0-triangle lib3mf mesh raised out of the oracle (`ValueError` → mislabeled `INVALID_INPUT`, or an unmapped exception → `RECOMPUTE_ERROR` crash) rather than reading as a verification FAIL. Added `export_oracle.safe_oracle(name, fn)` turning any oracle failure into a failed leg (`<name>.readable` check, `ok=False`); the handler now wraps every oracle call. New external tests pin missing-file → failed leg → FAIL verdict.
  - `[medium]` `[patch]` `export_stl`/`export_3mf` accepted an unbounded `linear`/`angular` deflection, so `linear: 0` would tessellate an unbounded mesh and hang inside the 120 s marshal. Added a `_MIN_DEFLECTION` (1e-4) / `angular>0` guard raising `ValidationError` → `INVALID_INPUT`; new infc test `test_zero_deflection_is_invalid_input`.
  - `[low]` `[patch]` `_step_checks` volume band was `abs(expected)*rel` with no absolute floor, so a zero/near-zero-volume STEP source demanded exact equality and float noise on re-import would spuriously FAIL. Added `_STEP_VOLUME_ABS_FLOOR` (1e-6) via `max(...)`.
  - `[low]` `[patch]` `verify_export_step` created a `FCB_TMP_` document that was never used (`Part.Shape().read()` is document-independent) — dead resource churn contradicting the "fresh document" docstring. Removed the temp document; corrected the docstring to "fresh reader".
- rejected (noise / by-design / not reachable): 3MF single-leg "no cross-oracle disagreement" (by-design per §6.4 — lib3mf + trimesh checks flattened into one leg, any failure → FAIL, proven 3/3; the disagreement apparatus is decorative for 3MF, not a defect); STL disagreement check redundant for FAIL (belt-and-suspenders; the flattened leg checks already fail); STEP static state not restored (the bridge pins config per call by design §6.2 — no user preference to protect headless); STEP unit-lie caught only via volume (volume IS the fault-README detection signal; fixture caught); `_is_mm` hardcoded True (FreeCAD internal unit is always mm — correct; the file-side unit check catches the lie); byte-content not diffed / file-swap TOCTOU (re-reading the recorded path is the design; local-FS race out of scope); hand-rolled `case.yaml` parser brittle (mirrors the committed 1.6 parser; works on committed fixtures); StdlibStlOracle uniform-reversal blind spot (INTENTIONAL — it manufactures the trimesh/stdlib disagreement that detects flipped-normals); vertex quantization 1e-6 (matches the fingerprint quantum; Phase-0 parts are cm-scale); arbitrary file-write path (same surface as `document_save`; no new attack surface); provenance trusts `export_file` name (existence check matches the `.FCStd` precedent); banner lacks oracle versions (banner contract is FreeCAD-version only); scorer doc-name collision (uses `tmp.Name` in `finally`; ids distinct); validators.yaml whitespace reflow (cosmetic; data preserved, tested); STL binary/ascii detection edge (the loader already handles the "solid"-prefixed-binary case by size match and FreeCAD's writer emits non-`solid` headers — not reachable via this story's writers).
- deferred_findings:
  - `_trimesh_checks` hardcodes `euler_number == 2` (genus-0 single-shell); a legitimate multi-shell / through-hole / multi-solid part would false-alarm. Not reachable in Phase-0 (single-solid golden models), real forward gap for Phase 3+ real geometry.
  - Export fault suites are small (verify_export_step n=2, stl/3mf n=3); the ≥95 %/≤5 % gate passes but the Wilson lower bound (0.34–0.44) is weak. A later story should add planted cases (more STEP faults; STL duplicated-shell, coordinate-truncation; 3MF missing-`3dmodel.model`, malformed transform) toward the ≥10-per-validator target.
  - `_read_ascii_stl_facets` silently drops a facet whose `endfacet` has ≠3 vertices (a truncated ASCII facet), a fail-open in the stdlib parser. Not reachable via this story's writers (FreeCAD emits BINARY STL); harden if an ASCII-STL input path is ever added.

### 2026-07-22 — Review pass (follow-up)
- intent_gap: 0
- bad_spec: 0
- patch: 4: (high 0, medium 2, low 2)
- defer: 4
- reject: 15
- addressed_findings:
  - `[medium]` `[patch]` `_mesh_export` deflection guard used `lin < _MIN_DEFLECTION or ang <= 0.0`, both False for `NaN`/`inf` — a non-finite `linear`/`angular` slipped past the guard into `MeshPart.meshFromShape`, producing an undefined tessellation / unbounded work inside the 120 s marshal instead of fail-closed. Added `math.isfinite` on both deflections (raise `ValidationError` → `INVALID_INPUT`); new infc test `test_non_finite_deflection_is_invalid_input`.
  - `[medium]` `[patch]` `_mesh_export` wrote the mesh with no facet-count check, so a shape that tessellates to zero facets produced an empty export whose paired self-read (recorded facets 0 == self-read 0) passed — an empty file reported verifiable, contradicting AD-9. Added `if int(mesh.CountFacets) == 0: raise ValidationError` before `mesh.write`.
  - `[low]` `[patch]` `_resolve_export_object` with no `objects` silently exported `Objects[0]`, contradicting its own docstring's "fail-closed rather than silently exporting the first". Made the no-selection branch require an explicit `objects` when the document holds more than one object (single-object docs unaffected); new infc test `test_no_selection_with_multiple_objects_is_invalid_input`. Also added `test_null_shape_object_is_invalid_input` pinning the null-shape rejection path.
  - `[low]` `[patch]` `score_export_verify.py::_score_step_case` opened an unused `FCB_TMP_` document (`Part.Shape().read()` is document-independent) — dead resource churn mirroring the bug already fixed in `verify_export_step`. Removed the temp document.
- rejected (noise / by-design / prior-pass adjudicated): `assemble_export_verdict` empty-legs fail-open (not reachable — the host handler hardcodes a non-empty leg list per format); 3MF single-oracle disagreement inert (already adjudicated by-design §6.4); `_is_mm` hardcoded True (already adjudicated — FreeCAD internal unit is always mm; the file-side unit check catches the lie); STEP static state / shim `Scheme` not restored (already adjudicated — per-call pin by design §6.2); `print()` in `build_export_fault_fixtures.py` (config-allowed — `benchmarks/**` per-file-ignores T201); binary STL `<84` bytes → `struct.error` (not reachable — `_load_stl_facets` gates the binary path on `len >= 84`); path/extension mismatch on `mesh.write` (same surface as `document_save`, prior-pass rejected class); validators.yaml header-comment provenance stale after merge (cosmetic); 1.6 `score_verify_shape.py` full-clobber (spec-explicit cross-story deferral, out of scope); ASCII STL truncation fail-open (already deferred — FreeCAD writes binary STL); `euler == 2` genus-0 hardcode (already deferred); small fault-suite n / weak Wilson lower bound (already deferred); STEP failures classified `SPEC_FAILED` not distinguishing garbage-vs-wrong (acceptable — within the closed status set); scorer `source['is_mm']` KeyError → DETECT (benchmark-only, all committed 3mf fixtures carry `is_mm`); non-mm/non-meter 3MF unit lie untested beyond fixtures (guard present, coverage note not a defect).
- deferred_findings:
  - `score_export_verify.py::_score_mesh_case` calls the oracle legs raw (its own `try/except` returns `True` = DETECT on any exception) instead of routing through `export_oracle.safe_oracle` like the production handler; a clean-control that threw for an unrelated reason would be scored DETECTED, masking a false-alarm-class failure. Benchmark-only path divergence (production handler is correct); harden the scorer to reuse `safe_oracle` for parity.
  - The STL/3MF mesh-verify handler runs the un-marshaled oracle legs (`entry.py::_mesh_verify_handler`) with no timeout, while the self-read leg is bounded at 120 s; a hung trimesh/lib3mf read would block RPC dispatch indefinitely. Not reachable with Phase-0 small meshes; add a bound when large-mesh inputs land.
  - `export_oracle._lib3mf_mesh` checks only the first mesh object of a 3MF model; a defect in the 2nd+ mesh object of a multi-mesh container passes undetected. Not reachable via this story's single-mesh writer; iterate all mesh objects if a multi-mesh input path is added.
  - `mesh3mf_oracle`'s trimesh geometry leg is built from the lib3mf-parsed vertex/triangle arrays (`_trimesh_from_lib3mf`), so the two "oracles" share lib3mf's geometry parse — the 3MF independence claim is weaker than the STL path (which loads independently). A later story should add an independent 3MF geometry parse or a second container reader.

### 2026-07-22 — Review pass (follow-up 2)
- intent_gap: 0
- bad_spec: 0
- patch: 3: (high 0, medium 2, low 1)
- defer: 1
- reject: 6
- addressed_findings:
  - `[medium]` `[patch]` The FreeCAD self-read leg (`exports.py::_self_read`) read the exported file (`Mesh.Mesh(entry["path"])`) UNGUARDED — the one leg the prior pass's `safe_oracle` hardening did not cover. A missing/corrupt/deleted export file (same TOCTOU window) raised out of the marshaled call, propagating to dispatch as `RECOMPUTE_ERROR` (unexpected crash-class) instead of reading as a verification FAIL. Wrapped the read in try/except emitting `self_read.readable=False`; `export_verdict._self_read_checks` now fails closed on an unreadable self-read; new external test `test_unreadable_self_read_leg_forces_fail_verdict`.
  - `[medium]` `[patch]` `mesh3mf_oracle`'s `lib3mf.metadata_present` check drove the verdict (`passed=metadata_count>0`), coupling correctness to an unspecified FreeCAD writer side-effect. Missing model-metadata is not a declared 3MF fault (the contract's 3MF faults are unit-lie + type-model-lie); a geometrically-valid, correctly-united, manifold 3MF lacking metadata would false-alarm against the FA≤5% bar. Demoted to a non-verdict fact (`passed=True`, count still reported); docstring corrected. Scorer re-run: verify_export_3mf sensitivity 1.000 / FA 0.000 unchanged.
  - `[low]` `[patch]` `StdlibStlOracle` check id `stl2.winding_consistent` + docstring claimed it asserts "each shared edge is traversed in opposite directions" (consistent winding), but the code only fails when a directed edge recurs — it cannot detect a uniform reversal and never fires on a clean OR uniformly-flipped closed mesh, so the reported orientation assertion was decorative. Renamed to `stl2.local_winding` and corrected the docstring to state precisely what it detects (locally-inconsistent winding); uniform-reversal detection is (by design) left to the trimesh-disagreement signal.
- rejected (noise / by-design / prior-pass adjudicated): mesh_volume_band has no upper bound on `linear` (by-design — the band derives from the deflection used per §8/Design Notes; a huge deflection legitimately widens the tolerance); solidless/zero-volume STEP passes vacuously (out of Phase-0 single-solid golden-model scope; the counts-equal check still binds source-0-solids==reread-0-solids as faithful); `assemble_export_verdict` oracle-name key collision in `_disagreement_check` (not reachable — the two STL legs carry distinct names and 3MF is single-leg; and the real FAIL gate is per-check flattening, not the supplementary agreement dict); `measured` nested-dict serialization in the agreement check (keys are always str oracle names; cosmetic); mesh_volume_band `char` floor of 1.0 for sub-mm parts (Phase-0 parts are cm-scale; overlaps the already-deferred band-calibration-across-scales note).
- deferred_findings:
  - The `step-unit-lie` fault fixture writes a genuinely smaller solid (`makeBox(1,2,3)`, vol 6) mislabeled against the full box (vol 6000), so detection comes from a gross shape mismatch, not from a mislabeled `write.step.unit`. The per-call unit-pinning path (`shim.pin_step_config` / `write.step.unit=MM`) therefore has no fault-suite case that exercises a true 1000× unit scale on the SAME geometry. The verifier's volume check WOULD catch a real unit-lie, so this is a coverage gap, not a product defect; a later story should add a fixture that writes the clean box with `write.step.unit` set to `M`/`CM` referenced against the mm facts.

## Design Notes

- **Ring split for the merged verdict.** STL/3MF verify cannot be a single marshaled usecase: oracles are third-party (must live in `adapters/`, banned in `usecases/`). The host handler in `entry.py` calls (a) the marshaled `export_self_read_*` usecase (FreeCAD facts + banner) and (b) the un-marshaled `export_oracle` functions (read the file directly), then `assemble_export_verdict` merges. `verify_export_step` needs no third-party oracle, so it stays a pure marshaled usecase. `entry.py` is `hosts/` and may import both rings.
- **CI leg reality.** No single CI leg has both FreeCAD and trimesh/lib3mf: the uv arch-check leg has the oracles (no FreeCAD); the micromamba headless legs have FreeCAD (no oracles installed). So the fault scorer's oracle legs read committed exported fixture files (no FreeCAD needed to re-read a written `.stl`/`.3mf`), and `test_export_oracle.py`/`test_export_fault_score.py` run in the uv leg; `test_export_tools.py` (writer + STEP round-trip + self-read) runs in the FreeCADCmd leg. End-to-end export→all-legs integration is exercised locally where FreeCAD 1.1 + the uv `.venv` (trimesh 4.x, lib3mf 2.x) coexist.
- **Mesh volume band.** Derive from the deflection actually used: e.g. `band = max(rel_from_deflection, abs_floor)` where the relative term scales with linear deflection / characteristic size. Never the STEP ±0.1%. Record the band and the deflection in the report so the tolerance is auditable. Calibrate against the fault suite until ≥95%/≤5%.
- **STEP schema/unit pin (verified on 1.1):** `Part.setStaticValue("write.step.unit","MM")` succeeds; `Part.setStaticValue("write.step.schema",...)` RAISES on 1.0/1.1 — pin the schema via the `User parameter:BaseApp/Preferences/Mod/Part/STEP` `Scheme` string instead. Both go through `shim.pin_step_config`; capability-probe, never version-string.
- **type="model" lie / unit lie (research §1.2, §5.1):** lib3mf leg asserts declared `unit == "millimeter"` AND the source doc was mm (guard the hardcoded-mm writer), and asserts `IsManifoldAndOriented()` consistent with the declared object `type` (catches an open surface written as `type="model"`).
- **validators.yaml merge:** load the current text, keep the `verify_shape` block verbatim, replace/append only `verify_export_*`. The Story-1.6 scorer still full-clobbers — log as a cross-story deferral (a later story should refactor both onto a shared merge writer); do not rewrite 1.6's scorer here beyond extracting a shared helper if trivial.
- **export_id record example:** `{export_id, path, doc, format:"stl", tess:{linear,angular}, source:{volume,faces,edges,solids,is_mm}}` — `verify_export_*` compares the re-read file against these recorded source facts.

## Verification

**Commands:**
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`.
- `uv run ruff check .` -- expected: clean.
- `uv run python scripts/gen_schemas.py --check` -- expected: schemas byte-identical (if contracts touched).
- `uv run pytest tests/external -q` -- expected: all pass (oracle + fault score + surface).
- `"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" tests/run_tests.py` -- expected: `test_export_tools` + prior infc suites green.
- `"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" benchmarks/g0/export-fault-injection/score_export_verify.py` -- expected: per-verifier sensitivity ≥0.95, FA ≤0.05; `validators.yaml` updated (verify_export_* added, verify_shape preserved).

## Auto Run Result

Status: done (follow-up review pass 2)

**Change:** Independent follow-up adversarial + edge-case review of the already-implemented Story 1.7 export/verify surface. Two review subagents (Blind Hunter, Edge Case Hunter) ran in parallel; findings deduped, classified, and 3 patches applied. No intent_gap, no bad_spec — the intent contract held and no re-derivation was needed.

**Files changed:**
- `src/freecad_buddy/usecases/exports.py` — `_self_read` now guards the `Mesh.Mesh(path)` re-read; a missing/corrupt export file emits `self_read.readable=False` instead of raising (was → RECOMPUTE_ERROR crash-class).
- `src/freecad_buddy/adapters/export_verdict.py` — `_self_read_checks` fails closed on an unreadable self-read leg.
- `src/freecad_buddy/adapters/export_oracle.py` — `lib3mf.metadata_present` demoted to a non-verdict fact (missing metadata is not a declared 3MF fault; prevents an FA-class false-alarm); `StdlibStlOracle` `winding_consistent` check renamed `local_winding` with a corrected docstring (it detects locally-inconsistent winding, not full orientation — uniform reversal is by-design left to the trimesh-disagreement signal).
- `tests/external/test_export_oracle.py` — new `test_unreadable_self_read_leg_forces_fail_verdict`.
- `benchmarks/_registry/validators.yaml` — re-scored `verify_export_stl`/`3mf`/`step` (validator_sha refreshed after the oracle/verdict edits); `verify_shape` preserved.

**Review findings breakdown:** patch 3 (medium 2, low 1) applied; defer 1 (new DW ledger entry — `step-unit-lie` fixture exercises a shape mismatch, not the unit-pin path); reject 6 (mesh_volume_band no upper bound = by-design tolerance derivation; solidless STEP vacuous pass = out of Phase-0 scope; oracle-name key collision = not reachable + per-check flatten is the real gate; measured-dict serialization = cosmetic; char-floor sub-mm = Phase-0 cm-scale / overlaps deferred band note).

**Verification:**
- `uv run python scripts/check_imports.py` → `check_imports OK`.
- `uv run ruff check .` → `All checks passed!`.
- `uv run ruff format` (changed files) → unchanged (already formatted).
- `uv run python scripts/gen_schemas.py --check` → `gen_schemas --check OK`.
- `uv run pytest tests/external -q` → 140 passed.
- `FreeCADCmd tests/run_tests.py` → Ran 64 tests, OK.
- Scorers (both legs): verify_export_step/stl/3mf sensitivity 1.000, false_alarm 0.000; `verify_shape` block preserved.

**Residual risks:** the deferred fixture-coverage gap (unit-pin path not exercised by its own fault case — verifier still catches a real unit-lie via volume); pre-existing deferred items (euler==2 genus-0 hardcode, small fault-suite n / weak Wilson lower bound, un-timeout'd oracle legs, 3MF shared-parse independence) remain open in the ledger, unchanged by this pass.

