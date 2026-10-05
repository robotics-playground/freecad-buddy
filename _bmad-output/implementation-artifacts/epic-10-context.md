# Epic 10 Context: UAT Gate 1 Green

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Make the bridge do what the design says when a real agent drives it through the real FreeCAD 1.1.4 window: queries return what matches, mutations that should fail do fail, rollback is proven, and every report states what actually happened. The UAT suite and its harness must describe the product as it is, and a full UAT run must become cheap enough to repeat (scripted runner plus an independent FreeCAD probe). Trigger: UAT run `2026-10-03-04` (HEAD `bece7ac`) was the first to run all of TC-01..TC-14 and left Gate 1 red: 34 of 251 scenarios FAIL, 29 on product defects F-01..F-33 (Critical 74.7 %, needs 100 %; High 79.1 %, needs ≥ 95 %). Most defects are code that does not match an AD that is already correct. Epic 4 is paused: Story 4.3 starts only when Epic 10 is done.

## Stories

- Story 10.1: Documents and Queries
- Story 10.2: Sketch and Verify Correctness
- Story 10.3: Feature Tools and the Mutation Protocol
- Story 10.4: Render and Framing
- Story 10.5: STEP Export Schema
- Story 10.6: Session, Transport and Bounded Execution
- Story 10.7: UAT Suite and Harness Maintenance
- Story 10.7b: Scripted UAT Runner and FreeCAD Probe
- Story 10.8: UAT Gate 1 Re-run

## Requirements & Constraints

- **Each finding is a hypothesis.** Reproduce it first from `tests/uat/run/2026-10-03-04/report.md` ("Findings" gives request, output and `file:line` at `bece7ac`; re-locate lines before editing). Fix with a regression test. A finding that does not reproduce is closed with evidence, not fixed.
- **Re-run every validator score whose sources change:** G0 `verify_shape`; G2 `assertions`, `verify_sketch`, `audit_references`, `run_mutation`; G3 `spec_assertions`. Never open `benchmarks/*/heldout`. CI stays green throughout.
- **Findings by story:**
  - 10.1: F-01 tree filters (`types`, `name_pattern`, `renderable_only`) hoist matching descendants of a non-matching node; `visible_only`/`exclude_types` drop the whole subtree. F-02 new-path save/create sets label to file stem, reports `label` and `path`. F-03 bad save targets are `INVALID_INPUT` naming the path. F-12/F-20 malformed `expect_fingerprint` refused before undo. F-25 stale handle is `INVALID_INPUT`. F-30 sweep removes only `FCB_TMP_` entries.
  - 10.2: F-04 point from `start` or `center` (both is `INVALID_INPUT`); F-05 single-point `DistanceX`/`DistanceY` (omit `second`); F-06 order-independent verdict; F-17 DoF read after solving; F-19 sketch in error makes `recompute_clean` false; F-22/F-23 `verify_shape` refuses nested `fn` and `object: ""`.
  - 10.3: F-07 `second_length` builds two sides, refused with `midplane` or `up_to: "TwoLengths"`; F-08 wrong-typed `feature_set_parameters` refused pre-transaction; F-09 post-verify grades consumed sketch; F-10/F-11 rollback proof and null shapes; F-13 audit never `CLEAN` when not run; F-21 audit lines join the approval line.
  - 10.4: F-14 `include` naming a Body renders the Body or reports `empty_scene: true`. F-15 rendering a hidden object never changes live `Visibility` or the modified flag. F-16 a style with `transparency` and no `color` still applies the transparency. F-27 is not a product defect (user decision): framing measures the whole 3D view (`getSize()`), whatever its size. F-28 the fit frames a visible sketch or mesh, refuses before any camera move when nothing is measurable (datum-only), and never returns `OK` with `ratio: 0.0`.
  - 10.5: F-18 `ap:"AP242"` and the default write AP242 `FILE_SCHEMA`; paired verify checks it.
  - 10.6: TC-10-11 every headless tool bounded by registry `timeout_s`; F-33 no wait on an abandoned `debug_exec` lock; TC-99-07 second client gets the busy error; F-26 verify `/healthz` session identity before adopting `:8765`; F-24/F-31 each event logged once at the right level, no traceback on clean exit; F-32 truthful Windows ACL comment.
