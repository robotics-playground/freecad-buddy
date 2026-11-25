---
title: 'query_interference tool'
type: 'feature'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'bda755e7c9f5a5a45985a87fbdf95336766bfcf5'
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** An agent that must know whether two parts overlap runs `Shape.common` and `distToShape` in `script_exec` (CAP-1). A failed boolean returns an empty shape there, and an empty shape reads as "no overlap" (a measured false pass, usage-evidence.md).

**Approach:** New read-only tool `query_interference` measures `common_volume` and `min_distance` for object pairs and sets `boolean_failed` when the boolean cannot prove zero overlap. It returns numbers only (AD-35). Schema is new, so additive (AD-28).

## Boundaries & Constraints

**Always:** Exactly one of `objects` (2 to 20 names, every pair measured) and `pairs` (up to 100 `[a, b]` name pairs) is given, otherwise `INVALID_INPUT`. Resolve objects by immutable `Name`. An unknown name fails the whole call with `INVALID_INPUT` "unknown object: <name>" before any measurement. An object with no shape, a null shape, or an empty shape fails the call with `INVALID_INPUT` (a skipped object would read as no overlap). Each result record is `{a, b, common_volume, min_distance, boolean_failed}`, in pair order; `objects` yields pairs in order `(i, j)` with `i < j`. `min_distance` is `distToShape` and is 0 when shapes touch or overlap. `common_volume` is the `Volume` of `Shape.common`. When `common` raises, or returns an empty shape, while `min_distance` is not a positive number, then `boolean_failed` is `true` and `common_volume` is `null`. A non-empty `common` result with zero volume (a face or edge) gives `common_volume` 0 and `boolean_failed` false. When `min_distance` is positive the shapes are disjoint: `common_volume` is 0 and `boolean_failed` is `false`. A truly empty result at distance 0 is `boolean_failed` true (decision 24, safe side). The schema keeps `objects` maxItems 20 (190 pairs) and `pairs` maxItems 100 (decision 23); 20 realistic objects are timed against the 60 s budget, and a result over budget stops the build for a report before any bound changes. The tool is added to `READ_ONLY_PROFILE`. The design document `mcp-tools-design.md` gets the §2 row, the §3 schema, and updated counts.

**Never:** Return a "pass", "done" or "no interference" verdict (AD-35). Mutate the document, recompute, or touch the viewport. Add FreeCAD imports outside `usecases/shim.py` or the whitelisted App modules (AD-1). Change other tools. Add a status value: failures use `INVALID_INPUT`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Overlap | two boxes overlapping 5x5x5 | `common_volume` 125 mm^3, `min_distance` 0, `boolean_failed` false | N/A |
| Disjoint | two boxes 10 mm apart | `common_volume` 0, `min_distance` 10, `boolean_failed` false | N/A |
| Failed boolean | `common` raises or returns empty, distance 0 | `common_volume` null, `boolean_failed` true | N/A |
| Many objects | `objects` of 3 names | 3 records, order (0,1) (0,2) (1,2) | N/A |
| Explicit pairs | `pairs` of 2 pairs | 2 records in input order | N/A |
| Both or neither | `objects` and `pairs`, or none | none | `INVALID_INPUT` |
| Bad list | `objects` under 2 or over 20, a pair not of 2 names, over 100 pairs, same name twice in a pair | none | `INVALID_INPUT` |
| Unknown name | any listed name missing | none | `INVALID_INPUT` "unknown object: <name>" |
| No shape | a listed object has no or empty shape | none | `INVALID_INPUT` naming it |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/queries.py:191` -- `_resolve_object` reuse (unknown-name message). `_queryable_shape` (`:572`), `_quantity` (`:112`), `_ok_envelope` (`:26`), `query_mass_properties` (`:634`) are the pattern. Add interference helpers here, named for interference (Story 13-8 edits the same file).
- `src/freecad_buddy/hosts/tool_catalog.py:1252` -- `query_mass_properties` spec is the pattern; add the spec after it; add the name to `READ_ONLY_PROFILE` (`:1030`). `timeout_s` 60.
- `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md:131` -- §2 `query_` row; §3.2.3 new schema after §3.2.2 (`:309`); counts table (`:216`): `query_` 11 specified, 9 shipped, total 46 shipped, 47 registered.
- `tests/infc/test_query_tools.py` -- in-FreeCAD tests; `setUp` builds the document. `tests/external/test_assistant_readonly_profile.py:46` and `test_mcp_surface.py:60` list tool names and must gain the new name.
- FreeCAD source: `docs/references/FreeCAD/src/Mod/Part/App/TopoShapePyImp.cpp:745` (`common` through `makeShape`, raises on OCC failure), `:2350` (`distToShape` returns `(dist, pts, info)`; raises `RuntimeError` when not done).
- Do not change: `shape_metrics`, other tool specs, export code.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/queries.py` -- `query_interference`, input validation, pair builder, per-pair measure, summary -- implements T-2
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- spec, schema, description, `READ_ONLY_PROFILE` entry
- [x] `mcp-tools-design.md` -- §2 row, §3.2.3 schema, counts table and tool-count sentence
- [x] `tests/infc/test_query_tools.py` -- one test per matrix row, a planted failed boolean, a dispatch test
- [x] `tests/external/test_assistant_readonly_profile.py`, `tests/external/test_mcp_surface.py` -- add the tool name

