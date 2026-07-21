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

### DW-1: Follow-up review still recommended for 1-1-repo-scaffold-ci-matrix-phase-0-spikes after the damping cap was spent
origin: review-budget-followup
source_spec: `spec-1-1-repo-scaffold-ci-matrix-phase-0-spikes.md`
severity: low
reason: The follow-up-review damping cap (limits.max_followup_reviews = 1) was spent with the story finalized (status: done, verify green) while the review pass still recommended an independent follow-up. The work was committed by bmad-loop run 20260721-185755-5f54; this entry preserves the lingering recommendation for a deliberate later review.
status: open
