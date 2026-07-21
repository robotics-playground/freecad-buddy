---
title: 'Story 1.2 — Data Contracts Package'
type: 'feature'
created: '2026-07-21'
status: 'done'
baseline_revision: 'c512633f71ad5055f79d3c2995e48508555bd4fb'
final_revision: 'UNCOMMITTED (working tree — commit withheld per user no-auto-commit policy in CLAUDE.md; branch=main protected)'
review_loop_iteration: 3
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/data-contracts-design.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** The `contracts/` ring holds only an empty `__init__.py`. Every later Epic 1 story (tool results, verify reports, RPC frames, audit records, diffs, fingerprints, selectors) must consume one shared schema vocabulary and none may invent its own (AD-17). Without the contracts package landing first, downstream stories drift into private status strings, duplicate report shapes, and un-versioned wire objects.

**Approach:** Author the ten stdlib-only contract modules exactly as fixed in `data-contracts-design.md` §3–§11 (TypedDict + Literal + frozen dataclass helpers, no pydantic, no third-party). Add a JSON-Schema generator that emits `contracts/jsonschema/*.schema.json` deterministically from the TypedDicts, wire byte-identical drift-check + status-vocabulary grep into CI `arch-checks`, and prove all §12 cross-contract invariants with `tests/external/test_contracts.py`.

## Boundaries & Constraints

