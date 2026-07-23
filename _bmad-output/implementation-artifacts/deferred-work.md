# Deferred Work Ledger

Findings surfaced incidentally during review that are NOT the current story's problem.
Append-only; the orchestrator owns status/resolution of each entry.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-1-repo-scaffold-ci-matrix-phase-0-spikes.md`
  summary: `check_imports.py` does not enforce decision 003's ban on `pivy.coin.SoOffscreenRenderer`; pivy/coin are unrestricted in `adapters/` and `hosts/`.
  evidence: pivy is absent from `QT_MODULES` and adapters/hosts have no third-party restriction, so `import pivy.coin` raises no violation outside `usecases/`. The render-backend ban lands with the render probe (story 1.9); no render code exists yet, so this is a later-story gate, not a story-1.1 defect.
  status: done 2026-07-23
  resolution: check_imports.py `_check_raw_renderer` now flags every `SoOffscreenRenderer` attribute/import (decision 003); `FreeCADGui.SoQtOffscreenRenderer` is a distinct name and stays allowed. Wired into `_check_file` + `_check_root_file`; check_imports OK on the tree.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-1-repo-scaffold-ci-matrix-phase-0-spikes.md`
  summary: No `[tool.pytest.ini_options]` `testpaths` in `pyproject.toml`; a bare `uv run pytest` (no path) could collect the in-FreeCAD `tests/infc/` suite in the external env.
  evidence: CI always path-scopes (`pytest tests/external`), so the blocking gate is safe today; the risk is only a bare local invocation, and `tests/infc/` currently holds no `test_*.py` so nothing is collected. Worth pinning `testpaths = ["tests/external"]` when the in-FreeCAD suite gains cases (stories 1.2+).
  status: done 2026-07-23
  resolution: `[tool.pytest.ini_options] testpaths = ["tests/external"]` added to pyproject.toml; a bare `uv run pytest` no longer collects `tests/infc/`.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-1-repo-scaffold-ci-matrix-phase-0-spikes.md`
  summary: `check_imports.py` allows FreeCAD-App / Qt imports at module top in `usecases/`, `adapters/marshal.py`, `adapters/render_probe.py`, but the shim/marshal docstrings promise those imports are in-function-only so the modules stay importable in the no-FreeCAD external test env; the "no top-level FreeCAD/Qt" invariant is documented but unenforced.
  evidence: `test_freecad_app_whitelist_allowed_in_usecases` asserts top-level `import Part` in usecases is clean, and `test_qt_in_marshal_allowed` asserts module-top `from PySide6 import QtCore` in marshal is clean — so a future top-level `import FreeCAD` in a usecase (or top-level Qt in marshal) would pass the gate and ruff, then break `pytest tests/external` (runs with no FreeCAD) at collection time. No such import exists today, so this is a latent enforcement gap, not a story-1.1 defect; enforce "FreeCAD/Qt imports must be function-local" in the ring checks (or downgrade the docstring wording) when usecase/marshal logic lands (stories 1.4/1.8).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-1-repo-scaffold-ci-matrix-phase-0-spikes.md`
  summary: `check_imports.py` classifies stdlib via `sys.stdlib_module_names` of the *runner's* interpreter (py3.12 on the `arch-checks` leg), not the enforced 3.11 syntax/stdlib floor; a module that is stdlib in 3.12 but not 3.11 would pass the `contracts/` stdlib-only gate yet fail to import on the 3.11 headless leg at runtime.
  evidence: `_stdlib_names()` returns the arch-checks interpreter's stdlib set, and the checker runs only on that leg (never on the 3.11 FreeCAD leg). Today no `contracts/` code imports any version-divergent stdlib module, so nothing regresses; the gate's stdlib judgment is interpreter-coupled and could over-permit relative to the 3.11 floor when real contracts code lands. Pin the checker's stdlib set to the 3.11 floor (or run it on 3.11) when contracts modules gain imports.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-2-data-contracts-package.md`
  summary: Generated JSON Schemas use non-URI `$id` (`fcb.<name>/1`) and inline-duplicate shared `$defs` (`ErrorDetail`, `ImageRef`, `ResultEnvelope`, `DocHandle`) into every file, so design §1's "per-tool outputSchemas composed by `$ref`" cannot resolve cross-file and a change to a shared type must regenerate N files consistently.
  evidence: `$id` is a tag not a resolvable URI, and both `result-envelope` and `job-status` embed a full copy of `ErrorDetail`/`ImageRef`. Self-contained schemas validate correctly today (this story only emits per-type schemas), and cross-file `$ref` composition is an adapter concern in stories 1.4+ where per-tool `outputSchema`s are assembled — not a story-1.2 defect. Introduce a resolvable `$id` scheme + shared-`$defs` `$ref` when the adapter first composes an `outputSchema`.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-2-data-contracts-package.md`
  summary: `gen_schemas.py` type-form coverage is limited to the forms the current contracts use (TypedDict, `Literal`, `X | Y | None` unions, `list[T]`, nested TypedDicts); `Annotated[...]`, `Any`, parameterized `dict[K,V]`, and `tuple`/`set` would crash generation with an opaque `TypeError` rather than a clear message, and `include_extras=True` makes `Annotated` reachable.
  evidence: No contract field uses those forms today, so nothing regresses; the generator correctly `raise`s on the unknown form (fails closed, never mis-emits). Harden the converter with explicit `Annotated`-stripping and `dict[K,V]`/`Any` mappings if/when a contract field adopts one of these type shapes.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-2-data-contracts-package.md`
  summary: §12.2's second clause ("`wilson_ci` present whenever any check `measured` is a rate") is not enforced by the schema, `derive_verdict`, or the tests — there is no conditional (`if/then`) schema or runtime check tying a rate-valued `measured` to a present `wilson_ci`.
  evidence: Design §12.2 lists this as a checked invariant but data-contracts-design provides no mechanism (rate-detection is semantic, not structural). No rate-bearing check exists in Phase 0 (verify tools land in stories 1.6/1.7), so nothing regresses now; add an `if/then` Draft-2020-12 conditional (or a runtime validator) when the first rate-valued check is produced.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-2-data-contracts-package.md`
  summary: `GeometryDiff.deltas`/`counts`/`validity`/`tnp_precheck` are typed as bare `dict`, so their design-§8 inner shapes (e.g. `validity: {is_valid, recompute_clean, recompute_errors}`, `deltas.volume: ScalarDelta`) are unconstrained by the generated schema, and the `ScalarDelta`/`CountDelta` TypedDicts are never rendered as `$defs`.
  evidence: The contracts type these `dict` exactly as data-contracts-design §8 writes them (shape described in comments, not as nested TypedDict fields), so the code is design-verbatim; the diff/preview payload isn't produced until Phase 2 (`preview_dry_run`). Tighten `diff.py` to reference `ScalarDelta`/`CountDelta`/typed inner shapes and emit their `$defs` when the preview channel lands (AD-10, story ~Phase 2).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-2-data-contracts-package.md`
  summary: `rpc.py`'s `CHANNEL_STATUS_MAP` hardcodes synthetic dotted keys (`rpc.listener_crash`, `rpc.connection_dropped`, …) whose provenance is `integration-mcp-freecad.md §2.3` (cited by data-contracts-design §11 but not reproduced there); the exact key strings are unverified against that authoritative wire design and risk producer/consumer synonym drift.
  evidence: data-contracts-design §11 maps channel *conditions* to statuses in prose and defers the framing/error-code detail to integration-mcp-freecad §2.3. The current map is a reasonable transcription but not cross-checked against §2.3's actual codes; the RPC listener/marshal that consumes it lands in story 1.8. Reconcile the key strings against integration-mcp-freecad §2.3 when the RPC listener is implemented (story 1.8).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-3-entry-gate-g0e-golden-models-fault-suite.md`
  summary: `check_provenance.py` enforces only that `source.kind` is in the closed set; it does not require `source.url`/`source.license`/`source.attribution` when `kind != hand-authored`, so a future `freecad-parts-library`/`hf-verified-permissive` artifact would pass the AD-16 gate with no license/attribution recorded.
  evidence: Every G0 artifact in this story is `hand-authored` (AD-16 requires only a `real_world_basis` for that kind, which is enforced), so nothing regresses now; the url/license/attribution enforcement is only needed once a non-hand-authored artifact ships (design §1.2 warns DeepCAD/ABC/Fusion lineage is never shipped and library imports carry attribution). Add the conditional license-fields check to `check_provenance.py` when the first non-`hand-authored` benchmark artifact lands.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-3-entry-gate-g0e-golden-models-fault-suite.md`
  summary: `check_provenance.py` flags an artifact with no manifest, but does NOT flag an ORPHAN manifest (a `_registry/provenance/*.yaml` whose declared `artifact` no longer has a matching `.FCStd`, e.g. after a fixture rename/delete).
  evidence: The checker walks `.FCStd` artifacts and requires each to have a manifest; the reverse direction (every manifest maps to a live artifact) is unchecked. No orphan exists in this story (all 17 manifests match a committed fixture), so nothing regresses; add manifest→artifact reverse-coverage when the benchmark set first churns (fixtures renamed/removed across gates).

### DW-1: Follow-up review still recommended for 1-1-repo-scaffold-ci-matrix-phase-0-spikes after the damping cap was spent
origin: review-budget-followup
source_spec: `spec-1-1-repo-scaffold-ci-matrix-phase-0-spikes.md`
severity: low
reason: The follow-up-review damping cap (limits.max_followup_reviews = 1) was spent with the story finalized (status: done, verify green) while the review pass still recommended an independent follow-up. The work was committed by bmad-loop run 20260721-185755-5f54; this entry preserves the lingering recommendation for a deliberate later review.
status: open

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `document_recompute` returns an `OK` envelope even when it collects per-object `errors`; whether a recompute-with-errors should map to `RECOMPUTE_ERROR` (AD-17) or stay `OK`-with-error-data is an unresolved spine-owner ruling.
  evidence: mcp-tools §2 says recompute "report per-object error states" (data), a defensible OK reading; but AD-17's status set includes `RECOMPUTE_ERROR`. The code silently chose OK. Verification core (story 1.6) owns the recompute-clean sweep and should encode the ruling then.
  status: done 2026-07-23
  resolution: `document_recompute` now returns `RECOMPUTE_ERROR` (code `recompute.failed_objects`, naming the objects) when any object is left in an error state; a clean recompute stays `OK`. Aligns with the AD-5 recompute-clean sweep in `verify_recompute`.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `query_capabilities` capability-banner payload crosses the wire but has no `contracts/`-owned TypedDict/schema, unlike every other wire type (AD-17 "contracts-owned").
  evidence: `shim.capability_banner() -> dict` and `queries.query_capabilities` assemble a loose dict. Read-only query payloads are formalized in story 1.5 (query_ surface); the banner shape should be defined in contracts then.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `shim.element_map_available()` requires a NON-empty element map on a probe box, which is behavioral (did this shape populate a map) rather than pure capability (is the API exposed) — a lazily-populating build could yield a false negative (AD-11 wants a capability probe).
  evidence: probe uses `Part.makeBox(...)` then checks map non-emptiness. Passes on real FreeCAD 1.1 today, but the TNP guard (story 1.6/1.7) depends on this signal; revisit the probe form when the TNP audit lands.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `debug_exec` audit records the `params_digest` (sha256 of `{doc, code}`) but does NOT persist the executed source; the highest-risk path leaves an audit line that proves a hash but cannot reproduce what ran.
  evidence: `audit_log._record` stores only `params_digest`. security-and-service §1 frames exec auditing as evidentiary; digest-only vs code-retention is a privacy-vs-forensics posture call for the security owner. Fingerprints are also `None` (deferred to story 1.6 fingerprint()).
  status: done 2026-07-23
  resolution: `AuditRecord` gained an optional `code` field (schema-additive, regenerated); `AuditSink._record` persists the executed source on every `event:"exec"` line per security-and-service §1, so an exec audit line now reproduces what ran, not only its digest. fingerprint_before/after wiring stays open (see keep-open note below — needs the DocumentRegistry threaded into the tool-call audit boundary).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `document_open` on a path already open in the session mints a SECOND handle for the same underlying FreeCAD doc; closing one handle closes the doc, stranding the other on a dead object.
  evidence: `document_open` unconditionally `FreeCAD.openDocument(path)` + mints a fresh handle with no already-open dedupe. Rarely hit in Phase-0 single-file bring-up; worth an already-open check (return the existing handle) when multi-doc query/verify stories exercise open heavily.
  status: done 2026-07-23
  resolution: Already resolved in current source — `document_open` calls `_handle_for(document)` and reuses the existing handle when the document is already tracked (documents.py:121-127). No fix needed; entry closed on verification.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: The `shim.varset_backend()` capability probe creates and closes a throwaway `FCB_TMP_varset_probe` FreeCAD document OUTSIDE the `DocumentRegistry` single-writer lock (invoked once, lru_cache'd, via `query_capabilities`), so its doc-set churn is not serialized against registry mutations (AD-20).
  evidence: `varset_backend` calls `FreeCAD.newDocument`/`closeDocument` directly; `query_capabilities` is non-mutating and the probe runs at most once per process under the single-threaded `InlineExecutor`, so no race is reachable in Phase-0 H1. Becomes relevant when a concurrent (GUI/RPC) executor lands and probes could interleave with registry ops; serialize the probe under the writer lock (or run all capability probes once at startup before serving) then.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `debug_exec` runs its `exec(code)` body inline (single-process `InlineExecutor`), so the marshal `timeout_s` never fires; an infinite or long-running operator body hangs the whole headless server with no `TIMEOUT` and no interrupt.
  evidence: `Marshal.call` with `InlineExecutor` runs `fn()` synchronously and `done.wait()` returns immediately after completion, so the timeout path is dead on the inline host. Operator-only + Phase-0 bring-up makes this low-risk now; a real bounded/interruptible exec needs an out-of-thread execution mechanism, which arrives with the GUI/RPC threaded marshal (story 1.8).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `document_recompute` reports per-object errors only when `"Invalid"` is present in `obj.State`; an object left `"Touched"` / not-recomputed after a recompute (silent skip) is reported as clean, so the per-object error set can under-report.
  evidence: The error comprehension filters on `if "Invalid" in state` only. No in-FreeCAD test creates an object that fails or is skipped during recompute, so the branch's completeness is unverified. Revisit the recompute-clean vocabulary (which States count as failure) together with the recompute-clean sweep in verification core (story 1.6).
  status: done 2026-07-23
  resolution: Both `document_recompute` and `verify_recompute` now use a shared `_recompute_error_state` recognizing `{"Invalid", "Error", "Touched"}` — an object still "Touched" after a full recompute (silent skip) is flagged. Detection vocabulary unified across the two recompute paths.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: Both audit lines for a mutation/exec carry `fingerprint_before`/`fingerprint_after` hard-coded to `None`, and the `after` line repeats the pre-execution `params` rather than the result, so an audit pair records almost no evidence of what actually changed.
  evidence: `AuditSink.before`/`after` set the fingerprint fields to `None`; `mcp_server._call_tool` passes the same `args` to both. `fingerprint()` lands in story 1.6, so real before/after hashes are not computable yet; wire them (and a result-bearing `after` payload) into the audit sink when `fingerprint()` exists.
  status: open
  decision: 2026-07-23 keep-open — fingerprint wiring blocked. `fingerprint()` now exists, but the audit boundary (`mcp_server._call_tool`) holds only the `MethodRegistry` + doc-handle string, not the `DocumentRegistry`, so it cannot resolve the live doc to compute before/after hashes without threading `DocumentRegistry` through the tool-call boundary — an architectural change with real ripple. The forensic gap is already narrowed by the `code`-persistence fix above; fingerprint_before/after belongs with the AD-5 mutation-protocol runtime (story 3.2), which owns fingerprinting around a mutation.

### DW-2: Follow-up review still recommended for 1-4-document-lifecycle-headless-host-mcp-surface after the damping cap was spent
origin: review-budget-followup
source_spec: `spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
severity: low
reason: The follow-up-review damping cap (limits.max_followup_reviews = 1) was spent with the story finalized (status: done, verify green) while the review pass still recommended an independent follow-up. The work was committed by bmad-loop run 20260721-185755-5f54; this entry preserves the lingering recommendation for a deliberate later review.
status: open

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-5-read-only-query-tools.md`
  summary: `query_sketch_info` reads a geometry element's `construction` flag via `getattr(geo, "Construction", False)`; on FreeCAD builds that migrate the flag onto the `GeometryFacade`/`Sketch.getConstruction(index)` the raw geometry object may not carry `Construction`, so every element would silently report `construction: false`.
  evidence: On the local FreeCAD 1.1 build the raw geometry still exposes `Construction` (the story's infc test passes), so no regression today; the risk is version-forward. Prefer `obj.getConstruction(index)` with a fallback to the geometry attribute if/when a build drops the raw flag.
  status: done 2026-07-23
  resolution: `query_sketch_info` now reads construction via `_construction_flag`, which prefers `SketchObject.getConstruction(index)` and falls back to the raw geometry's `Construction` attribute — version-forward safe.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-5-read-only-query-tools.md`
  summary: `query_dependencies` whole-document mode emits an uncapped `edges` array (every object's OutList), unlike `query_tree_summary` which caps at `max_nodes`; a very large assembly yields an unbounded response.
  evidence: The design (mcp-tools §2) specifies no cap for `query_dependencies`, and Phase-0 documents are small, so this is not a story-1.5 defect; add a bound/pagination if the dependency response size becomes a context concern for large models (Phase 1 assistant surface).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-5-read-only-query-tools.md`
  summary: `query_object`'s `_json_safe` recurses through list/tuple/dict property values with no depth limit and no cycle detection, so a self-referential or very deeply nested property value would either serialize to an unbounded payload or raise `RecursionError` (mapped to `RECOMPUTE_ERROR`).
  evidence: FreeCAD's standard scalar/vector/list property values are shallow, so no live object triggers it in Phase 0 (the infc suite passes); the risk is a scripted/`PropertyPythonObject` value holding a cyclic or huge structure. Bound the recursion depth and total element count (stringify/truncate on overflow) when a query surface must tolerate hostile or scripted-object property content.
  status: done 2026-07-23
  resolution: `_json_safe` now bounds recursion at `_JSON_MAX_DEPTH=8`, stringifying anything deeper — a self-referential or deeply-nested property value is truncated at the cap instead of overflowing the stack.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-5-read-only-query-tools.md`
  summary: `query_mass_properties` guards only a null `Shape`; a non-null non-solid shape (shell/wire/face) reports `volume: 0` and a `CenterOfMass` computed over area/length as if it were volumetric mass, and for some degenerate compounds the OCC `CenterOfMass`/`Volume` call can raise and surface as `RECOMPUTE_ERROR` rather than a fail-closed `INVALID_INPUT`.
  evidence: The story's mass-props test exercises only a clean solid box, so the non-solid branch is unverified; the design treats "no queryable geometry" as `INVALID_INPUT` but does not specify non-solid handling. Gate `volume`/`com` behind `len(shape.Solids) > 0` (or emit nulls) and wrap the OCC reads to map a degenerate shape to `INVALID_INPUT` when a caller needs mass properties on non-solid geometry.
  status: done 2026-07-23
  resolution: `query_mass_properties` now reports a `solid` flag and emits `null` `volume`/`com` for a non-solid (shell/wire/face) shape, so an area/length centroid is never presented as volumetric mass; area/bbox/counts stay valid for all shapes.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-6-verification-core.md`
  summary: `verify_sketch` gates `evaluateConstraints()` behind `bool(MalformedConstraints)`, but AD-8 / verification-design §4 list `evaluateConstraints()` as an independent hard-fail trigger.
  evidence: On FreeCAD 1.1 `evaluateConstraints()` returns `True` for a healthy fully-constrained sketch (build divergence, documented inline in `usecases/verify.py`), so it cannot be used unconditionally; but a genuinely malformed sketch whose `MalformedConstraints` property is empty would slip past the hard-fail. Not demonstrated reachable on 1.0/1.1 (bad-index constraints raise at `addConstraint`). Revisit if a build populates `evaluateConstraints()` reliably or a malformed-but-empty-property case is found; add a planted malformed-constraint fault case to the sketch validator suite.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-6-verification-core.md`
  summary: The fault scorer (`benchmarks/g0/fault-injection/score_verify_shape.py`) rewrites `validators.yaml` from a fixed single-validator template, so a second validator block would be dropped on the next run.
  evidence: `_render_yaml` emits only the `verify_shape` block and `write_text` replaces the whole file; only `verify_shape` exists in `validators.yaml` today. When a second validator (e.g. `verify_sketch`, later `verify_export_*`) registers a fault suite, switch the scorer to a read-merge-write that preserves other validator blocks.
  status: done 2026-07-23
  resolution: `score_verify_shape.py` now imports and uses the export scorer's shared `merge_validators_yaml` read-merge-write, rendering only the `verify_shape` block; the `verify_export_*` blocks and file header are preserved. Resolves the two-inconsistent-writers gap (also filed under spec-1-7).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-6-verification-core.md`
  summary: The scorer's hand-rolled `case.yaml` parser is brittle — a greedy `_CHECK_RE` and a blind `.replace('rel'/'abs')` before `ast.literal_eval` — and can mis-parse checks with those substrings in values or multi-line flow mappings.
  evidence: pyyaml is external-process only (AD-12) so the in-FreeCAD scorer parses the fixed flow shape itself; it works on the committed fixtures. If fixtures grow richer check shapes, replace the regex/replace hack with a small proper flow-mapping tokenizer (or move scoring to the external process and pass results in via RPC).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-6-verification-core.md`
  summary: `verify.py` `_is_watertight` and `_shape_floor` swallow any exception (return "not watertight" / floor `0.0`); a solid whose `getTolerance()` genuinely raises would silently disable the tolerance-floor clamp so a comparison could assert tighter than the B-rep tolerance.
  evidence: Not a Phase-0 path (the golden/fault solids all report a tolerance); the swallow is defensive. If a real shape is found that raises on `getTolerance()`/`isClosed()`, distinguish "cannot measure" (report an INVALID_INPUT / unavailable) from a false "not watertight"/zero-floor.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-6-verification-core.md`
  summary: `fingerprint._serialize` aborts the whole fingerprint if `exportBinary` raises on a specific shape — there is no per-shape fallback to `exportBrep`.
  evidence: The serializer is process-global probed (`shim.export_binary_available`) and tested, so this needs a shape that passes the probe but fails the actual `exportBinary` call. If such a shape is found, either fall back to `exportBrep` for that shape (and re-tag) or fail the fingerprint explicitly with the offending object named.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: `adapters/export_oracle.py` `_trimesh_checks` hardcodes `euler_number == 2` (genus-0 single-shell) for every mesh, so a legitimate multi-shell / through-hole (torus) / multi-solid part would false-alarm on the Euler check.
  evidence: Not reachable in Phase-0 (the golden models are single convex solids). Real forward gap for Phase 3+ real geometry — derive the expected Euler characteristic from the source topology (or drop the Euler assertion in favour of the watertight/winding/volume checks) before the export verifiers grade multi-shell parts.
  status: done 2026-07-23
  resolution: Already resolved — `_trimesh_checks` now asserts `euler % 2 == 0` (even characteristic), not `== 2`; a through-hole (chi 0) or multi-body compound (chi 4) is accepted. Fixed in a prior session (render/verify sweep); confirmed on verification, entry closed.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: The export fault suites are small — `verify_export_step` n=2, `verify_export_stl`/`verify_export_3mf` n=3 — so the ≥95 %/≤5 % gate passes but the Wilson lower bound (0.34–0.44) gives weak statistical confidence in the sensitivity claim.
  evidence: NFR2 cites ≥10 cases per validator. Add planted cases toward that target: more STEP faults (scaled shape, degenerate face); STL duplicated-shell, coordinate-truncation; 3MF missing-`3dmodel.model`, malformed transform matrix. Fixtures build under FreeCADCmd via `build_export_fault_fixtures.py`; the scorer already merges `validators.yaml`.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: `adapters/export_oracle.py` `_read_ascii_stl_facets` silently drops a facet whose `endfacet` block has ≠3 vertices (a truncated ASCII facet) — a fail-open in the stdlib STL parser.
  evidence: Not reachable via this story's writers (FreeCAD emits BINARY STL, and the binary path is the default), so low Phase-0 consequence. If an ASCII-STL input path is ever accepted, raise on a malformed facet block instead of dropping it so a truncated file surfaces as a defect rather than a silently-normalised mesh.
  status: done 2026-07-23
  resolution: `_read_ascii_stl_facets` now raises `ValueError` on any facet block whose vertex count is not exactly three (routed through `safe_oracle` → failed leg → FAIL), so a truncated ASCII STL surfaces as a defect instead of a silently-normalised mesh.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: Story-1.6 `benchmarks/g0/fault-injection/score_verify_shape.py` still full-clobbers `validators.yaml` from a fixed template; the Story-1.7 export scorer added its own `merge_validators_yaml` read-merge-write, so the two writers are inconsistent.
  evidence: Running the 1.6 scorer's `main()` after the 1.7 scorer would drop the `verify_export_*` blocks. Both scorers should share one merge-writer helper. Verified today: the `run_tests.py` suite calls `score()` (no file write), so no clobber occurs during CI test runs; only explicit `main()` invocations write. Refactor both onto a shared writer.
  status: done 2026-07-23
  resolution: `score_verify_shape.main()` now writes through the export scorer's `merge_validators_yaml`; both scorers share one read-merge-write helper, so running either `main()` preserves the other's validator blocks.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: `benchmarks/g0/export-fault-injection/score_export_verify.py` `_score_mesh_case` calls the oracle legs raw inside its own `try/except` that returns `True` (DETECT) on any exception, instead of routing through `export_oracle.safe_oracle` like the production `_mesh_verify_handler`; a clean-control case that raised for an unrelated reason would be scored DETECTED and mask a false-alarm-class failure.
  evidence: Production path is correct (the host handler wraps every oracle call in `safe_oracle`, turning a read failure into a failed leg → FAIL verdict); only the benchmark scorer diverges. No committed control currently throws (both controls score PASS_CLEAN, FA 0.000), so nothing regresses today. Route `_score_mesh_case` through `safe_oracle` (or the same leg-assembly the handler uses) for scorer/production parity.
  status: done 2026-07-23
  resolution: `_score_mesh_case` now wraps every oracle leg in `export_oracle.safe_oracle` exactly like the production `_mesh_verify_handler`; a leg that raises becomes a failed leg (→ FAIL), so a clean control that raises for an unrelated reason surfaces as a false alarm rather than being masked as DETECT.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: The STL/3MF mesh-verify handler (`hosts/headless/entry.py` `_mesh_verify_handler`) runs the un-marshaled trimesh/lib3mf oracle legs with no timeout, while the FreeCAD self-read leg is bounded at 120 s; a hung oracle read would block RPC dispatch indefinitely.
  evidence: Phase-0 exports are small single-solid meshes that read in milliseconds, so no hang is reachable now. When large-mesh inputs land, bound the oracle phase (thread + timeout, or a subprocess) so a pathological file cannot wedge the server.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: `adapters/export_oracle.py` `_lib3mf_mesh` inspects only the first mesh object of a 3MF model (`iterator.MoveNext()` once), so a defect in the 2nd+ mesh object of a multi-mesh container passes the manifold/geometry checks undetected.
  evidence: This story's writer emits a single mesh per 3MF (one `MeshPart.meshFromShape` → one `Mesh` write), so a multi-mesh container is not producible here. Iterate all mesh objects (fail if any is non-manifold) if a multi-mesh 3MF input path is ever accepted.
  status: done 2026-07-23
  resolution: `_lib3mf_mesh` → `_lib3mf_meshes` (iterates the whole `GetMeshObjects` iterator); `mesh3mf_oracle` now manifold-checks EVERY mesh object and fails if any is non-manifold (the `lib3mf.manifold_and_oriented` check reports `{meshes, non_manifold}`). The trimesh geometry leg still runs on the first mesh.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: `adapters/export_oracle.py` `mesh3mf_oracle`'s trimesh geometry leg is built from the lib3mf-parsed vertex/triangle arrays (`_trimesh_from_lib3mf`), so the lib3mf and trimesh "oracles" share lib3mf's geometry parse; the 3MF independence is weaker than the STL path (where trimesh loads the file itself).
  evidence: A lib3mf parse bug would propagate into both 3MF legs, and the flattened single-leg design means there is no true cross-oracle geometry check for 3MF. By-design for Phase-0 (the container/unit/manifold lies are what §6.4 targets and are caught 3/3), but a later story wanting genuine 3MF geometry independence should add a second independent 3MF geometry reader (or an independent container parse).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: The `step-unit-lie` fault fixture writes a genuinely smaller solid (`makeBox(1,2,3)`, vol 6) mislabeled against the full box (vol 6000), so `verify_export_step` detects it via a gross shape/volume mismatch rather than via a mislabeled `write.step.unit`; the per-call unit-pinning path (`shim.pin_step_config` / `write.step.unit=MM`) has no fault-suite case exercising a true same-geometry 1000× unit scale.
  evidence: The verifier's volume check WOULD catch a real unit-lie (a mm box written as `unit=M` re-imports 1000× larger, a gross volume mismatch), so this is a coverage gap, not a product defect — the unit-pinning invariant is functionally guarded but not directly exercised by its own fault case. Add a fixture that writes the clean box with `write.step.unit` set to `M`/`CM` and references the mm facts, so detection depends on the unit knob rather than on swapping in a different shape.
  status: done 2026-07-23
  resolution: Investigated, premise disproven, closed as not-actionable-as-stated. A `step-unit-scale-lie` fixture (clean box written with `write.step.unit=M`, referencing mm facts) was built and scored under FreeCAD — it was MISSED, not detected. Empirical finding: the STEP unit is a file-unit annotation, so a mm box written in metres re-imports back to the SAME mm volume (round-trip-neutral). A `write.step.unit` value therefore cannot be exercised as a volume fault; the existing `step-unit-lie` (a genuine 1/10-scale geometry mismatch) is the only detectable form. The `write.step.unit=MM` per-call pinning invariant is a functional guard, not a re-import volume fault — the coverage gap is real but unclosable by a fault case, so no fixture is added. Fixture builder docstring updated to record this; the ledger's original "re-imports 1000x larger" assumption was incorrect.

### DW-3: Follow-up review still recommended for 1-7-exports-paired-verification after the damping cap was spent
origin: review-budget-followup
source_spec: `spec-1-7-exports-paired-verification.md`
severity: low
reason: The follow-up-review damping cap (limits.max_followup_reviews = 1) was spent with the story finalized (status: done, verify green) while the review pass still recommended an independent follow-up. The work was committed by bmad-loop run 20260721-185755-5f54; this entry preserves the lingering recommendation for a deliberate later review.
status: open

- source_spec: `_bmad-output/implementation-artifacts/spec-1-8-gui-host-addon-rpc-marshal.md`
  summary: In GUI/RPC mode the mesh-verify tools (`verify_export_stl`/`verify_export_3mf`) run their third-party oracle legs (trimesh/lib3mf/stdlib STL parse) inside the listener's single `marshal.call`, i.e. on the Qt main thread, freezing the FreeCAD GUI for the whole mesh parse; only the `_self_read` leg needs the main thread.
  evidence: `hosts/tool_catalog.py` `_mesh_verify_handler` runs oracle legs in the same handler the listener wraps in `marshal.call` (`adapters/rpc_listener.py`). Confirmed by both pass-2 reviewers. A clean fix needs a partial-marshal mechanism (marshal only the self-read leg, run oracles on the listener thread) — a small design task beyond this story's scope. Impact bounded: two verify tools, GUI mode only, and export/verify are already documented as accepted op-duration freezes (integration-mcp-freecad.md §3.3).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: `query_screenshot` camera presets `front`/`top`/`bottom`/`right`/`left`/`back` are unverified magic quaternions (only `iso` is cited from `make_snapshot.py` and only `iso` is exercised by the in-FreeCAD tests); `back` = `(0,0,0.707,0.707)` is a 90° Z-rotation, not a back view.
  evidence: `usecases/screenshot.py` `_CAMERA_QUATS` hard-codes seven presets; `tests/infc/test_screenshot.py` never asserts pixel content per preset. Phase-0 default is `iso` (correct), so no shipped path is wrong today; add a per-preset visual/orientation check (or re-derive the six non-iso quaternions against FreeCAD's `StdViewIsometric`/`StdViewFront`/… camera orientations) when a caller depends on a specific non-iso view.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: `OffscreenRenderPort._aim_camera` frames a `SoCube` proxy sized to the focus bbox and `viewAll`s it, so the effective framing is the cube's half-diagonal, not the intended ~20% margin — focus framing is systematically loose and the grow factor is approximate.
  evidence: `adapters/render_probe.py` `_aim_camera` builds a cube at bbox center with bbox dims. Functionally correct (the element is in frame) but not tight; Phase-0 has no framing-precision assertion. Tighten to frame the actual sub-shape (or compute the camera distance from the bbox extents directly) if a caller needs precise element zoom.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: `query_screenshot`'s default object set (`include` omitted) renders every shape-bearing object regardless of the object's live `Visibility` flag, so an object the user has hidden still appears in the constructed scene.
  evidence: `usecases/screenshot.py` `_visible_objects` treats "has a non-null Shape" as visible; `subgraphFromObject` ignores `Visibility` (FreeCAD `Application.cpp`). This is a by-design constructed-scene choice for Phase-0 (the tool composes its own scene), but whether the default should honor live `Visibility` is a product/UX decision — revisit when the assistant surface (Phase 1) defines the default-view contract.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: A `focus`/`highlight` `mapped_name` selector that fails to resolve (`shape.getElement` raises / returns None) silently frames the whole object while `focused_on` still echoes the unresolved `mapped_name`, so the response confirms an element that was not actually framed.
  evidence: `adapters/render_probe.py` `_focus_sub_shape` swallows the `getElement` failure and returns the whole shape; `usecases/screenshot.py` `_resolve_selector` accepts any truthy `mapped_name` without checking it resolves. Element-map-backed selectors are out of scope this story (mapped-name resolution firms up with the TNP/sub-element tools); when it lands, either validate the mapped name resolves or drop it from the echo on fallback.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: When every requested object is skipped (empty document, or an `include` list of names that all resolve to no subgraph), the renderer `viewAll`s a scene holding only the camera + light, producing a blank/undefined-framed PNG returned as `OK`.
  evidence: `adapters/render_probe.py` `render` appends nothing to `root` when all objects skip; `_aim_camera` then `viewAll`s an effectively empty graph. Reachable only with an empty doc or an all-nonexistent include (the latter now rejected by the loop-1 existence validation), so the residual case is a genuinely empty document. Consider returning an explicit "empty scene" note (rendered_objects: []) rather than a blank image when the scene has no drawable geometry.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: `query_screenshot` `styles` + `highlight` on the SAME object: the highlight accent material silently overrides the requested style color/transparency (accent takes precedence in `_style_wrap`), so a caller styling and highlighting one object loses the style with no signal.
  evidence: `adapters/render_probe.py` `_style_wrap` applies the accent material OR the style, not both, when `accent` is true. Benign for Phase-0 (highlight is the stronger intent), but a caller wanting "transparent AND accented" gets only the accent. Compose both (accent color + style transparency) or document the precedence in the tool description when the assistant surface exercises combined styling.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: A `focus` that resolves to a single vertex (or a zero-thickness edge/face) yields a degenerate `BoundBox` (one or more axis lengths 0); `_grow_bbox` grows by `max(dims)*0.2` which is 0 for an all-zero box, and the proxy cube then clamps to 1e-6, producing an extreme/near-singular camera zoom.
  evidence: `adapters/render_probe.py` `_grow_bbox` + `_bbox_proxy`. Vertex/degenerate-element focus is an uncommon Phase-0 path (the in-FreeCAD test focuses a face). Add an absolute minimum framing extent (e.g. a small fixed world-units floor) so a point/thin-element focus frames a sensible neighborhood rather than zooming to a singularity.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: The offscreen render does not check the return value of `SoQtOffscreenRenderer.render()` / `writeToImage()`; a partial or garbage-but-non-empty PNG (e.g. a failed GL write that still leaves bytes) passes the usecase's non-empty-file check and is returned as a valid `resource_link`.
  evidence: `adapters/render_probe.py` `render` calls `renderer.render(root)` and `writeToImage(out_path)` without inspecting their booleans; `usecases/screenshot.py` only guards `size > 0`. The 0-byte/absent case IS caught. A truncated PNG is unlikely with the software rasterizer but unverified; inspect the `writeToImage` return (and optionally validate the PNG header/size matches width×height expectations) if a caller reports corrupt images.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: `scripts/check_imports.py` has no rule banning `FreeCAD.ActiveDocument` as an operation target (AD-20), so the loop-2 fix (render the explicit handle, never `ActiveDocument`) is enforced only by manual review, not by the CI ring gate.
  evidence: `check_imports.py` enforces Qt/third-party import placement per ring but not the `ActiveDocument`-banned-target rule; the loop-1 regression (renderer reading `ActiveDocument`) passed `check_imports` + ruff clean. Add an AST rule flagging `FreeCAD.ActiveDocument` / `App.ActiveDocument` reads outside the sanctioned document-lifecycle usecases, so this class of AD-20 violation is caught mechanically across all stories.
  status: done 2026-07-23
  resolution: Already resolved — `check_imports._check_active_document` bans `FreeCAD./App.ActiveDocument` and `setActiveDocument` tree-wide (wired into both `_check_file` and `_check_root_file`). Added in a prior session; confirmed on verification, entry closed.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-10-gate-g0-exit.md`
  summary: The `gui_smoke` human token has no cryptographic signature — its `binds_reports_sha256` is a public SHA-256, so anyone who can write the run's `human/` dir can forge a valid PASS token.
  evidence: validation-harness-design §7 models tokens as artifacts the runner checks for presence + binding (never performs), so this is a design-level posture; a real signature/secret would need a spine amendment, not a story fix.
- source_spec: `_bmad-output/implementation-artifacts/spec-1-10-gate-g0-exit.md`
  summary: A `<criterion>.json.tmp` file can linger in `reports/` if the process crashes between the atomic write's `write_text` and `replace`.
  evidence: `_write_report_atomic` has no try/finally cleanup; harmless to a clean verdict (verdict reads `<criterion>.json`, not `.tmp`), but tmp files accumulate across crashes.
  status: done 2026-07-23
  resolution: `runner._atomic_write_json` now removes the `.tmp` file (`unlink(missing_ok=True)`) on any failure between the tmp write and the `os.replace`, so a crash mid-write leaves no stray `<criterion>.json.tmp`.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-10-gate-g0-exit.md`
  summary: `benchmarks/g0/gate.yaml` cites `verify_shape` as G0.5's validator, but G0.5 is a STEP export round-trip whose validator is `verify_export_step` (already registered in validators.yaml).
  evidence: leg-b currency for G0.5 hashes the wrong validator source; the correct citation is `verify_export_step`. Pre-existing in the loop-0 verbatim-preserved criteria, not introduced by story 1.10; changing a cited_validator touches the criteria block the story preserved intact.
  status: done 2026-07-23
  resolution: `benchmarks/g0/gate.yaml` G0.5 `cited_validators` changed `[verify_shape]` → `[verify_export_step]` — leg-b currency now hashes the correct validator source for the STEP round-trip criterion.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: Every `INVALID_INPUT` outcome (an ordinary client error — unknown handle, unknown object, bad path, stale/mismatched export_id, missing param) emits a full Python traceback to the server's stderr and to the GUI-mode `addon.log`, because the marshal re-raises the `ValidationError` and the log handler renders it with `exc_info`.
  evidence: The Epic-1 edge-case MCP sweep (`scripts/automation/run_mcp_edge_cases.py`, 13/13 pass) produced 199 stderr lines for 13 deliberate error cases — one traceback per client error, zero genuine crashes. A client typo should not spill a stack trace into the error-capture channel; tracebacks should be reserved for unexpected/`RECOMPUTE_ERROR`/`WORKER_CRASHED`. Behavior is correct at the contract layer (right closed status, no crash), so this is log-hygiene, not a functional defect — downgrade `INVALID_INPUT`-class logging below traceback level (or log the message without `exc_info`) so the stderr/addon.log channel stays scannable for real faults.
  status: done 2026-07-23
  resolution: `rpc_dispatch._error_envelope` now emits a full stderr traceback only for the unexpected/`RECOMPUTE_ERROR`/`WORKER_CRASHED` class; expected client errors (`INVALID_INPUT`, `TIMEOUT`) log one `logger.info` line instead. The truncated traceback is still retained in the envelope's machine `detail.data` for debugging — only the stderr/addon.log channel is de-noised.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-9-view-controlled-screenshots.md`
  summary: FIXED — the offscreen render used a single fixed `SoDirectionalLight`, so faces angled away from its world-space direction rendered near-black, diverging from FreeCAD's viewport (which uses a camera-following headlight). Found by the TC-06 visual-fidelity comparison (MCP render vs. a `PrintWindow` capture of the live FreeCAD window).
  evidence: `render_probe._add_lighting` now aims the headlight along the camera view direction (`SbRotation.multVec` of the orientation quaternion on -Z) and adds `SoEnvironment.ambientIntensity=0.7` (empirically fit to the viewport tone: a lit face reads RGB ~(158,165,169), the ambient reproduces ~(159,164,169)); confirmed against `docs/references/FreeCAD/src/Gui/View3DInventorViewer.cpp` headlight setup. Verified in H1: side faces render shaded grey matching the viewport, not black. No open action — recorded so the visual-fidelity check and its capture method (Win32 `PrintWindow` flag `2 = PW_RENDERFULLCONTENT`) are discoverable.

### DW-4: query_screenshot default render set includes Sketcher::SketchObject (sketch leaks into the scene)

origin: TC-06 render-visual-fidelity manual test, 2026-07-23
location: src/freecad_buddy/usecases/screenshot.py (`_is_default_renderable` / `_NON_RENDER_TYPES`)
severity: low
reason: A sketch has a non-null `Shape` (edges/wires), so `_is_default_renderable` passes it; the skip-list catches only `PartDesign::Body` + `App::Origin/Line/Plane/Point`. Rendering the live Pad returned `scene.rendered_objects = ["Sketch001", "Pad"]` where the viewport shows only the Pad solid (Sketch hidden). Benign in that case (the sketch is coplanar with a pad face, invisible), but the default set is meant to be the shape-bearing leaf solids (integration-mcp-freecad §6). Same default-view-contract call as the earlier spec-1-9 `Visibility`-honoring entry — resolve together (add `Sketcher::SketchObject` to the skip-list, gate on `len(Shape.Solids) > 0`, or honor live `Visibility`), Phase-1 assistant surface.
status: done 2026-07-23
resolution: Added `Sketcher::SketchObject` to `_NON_RENDER_TYPES`, so a sketch no longer leaks into the default (no-`include`) render set — an explicit `include` still renders it. The separate "honor live `Visibility`" question (a Phase-1 default-view-contract UX decision) stays open under the spec-1-9 Visibility entry above.
