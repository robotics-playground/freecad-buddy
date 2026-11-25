---
title: 'feature_loft and feature_sweep tools'
type: 'feature'
created: '2026-11-24'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'dd7e8355eacffc58041fd89eba39e13d6177d60f'
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-13-lessons.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** An agent that needs a loft or a sweep builds `PartDesign::AdditiveLoft` or `AdditivePipe` in `script_exec` (CAP-9). No typed tool exists, so nothing checks the sections, the spine or the cost, and a wrong input fails late with a FreeCAD message.

**Approach:** Two new mutations, `feature_loft` and `feature_sweep` (T-9), follow the `feature_revolve` pattern: refusals before the AD-5 bracket, one bracket, one undo step, previewable, not in `READ_ONLY_PROFILE`.

## Boundaries & Constraints

**Always:**
- `feature_loft` input: `doc`, `body`, `profile` (sketch Name), `sections` (array of sketch Names, 1 or more), `ruled` (bool, default false), `closed` (bool, default false), `subtractive` (bool, default false), `name`, `confirm`. Creates `PartDesign::AdditiveLoft` or `SubtractiveLoft`; writes `Profile`, `Sections` (each as `(sketch, [""])`), `Ruled`, `Closed`.
- `feature_sweep` input: `doc`, `body`, `profile` (sketch Name), `spine` (a sketch Name string, or a `mapped_name` Selector object naming an Edge or a whole object), `mode` (`"standard"` or `"frenet"`, default `"standard"`), `subtractive` (bool, default false), `name`, `confirm`. Creates `PartDesign::AdditivePipe` or `SubtractivePipe`; writes `Profile`, `Spine`, `Mode`. The JSON Schema for `spine` is `oneOf` a string and the Selector object.
- `mode` maps by name to the build's `Mode` enumeration members `Standard` and `Frenet` (source: `FeaturePipe.cpp:60`, `ModeEnums = {Standard, Fixed, Frenet, Auxiliary, Binormal}`); the member is read from the live enumeration, never by index. `Fixed`, `Auxiliary` and `Binormal` are not offered.
- Refusals (`INVALID_INPUT`, before the bracket, no snapshot, no transaction; message names the input): unknown body, profile, section or spine object; profile or section that is not a sketch; a sketch with a null shape; the profile listed in `sections`, or a section listed twice; sketches with different wire counts (FreeCAD raises at recompute); `closed: true` with fewer than 2 `sections` (FreeCAD silently ignores it, `FeatureLoft.cpp:209-212`); a spine whose shape is not an Edge, a Wire or a compound of those; a spine that is the profile sketch; an Edge selector that does not resolve to an Edge; a `mapped_name` selector of kind other than `mapped_name`; a taken or illegal `name`; a non-bool flag.
- Cost guard (L2): a request whose measured cost passes a limit is refused before the bracket with `INVALID_INPUT` and `detail.code` `loft.too_complex` or `sweep.too_complex` (`CodedValidationError`, AD-17 closed status set). The limit and its measurements are written beside the constant and in `mcp-tools-design.md`. Probes on FreeCAD 1.1.4 (host): loft of 100 sections of 200 edges 11.4 s, 200 sections of 300 edges 49 s; sweep of a 200-edge profile along a 20-turn helix 4.2 s, a 400-edge profile along 25 turns 8.7 s. Final limits and the BSpline case are measured in the build.
- A recompute that gives no solid (open sections, a self-intersecting sweep) returns `RECOMPUTE_ERROR` with proven rollback; no new status. The result carries `feature` and `feature_state` like `feature_pad`. One `document_undo` removes the feature.
- Previewable through `preview_dry_run` (the op table derives from `_feature_specs`). `mcp-tools-design.md` agrees with the code: §2 `feature_` rows, §3 schema, counts, refusals, cost limits.

