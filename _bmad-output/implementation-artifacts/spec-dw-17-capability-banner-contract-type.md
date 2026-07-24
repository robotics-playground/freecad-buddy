---
title: 'DW-17: contracts-owned CapabilityBanner TypedDict + schema for query_capabilities'
type: 'refactor'
created: '2026-07-24'
status: 'done'
baseline_revision: '8cda01070f2e6791bf0d237241937d13b494feb0'
final_revision: '651845f'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - '{project-root}/src/freecad_buddy/contracts/report.py'
  - '{project-root}/scripts/gen_schemas.py'
warnings: []
---

<intent-contract>

## Intent

**Problem:** The `query_capabilities` capability-banner payload crosses the wire but is the lone loose `dict` — assembled by `shim.capability_banner()` and extended in `queries.query_capabilities`, with no `contracts/`-owned TypedDict or generated/drift-checked schema, unlike every other wire type (AD-17 "contracts-owned").

**Approach:** Add a `CapabilityBanner` TypedDict to `contracts/`, register it as a wire root in `scripts/gen_schemas.py` so its schema is emitted and drift-checked, emit the schema file, and type the shim/query producers against it — no field-value changes to the emitted payload.

## Boundaries & Constraints

**Always:**
- `contracts/` stays stdlib-only: `TypedDict` + `Literal`, no FreeCAD, no third-party (AD-1).
- The emitted `query_capabilities` `structured_content` keys and values stay byte-for-byte what they are today: `freecad_version`, `element_map_available`, `serializer`, `varset_backend`, `render`, `exec_enabled`.
- `CapabilityBanner` is `total=False` (additive-evolution rule); prose-required fields declared via the `REQUIRED_FIELDS` manifest, mirroring every other wire root.
- `gen_schemas.py` regenerates byte-identical or CI fails — regenerate the schema file in the same change.
- Import direction inward-only: `usecases/shim.py` and `usecases/queries.py` may import from `contracts/`.

**Block If:**
- Formalizing the banner would force a change to the `fcb.result-envelope/1` wire root or any existing schema file's bytes (it must not — the banner lives inside `structured_content`, the envelope stays the transport).

**Never:**
- Do not change `query_capabilities` behavior, field names, field values, or the tool's `input_schema`/`outputSchema` (the shared envelope stays the wire-validated `outputSchema`).
- Do not fold this into the existing `ReportBanner` (validation-report banner) — different shape and purpose.
- Do not touch `benchmarks/*/heldout/`, unrelated contracts, or the deferred-work ledger.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full banner assembled | `query_capabilities(exec_enabled=False, render="none")` on a live build | `structured_content` matches `CapabilityBanner` shape with all six keys | No error expected |
| Schema regeneration | `python scripts/gen_schemas.py` | `capability-banner.schema.json` written; `--check` reports clean | No error expected |
| Empty object rejected | `{}` validated against `capability-banner` schema | Rejected — the required keys are absent | Validation failure is the expected signal |

</intent-contract>

## Code Map

