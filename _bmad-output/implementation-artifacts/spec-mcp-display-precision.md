---
title: 'MCP numbers at FreeCAD display precision'
type: 'feature'
created: '2026-10-08'
status: 'done'
baseline_commit: '35ecaa89369a63d408f3a52e72b4a9850a29e7bb'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/data-contracts-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** MCP results print floats at full length, e.g. `5.999999998` where FreeCAD GUI shows `6.00 mm`. Kernel and solver noise (Sketcher solver stops at `convergence(1e-10)`, `GCS.cpp:484`; OCC tolerance 1e-7) reaches the agent and can sway its decisions.

**Approach:** Round every float the agent reads to FreeCAD's display precision (preference `BaseApp/Preferences/Units` `Decimals`, default 2). Checks compare a once-rounded deviation, so noise never changes a verdict and a verdict never contradicts its displayed numbers.

## Boundaries & Constraints

**Always:**
- Rounding is decimal places in internal units. Decimals = FreeCAD's current preference, read on every tool call (FreeCAD applies a change at once, `DlgSettingsGeneral.cpp:209`); missing or negative → 2.
- Zero floor: `|x| < 1e-9` → `0.0`. Else a non-zero value that rounds to 0 keeps 3 significant digits (inertia 3.3e-8, tolerance 1e-7 survive). `-0.0` → `0.0`. Integers stay integers.
- Echoed tolerances are never rounded: the subtree under any `tolerance` or `tol` key stays raw.
- Verdict rule, for assertions and STEP/STL/3MF export checks: `deviation = round_display(|raw measured − raw expected|)`; pass when `deviation <= band`, band raw as declared/computed. Never round operands separately; never round the band.
- JSON block, `structuredContent`, `text` and `detail.message` show the same rounded values.
- Change detection keeps the AD-6 1e-6 fingerprint quantum; only printed values are rounded.
- Rounding is on by default. Addon preference `BaseApp/Preferences/Mod/FreeCADBuddy` `RoundToDisplay` (checkbox on the FreeCAD Buddy page in Edit > Preferences, read on every call) turns it off: `display_decimals` is `None`, output stays raw, and verdicts compare the raw deviation.