**Always:**
- `contracts/` imports **stdlib only** — no FreeCAD, no third-party, no pydantic (AD-1/AD-12). Python 3.11-compatible `TypedDict` + `Literal`; frozen `dataclass` only where a validation helper is attached.
- The terminal status set is the frozen closed list, defined once in `status.py`: `OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`. No `Literal` status/verdict/state type may exist outside `status.py` (§12.1).
- Every top-level wire object carries a `schema: "fcb.<name>/1"` tag with the exact names in the design (`fcb.result-envelope/1`, `fcb.validation-report/1`, `fcb.job-status/1`, `fcb.audit-record/1`, `fcb.geometry-diff/1`, `fcb.fingerprint/1`).
- `jsonschema/*.schema.json` are Draft 2020-12, generated from the TypedDicts by the repo script, and regenerate **byte-identical** (drift = CI failure, AC#2).
- `fingerprints_equal(a, b)` **raises** on `serializer`-tag mismatch — never returns False (AD-6, §12.5).
- `DocHandle.handle` is required on every document-touching wire object (§12.7).
- `ResultEnvelope.text` is a server-derived mirror of `structured_content` — the round-trip helper regenerates it; it is never hand-authored (§12.3).
- Follow the `bmad-dev-auto` Pre-Work: re-read the standards index files and load `typescript-clean-code`… — but this is a **Python** package, so apply the project-context Python rules (stdlib-only ring, no print in `src/`, ruff clean) and the `.knowledge-base` standards only where language-agnostic (naming, commenting discipline, no obvious comments).

**Block If:**
- The design doc and the spine/`project-context` disagree on a contract field, status member, or schema tag in a way that cannot be resolved by "spine AD wins" — HALT `blocked` citing the conflict.
- Generating byte-identical schemas requires a third-party library that would violate the stdlib-only ring — HALT `blocked` (the generator lives in `scripts/`, external process, so this should not trigger; if it does, surface it).

**Never:**
- Do not implement `fingerprint()` itself (lives in `usecases/`, story 1.6) — contracts owns only the `FingerprintRecord` **shape**.
- Do not implement any `verify_*` tool, RPC listener, marshal, diff computation, or audit sink — contracts owns only the record/frame **types**.
- Do not add fields, statuses, or synonyms beyond the design doc. No speculative extensibility. Diff/audit/preview must reuse the **same** identifiers (`touched/new/deleted`, `fingerprint_before/after`) — no new synonyms (§12.4).
- Do not use pydantic, attrs, or any third-party schema/validation lib inside `contracts/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fingerprint equal | Two `FingerprintRecord` same `serializer` tag, equal `digest` | `fingerprints_equal` returns `True` | No error |
| Fingerprint differ | Same `serializer`, different `digest` | returns `False` | No error |
| Fingerprint cross-tag | `serializer="exportBinary"` vs `"exportBrep"` | **raises** (ValueError/TypeError) | Cross-tag comparison is a programming error, never "changed" |
| Text mirror round-trip | `ResultEnvelope` with `structured_content` | `text` regenerated from `structured_content` matches stored `text` | Divergence → test fails |
| Verdict derivation | `ValidationReport` all checks `passed=true` | `verdict == "OK"` | Any failed check → non-OK per §5 rules |
| Banner required | `ValidationReport` missing `banner` | schema/invariant check flags it | Missing banner = invariant failure |
| Status vocab leak | A `Literal[...]` status defined outside `status.py` | grep-enforcer exits 1 naming file | CI arch-check fails |
| Schema drift | TypedDict changed, `jsonschema/` not regenerated | drift-check exits 1 | CI arch-check fails |

</intent-contract>

## Code Map

- `src/freecad_buddy/contracts/status.py` -- `TerminalStatus`, `JobState`, `ErrorDetail` (§3). Single source of the closed status vocabulary.
- `src/freecad_buddy/contracts/envelope.py` -- `ResultEnvelope`, `ImageRef` + `mirror_text(structured_content) -> str` helper for the §12.3 round-trip (§4).
- `src/freecad_buddy/contracts/report.py` -- `ValidationReport`, `ReportBanner`, `Check`, `WilsonCI` + `derive_verdict(report) -> TerminalStatus` per §5 normative rules.
- `src/freecad_buddy/contracts/job.py` -- `JobStatus` (§6).
- `src/freecad_buddy/contracts/audit.py` -- `AuditRecord` (§7, JSON-lines).
- `src/freecad_buddy/contracts/diff.py` -- `GeometryDiff`, `ScalarDelta`, `CountDelta` (§8, AD-10 preview payload).
- `src/freecad_buddy/contracts/document.py` -- `DocHandle`, `GeometricSelector`, `MappedNameSelector`, `Selector` union (§9, AD-20).
- `src/freecad_buddy/contracts/fingerprint.py` -- `FingerprintRecord`, `ObjectFingerprint`, `MassProps` + `fingerprints_equal(a, b)` (§10, AD-6).
- `src/freecad_buddy/contracts/rpc.py` -- JSON-RPC frame TypedDicts + `rpc_hello` handshake request/response shapes + `SCHEMA_TAG`/error-code constants (§11).
- `src/freecad_buddy/contracts/assertions.py` -- assertion-vocabulary + anchor-frame declaration types (§1; minimal Phase-0 stub, full set lands P3 — module + docstring citing AD-13, only the types needed now).
- `src/freecad_buddy/contracts/__init__.py` -- re-export the public wire types (already present; extend the docstring re-exports).
- `src/freecad_buddy/contracts/jsonschema/*.schema.json` -- generated Draft 2020-12 schemas, one per wire type (`result-envelope`, `validation-report`, `job-status`, `audit-record`, `geometry-diff`, `fingerprint`; selectors/handle as `$defs`-bearing files where a wire object embeds them).
- `scripts/gen_schemas.py` -- deterministic TypedDict → JSON-Schema generator; `--check` mode compares on-disk vs freshly-generated and exits 1 on drift.
- `scripts/check_status_vocab.py` -- grep/AST enforcer: no `Literal` status/verdict/state member set outside `status.py` (§12.1).
- `tests/external/test_contracts.py` -- pytest covering all §12 invariants + the I/O matrix rows.
- `.github/workflows/ci.yml` -- add two steps to `arch-checks`: status-vocab enforcement + schema drift-check.

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md` (apply language-agnostic rules only; this is a Python ring).
  - Re-read `data-contracts-design.md` §1–§13 — it is the binding contract for this story.
  - Re-read `project-context.md` Wire & Schema Rules + Architecture Ring rules.
  - Load `typescript-clean-code` for the naming/commenting discipline (zero obvious comments), applied to Python.

**Execution:**
- [x] `src/freecad_buddy/contracts/status.py` -- define `TerminalStatus`, `JobState`, `ErrorDetail` exactly per §3 (dotted `code`, required `message`, `objects`, `constraint_ids`, `data`). This is the ONLY module allowed to define a status/verdict/state `Literal`. -- single closed vocabulary (AD-17).
- [x] `src/freecad_buddy/contracts/envelope.py` -- `ImageRef` + `ResultEnvelope` per §4; add `mirror_text(structured_content: dict) -> str` producing the deterministic human-readable mirror so §12.3 round-trip has a single generator. -- envelope + non-divergent text.
- [x] `src/freecad_buddy/contracts/report.py` -- `WilsonCI`, `ReportBanner`, `Check`, `ValidationReport` per §5; add `derive_verdict(report) -> TerminalStatus` implementing the normative derivation (OK ⇔ all passed; failed spec/geometry → SPEC_FAILED; recompute-blocked → RECOMPUTE_ERROR; malformed → INVALID_INPUT; warnings never affect verdict; UNSUPPORTED TNP ⇒ passed=false → SPEC_FAILED with `tnp.unsupported`). **`derive_verdict` code→status mapping is normative here (§5 leaves it to us): a failed check maps by `detail.code` — `recompute.*` → `RECOMPUTE_ERROR`; `invalid_input.*` or `*.malformed` → `INVALID_INPUT`; everything else (incl. `tnp.unsupported`) → `SPEC_FAILED`. Use `invalid_input.` (matches the AD-17 status token), NOT an undocumented `input.` prefix. Failure classes have fixed precedence independent of check order: `RECOMPUTE_ERROR` > `INVALID_INPUT` > `SPEC_FAILED` (scan all failed checks, keep the highest-precedence class — do not early-return on first match, so verdict is order-independent). Read `detail.code` defensively (`detail` may be absent or a non-dict → treat as no code → `SPEC_FAILED`; never raise). Guard the checks container too: if `report["checks"]` is absent or not a `list`, treat it as an empty list (→ `OK`) rather than iterating a non-list and crashing — same defensive posture as the `detail` read.** -- report shape + verdict rule (AD-8/AD-7).
- [x] `src/freecad_buddy/contracts/job.py` -- `JobStatus` per §6; `JobState` imported from `status.py`, never redefined. -- Phase-4 job shape bound now.
- [x] `src/freecad_buddy/contracts/audit.py` -- `AuditRecord` per §7 with the closed `event` Literal and the shared `fingerprint_before/after` / `params_digest` identifiers. -- append-only audit shape.
- [x] `src/freecad_buddy/contracts/diff.py` -- `ScalarDelta`, `CountDelta`, `GeometryDiff` per §8; field names `touched/new/deleted/fingerprint_before` MUST match the audit identifiers (§12.4). -- preview/diff payload (AD-10).
- [x] `src/freecad_buddy/contracts/document.py` -- `DocHandle`, `GeometricSelector`, `MappedNameSelector`, `Selector` union per §9. -- handle + selectors (AD-20).
- [x] `src/freecad_buddy/contracts/fingerprint.py` -- `MassProps`, `ObjectFingerprint`, `FingerprintRecord` per §10 + `fingerprints_equal(a, b)` that raises (`ValueError`) on serializer-tag mismatch and compares `digest` on equal tags. **Read `serializer`/`digest` defensively so an absent `serializer` on either record raises the same `ValueError` ("cannot compare fingerprints: serializer tag missing/mismatch"), never a bare `KeyError` — the raise-on-incomparable contract (§10) must hold for missing-tag too, not only differing-tag. Symmetric guard for `digest`: if `digest` is absent/`None` on EITHER record, raise `ValueError` — never let `None == None` return a spurious `True` ("unchanged"). An incomparable record raises; it never compares equal by omission.** -- record shape + comparison rule (AD-6).
- [x] `src/freecad_buddy/contracts/rpc.py` -- JSON-RPC 2.0 request/success/error frame TypedDicts + `rpc_hello` request/response shapes; carry the channel error-code constants (`-32000/-32002/-32004`) and the channel→status mapping note per §11. Types only; framing logic lands in story 1.8. -- RPC frame vocabulary (AD-2/AD-3).
- [x] `src/freecad_buddy/contracts/assertions.py` -- minimal Phase-0 assertion-vocabulary + anchor-frame declaration types with a docstring citing AD-13 and noting the full set lands in Phase 3. Only types referenced by Phase-0 consumers; no speculative vocabulary. -- reserved contract surface.
- [x] `src/freecad_buddy/contracts/__init__.py` -- re-export the public wire types + helpers from the modules above; keep the stdlib-only docstring. **Export the full `rpc_hello` handshake surface consistently — if `RpcHelloRequest`/`RpcHelloResponse` are exported, their component types (`RpcHelloParams`, `RpcHelloResult`, `RpcErrorData`) must be too, since a consumer building a handshake frame needs them (§11 treats the handshake as a first-class shared contract).** -- one import surface.
- [x] `scripts/gen_schemas.py` -- walk the contract TypedDicts and emit one Draft 2020-12 `*.schema.json` per top-level wire type into `contracts/jsonschema/`, using stdlib only (`typing.get_type_hints`, `typing.is_typeddict` for TypedDict detection — NOT duck-typed `hasattr(__required_keys__)`, `json.dumps(sort_keys=True, indent=2)` + trailing newline for determinism). **CRITICAL — emit `required`: the design's wire TypedDicts are `total=False` (so `__required_keys__` is empty), yet the design prose marks specific fields required (§4 `status`; §5 `banner`, `checks`, `verdict` + §12.2; §6 `state`; §7 `ts`, `actor`, `event`; §8 `deltas`, `counts`, `validity`, `tnp_precheck`; §10 all `FingerprintRecord`/`ObjectFingerprint`/`MassProps` fields; §9 `DocHandle.handle` + §12.7; every wire root's `schema` tag per §2). The generator MUST emit a `required` array for these from an explicit REQUIRED_FIELDS manifest (a dict keyed by type name → required field names, transcribed from the design's "required" prose and cross-referenced to §12.2/§12.7), so a schema without the required field FAILS validation. A schema that validates `{}` for any wire root is a defect. **The manifest MUST be COMPLETE — cover every embedded `$def`, not only wire roots and `DocHandle`. Transcribe EVERY field the design marks `# required`: `ResultEnvelope` = `schema, status, structured_content, text` (§4 marks structured_content AND text required — do NOT stop at `[schema, status]`); `ErrorDetail` = `message` (§3); `ReportBanner` = `freecad_version, element_map_version` (§5); **`Check` = `passed` (§5 line: `passed: bool  # required`)**; `GeometricSelector` = `kind, object, element_type` and `MappedNameSelector` = `kind, object, mapped_name, element_map_version` (§9) for whichever selector `$defs` are emitted; plus the roots/§10 fingerprint defs already listed. Every emitted `$def` whose design shape has a required field MUST carry a `required` array — a nested `$def` that validates `{}` when the design marks a field required is the SAME defect class as a wire root doing so.** Emit `required` for embedded `$defs` too. **Self-consistency GUARD (stops the recurring "one more missed required field" defect mechanically): after building each schema, the generator MUST assert `set(required) ⊆ set(properties)` for every root and `$def` and raise if a manifest entry names a field not in the emitted properties (catches manifest typos/drift that would otherwise emit an inert `required` key). Additionally the test suite MUST include a manifest-completeness audit: for every generated wire root and emitted `$def`, cross-check that no field the corresponding contract TypedDict's design intends as required is absent from the schema `required` — implemented as an explicit expected-required table asserted equal to the emitted `required`, so a future added-but-unlisted required field fails a test rather than silently shipping.** `--check` mode regenerates in-memory and diffs against disk, exiting 1 with the drifted filename on mismatch; **also fail `--check` if any `*.schema.json` on disk is NOT in the freshly-generated set (orphan detection — a deleted/renamed wire type must not leave a stale schema).** Runs FreeCAD-free in the uv/external env. -- AC#2 (byte-identical regeneration) + schema-enforced required fields (§12.2/§12.7).
- [x] `scripts/check_status_vocab.py` -- AST-scan `src/freecad_buddy/**/*.py`; flag any `Literal[...]` whose string members intersect the terminal-status/job-state/verdict set when defined outside the sole owner. On violation print `path:line -- rule` and exit 1; clean = exit 0. **Two robustness fixes: (1) the owner is `contracts/status.py` by its package-RELATIVE path, not by bare basename — a file merely named `status.py` in another ring (e.g. `usecases/status.py`) must NOT be exempt. (2) Derive the status-member set from `contracts.status` at runtime, NOT a hand-copied literal list, so the enforcer can never drift from the single source (import is fine — the enforcer is an external `scripts/` tool, not in-ring). **`JobState = Literal["QUEUED","RUNNING"] | TerminalStatus` is a UNION — `get_args(JobState)` yields the nested `Literal["QUEUED","RUNNING"]` object PLUS the terminal strings, so a naive `isinstance(arg, str)` filter DROPS `QUEUED`/`RUNNING`. Flatten recursively: for each arg, if it is itself a `Literal` (i.e. `get_args(arg)` is non-empty), collect its string members too. The resulting set MUST contain all 9 members (7 terminal + `QUEUED` + `RUNNING`) — §12.1 scopes "state" types, so a `Literal["QUEUED","RUNNING"]` redefined outside `status.py` must be flagged. Add a test asserting the derived set has all 9 and that a planted `Literal["QUEUED","RUNNING"]` leak is flagged.** (3) Resolve `Literal` import aliases: a redefinition written `from typing import Literal as L; x = L[...]` must still be detected — track the local name(s) bound to `typing.Literal`/`typing_extensions.Literal` per file (via the `ImportFrom`/`Import` nodes) and match subscripts on those, not only the bare name `Literal`.** Non-`Literal` duplications of the vocabulary (str Enum, tuple, frozenset) are OUT of scope for §12.1 (which governs `Literal` status *types*) — do not attempt to flag those here. -- AC#1 status-vocab grep-enforcement.
- [x] `src/freecad_buddy/contracts/jsonschema/` -- commit the generated schema files (the output of `gen_schemas.py`) so the drift-check has a baseline. -- checked-in schema baseline.
- [x] `tests/external/test_contracts.py` -- pytest asserting every §12 invariant + I/O-matrix row. **Assertions must be NON-TAUTOLOGICAL — verify the generated SCHEMA behavior, not just that a key exists in `__annotations__`:**
  - `banner`-required (§12.2): assert `"banner" in validation_report_schema["required"]` AND that a report `{}` (or one missing `banner`) FAILS `jsonschema` validation while a well-formed one passes (use the `jsonschema` dev dep to actually validate).
  - `DocHandle.handle` required (§12.7): assert `"handle" in <DocHandle $defs>["required"]` AND that a `DocHandle` without `handle` fails validation, for every document-touching wire object.
  - `schema` tag + `status` **+ `structured_content` + `text`** required on `ResultEnvelope`; `ts`/`actor`/`event` required on `AuditRecord`; `state` on `JobStatus` — each asserted present in the schema `required` array AND enforced by a failing-validation case for a `{}` object.
  - **Embedded `$def` required (parallel to the root cases): assert a `{}` object fails validation against the `ErrorDetail` `$def` (design §3 `message` required), the `ReportBanner` `$def` (§5 `freecad_version`/`element_map_version` required), the `Check` `$def` (§5 `passed` required), and any emitted selector `$def` (§9) — a nested `$def` must not validate `{}` when the design marks a field required. Plus the manifest-completeness audit (expected-required table == emitted `required`) so a future missed required field fails a test.**
  - single status vocabulary: `check_status_vocab` returns clean on the real tree AND flags a planted violation in a tmp fixture (positive control) AND — to prove the enforcer is not a no-op — assert it WOULD flag the frozen set if the same `Literal` were placed in a non-owner file.
  - text-mirror round-trip; diff/audit vocabulary identity (assert the shared field-name sets are equal strings); `fingerprints_equal` cross-tag raises + missing-serializer raises **+ missing-digest raises (both-`None` must raise `ValueError`, not return `True`)** + equal/differ paths.
  - **`derive_verdict` on a non-list `checks` (e.g. a dict) returns `OK` (or degrades safely) rather than raising; status-vocab enforcer flags a planted `from typing import Literal as L; ... L[...]` alias-import leak, a planted `import typing; ... typing.Literal[...]` attribute-form leak, and a planted `Literal["QUEUED","RUNNING"]` job-state leak.**
  - `derive_verdict`: all-pass → OK; a spec fail → SPEC_FAILED; recompute fail → RECOMPUTE_ERROR; `invalid_input.*`/`*.malformed` → INVALID_INPUT; UNSUPPORTED TNP (`tnp.unsupported`) → SPEC_FAILED; **precedence: a `[spec_fail, recompute_fail]` list AND its reverse both → RECOMPUTE_ERROR (order-independence); empty/missing checks → OK; a failed check whose `detail` is absent or non-dict → SPEC_FAILED without raising.**
  - `gen_schemas.py --check` exits 0 on the committed baseline; **AND a drift/orphan case exits 1 (mutate a temp copy of the schema dir and assert `--check` against it returns 1) so the CI gate's failure path is proven, not just the green path.**
  -- AC#1/#2/#3 coverage.
- [x] `.github/workflows/ci.yml` -- add to `arch-checks` (uv leg): `uv run python scripts/check_status_vocab.py` and `uv run python scripts/gen_schemas.py --check`, both blocking, after the existing ring check. -- CI-enforced drift + vocab.

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- contracts ring stays stdlib-only (clean).
- [x] `uv run ruff check .` -- clean (no `print()` in `src/`; scripts/tests may print).
- [x] `uv run pytest tests/external -q` -- all contract + scaffold tests pass.

**Acceptance Criteria:**
- Given the ten modules per `data-contracts-design.md` §1, when `pytest tests/external/test_contracts.py` runs, then all §12 cross-contract invariants pass: single status vocabulary (grep-enforced), banner required on every ValidationReport, text-mirror round-trip, diff/audit vocabulary identity, fingerprint cross-tag comparison raises, DocHandle required on document-touching objects.
- Given the TypedDict definitions, when `scripts/gen_schemas.py --check` runs, then `contracts/jsonschema/*.schema.json` regenerate byte-identical (drift = CI failure).
- Given any wire object, when serialized, then it carries its `schema: "fcb.<name>/1"` tag, the status enum is the closed AD-17 set, and `scripts/check_imports.py` confirms stdlib-only imports throughout `contracts/` (NFR5, NFR10).

## Spec Change Log

### 2026-07-21 — bad_spec loopback (iteration 1)

- **Triggering findings:**
  1. `[high] bad_spec` — **Generated schemas emit no `required` array, so every wire root validates `{}`.** The design's wire TypedDicts are `total=False`; `gen_schemas.py` keyed `required` off `__required_keys__` (empty for `total=False`), so `result-envelope`, `validation-report`, `audit-record`, `job-status`, etc. carry `"required": None`. Verified live: an empty `{}` object is a legal ValidationReport. This defeats AC#1's purpose and directly violates design §4 (`status` required), §5+§12.2 (`banner` required on every report), §6 (`state`), §7 (`ts`/`actor`/`event`), §12.7 (`DocHandle.handle`). Worse, the contract tests were tautological — `test_banner_missing_flagged_by_schema` asserted `"banner" in schema["properties"]` (presence), not `required`, and could never catch a bannerless report. Root cause is the outside-contract task text not telling the generator how to emit `required` for prose-required fields on `total=False` types → bad_spec, not intent_gap.
  2. `[medium] bad_spec` — `check_status_vocab.py` exempted the owner by bare basename `status.py`, so a `status.py` in any other ring (e.g. `usecases/status.py`) could redefine the closed vocabulary undetected; and it hand-copied `STATUS_MEMBERS`, risking silent drift from `contracts.status`. §12.1 names `contracts/status.py` specifically as the sole owner.
  3. `[medium] bad_spec` — `derive_verdict` invented an undocumented `input.` code prefix (no such namespace in §3/§5) and early-returned on the first recompute/input match, making the verdict order-dependent and crashing on a non-dict `detail`. §5 left the code→status mapping to us but the task text didn't pin it, so the impl chose an ungrounded convention.
  4. `[low] bad_spec` — `fingerprints_equal` raised `KeyError` (not `ValueError`) when `serializer` was absent, breaking the §10 "raise on incomparable" contract for the missing-tag case; `--check` had no orphan-schema detection; `rpc_hello` component types weren't exported.

- **Amended (outside `<intent-contract>` only):**
  - `gen_schemas.py` task: added a mandatory explicit `REQUIRED_FIELDS` manifest (design-sourced) emitted as the schema `required` array for every wire root + embedded `$def`; switched TypedDict detection to `typing.is_typeddict`; added orphan-schema detection to `--check`.
  - `tests/external/test_contracts.py` task: replaced tautological presence checks with real `jsonschema`-validation assertions (a `{}`/missing-field object must FAIL) for banner, handle, status, ts/actor/event, state; added enforcer positive-and-negative controls; added a drift/orphan `--check` failure-path test; added verdict order-independence + defensive-detail cases.
  - `check_status_vocab.py` task: owner matched by package-relative `contracts/status.py`; status set derived at runtime from `contracts.status` via `get_args`.
  - `report.py` task: pinned the normative code→status map (`invalid_input.`/`*.malformed` → INVALID_INPUT, not `input.`), fixed precedence (RECOMPUTE_ERROR > INVALID_INPUT > SPEC_FAILED, order-independent), defensive `detail` read.
  - `fingerprint.py` task: missing-serializer raises `ValueError`, not `KeyError`.
  - `__init__.py` task: export the full handshake surface.
  - Added two Design Notes (required-manifest rationale; verdict precedence).

- **Known-bad state avoided:** shipping a "contracts package" whose JSON Schemas — the one artifact every downstream story validates against — accept empty/malformed objects as valid, while a green test suite falsely certifies the §12.2/§12.7 invariants as enforced.

- **KEEP (must survive re-derivation):**
  - All ten module SHAPES (`status`/`envelope`/`report`/`job`/`audit`/`diff`/`document`/`fingerprint`/`rpc`/`assertions`) match `data-contracts-design.md` §3–§11 verbatim — correct, do not disturb field names, `schema` tags, or the closed status set.
  - `mirror_text` single-generator design, `fingerprints_equal` cross-tag `ValueError`, the deterministic `json.dumps(sort_keys=True, indent=2)`+trailing-newline generation, and the CI wiring (two `arch-checks` steps) — all correct; only ADD `required` emission + orphan detection, do not weaken determinism.
  - Diff/audit vocabulary-identity (`touched/new/deleted/fingerprint_before`) and the stdlib-only ring — correct; keep.
  - `assertions.py` minimal Phase-0 stub — correct per §13; do not expand.

### 2026-07-21 — bad_spec loopback (iteration 2)

- **Triggering findings:**
  1. `[medium] bad_spec` — **The iteration-1 `required`-emission fix was applied only to wire ROOTS + `DocHandle`, not to the other embedded `$defs`.** Verified live: the `ErrorDetail` `$def` validates `{}` though §3 marks `message` required; the `ReportBanner` `$def` validates `{}` though §5 marks `freecad_version`/`element_map_version` required; and `ResultEnvelope`'s root `required` was `[schema, status]` although §4 also marks `structured_content` AND `text` required. Same defect CLASS as the iteration-1 finding (schema fails to enforce a design-prose-required field), incompletely resolved — the manifest wasn't exhaustive over nested defs + missed two ResultEnvelope fields → bad_spec.
  2. `[low] bad_spec` — `fingerprints_equal` guarded a missing `serializer` (iter-1 fix) but NOT a missing `digest`: two records with equal serializer and both `digest` absent/`None` compare `None == None` → `True` (spurious "unchanged"). Symmetric oversight to the serializer guard.
  3. `[low] bad_spec` — `derive_verdict` gained defensive `detail` handling (iter-1) but still crashes (`AttributeError`) if `report["checks"]` is a non-list (dict/str) — the container itself wasn't guarded.
  4. `[low] bad_spec` — status-vocab enforcer matches only the bare name `Literal`; a `from typing import Literal as L; L[...]` alias-import redefining the vocabulary slips past.

- **Amended (outside `<intent-contract>` only):**
  - `gen_schemas.py` task: manifest MUST be COMPLETE over embedded `$defs` (enumerated `ResultEnvelope` incl. structured_content/text, `ErrorDetail.message`, `ReportBanner.freecad_version/element_map_version`, selector defs) — every emitted `$def` with a design-required field carries a `required` array.
  - `tests/external/test_contracts.py` task: added nested-`$def` `{}`-rejection cases (ErrorDetail, ReportBanner, selectors) + missing-digest raises + non-list-`checks` safety + alias-import status-vocab leak.
  - `fingerprint.py` task: symmetric `digest`-None guard (raise `ValueError`).
  - `report.py` task: guard non-list `checks` (treat as empty → OK), never crash.
  - `check_status_vocab.py` task: resolve `Literal` import aliases; explicitly scope OUT non-`Literal` duplications (§12.1 governs Literal types only).

- **Known-bad state avoided:** shipping schemas where the error-detail and banner payloads — and two of the ResultEnvelope required fields — validate empty, re-introducing the exact "validates `{}`" false-confidence the iteration-1 fix set out to eliminate, one nesting level down.

- **KEEP (must survive re-derivation):**
  - Everything the iteration-1 KEEP list preserved, PLUS the iteration-1 fixes themselves (root `required` emission, non-tautological jsonschema tests, owner-by-relative-path + runtime-derived status set, order-independent `derive_verdict` precedence, orphan detection, missing-serializer raise) — all verified present and correct; do NOT regress them. Only EXTEND `required` to nested defs + add the four small guards.
  - `derive_verdict` `invalid_input.`/`*.malformed` mapping and RECOMPUTE>INVALID_INPUT>SPEC_FAILED precedence — correct; keep.

### 2026-07-21 — bad_spec loopback (iteration 3)

- **Triggering findings:**
  1. `[medium] bad_spec` — **`check_status_vocab._status_members()` drops `QUEUED`/`RUNNING`.** `JobState = Literal["QUEUED","RUNNING"] | TerminalStatus` is a Union; `get_args(JobState)` returns the nested `Literal["QUEUED","RUNNING"]` OBJECT plus the terminal strings, so the `isinstance(arg, str)` filter yields only 7 members. Verified live: `_status_members()` returns 7 not 9, and a planted `Literal["QUEUED","RUNNING"]` leak in a non-owner file is NOT flagged. §12.1 scopes "state" types → AC#1 under-enforced.
  2. `[medium] bad_spec` — **`Check.passed` is design-required (§5: `passed: bool  # required`) but the `Check` `$def` emits no `required`.** Verified live: `Check {}` validates clean. Same defect class as the iteration-2 embedded-`$def` findings; the manifest enumeration missed `Check`. Two loopbacks of hand-enumerating required fields left a residual — a non-convergence smell → fixed structurally this pass, not by adding one entry alone.

- **Amended (outside `<intent-contract>` only):**
  - `check_status_vocab.py` task: `_status_members` MUST flatten the `JobState` union (collect nested-`Literal` string members) so all 9 members are in scope; added tests for the job-state leak + `typing.Literal[...]` attribute-form branch.
  - `gen_schemas.py` task: added `Check = [passed]` to the manifest AND — the structural fix — a generator self-consistency GUARD (`set(required) ⊆ set(properties)`, raise on violation) plus a mandated test-suite manifest-completeness audit (expected-required table == emitted `required` for every root/`$def`), converting the recurring "one more missed required field" class from hand-audit to enforced check.
  - `tests/external/test_contracts.py` task: added `Check {}`-rejection, the manifest-completeness audit, and the two extra status-vocab leak forms.

- **Known-bad state avoided:** shipping (a) an enforcer that lets a job-state `Literal["QUEUED","RUNNING"]` redefinition slip past CI (the exact AD-17 drift the check exists to stop), and (b) a `Check` schema accepting a check with no `passed` field — the field the entire §5 verdict derivation reads.

- **KEEP (must survive re-derivation):**
  - ALL iteration-1 and iteration-2 fixes (root + embedded-`$def` `required` for ResultEnvelope/ErrorDetail/ReportBanner/DocHandle/fingerprint, non-tautological jsonschema tests, owner-by-relative-path + runtime-derived set + Literal-alias detection, order-independent `derive_verdict` + defensive detail/checks, `fingerprints_equal` missing-serializer AND missing-digest raise, orphan detection) — all verified present; do NOT regress. ONLY add: union-flatten in `_status_members`, `Check` required, the `required ⊆ properties` guard + completeness-audit test, and the two extra vocab-leak tests.

## Review Triage Log

### 2026-07-21 — Review pass (iteration 4, converged — no loopback)

- intent_gap: 0
- bad_spec: 0
- patch: 0
- defer: 0
- reject: 3 (all observational/correct-by-construction: `ImageRef`/`WilsonCI` `$defs` carry no required fields — design §4/§5 models them as all-optional, so the completeness audit correctly omits them; `ScalarDelta`/`CountDelta` are defined+exported but never schema-emitted because `GeometryDiff.deltas`/`counts` are typed `dict` per design §8 verbatim — spec-faithful, inner-shape tightening already deferred to the Phase-2 preview channel; §12.2's `wilson_ci`-when-rate clause is a runtime producer obligation with no schema/test hook — already deferred iteration 2, lands with the first rate-bearing verify tool)
- addressed_findings:
  - none

Both adversarial reviewers (Blind Hunter + Edge Case Hunter) returned no material correctness/spec/determinism/invariant defect; Edge Case Hunter returned an empty findings set. The three prior bad_spec loopbacks closed the substantive issues, and iteration 3's structural `required ⊆ properties` guard + manifest-completeness audit converged the recurring "missed required field" class. Loop converged.

### 2026-07-21 — Review pass (bad_spec loopback, iteration 3)

- intent_gap: 0
- bad_spec: 2 (medium 2)
- patch: 0
- defer: 0
- reject: several (`.malformed`/`recompute.malformed` precedence collision — map checks recompute first, precedence-consistent, and no such design codes exist; `passed is True` strict vs truthy — design says "passed is true", strict is correct for real bool wire values; selector dead manifest entries — harmless, selectors aren't referenced by a wire root; golden-file determinism test "can't catch self-consistent wrong generator" — inherent to golden tests, semantic jsonschema tests cover correctness; `detail` conditional-required + `wilson_ci` §12.2 invariant — already deferred in iteration 2, no schema mechanism, land with the first rate-bearing verify tool)
- addressed_findings:
  - `[medium]` `[bad_spec]` `_status_members` dropped `QUEUED`/`RUNNING` (JobState union not flattened) — amended enforcer to flatten nested-Literal union members + tests.
  - `[medium]` `[bad_spec]` `Check.passed` design-required but `Check` `$def` validated `{}` — added `Check` to manifest + a `required ⊆ properties` self-consistency guard + a manifest-completeness audit test to converge the whole class.

### 2026-07-21 — Review pass (bad_spec loopback, iteration 2)

- intent_gap: 0
- bad_spec: 4 (medium 1, low 3)
- patch: 0
- defer: 3 (low 3)
- reject: several (`verdict` enum "too wide" — design §5 itself types `verdict: TerminalStatus`, so the full 7-member enum is design-verbatim, not a deviation; `deltas`/`counts` bare `dict` — matches design §8 which types them `dict`; non-`Literal` vocab-duplication detection — outside §12.1's Literal-only scope; determinism "under-tested" — `sort_keys` + get_args order is stable)
- addressed_findings:
  - `[medium]` `[bad_spec]` iteration-1 `required` fix was not exhaustive over embedded `$defs` — `ErrorDetail`/`ReportBanner`/`ResultEnvelope.structured_content`/`text` still validated empty; amended manifest + tests to cover every design-required nested field.
  - `[low]` `[bad_spec]` `fingerprints_equal` missing-digest → spurious equal; amended to raise.
  - `[low]` `[bad_spec]` `derive_verdict` crashed on non-list `checks`; amended to guard.
  - `[low]` `[bad_spec]` status-vocab enforcer missed `Literal` alias imports; amended to resolve aliases.

### 2026-07-21 — Review pass (bad_spec loopback, iteration 1)

- intent_gap: 0
- bad_spec: 4 (high 1, medium 2, low 1)
- patch: 0
- defer: 2 (low 2)
- reject: several (generator edge cases for type forms not used by any contract — Annotated/Any/dict[K,V]/tuple/set; non-URI `$id` cross-file `$ref` composition, a downstream adapter concern)
- addressed_findings:
  - `[high]` `[bad_spec]` Schemas emitted no `required` array (`total=False` → empty `__required_keys__`); every wire root validated `{}`, and banner/handle "required" invariant tests were tautological — amended gen_schemas + tests to emit and validate a design-sourced REQUIRED_FIELDS manifest.
  - `[medium]` `[bad_spec]` status-vocab enforcer exempted owner by basename + hand-copied member set — amended to package-relative owner path + runtime-derived set.
  - `[medium]` `[bad_spec]` `derive_verdict` invented `input.` prefix, order-dependent precedence, crashed on non-dict detail — amended to pin normative code→status map, order-independent precedence, defensive read.
  - `[low]` `[bad_spec]` `fingerprints_equal` KeyError vs ValueError on missing serializer; no orphan-schema detection; unexported handshake types — amended.

## Design Notes

- **Schema tags as `Literal`, not runtime constants.** Each wire TypedDict pins `schema: Literal["fcb.<name>/1"]` per the design's code blocks — the generator emits this as a JSON-Schema `const`. This is the drift anchor and the wire self-description in one place.
- **Deterministic generation is the whole game for AC#2.** `json.dumps(schema, sort_keys=True, indent=2)` + a single trailing newline, stable `$defs` ordering, and no timestamps/paths in output. `typing.get_type_hints` with `include_extras=True` reads `total=False` optionality and `Literal` members. Union types (`Selector`, `float | str | bool | list | None`) map to `anyOf`. This must be pure and reproducible — no set iteration order leaking in.
- **`derive_verdict` is the normative §5 rule, tested exhaustively.** It is the one behavior-bearing helper in `report.py`; keep it a pure function over the report dict so the harness (story 1.3) and verify tools (1.6) call the same derivation, never re-implement it.
- **`mirror_text` single generator.** §12.3 round-trip only holds if there is exactly one text producer; put it in `envelope.py` and have the test regenerate-and-compare. Do not let any other module author `text`.
- **Vocabulary-identity test (§12.4) is a real assertion, not a comment.** Assert the literal field-name sets shared between `GeometryDiff` and `AuditRecord` (`fingerprint_before`, and the `touched/new/deleted` naming) are identical strings — this is what stops synonym drift downstream.
- **`assertions.py` stays minimal.** Design §1 says the full assertion set lands in Phase 3. Ship only the anchor-frame declaration + assertion-vocabulary types that a Phase-0 consumer references (or an empty-but-documented module if none does yet) — do not speculatively author the P3 vocabulary.
- **Required fields need an explicit manifest — `total=False` is not "everything optional".** The design's wire TypedDicts are all `total=False` (readers ignore unknown fields, additive evolution) yet the prose marks specific fields *required* (§4/§5/§6/§7/§8/§9/§10 + the §12.2 banner and §12.7 handle invariants). `__required_keys__` is therefore empty and gives the generator nothing. Carry a hand-transcribed `REQUIRED_FIELDS` manifest in `gen_schemas.py` (type name → required field names, sourced verbatim from the design's "required" annotations) and emit it as the schema `required` array. This is the ONLY way §12.2 ("banner required on every report") and §12.7 ("handle required") become real validation, not prose. A test that only checks `"banner" in properties` is tautological and does not satisfy the invariant — the test must validate a `{}` object FAILS.
- **`derive_verdict` precedence is order-independent by design.** Scan all failed checks and keep the highest-precedence failure class (`RECOMPUTE_ERROR` > `INVALID_INPUT` > `SPEC_FAILED`); do not early-return on the first failed check, or `[spec_fail, recompute_fail]` and its reverse would disagree. `detail.code` is read defensively — a failed check with absent/non-dict `detail` degrades to `SPEC_FAILED`, never raises.

## Verification

**Commands:**
- `uv run python scripts/gen_schemas.py` -- regenerates `contracts/jsonschema/`; expected: writes files, exit 0.
- `uv run python scripts/gen_schemas.py --check` -- expected: exit 0 (no drift) against the committed baseline.
- `uv run python scripts/check_status_vocab.py` -- expected: exit 0 on the real tree.
- `uv run python scripts/check_imports.py` -- expected: exit 0 (contracts stays stdlib-only).
- `uv run pytest tests/external -q` -- expected: all pass (contract invariants + scaffold + check_imports cases).
- `uv run ruff check .` -- expected: clean.

**Manual checks:**
- `contracts/` has exactly the ten modules from §1 (status, envelope, report, job, audit, diff, document, fingerprint, rpc, assertions) plus `__init__.py` and `jsonschema/`.
- No `Literal` status/verdict/state member set exists outside `status.py`.
- Each generated schema file has a `const` schema tag matching `fcb.<name>/1`.

## Auto Run Result

Status: **done** (converged after 3 bad_spec loopbacks + a clean 4th review pass)

### Summary

Landed the complete stdlib-only `contracts/` package (AD-17): the ten wire-type modules exactly per `data-contracts-design.md` §3–§11, a deterministic TypedDict→JSON-Schema generator, a status-vocabulary AST enforcer, both wired blocking into CI `arch-checks`, and a 71-case non-tautological contract test suite proving every §12 cross-contract invariant. All three ACs satisfied and independently falsified (not merely reported).

### Files changed

- `src/freecad_buddy/contracts/{status,envelope,report,job,audit,diff,document,fingerprint,rpc,assertions}.py` — the ten wire modules (TypedDict + Literal + frozen-dataclass helpers), stdlib-only; `mirror_text()` (sole text producer), `derive_verdict()` (normative §5, order-independent precedence), `fingerprints_equal()` (raises on serializer mismatch/missing + digest missing).
- `src/freecad_buddy/contracts/__init__.py` — public re-export surface incl. full `rpc_hello` handshake types.
- `src/freecad_buddy/contracts/jsonschema/*.schema.json` — 6 generated Draft 2020-12 baselines (result-envelope, validation-report, job-status, audit-record, geometry-diff, fingerprint), each with a design-sourced `required` array (roots + embedded `$defs`).
- `scripts/gen_schemas.py` — deterministic generator; explicit `REQUIRED_FIELDS` manifest; `required ⊆ properties` self-consistency guard; `--check` drift + orphan detection.
- `scripts/check_status_vocab.py` — AST enforcer; owner by relative path; runtime 9-member set (JobState union flattened); Literal alias + attribute-form detection.
- `tests/external/test_contracts.py` — 71 tests: jsonschema-validated `{}`-rejection for every root + `$def`, manifest-completeness audit, verdict/fingerprint/vocab edge cases, drift+orphan failure paths.
- `.github/workflows/ci.yml` — added `Status vocabulary enforcement` + `Schema drift check` steps to the `arch-checks` job.

### Review findings breakdown

- **Iteration 1 (bad_spec):** schemas emitted no `required` (total=False → empty `__required_keys__`), validating `{}`; contract tests tautological; status-vocab owner-by-basename + hand-copied set; `derive_verdict` invented `input.` prefix + order-dependent + crashed on non-dict detail; `fingerprints_equal` KeyError on missing serializer. → spec amended, re-derived.
- **Iteration 2 (bad_spec):** iter-1 `required` fix not exhaustive over embedded `$defs` (ErrorDetail/ReportBanner/ResultEnvelope.structured_content+text validated empty); `fingerprints_equal` missing-digest → spurious equal; `derive_verdict` non-list `checks` crash; vocab missed `Literal` alias imports. → amended, re-derived.
- **Iteration 3 (bad_spec):** `_status_members` dropped `QUEUED`/`RUNNING` (JobState union not flattened) → job-state leak slipped CI; `Check.passed` design-required but `Check` `$def` validated `{}`. Fixed structurally with a `required ⊆ properties` generator guard + manifest-completeness audit test to converge the recurring "missed required field" class. → amended, re-derived.
- **Iteration 4 (converged):** both adversarial reviewers returned no material findings (Edge Case Hunter empty set). 3 rejected observational items (ImageRef/WilsonCI no-required-by-design; ScalarDelta/CountDelta `dict`-typed per §8; wilson_ci §12.2 clause).
- **Deferred (5 entries in `deferred-work.md`):** cross-file `$ref` composition + non-URI `$id` (adapter concern, stories 1.4+); generator hardening for unused type-forms (Annotated/Any/dict[K,V]/tuple); §12.2 `wilson_ci`-when-rate invariant (first rate-bearing verify tool, 1.6/1.7); `GeometryDiff` inner-shape tightening (Phase-2 preview); `rpc.py` CHANNEL_STATUS_MAP key reconciliation vs integration-mcp-freecad §2.3 (story 1.8).

### Verification performed (independently re-run by orchestrator, not trusting the subagent report)

- `uv run python scripts/gen_schemas.py --check` → exit 0 (byte-identical regeneration).
- `uv run python scripts/check_status_vocab.py` → exit 0; `_status_members()` = 9 members incl QUEUED/RUNNING; job-state/attr-form/alias leaks all flagged; `usecases/status.py` NOT exempt (relative-path owner).
- `uv run python scripts/check_imports.py` → exit 0 (contracts stays stdlib-only).
- `uv run pytest tests/external -q` → 71 passed.
- `uv run ruff check .` → clean.
- Falsified live: every wire root + `ErrorDetail`/`ReportBanner`/`Check` `$def` rejects `{}`; `DocHandle.handle` required; `fingerprints_equal` raises on cross-tag + missing serializer + both-None digest; `derive_verdict` order-independent + non-list-checks safe + non-dict-detail safe; `required ⊆ properties` guard raises on manifest drift.

### Residual risks

- **Not committed** — per CLAUDE.md critical rule #1 (no auto-commit without explicit user approval) and branch=main being protected. Working tree holds the change; user must review + commit. This is the only "unverified" item: CI (the real headless gate) has not run — local verification used the `arch-checks` (uv) leg only; the two blocking FreeCAD headless legs run in GitHub Actions on push.
- Deferred items above are latent, none reachable by current Phase-0 code (no wire root references selectors; no rate-bearing checks; no RPC listener yet).