- `src/freecad_buddy/contracts/capabilities.py` -- NEW: `CapabilityBanner` TypedDict with `Literal` closed-vocab fields (this file does not exist yet; `usecases/capabilities.py` is a different, unrelated startup record).
- `src/freecad_buddy/contracts/__init__.py` -- re-export `CapabilityBanner` on the package surface + `__all__`.
- `scripts/gen_schemas.py` -- register `CapabilityBanner` in `WIRE_ROOTS` (stem `capability-banner`) and `REQUIRED_FIELDS`.
- `src/freecad_buddy/contracts/jsonschema/capability-banner.schema.json` -- NEW: emitted schema (generated, not hand-authored).
- `src/freecad_buddy/usecases/shim.py` -- type `capability_banner()` return as `CapabilityBanner`.
- `src/freecad_buddy/usecases/queries.py` -- type the `query_capabilities` assembled payload as `CapabilityBanner`.
- `tests/external/test_contracts.py` -- extend the wire-root coverage/manifest audit to include the new root.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/contracts/capabilities.py` -- Define `CapabilityBanner(TypedDict, total=False)` with fields `freecad_version: str`, `element_map_available: bool`, `serializer: Literal["exportBinary", "exportBrep"]`, `varset_backend: Literal["varset", "spreadsheet"]`, `render: Literal["gui_constructed", "offscreen", "none"]`, `exec_enabled: bool`. The three closed-vocabulary fields MUST be `Literal` (not bare `str`) so the emitted schema pins the value domain, matching every other closed-vocab contract field (`ResultEnvelope.schema`, `JobState`). The exact members are authoritative from `shim.py`: `serializer_tag()` → `exportBinary`/`exportBrep`; `varset_backend()` → `varset`/`spreadsheet`; render-ladder → `gui_constructed`/`offscreen`/`none`. Mark all six fields `# required` (mirror `ReportBanner`). Module docstring: one line, it is the `query_capabilities` payload. `from typing import Literal, TypedDict`.
- [x] `src/freecad_buddy/contracts/__init__.py` -- Import and re-export `CapabilityBanner`; add to `__all__` (keep alphabetical).
- [x] `scripts/gen_schemas.py` -- Add `("capability-banner", CapabilityBanner)` to `WIRE_ROOTS` and a `"CapabilityBanner"` entry to `REQUIRED_FIELDS` listing all six keys; import the type. (The generator already maps `Literal` → `enum`/`const`; no generator-logic change needed.)
- [x] `src/freecad_buddy/contracts/jsonschema/capability-banner.schema.json` -- Generate by running `gen_schemas.py` (do not hand-author). The three Literal fields MUST emit as `enum` arrays, not `{"type": "string"}`.
- [x] `src/freecad_buddy/usecases/shim.py` -- Annotate `capability_banner(render: str = "none") -> CapabilityBanner`; import from `freecad_buddy.contracts`. Body returns the five probe fields (no `exec_enabled`) — acceptable under `total=False`; keep the docstring note that it is completed by the query.
- [x] `src/freecad_buddy/usecases/queries.py` -- In `query_capabilities`, assemble the payload in a single complete expression so the annotated value is never momentarily partial: `structured: CapabilityBanner = {**shim.capability_banner(render), "exec_enabled": exec_enabled}`. Drop the redundant `dict(...)` copy and the separate `structured["exec_enabled"] = ...` line. Import `CapabilityBanner`. No behavior/value change.
- [x] `tests/external/test_contracts.py` -- (a) add `capability-banner` to the `{}`-rejection wire-root loop; (b) add the `CapabilityBanner` required set to `EXPECTED_REQUIRED`; (c) NEW positive-validity test: a fully-assembled banner (all six keys with valid values) VALIDATES against `capability-banner` schema, and a banner with an off-vocabulary `render`/`serializer`/`varset_backend` value is REJECTED (proves the `enum` emission); (d) NEW invariant test asserting `set(CapabilityBanner.__annotations__) == set(gen_schemas.REQUIRED_FIELDS["CapabilityBanner"])` so the "all fields required" contract cannot silently rot.

**Acceptance Criteria:**
- Given the six existing wire schemas plus the new one, when `gen_schemas.py --check` runs, then it exits `0` (clean, no drift, no orphan) with `capability-banner.schema.json` present.
- Given the emitted `capability-banner` schema, when inspected, then `serializer`, `varset_backend`, and `render` are `enum` arrays over their exact member sets — NOT `{"type": "string"}`.
- Given the `capability-banner` schema, when a fully-assembled valid banner is validated, then it passes; when `{}` is validated, it is rejected; when a banner with an off-vocabulary `render` (e.g. `"offscren"`) is validated, it is rejected.
- Given `query_capabilities(exec_enabled=False, render="none")` on a live FreeCAD build, when called, then `structured_content` carries exactly the six `CapabilityBanner` keys with the same values as before this change (no behavior drift; `tests/infc/test_document_lifecycle.py::CapabilityProbeTest` stays green).
- Given `python -m pytest tests/external/test_contracts.py`, when run, then all contract tests including the new positive-validity and annotation-invariant tests pass.

## Spec Change Log

### 2026-07-24 — bad_spec loopback (review pass 1)