**Never:** Pass or verdict (AD-35). A new status value. Edit `transaction.py`, `rpc_dispatch.py`, `tnp_guard.py` or `confirm.py`. Offer `Fixed`, `Auxiliary` or `Binormal` mode, `SpineTangent`, `Transition` or auxiliary spines. Change other tools' behaviour. Change skills or `docs/intent.md` (Story 13-19 owns routing).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Ruled loft | two squares 20 and 12 mm, 20 mm apart, `ruled` true | `OK`, frustum volume 5226.67 | N/A |
| Smooth loft, 3 sections | profile + 2 sections | `OK`, valid solid | N/A |
| Subtractive loft | base pad, loft inside | volume smaller by the loft volume | N/A |
| Closed loft, 1 section | `closed` true | nothing written | `INVALID_INPUT` names `closed` |
| Wire count mismatch | profile 1 wire, section 2 wires | nothing written | `INVALID_INPUT` names the section |
| Profile in sections | `sections` holds `profile` | nothing written | `INVALID_INPUT` |
| Straight sweep | circle r=3, spine line 30 mm | `OK`, volume pi*9*30 = 848.23 | N/A |
| Sweep by sketch name | spine sketch of line + arc | `OK`, volume profile area x spine length | N/A |
| Sweep by Edge selector | spine `{object, mapped_name:"Edge1"}` | `OK` along that edge only | bad edge: `INVALID_INPUT` |
| Frenet mode | helix spine | `Mode` reads `Frenet` | N/A |
| Unknown mode | `"fixed"` | nothing written | `INVALID_INPUT` lists the two |
| Solid as spine | whole-object selector of a Pad | nothing written | `INVALID_INPUT` |
| Open sections | open profile | `RECOMPUTE_ERROR`, rollback proven, object set as before | rollback |
| Over cost | sections x edges past limit | nothing written | `loft.too_complex` |
| Undo | `document_undo` after either tool | feature gone, `matches_pre_op` true | N/A |
| Preview | `preview_dry_run` of either | diff lists the feature; live document unchanged | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/features.py:731` `feature_revolve` -- pattern to copy (`precheck`, `op`, `_feature_mutation`); reuse `_resolve_body`, `_resolve_sketch`, `_name_available`, `_checked_enum`, `_selector_subelement`, `_require_shape`, `_add_feature`; new `LoftRefusal` and `SweepRefusal` or one `FeatureRefusal(CodedValidationError)` beside `ParameterRefusal` (`:1935`).
- `src/freecad_buddy/hosts/tool_catalog.py:630` `_feature_specs` -- two `_feature_method` entries after `feature_revolve`; `_SUBELEMENT_SELECTOR_SCHEMA` (`:257`) for the Selector branch of `spine`.
- `docs/references/FreeCAD/src/Mod/PartDesign/App/FeatureLoft.cpp:45-48,188-212`, `FeaturePipe.cpp:59-60,206-260,716-760` -- properties, `ModeEnums`, silent `closed` reset, `buildPipePath` accepted spine shapes (main tree).
- Probed in FreeCAD 1.1.4: `L.Sections = [(sketch, [""])]`, `P.Spine = (sketch, [""])` both recompute valid; loft of two squares valid; pipe circle r=3 along line 30 + arc 30 gives 1696.46 = area x 60.
- `mcp-tools-design.md:181-183` rows; §3.7 schema block and refusal list (`:545-572`); tool count text.
- Tests: `tests/infc/test_feature_tools.py` (new `LoftTest`, `SweepTest` classes, `_FeatureFixture`); `tests/external/test_feature_contract.py:30`, `test_mcp_surface.py:99`, `test_confirm_contract.py`, `test_assistant_readonly_profile.py` (name lists, schema, `oneOf`).
- Do not change: `transaction.py`, `confirm.py`, `tnp_guard.py` (`Spine` is a `PropertyLinkSub`, audited as is), skills, `docs/intent.md`.

## Tasks & Acceptance

**Execution:**
- [x] `features.py` -- `_section_sketches` (wire count, shape), `_spine_target`, cost measure and refusal, `feature_loft`, `feature_sweep`
- [x] `tool_catalog.py` -- two specs, `spine` `oneOf`
- [x] design doc -- rows, §3 schemas, counts, cost measurements
- [x] tests -- one per matrix row, undo round trip, rollback by real state, preview, TNP audit CLEAN, schema `oneOf`, mode map against the live enumeration, cost guard

**Acceptance Criteria:**
- Given a Body with a profile square and two section sketches, when `feature_loft` runs, then the feature is valid and one `document_undo` restores the earlier state.
- Given a profile circle and a spine sketch, when `feature_sweep` runs with `mode: "frenet"`, then `Mode` reads `Frenet` and the volume equals the profile area times the spine length.

## Implementation Notes

- Implemented directly by the builder (the probes lived in this session).
- Probed: AD-5 post-verify runs `verify_sketch` on every touched sketch, so a spine or section sketch must be fully constrained (`SPEC_FAILED` otherwise). Stated in the tool descriptions and the design doc.
- Probed: a BSpline spine that doubles back holds the interpreter more than 280 s; a tangent-sign guard (`sweep.degenerate_spine`) refuses it. Cost limits: loft 8,000 edge units, sweep 10,000 units, measured at the limit (4 to 6.4 s loft, 5.8 s sweep).
- Closed loft: three circle sections on a ring fail in FreeCAD (`Failed to create shell`); a stack of three squares builds, so the test uses the stack.
- Test count assertion in `test_confirm_contract.py` moves 21 to 23 mutation tools.

## Spec Change Log

## Review Triage Log

Lenses: Blind Hunter ac866481e169b08a1 (opus, high), Edge Case Hunter afc3620d14122415a (opus, high), Verification Gap a195efefcdce32b94 (sonnet, medium). A first launch of all three ended on a usage limit with no findings (partial ids a8dcf8d3a05d10c2a and two with no output); the three above are the relaunch.

| Lens | Finding | Verdict | Route and evidence |
| --- | --- | --- | --- |
| Blind, Edge, Gap | Tangent sampling ran before the cost guard, unbounded (401 calls per edge) | medium | patch: cost first, only BSpline-like edges sampled, at most 100; tests `Should_refuse_with_a_code_When_the_spine_has_more_curved_edges...` |
| Blind | Refusals other than too_complex carry no `detail.code` (Q4) | medium | patch: `loft.invalid_sections`, `loft.wire_count_mismatch`, `loft.closed_needs_sections`, `sweep.invalid_spine`, `sweep.invalid_mode`; code tests |
| Blind | "At the limit" timings were above the limit | low | patch: re-measured accepted cases (7,619 BSpline 4.0 s, 7,839 6.7 s), comment and doc corrected |
| Blind, Edge | Sweep cost ignores BSpline profile poles | medium | patch: profile edge counts poles; measured 200-pole profile on a 20-turn helix 1.3 s; test |
| Edge | Thousands of one-edge sections pass the loft cost (cost = count) | medium | patch: measured 1,500 circles 19 s; `_LOFT_MAX_SECTIONS` 500 (1.6 s); test |
| Blind | Corners of the accepted range unmeasured | low | rejected: the product limit and the section limit bound both corners; each measured |
| Blind | Spine outside the Body not refused | false | probed: a `Part::Feature` helix at document root sweeps and builds (new test `Should_sweep_along_a_helix...`) |
| Edge | Body as spine selector forms a cycle | medium | patch: `sweep.invalid_spine`; test |
| Edge | Sketch spine with a point is refused | false | FreeCAD itself raises "neither an edge nor a wire" for a vertex in the compound (`FeaturePipe.cpp:735`) |
| Edge | Degree-1 BSpline with a corner refused as degenerate | low | rejected: a fix needs derivative magnitudes and adds complexity; the doc states the 90 degree rule |
| Edge, Gap | Zero-velocity point without a reversal not detected | maybe-false | defer: would be medium; settle with a probe of a cusp-free zero-velocity BSpline |
| Edge | `edge.Curve` can raise past `getattr` | low | patch: whole read in `try` |
| Edge | Test of the degenerate spine has no watchdog | low | rejected: a hang holds the GIL, so a thread timer cannot fire; the pre-bracket refusal is asserted |
| Edge, Gap | Doc "a tenth of its poles" is rounded down | low | patch: doc says rounded down |
| Gap | Sweep cost BSpline spine, limit boundary untested | medium | patch: tests for `_sweep_cost` on a helix and a BSpline profile, and for the limit |
| Gap | Accept side of the degenerate check untested | medium | patch: helix spine test (194 poles) builds |
| Blind | Untested refusals: profile not a sketch, empty sketch, `Edge99`, profile-edge selector | low | patch: tests |
| Blind, Gap | Sweep rollback lacks the undo-after-refusal test (L14) | medium | patch: test |
| Gap | Unconstrained section gives `SPEC_FAILED`, untested | low | patch: test `Should_roll_back_with_spec_failed...` |
| Blind | Closed-loft test passes for any different volume | low | rejected: the closed volume has no independent derivation; the Closed property, validity and difference are asserted |
| Blind | Schema lacks `uniqueItems` and a conditional for `closed` | low | rejected: runtime refusals cover both with codes |
| Blind | Doc schema text differs from code | low | patch: descriptions aligned |
| Blind | Profile shape fetched twice in the loft precheck | low | rejected: no measurable cost |


## Verification

**Commands:**
- `uv run --extra dev ruff check`, `ruff format --check <changed files>`, `check_imports`, `gen_schemas --check`, `check_provenance` -- expected: pass
- `uv run --extra dev pytest tests/external -q` (Git Bash) -- expected: pass
- freecadcmd `tests/run_tests.py` with temp cfg and `FREECAD_USER_HOME` -- expected: pass