**Never:**
- Never round tool inputs or values written into the FreeCAD document.
- No unit switching (µm/m/in); numeric fields stay numbers in internal units.
- No change to the audit log.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Solver noise | `5.999999998` | `6.0` | N/A |
| Kernel gap | `6.0000001` | `6.0` | N/A |
| Real value | `1234.5678` | `1234.57` | N/A |
| Tiny real | `3.3e-8` | `3.3e-8` | N/A |
| Noise at zero | `-4.281973375071899e-16` | `0.0` | N/A |
| Negative zero | `-0.0` | `0.0` | N/A |
| Non-finite | `nan`, `inf` | unchanged | N/A |
| Preference 4 | `Decimals=4`, `5.12345` | `5.1235` | missing/negative → 2 |
| Pref changed live | 2 → 4 between two calls | second call at 4 | N/A |
| Echoed tolerance | `tolerance {"rel": 0.005}` | `0.005` | N/A |
| Verdict, noise | m `5.999999998`, e `6`, band 0.05 | deviation `2e-09`, PASS | N/A |
| Verdict, straddle | m `6.0150001`, e `6.015`, band 0.001 | deviation `1e-07`, PASS | N/A |
| Verdict, edge | m `6.054`, e `6.0`, band 0.05 | deviation `0.05`, PASS | N/A |
| Verdict, tight | m `6.004`, e `6.0`, band 0.001 | deviation `0.004`, FAIL | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/adapters/mcp_server.py:85` `_to_call_result` -- single choke point for every tool on both hosts; pops `text_blocks` (pattern to copy) then builds JSON (:93) and `structuredContent` (:99).
- `src/freecad_buddy/contracts/envelope.py:49` `ResultEnvelope` -- add internal `display_decimals: int`, documented like `text_blocks` (:57-59): popped at the MCP boundary, never sent.
- `src/freecad_buddy/adapters/rpc_dispatch.py:123` `MethodRegistry.dispatch` -- runs inside FreeCAD (headless host, GUI listener) and in the proxy. Stamp with `setdefault`, so a proxy never overwrites FreeCAD's value.
- `src/freecad_buddy/hosts/gui_external/entry.py:48-86` `_mesh_verify_proxy_handler` -- builds a new envelope in the proxy (no FreeCAD); must copy `display_decimals` from `self_read` and pass it to the oracles. `hosts/tool_catalog.py:96,106` -- headless twin of the same oracle calls.
- `src/freecad_buddy/adapters/export_oracle.py:193` `volume_ok = abs(volume - ...) <= band` -- raw verdict; `:205-208` check dict.
- `src/freecad_buddy/usecases/exports.py:335-351` STEP volume check, raw verdict + raw message.
- `src/freecad_buddy/usecases/shim.py` -- only FreeCAD App access; `ParamGet` pattern at :425.
- `src/freecad_buddy/usecases/assertions.py` -- `_check` :87 puts the echoed `tol` under `tolerance`; band checks at `_matches_diameter` :755, `_compare_all` :847-849, `expect_volume` :873-878, `expect_bbox` :901, `expect_extent` :932, `hole_position` :987, `hole_spacing` :1031/1034, `hole_through` :1071 (one-sided: `wall >= material - 0.05`). Messages at :849/879/903/938/993, floor note :549.
- `src/freecad_buddy/usecases/queries.py:201` `_json_safe` -- `str(value)` at :211/:216 leaks raw floats from `Quantity` (`"3.33333 mm"`) and `Vector`; `Placement` str already short, leave. Summaries `:61-68`, `:88-95`.
- `src/freecad_buddy/usecases/preview.py:416` `{volume:+.4f}` -- align with display rounding.
- Do not change: fingerprint quantum/equality (`usecases/fingerprint.py`, `contracts/fingerprint.py`), export_oracle vertex quantum, mesh/STEP band formulas, `framing.py`, `audit_log.py`.
- Test pitfalls from loop 0: insert new test classes after the end of an existing class (`tests/infc/test_document_lifecycle.py` `CapabilityProbeTest` ends after `test_warm_capability_probes_is_idempotent_and_leaves_no_temp_doc`); infc tests asserting message text must pin decimals by patching `shim.display_decimals`, never rely on the machine preference; a test that writes the real preference restores it.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/contracts/numbers.py` (new) -- `round_display(x, decimals)`, `round_floats(obj, decimals)` (skips `tolerance`/`tol` subtrees), `displayed_deviation(measured, expected, decimals)`; export from `contracts/__init__.py` -- one rule for every ring.
- [x] `tests/external/test_numbers.py` -- one fixture-driven case per I/O matrix row that `contracts` can express.
- [x] `src/freecad_buddy/usecases/shim.py` -- `display_decimals()` read live per call (no cache); `displayed(value)` helper for message strings.
- [x] `src/freecad_buddy/contracts/envelope.py` + `adapters/rpc_dispatch.py` -- internal `display_decimals` key stamped with `setdefault` on every dispatched envelope.
- [x] `src/freecad_buddy/adapters/mcp_server.py` -- `_to_call_result` pops `display_decimals` (default 2) and applies `round_floats` before both outputs.
- [x] `src/freecad_buddy/hosts/gui_external/entry.py`, `hosts/tool_catalog.py`, `adapters/export_oracle.py` -- oracles take `decimals` and use `displayed_deviation`; proxy copies `display_decimals` from the self-read envelope.
- [x] `src/freecad_buddy/usecases/assertions.py`, `exports.py` -- every band check uses the verdict rule; `hole_through` as `displayed_deviation` of the one-sided shortfall `max(material - wall, 0)`; messages print displayed measured/expected/deviation and the band as `f"{band:g}"`.
- [x] `src/freecad_buddy/usecases/queries.py`, `preview.py` -- summaries via `shim.displayed`; `_json_safe` renders `Quantity` as rounded `Value` + its unit text and `Vector` with rounded components.
- [x] Tests: infc verdict cases (matrix verdict rows) for each check family (`expect_volume`, `expect_bbox`, `expect_extent`, `hole_diameter`, `hole_position`, `hole_spacing`, `hole_through`) and STEP volume; external tests for summaries with noisy inputs, `_to_call_result` popping `display_decimals`, proxy mesh handler carrying decimals 4, and `_json_safe` Quantity/Vector; infc live-preference test (2 → 4 between calls); update pinned tests.
- [x] `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md` §8 -- add row: verdicts compare the once-rounded deviation against the raw band; output rounding at display precision.
- [x] `src/freecad_buddy/hosts/gui_addon/preferences.py` (new) + `InitGui.py` -- FreeCAD Buddy preference page with the `RoundToDisplay` checkbox; `shim.display_decimals()` returns `None` when it is off; `numbers` treats `None` as no rounding.
- [x] `benchmarks/_registry/validators.yaml` -- re-run the g0, g2 and g3 scorers whose source hash covers changed files; record new runs.

