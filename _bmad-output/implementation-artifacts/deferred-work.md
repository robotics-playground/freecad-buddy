# Deferred Work Ledger

Findings surfaced incidentally during review that are NOT the current story's problem.
Append-only; the orchestrator owns status/resolution of each entry.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-1-repo-scaffold-ci-matrix-phase-0-spikes.md`
  summary: `check_imports.py` does not enforce decision 003's ban on `pivy.coin.SoOffscreenRenderer`; pivy/coin are unrestricted in `adapters/` and `hosts/`.
  evidence: pivy is absent from `QT_MODULES` and adapters/hosts have no third-party restriction, so `import pivy.coin` raises no violation outside `usecases/`. The render-backend ban lands with the render probe (story 1.9); no render code exists yet, so this is a later-story gate, not a story-1.1 defect.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-1-repo-scaffold-ci-matrix-phase-0-spikes.md`
  summary: No `[tool.pytest.ini_options]` `testpaths` in `pyproject.toml`; a bare `uv run pytest` (no path) could collect the in-FreeCAD `tests/infc/` suite in the external env.
  evidence: CI always path-scopes (`pytest tests/external`), so the blocking gate is safe today; the risk is only a bare local invocation, and `tests/infc/` currently holds no `test_*.py` so nothing is collected. Worth pinning `testpaths = ["tests/external"]` when the in-FreeCAD suite gains cases (stories 1.2+).

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

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `query_capabilities` capability-banner payload crosses the wire but has no `contracts/`-owned TypedDict/schema, unlike every other wire type (AD-17 "contracts-owned").
  evidence: `shim.capability_banner() -> dict` and `queries.query_capabilities` assemble a loose dict. Read-only query payloads are formalized in story 1.5 (query_ surface); the banner shape should be defined in contracts then.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `shim.element_map_available()` requires a NON-empty element map on a probe box, which is behavioral (did this shape populate a map) rather than pure capability (is the API exposed) — a lazily-populating build could yield a false negative (AD-11 wants a capability probe).
  evidence: probe uses `Part.makeBox(...)` then checks map non-emptiness. Passes on real FreeCAD 1.1 today, but the TNP guard (story 1.6/1.7) depends on this signal; revisit the probe form when the TNP audit lands.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `debug_exec` audit records the `params_digest` (sha256 of `{doc, code}`) but does NOT persist the executed source; the highest-risk path leaves an audit line that proves a hash but cannot reproduce what ran.
  evidence: `audit_log._record` stores only `params_digest`. security-and-service §1 frames exec auditing as evidentiary; digest-only vs code-retention is a privacy-vs-forensics posture call for the security owner. Fingerprints are also `None` (deferred to story 1.6 fingerprint()).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `document_open` on a path already open in the session mints a SECOND handle for the same underlying FreeCAD doc; closing one handle closes the doc, stranding the other on a dead object.
  evidence: `document_open` unconditionally `FreeCAD.openDocument(path)` + mints a fresh handle with no already-open dedupe. Rarely hit in Phase-0 single-file bring-up; worth an already-open check (return the existing handle) when multi-doc query/verify stories exercise open heavily.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: The `shim.varset_backend()` capability probe creates and closes a throwaway `FCB_TMP_varset_probe` FreeCAD document OUTSIDE the `DocumentRegistry` single-writer lock (invoked once, lru_cache'd, via `query_capabilities`), so its doc-set churn is not serialized against registry mutations (AD-20).
  evidence: `varset_backend` calls `FreeCAD.newDocument`/`closeDocument` directly; `query_capabilities` is non-mutating and the probe runs at most once per process under the single-threaded `InlineExecutor`, so no race is reachable in Phase-0 H1. Becomes relevant when a concurrent (GUI/RPC) executor lands and probes could interleave with registry ops; serialize the probe under the writer lock (or run all capability probes once at startup before serving) then.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `debug_exec` runs its `exec(code)` body inline (single-process `InlineExecutor`), so the marshal `timeout_s` never fires; an infinite or long-running operator body hangs the whole headless server with no `TIMEOUT` and no interrupt.
  evidence: `Marshal.call` with `InlineExecutor` runs `fn()` synchronously and `done.wait()` returns immediately after completion, so the timeout path is dead on the inline host. Operator-only + Phase-0 bring-up makes this low-risk now; a real bounded/interruptible exec needs an out-of-thread execution mechanism, which arrives with the GUI/RPC threaded marshal (story 1.8).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: `document_recompute` reports per-object errors only when `"Invalid"` is present in `obj.State`; an object left `"Touched"` / not-recomputed after a recompute (silent skip) is reported as clean, so the per-object error set can under-report.
  evidence: The error comprehension filters on `if "Invalid" in state` only. No in-FreeCAD test creates an object that fails or is skipped during recompute, so the branch's completeness is unverified. Revisit the recompute-clean vocabulary (which States count as failure) together with the recompute-clean sweep in verification core (story 1.6).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
  summary: Both audit lines for a mutation/exec carry `fingerprint_before`/`fingerprint_after` hard-coded to `None`, and the `after` line repeats the pre-execution `params` rather than the result, so an audit pair records almost no evidence of what actually changed.
  evidence: `AuditSink.before`/`after` set the fingerprint fields to `None`; `mcp_server._call_tool` passes the same `args` to both. `fingerprint()` lands in story 1.6, so real before/after hashes are not computable yet; wire them (and a result-bearing `after` payload) into the audit sink when `fingerprint()` exists.

### DW-2: Follow-up review still recommended for 1-4-document-lifecycle-headless-host-mcp-surface after the damping cap was spent
origin: review-budget-followup
source_spec: `spec-1-4-document-lifecycle-headless-host-mcp-surface.md`
severity: low
reason: The follow-up-review damping cap (limits.max_followup_reviews = 1) was spent with the story finalized (status: done, verify green) while the review pass still recommended an independent follow-up. The work was committed by bmad-loop run 20260721-185755-5f54; this entry preserves the lingering recommendation for a deliberate later review.
status: open

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-5-read-only-query-tools.md`
  summary: `query_sketch_info` reads a geometry element's `construction` flag via `getattr(geo, "Construction", False)`; on FreeCAD builds that migrate the flag onto the `GeometryFacade`/`Sketch.getConstruction(index)` the raw geometry object may not carry `Construction`, so every element would silently report `construction: false`.
  evidence: On the local FreeCAD 1.1 build the raw geometry still exposes `Construction` (the story's infc test passes), so no regression today; the risk is version-forward. Prefer `obj.getConstruction(index)` with a fallback to the geometry attribute if/when a build drops the raw flag.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-5-read-only-query-tools.md`
  summary: `query_dependencies` whole-document mode emits an uncapped `edges` array (every object's OutList), unlike `query_tree_summary` which caps at `max_nodes`; a very large assembly yields an unbounded response.
  evidence: The design (mcp-tools §2) specifies no cap for `query_dependencies`, and Phase-0 documents are small, so this is not a story-1.5 defect; add a bound/pagination if the dependency response size becomes a context concern for large models (Phase 1 assistant surface).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-5-read-only-query-tools.md`
  summary: `query_object`'s `_json_safe` recurses through list/tuple/dict property values with no depth limit and no cycle detection, so a self-referential or very deeply nested property value would either serialize to an unbounded payload or raise `RecursionError` (mapped to `RECOMPUTE_ERROR`).
  evidence: FreeCAD's standard scalar/vector/list property values are shallow, so no live object triggers it in Phase 0 (the infc suite passes); the risk is a scripted/`PropertyPythonObject` value holding a cyclic or huge structure. Bound the recursion depth and total element count (stringify/truncate on overflow) when a query surface must tolerate hostile or scripted-object property content.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-5-read-only-query-tools.md`
  summary: `query_mass_properties` guards only a null `Shape`; a non-null non-solid shape (shell/wire/face) reports `volume: 0` and a `CenterOfMass` computed over area/length as if it were volumetric mass, and for some degenerate compounds the OCC `CenterOfMass`/`Volume` call can raise and surface as `RECOMPUTE_ERROR` rather than a fail-closed `INVALID_INPUT`.
  evidence: The story's mass-props test exercises only a clean solid box, so the non-solid branch is unverified; the design treats "no queryable geometry" as `INVALID_INPUT` but does not specify non-solid handling. Gate `volume`/`com` behind `len(shape.Solids) > 0` (or emit nulls) and wrap the OCC reads to map a degenerate shape to `INVALID_INPUT` when a caller needs mass properties on non-solid geometry.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-6-verification-core.md`
  summary: `verify_sketch` gates `evaluateConstraints()` behind `bool(MalformedConstraints)`, but AD-8 / verification-design §4 list `evaluateConstraints()` as an independent hard-fail trigger.
  evidence: On FreeCAD 1.1 `evaluateConstraints()` returns `True` for a healthy fully-constrained sketch (build divergence, documented inline in `usecases/verify.py`), so it cannot be used unconditionally; but a genuinely malformed sketch whose `MalformedConstraints` property is empty would slip past the hard-fail. Not demonstrated reachable on 1.0/1.1 (bad-index constraints raise at `addConstraint`). Revisit if a build populates `evaluateConstraints()` reliably or a malformed-but-empty-property case is found; add a planted malformed-constraint fault case to the sketch validator suite.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-6-verification-core.md`
  summary: The fault scorer (`benchmarks/g0/fault-injection/score_verify_shape.py`) rewrites `validators.yaml` from a fixed single-validator template, so a second validator block would be dropped on the next run.
  evidence: `_render_yaml` emits only the `verify_shape` block and `write_text` replaces the whole file; only `verify_shape` exists in `validators.yaml` today. When a second validator (e.g. `verify_sketch`, later `verify_export_*`) registers a fault suite, switch the scorer to a read-merge-write that preserves other validator blocks.

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

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: The export fault suites are small — `verify_export_step` n=2, `verify_export_stl`/`verify_export_3mf` n=3 — so the ≥95 %/≤5 % gate passes but the Wilson lower bound (0.34–0.44) gives weak statistical confidence in the sensitivity claim.
  evidence: NFR2 cites ≥10 cases per validator. Add planted cases toward that target: more STEP faults (scaled shape, degenerate face); STL duplicated-shell, coordinate-truncation; 3MF missing-`3dmodel.model`, malformed transform matrix. Fixtures build under FreeCADCmd via `build_export_fault_fixtures.py`; the scorer already merges `validators.yaml`.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: `adapters/export_oracle.py` `_read_ascii_stl_facets` silently drops a facet whose `endfacet` block has ≠3 vertices (a truncated ASCII facet) — a fail-open in the stdlib STL parser.
  evidence: Not reachable via this story's writers (FreeCAD emits BINARY STL, and the binary path is the default), so low Phase-0 consequence. If an ASCII-STL input path is ever accepted, raise on a malformed facet block instead of dropping it so a truncated file surfaces as a defect rather than a silently-normalised mesh.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: Story-1.6 `benchmarks/g0/fault-injection/score_verify_shape.py` still full-clobbers `validators.yaml` from a fixed template; the Story-1.7 export scorer added its own `merge_validators_yaml` read-merge-write, so the two writers are inconsistent.
  evidence: Running the 1.6 scorer's `main()` after the 1.7 scorer would drop the `verify_export_*` blocks. Both scorers should share one merge-writer helper. Verified today: the `run_tests.py` suite calls `score()` (no file write), so no clobber occurs during CI test runs; only explicit `main()` invocations write. Refactor both onto a shared writer.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: `benchmarks/g0/export-fault-injection/score_export_verify.py` `_score_mesh_case` calls the oracle legs raw inside its own `try/except` that returns `True` (DETECT) on any exception, instead of routing through `export_oracle.safe_oracle` like the production `_mesh_verify_handler`; a clean-control case that raised for an unrelated reason would be scored DETECTED and mask a false-alarm-class failure.
  evidence: Production path is correct (the host handler wraps every oracle call in `safe_oracle`, turning a read failure into a failed leg → FAIL verdict); only the benchmark scorer diverges. No committed control currently throws (both controls score PASS_CLEAN, FA 0.000), so nothing regresses today. Route `_score_mesh_case` through `safe_oracle` (or the same leg-assembly the handler uses) for scorer/production parity.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: The STL/3MF mesh-verify handler (`hosts/headless/entry.py` `_mesh_verify_handler`) runs the un-marshaled trimesh/lib3mf oracle legs with no timeout, while the FreeCAD self-read leg is bounded at 120 s; a hung oracle read would block RPC dispatch indefinitely.
  evidence: Phase-0 exports are small single-solid meshes that read in milliseconds, so no hang is reachable now. When large-mesh inputs land, bound the oracle phase (thread + timeout, or a subprocess) so a pathological file cannot wedge the server.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: `adapters/export_oracle.py` `_lib3mf_mesh` inspects only the first mesh object of a 3MF model (`iterator.MoveNext()` once), so a defect in the 2nd+ mesh object of a multi-mesh container passes the manifold/geometry checks undetected.
  evidence: This story's writer emits a single mesh per 3MF (one `MeshPart.meshFromShape` → one `Mesh` write), so a multi-mesh container is not producible here. Iterate all mesh objects (fail if any is non-manifold) if a multi-mesh 3MF input path is ever accepted.

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: `adapters/export_oracle.py` `mesh3mf_oracle`'s trimesh geometry leg is built from the lib3mf-parsed vertex/triangle arrays (`_trimesh_from_lib3mf`), so the lib3mf and trimesh "oracles" share lib3mf's geometry parse; the 3MF independence is weaker than the STL path (where trimesh loads the file itself).
  evidence: A lib3mf parse bug would propagate into both 3MF legs, and the flattened single-leg design means there is no true cross-oracle geometry check for 3MF. By-design for Phase-0 (the container/unit/manifold lies are what §6.4 targets and are caught 3/3), but a later story wanting genuine 3MF geometry independence should add a second independent 3MF geometry reader (or an independent container parse).

- source_spec: `{project-root}/_bmad-output/implementation-artifacts/spec-1-7-exports-paired-verification.md`
  summary: The `step-unit-lie` fault fixture writes a genuinely smaller solid (`makeBox(1,2,3)`, vol 6) mislabeled against the full box (vol 6000), so `verify_export_step` detects it via a gross shape/volume mismatch rather than via a mislabeled `write.step.unit`; the per-call unit-pinning path (`shim.pin_step_config` / `write.step.unit=MM`) has no fault-suite case exercising a true same-geometry 1000× unit scale.
  evidence: The verifier's volume check WOULD catch a real unit-lie (a mm box written as `unit=M` re-imports 1000× larger, a gross volume mismatch), so this is a coverage gap, not a product defect — the unit-pinning invariant is functionally guarded but not directly exercised by its own fault case. Add a fixture that writes the clean box with `write.step.unit` set to `M`/`CM` and references the mm facts, so detection depends on the unit knob rather than on swapping in a different shape.

### DW-3: Follow-up review still recommended for 1-7-exports-paired-verification after the damping cap was spent
origin: review-budget-followup
source_spec: `spec-1-7-exports-paired-verification.md`
severity: low
reason: The follow-up-review damping cap (limits.max_followup_reviews = 1) was spent with the story finalized (status: done, verify green) while the review pass still recommended an independent follow-up. The work was committed by bmad-loop run 20260721-185755-5f54; this entry preserves the lingering recommendation for a deliberate later review.
status: open