- **Story 10.7:** test cases read build version and tool count from the live bridge, use current field names, accept MCP schema-layer refusals, show golden models before fitting, use 1.1.4 edge numbering and menu labels, build only fixtures the bridge allows. Disputed TC-02-17, TC-08-14, TC-10-06 and TC-06-01/TC-13-06 (render shading): keep product behaviour, assert it, cite the 2026-10-04 sprint change proposal. TC-99-03/04/05: promote implemented AD-25 parts; only the gap stays expected-fail. TC-06-10/TC-13-17: build Touched state through a bridge route, or retire with reason. Harness standard forbids modal dialogs via `invoke_menu`, requires FreeCAD at the agent shell's integrity level, documents background-input routes for 1.1.4. Fix `uat_watchdog.py --since` crash on offset-aware timestamps.
- **Story 10.7b:** test-only probe reads, read-only from FreeCAD kernel and GUI state: object type, visibility, `Shape` validity, volume, bbox, modified flag, active document, camera, visible view size. Shares no code with `src/freecad_buddy`, not shipped, loads only under the UAT launch profile. A FreeCADCmd reader checks a saved `.FCStd` offline. Probe catches every planted fault in its own set. Scenarios are executable files, no LLM call; TC markdown stays the human source. Pixel check grades fixed-size, fixed-DPI captures by extent and colour samples at probe-projected points. Runner groups by launch configuration, launches non-elevated with a dedicated `-u` profile. A failed check or probe/MCP disagreement is a finding, never a retry, and goes to the `cua-driver` escalation ladder; a scripted pass needs its capture. Test plan §9: agent reads the capture for every FAIL, every disagreement, the first scenario per TC, and a random 20 % of the rest. Runner reproduces the 2026-10-03-04 verdicts for every deterministic Then it covers.
- **Story 10.8 (epic acceptance):** full TC-01..TC-14, TC-99 and G3 live replay on FreeCAD 1.1.4 through the 10.7b runner, desktop free or GUI lane in an isolated Windows session. Gate 1 green (Critical 100 %, High ≥ 95 %); Gate 2 matches documented deviations; G3 replay unchanged. Report committed under `tests/uat/run/`.

## Technical Decisions