- **Triggering findings:** Reviewers flagged that `render`/`serializer`/`varset_backend` were typed as bare `str` in both the TypedDict and emitted schema despite being closed vocabularies (members fixed in `shim.py`), so a typo'd/off-ladder value would validate clean — under-delivering the intent of matching "every other wire type" (which use `Literal`→`enum`). Also: no positive-validity test asserts a real full banner validates against the schema (only `{}`-rejection was tested); the `structured` payload was momentarily partial (5 keys) before `exec_enabled` was mutated in, masked by `total=False`; a redundant `dict(...)` copy.
- **Amended:** Tasks + Design Notes now require the three closed-vocab fields to be `Literal` (schema emits `enum`), the query to assemble the banner in a single dict-merge (`{**shim.capability_banner(render), "exec_enabled": exec_enabled}`) so the annotated value is never partial, a positive-validity + off-vocabulary-rejection test, and an annotation-vs-manifest invariant test.
- **Known-bad state avoided:** A "formalized" contract that pins field *presence* but leaves the value *domain* open (weaker than the ReportBanner/status contracts it claims to match), and a schema whose full-payload validity is never actually exercised.
- **KEEP (must survive re-derivation):** The producer split (shim = 5 probe fields, query adds `exec_enabled`) is correct and intended — do NOT fold `exec_enabled` into the shim. The banner correctly has NO `schema:` discriminator (it rides inside `structured_content`; the envelope carries the transport tag). Do NOT add runtime envelope validation — query payloads are schema-checked by tests, not at runtime, per the project's established pattern. The `# required` inline-comment convention plus the `REQUIRED_FIELDS` manifest entry both stay.

## Review Triage Log

### 2026-07-24 — Review pass
- intent_gap: 0
- bad_spec: 1: (high 0, medium 1, low 0)
- patch: 0
- defer: 1
- reject: 6
- addressed_findings:
  - `[medium]` `[bad_spec]` Closed-vocabulary fields (`render`/`serializer`/`varset_backend`) typed as bare `str`; amended spec to require `Literal`→`enum`, plus positive-validity/off-vocabulary tests, single-expression payload assembly, and an annotation-invariant test. Code reverted; looping to re-derive.