**Acceptance Criteria:**
- Given a planted failed boolean at distance 0, when queried, then `boolean_failed` is true and `common_volume` is null, never 0.
- Given a large compound pair, when queried, then the elapsed time is recorded against the 60 s budget.
- Given the catalog, when `gen_schemas --check`, `check_imports`, `ruff` and `pytest tests/external` run, then all pass.

## Implementation Notes

Probe (FreeCAD 1.1, freecadcmd): `Shape.common` of two boxes sharing a face or a vertex returns an empty Compound (0 sub-shapes, volume 0) with `distToShape` 0.0, so touching solids read as `boolean_failed` true under the contract rule. A box against a self-intersecting (bowtie) solid returns an empty Compound with distance 0.0: the real failed boolean used in the infc test. Overlap boxes give volume 125. Two compounds of 200 boxes: `distToShape` 44.6 s, `common` 0.7 s. Timing through the tool, development host: 20 plates of 81 holes, 190 pairs: 8.1 s disjoint, 25.8 s overlapping (15 face-touching pairs read `boolean_failed`); two overlapping 200-box compounds: 0.4 s (the common-volume fast path skips `distToShape`). Both under the 60 s budget. A disjoint pair of large compounds still pays the full `distToShape`. So `common` runs first; `distToShape` runs only when `common` gives no positive volume.

## Spec Change Log

Red team round (decision 26): RT-1 invalid solid with a box inside a lobe read distance 7.07 not failed; RT-2 `Part::Reverse` gave common 875 against 125 and a contained box read volume 0; RT-3 a closed shell around a solid read 40 mm disjoint; RT-4 a volume below 1e-9 counted as overlapping in text and 0.0 in structured content; RT-5 Body-local frame for features. Fix: a pair is measured only when both shapes are valid, solids only, each with positive volume (checked once per object); otherwise `boolean_failed` true with null volume and distance. The `abs()` on common volume is removed (a negative common volume is a failed boolean). The text counts a pair as overlapping only when its displayed volume is non-zero. Frame note names Body features. Timing after the change: 190 plate pairs 10.7 s disjoint, 29.4 s overlapping.

## Review Triage Log

Lenses: Blind Hunter a47020905ae6d8459 (opus, high), Edge Case Hunter a5f4117b508fefa6d (opus, high), Verification Gap a41661ce8d89645be (sonnet, medium).

| # | Lens | Finding | Verdict | Route and evidence |
|---|------|---------|---------|--------------------|
| 1 | BH | Phase 0 label breaks the G0.2 count sentence (17 = 8+6+3) | medium | patch: row is Phase 1, counts `query_` P0 8, P1 3 |
| 2 | BH | `min_distance` nullable widens T-2 (non-null Quantity) | low | defer: leader-owned contract; design doc states the widening |
| 3 | BH | Schema accepts `pairs: []`, code refuses | low | patch: `minItems: 1` in catalog and design doc |
| 4 | BH, EC | Length tolerance used as a volume threshold | medium | patch: any non-zero volume counts; no volume tolerance |
| 5 | BH, EC | Negative or NaN common volume reads as zero overlap | medium | patch: `abs`, non-finite gives failed; fake-shape tests |
| 6 | BH, EC | Local frame in containers; `App::Link` refused | medium | defer: assemblies are Phase 5 (M-20); description and design doc state the frame |
| 7 | BH | Description says overlap is NOT zero, false for touching solids | medium | patch: wording now says unmeasured, touching also gives this |
| 8 | BH, VG | Read-only test thin (no placement, state, undo count) | low | patch: new test checks placement, state, volume, `UndoCount` |
| 9 | BH, EC | Null-shape and empty-compound refusal untested; self-pair message | medium | patch: tests for both and the message |
| 10 | BH, EC | Timing test small, not the large-compound case | low | patch: large pair and 190-pair plates measured in scratch, recorded in Implementation Notes |
| 11 | BH, EC | No deadline check in the pair loop; TIMEOUT gives no partial result | maybe-false | defer: medium if the marshal timeout does not stop the FreeCAD thread; container run settles it. Description now warns of cost |
| 12 | VG | Schema bounds untested | medium | patch: external test reads `tool_specs()` |
| 13 | EC | Duplicate pairs recompute | low | rejected: contrived, adds a check |
| 14 | EC | Tiny volume prints as 0.0 in text | low | rejected: structured value is exact |
| 15 | EC | Solid inputs with face-only common read zero overlap | false | decision 24 sets non-empty zero-volume to volume 0 |
| 16 | EC | Compound of empty children is non-empty | medium | patch: empty means invalid `BoundBox` |
| 17 | EC | NaN distance gives `{value: null}` | low | patch: non-finite distance becomes null |
| 18 | VG | No test for common raising with positive distance | low | patch: test added |

## Verification

**Commands:**
- `uv run ruff check .` -- expected: no errors
- `uv run ruff format --check <changed files>` -- expected: no changes
- `uv run python scripts/check_imports.py` -- expected: OK
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift
- `uv run pytest tests/external -q` -- expected: pass
- `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` -- expected: pass