- **AD-5 mutation protocol:** snapshot → `openTransaction` → op → `recompute()` → post-verify → commit. Post-verify: (1) recompute clean, (2) `verify_shape` on touched shapes, (3) `verify_sketch` on every touched sketch and every sketch in the `OutList` of a touched non-container object (Body membership alone never pulls a sketch in), (4) TNP audit. The audit runs on every path where the op returned; an audit that did not run is `UNSUPPORTED`, never `CLEAN`. Abort path proves rollback by digest equality; snapshot-restore path proves it with `massprops_equal` over the same object names (reopen re-serializes B-rep bytes). Feature input refusals are `INVALID_INPUT` before the bracket opens.
- **AD-6 fingerprint:** SHA-256 over per-object shape bytes sorted by `Name`, plus quantized mass properties, tagged by serializer. A null `Shape` enters as `sha256(b"")` with zeroed mass properties; an object with no `Shape` attribute stays out. FCStd/XML hashing banned as identity oracle.
- **Read-only-after-render guard:** compare `massprops_equal(before, after)` (volume, area, com, principal moments; not bbox, not digest). On a dirty document (Touched/Invalid/Error) the guard is skipped and the render reports `render.dirty_document: true`.
- **Audit log:** each mutation writes a `before` and `after` line from inside `run_mutation`, both with the full-parameter digest and real fingerprints; a call refused before the bracket gets its pair from the adapter. `debug_exec` writes its `before` line ahead of execution.
- **AD-8:** sketch PASS iff `solve()` returns 0, `FullyConstrained` and `DoF == 0`, read after `recompute()` and `solve()`. Hard fail on conflicting, malformed, fully redundant, over/under-constrained or degenerate; partial redundancy only warns.
- **AD-17:** closed status set `OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`. Input faults are `INVALID_INPUT`.
- **AD-13 / AD-19 / AD-20:** pass/fail by deterministic code or an independent grader (the 10.7b probe included, with its own sensitivity set). Epic 10 corrects shipped behaviour and opens no gate. Every call carries an explicit document handle.
- **AD-25:** bridge files live in a session-scoped workdir; temp files under `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/`. Sweep touches only `FCB_TMP_` entries of dead hosts.
- **AD-26 / AD-27:** one client session; second gets `-32000` busy. `TIMEOUT` quarantines the session until the in-flight op returns and rolls back; the method registry is the single source of `timeout_s`.
- **Render (constructed scene):** each call builds its own Coin scene; hiding is "not adding the subgraph", so `include`/`exclude`/styles never touch `Visibility`, the document or the live viewport. Default set (no `include`) uses `is_default_renderable`: own `Visibility` true, has a shape or a non-empty mesh, excludes `PartDesign::Body` and every datum/origin type (derived from `App::DatumElement`, `App::LocalCoordinateSystem` or `Part::Datum`). A visible sketch is in the set. An explicit `include` overrides the skip; an included Body draws its Tip. Style = per-object `SoSeparator` with prepended `SoMaterial` (transparency 0–1, diffuse colour optional). `empty_scene` is `true` when nothing drawable was added (no PNG written).
- **AD-34 lighting:** one off-axis `SoDirectionalLight` plus ambient, headlight 0.80. Every camera's face tone differs from background by ≥ 24/255 on one channel and lies in `[20, 235]`, with ≥ 500 interior samples. MCP render need not match live viewport shading.
- **AD-29:** live camera access only through `ViewportPort` (in `contracts/render.py`, implemented in `hosts/gui_addon/`); no viewport means the capability is unavailable, never a fabricated verdict.
- **AD-30 framing:** project the 8 union-bbox corners of the `is_default_renderable` set through `getPointOnViewport`; `fits` false iff any corner is outside. The bound is `getSize()`, the whole 3D view. Hidden-container children count as visible to both render and framing (stated limitation; change both or neither). Fit and verdict share one corner-projection routine; fit is three passes inside one `_animation_suspended` block: `fitAll(1.0)`, then `boxZoom` on the measured hull so the measured model is centred, then the verdict. A datum-only document has an empty measured set; the fit refuses it before any camera move.
- **AD-31:** `view_fit_viewport` is view-only, confirm-exempt, audited with `camera_before`; requires `doc` and refuses with `INVALID_INPUT` (naming both) when it is not the viewport's document. `fitted: true` requires its own post-fit `fits: true`, else `SPEC_FAILED` carrying the `framing` block. Cannot suspend animation → `SPEC_FAILED`.
- **AD-32 `FramingVerdict`:** top-level envelope key `framing` = `{fits, ratio, checked: computed|cached|unavailable, stale_reason}`. `ratio` = larger `extent / viewport_extent` of the projected 2D hull; `None` with `fits: false` if a corner exceeds 4× the viewport dimension. No viewport → block omitted; projection failed → `fits: null`, `checked: "unavailable"`. Non-`OK` status omits the block, except AD-31's post-fit `SPEC_FAILED`. Cache key `(fingerprint, camera_string, viewport_size, active_view_id)`. Read sits after commit, outside the AD-5 bracket.
- **AD-33:** bridge never fits spontaneously; it warns, and moves the camera only on `view_fit_viewport`.
- **AD-1 rings:** imports point inward only, `contracts/` ← `usecases/` ← `adapters/` ← `hosts/`. The 10.7b probe lives outside `src/freecad_buddy`.

## Cross-Story Dependencies

- 10.1 to 10.6 are parallel-eligible, except 10.2 before 10.3: both edit post-verify (`usecases/transaction.py`, `usecases/verify.py`).
- 10.4 shares the `is_default_renderable` predicate between render (`usecases/screenshot.py`) and framing (`usecases/framing.py`, `usecases/view_fit.py`); a change to one must hold for both.
- 10.7 runs alongside the product stories; 10.7 before 10.7b, because the runner encodes the corrected test cases.
- 10.8 is last: needs 10.1 to 10.7b done and CI green. It closes the epic.
- Epic 4: Story 4.3 is blocked until Epic 10 is done.