### 2026-07-24 — Review pass (2)
- intent_gap: 0
- bad_spec: 0
- patch: 1: (high 0, medium 1, low 0)
- defer: 1
- reject: 4
- addressed_findings:
  - `[medium]` `[patch]` Producer-side typing was looser than the enum-tightened contract: `shim.serializer_tag()`/`varset_backend()` returned bare `str` into `Literal` fields, and `capability_banner`/`query_capabilities` `render` params were `str`. Tightened all four to `Literal` so the producers are self-checking against the schema vocabulary (no runtime validation needed; matches the contract's enum). Verified: ruff/gen-check/imports clean, 55 contract tests pass. Rejected (noise/pre-existing): triple-copy of the required-set (generic manifest audit already guards it), `total=False`+all-required "tension" (reviewer conceded not a defect), missing-`exec_enabled`-specific negative test (covered by `{}`-rejection + annotation invariant), and the "no test binds live producer output to the schema" item (infeasible in the external suite without FreeCAD, and the `Literal` producer typing is the type-checked substitute). Deferred: `element_map_available` (bool) vs `element_map_version` (int|None) naming divergence across the two banners — pre-existing, both fields predate this change (see Auto Run Result).

## Design Notes

`CapabilityBanner` is the payload inside `structured_content`; the wire-validated `outputSchema` of the tool stays `fcb.result-envelope/1`. Adding the banner as its own generated schema formalizes the shape for drift-checking without changing the transport — this is what AD-17 asks for the "lone loose dict". It has no `schema:` discriminator field (unlike top-level wire frames) precisely because it rides inside the envelope, which carries the transport's `schema` tag; the banner's own version is pinned by the schema `$id` `fcb.capability-banner/1`.

Closed-vocabulary fields use `Literal`, so the schema emits `enum`/`const` rather than an open `{"type": "string"}` — an off-vocabulary value (a typo'd render mode) then fails schema validation, consistent with the rest of the package's status/vocab discipline. The members are read from `shim.py`, not invented.

The producer split: `shim.capability_banner()` returns the five probe fields; `queries.query_capabilities` completes it with `exec_enabled` in a single dict-merge so the `: CapabilityBanner`-annotated value is complete at the point of annotation (no partial-then-mutate window). Because the TypedDict is `total=False`, the shim's five-field return is still type-valid. Example:

```python
# shim.py
def capability_banner(render: str = "none") -> CapabilityBanner:
    return {
        "freecad_version": freecad_version(),
        "element_map_available": element_map_available(),
        "serializer": serializer_tag(),
        "varset_backend": varset_backend(),
        "render": render,
    }

# queries.py
structured: CapabilityBanner = {**shim.capability_banner(render), "exec_enabled": exec_enabled}
```

Required-field manifest entry (all six keys are the documented payload contract):
`"CapabilityBanner": ["freecad_version", "element_map_available", "serializer", "varset_backend", "render", "exec_enabled"]`.

The generator's self-consistency guard asserts `required ⊆ properties`; since every required key is an annotated field, generation stays clean.

## Verification

**Commands:**
- `python scripts/gen_schemas.py` -- expected: writes schemas including `capability-banner.schema.json`.
- `python scripts/gen_schemas.py --check` -- expected: prints `gen_schemas --check OK`, exit `0`.
- `python scripts/check_imports.py` -- expected: no import-direction violation from the new contract usage.
- `python -m pytest tests/external/test_contracts.py` -- expected: all pass.
- `"FreeCADCmd" tests/run_tests.py` -- expected: `CapabilityProbeTest` green (live probes unchanged). If FreeCADCmd is unavailable locally, report it and rely on the CI legs.

## Auto Run Result

Status: done

### Summary

Formalized the `query_capabilities` capability-banner — previously the lone loose `dict` crossing the wire — as a `contracts/`-owned `CapabilityBanner` TypedDict with a generated, drift-checked JSON schema (`fcb.capability-banner/1`). The three closed-vocabulary fields (`serializer`, `varset_backend`, `render`) are `Literal`, so the schema emits `enum` and the shim/query producers are type-checked against the exact value domain. No change to the emitted payload's keys or values.

### Files changed

- `src/freecad_buddy/contracts/capabilities.py` (NEW) — `CapabilityBanner(TypedDict, total=False)`; six `# required` fields, three as `Literal`.
- `src/freecad_buddy/contracts/__init__.py` — export `CapabilityBanner`.
- `src/freecad_buddy/contracts/jsonschema/capability-banner.schema.json` (NEW, generated) — enum-typed closed-vocab fields, all six required.
- `scripts/gen_schemas.py` — registered the new wire root in `WIRE_ROOTS` + `REQUIRED_FIELDS`.
- `src/freecad_buddy/usecases/shim.py` — `capability_banner() -> CapabilityBanner`; `serializer_tag()`/`varset_backend()` return types and the `render` param tightened to `Literal`.
- `src/freecad_buddy/usecases/queries.py` — single-expression banner assembly typed `CapabilityBanner`; `render` param tightened to `Literal`.
- `tests/external/test_contracts.py` — `{}`-rejection coverage, `EXPECTED_REQUIRED` entry, positive-validity + off-vocabulary-rejection test, annotation↔manifest invariant test.

### Review findings breakdown

- Pass 1: 1 bad_spec (medium) — closed-vocab fields typed as bare `str`; spec amended to require `Literal`→`enum` + positive/off-vocab tests + single-expression assembly + annotation-invariant test; code re-derived.
- Pass 2: 1 patch (medium) applied — tightened producer-side typing (`serializer_tag`/`varset_backend` returns, `render` params) to `Literal` so producers are self-checking. 4 rejected (pre-existing/noise). 1 deferred (below).
- Deferred (for orchestrator to record; ledger not edited per invocation directive): `element_map_available` (bool, this banner) vs `element_map_version` (int|None, `ReportBanner`) are two similarly-named representations of the element-map capability across two banners — pre-existing divergence, both fields predate this change; a maintainer could grab the wrong field. Low value.

### Verification performed

- `.venv/Scripts/python.exe scripts/gen_schemas.py --check` → `gen_schemas --check OK`.
- `.venv/Scripts/python.exe scripts/check_imports.py` → `check_imports OK`.
- `.venv/Scripts/python.exe -m pytest tests/external/test_contracts.py -q` → 55 passed.
- `ruff check` on all six changed source/test files → clean. (9 pre-existing E501s under `scripts/automation/` are unrelated and untouched.)
- Import smoke: `from freecad_buddy.usecases import queries, shim` → ok.
- NOT run: `FreeCADCmd tests/run_tests.py` — FreeCAD unavailable in this env. `CapabilityProbeTest` is untouched and the emitted payload keys/values are unchanged, so it stays green on the CI FreeCAD legs.

### Residual risks

- The full-banner-vs-schema conformance of *live* producer output is not asserted at runtime (external test suite has no FreeCAD; in-FreeCAD suite has no `jsonschema`). Mitigated by the `Literal` producer typing (type-checked) and the hand-rolled positive-validity fixture. Consistent with the project's test-not-runtime schema-check pattern.