**Acceptance Criteria:**
- Given a GUI session with `Decimals=4`, when any tool returns, then JSON, `structuredContent` and text carry 4 decimals; after setting 2 in Preferences, the next call carries 2.
- Given `query_object` on a Pad of length `3.33333`, when it returns, then `Length` reads `3.33 mm`.
- Given `RoundToDisplay` off in Preferences, when any tool returns, then floats are raw (`5.999999998`) and a 6.054 mm extent fails a 6.0 ± 0.05 check; after turning it on, the next call is rounded.
- Given a no-op recompute, when fingerprint change detection runs, then behavior equals today.

## Verification

**Commands:**
- `uv run pytest tests/external` -- expected: pass
- `"C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/run_tests.py` -- expected: OK
- `uv run ruff check .` -- expected: clean; `uv run ruff format --check <changed files>` -- expected: clean (repo has pre-existing unformatted files)
- `uv run python scripts/gen_schemas.py --check` and `uv run python scripts/check_imports.py` -- expected: pass

**Manual checks (if no CLI):**
- Live GUI after FreeCAD restart: build a padded sketch with a 6 mm constraint; `query_object`, `query_mass_properties`, `verify_shape` values match the property editor screenshot.

## Spec Change Log

- Loop 0 → 1. Trigger: review findings 1-7, 14 (intent gaps) and 8 (bad_spec). Amended: frozen verdict rule (once-rounded deviation, raw band; also export checks), live per-call decimals, zero floor 1e-9, echoed tolerances unrounded; Code Map adds `_json_safe`, dispatch stamping, proxy oracle path. Avoids: false FAIL on straddling values, widened tolerances, stale decimals, `-4.28e-16` noise, `rel 0.005` shown as `0.01`, export messages contradicting verdicts. KEEP: `round_floats` at `_to_call_result` as the single output point; `shim.displayed` for message strings; fixture-parametrized `test_numbers.py` style; `_server_reporting_decimals`-style stub registry tests in `test_mcp_surface.py`. Loop-0 diff backup: scratchpad `precision-loop0.diff`.

## Review Triage Log

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | Separate rounding of measured and expected fails a correct part (6.0150001 vs 6.015, tol 0.001) | high | loop 0 `assertions.py:554-556` rounded each operand | intent_gap → resolved |
| 2 | Rounding the band widens declared tolerances | high | loop 0 `shim.displayed(band)` | intent_gap → resolved |
| 3 | Decimals 0/1 let deviation under half a step pass | medium | same root as 1 | intent_gap → resolved |
| 4 | FreeCAD applies `Decimals` live; cache kept stale value | medium | `DlgSettingsGeneral.cpp:209` | intent_gap → resolved |
| 5 | Noise near zero survives tiny rule (`-4.28e-16`) | medium | `tests/uat/run/2026-10-03-04/evidence/tc-02-04-mcp.jsonl:16` | intent_gap → resolved |
| 6 | Unitless floats rounded: echoed `rel 0.005` → `0.01` | medium | loop 0 `round_floats` walked every float | intent_gap → resolved |
| 7 | STEP/mesh verdicts raw while messages rounded | medium | `exports.py:337`, `export_oracle.py:193` | intent_gap → resolved |
| 8 | `query_object` Quantity/Vector strings keep raw floats | medium | `queries.py:211,216` | bad_spec → Code Map + task |
| 9 | New test class split `CapabilityProbeTest` | medium | loop 0 `test_document_lifecycle.py:352-484` | patch → Code Map pitfall |
| 10 | GUI proxy precision wiring untested | medium | no test touched `build_proxy_server` | patch → task |
| 11 | Only `expect_extent` tested rounded verdicts | medium | loop 0 `test_assertion_primitives.py:782-822` | patch → task |
| 12 | Summary-string rounding untested | medium | fixtures already 2-decimal | patch → task |
| 13 | Infc message tests depend on machine `Decimals` | low | unpatched tests read live pref | patch → Code Map pitfall |
| 14 | Proxy read decimals once; RPC failure pinned 2 | medium | loop 0 `entry.py:132` | intent_gap → resolved by per-call stamp |
| 15 | New format error | low | loop 0 `test_contracts.py:292` | patch (moot after revert) |
| 16 | `hole_through` two-clause form hides one-sided rule | low | loop 0 `assertions.py:1097-1100` | patch → task wording |
| 17 | FAIL message prints `<=` | false | pre-existing message format | reject |
| 18 | Schema lacks `minimum: 0` | low | readers reject negatives; fix needs gen_schemas change | reject |
| 19 | Drift test hard-codes optional field | low | moot: loop 1 adds no CapabilityBanner field | reject |
| 20 | `validators.yaml` last_run not refreshed | maybe-false | moot after revert; re-score task added | reject |
| 21 | Band off display grid: in-band deviation rounds past band (0.0156 vs 0.016 → 0.02 FAIL); verdict flips at half-step | false | specified behavior of frozen verdict rule; consequence stated at decision time ("differs from raw only within half a display step of band edge") | reject |
| 22 | Message operands disagree with deviation (`|6.0 - 6.0| = 0.004` FAIL; `|6.02 - 6.01| = 1e-07`) | medium | `assertions.py` prints displayed operands next to once-rounded deviation | defer (needs human: message format choice) |
| 23 | `text` from `summary_text`/`mirror_text` prints top-level floats raw | medium | `export_verdict.py:100` `mirror_text(report)`; `round_floats` skips strings | patch |
| 24 | `contracts/numbers.py` missing from validator source lists; `validator_sha` blind to verdict rule | medium | recomputed hashes equal committed values without numbers.py | patch |
| 25 | g3 run_id `g3r-2026-10-08-1.1.x` drops FreeCAD build | low | `validators.yaml` diff | patch |
| 26 | No band-edge test for mesh `_trimesh_checks`; headless decimals wiring untested | medium | `test_export_oracle.py` cases far from band | patch |
| 27 | Selector `_matches_diameter` edge untested | medium | every `select` names exact diameter | patch |
| 28 | G3 frames-check now resolves 2 decimals, not documented 1e-6 | medium | `score_g3_replay.py:266-273` reads MCP `structuredContent` | defer |
| 29 | Raw-key list misses echoed `tess` deflection, top-level `volume_band`, declared `expect` | low | `exports.py:234`, `export_verdict.py:90` | defer (frozen key list) |
| 30 | `query_object` `Rotation`/`BoundBox` strings still raw | low | `queries.py:227` fallback | defer |
| 31 | Verdict depends on machine `Decimals`; registry does not record it | low | scorers read live pref | defer |
| 32 | `data-contracts-design.md` lacks `display_decimals` / `numbers.py`; CLAUDE.md repo map lacks `numbers` | low | design doc line 37 | patch (design doc); defer (CLAUDE.md, agent-context file) |
| 33 | Duplicate import in `test_tool_summaries.py` | low | two `from ...queries import` | patch |
| 34 | Zero floor 1e-9 below OCC 1e-7 noise | false | human decision in loop 0 | reject |
| 35 | `{band:g}` truncates large bands | low | needs deviation ≈ band ≈ 1e6; unlikely | reject |
| 36 | `dispatch` stamps outside exception boundary | low | handlers return envelopes by contract | reject |
| 37 | Preference read many times per call; proxy retries `import FreeCAD` | low | cost microseconds; mid-call change negligible | reject |
| 38 | Old addon without stamp → proxy rounds at 2 | low | dev addon is a junction to src | reject |
| 39 | Decimals ≥ 9 vs zero floor | low | unrealistic preference | reject |
| 40 | `verify_shape`/`assertions` last_run ids unchanged | maybe-false | same-day deterministic ids; settled by re-score in #24 | reject |
