---
title: 'DW-11: mechanically enforce "wilson_ci present whenever a check measures a rate"'
type: 'feature'
created: '2026-07-30'
status: 'done'
baseline_revision: 'e0c351a5f2fdd509546431c95871d74dfa3101a3'
final_revision: '10381660e9672d418f2cd94679422443f3075861'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/data-contracts-design.md'
warnings: ['oversized']
---

<intent-contract>

## Intent

**Problem:** data-contracts-design §12.2 lists "every `ValidationReport` has a `banner`; `wilson_ci` present whenever any check `measured` is a rate (AD-14)" as a contract-test-checked invariant, but nothing enforces the second clause: `validation-report.schema.json` has no conditional at all (it does not even require `wilson_ci`), `derive_verdict` ignores the banner, and no test covers it. Rate-detection was deferred because it is semantic, not structural — a bare `float` cannot be told apart from a volume.

**Approach:** Make it structural. Add an explicit discriminator field to the `Check` TypedDict so a check *declares* that its `measured` value is a rate, then enforce the clause on both surfaces that reports pass through: a Draft-2020-12 `if/then` conditional in the generated schema (rate-marked check present ⇒ `banner.wilson_ci` required and non-null) and a runtime guard in `contracts/report.py` that raises so a report assembled in code fails closed instead of validating loosely.

## Boundaries & Constraints

**Always:**
- `contracts/` stays stdlib-only — the runtime guard imports nothing beyond `typing`.
- Schema evolution is additive-only within a major (§ "Schema evolution"): a new optional `Check` field plus a conditional that only bites when that field is set. `schema` stays `fcb.validation-report/1`.
- `gen_schemas.py` output stays deterministic and byte-identical on regeneration; the conditional is emitted from an explicit manifest in the generator, in the same style as `REQUIRED_FIELDS`, never hand-edited into the `.json`.
- The generator's existing self-consistency guard style extends to the new manifest: a manifest entry naming a field absent from emitted properties raises.
- The runtime guard is opt-in-callable and never fires on today's reports (no existing check declares a rate), so every current producer and test keeps passing unchanged.

**Block If:**
- Enforcing the clause would require changing `Check.measured`'s type or removing an existing field (that is a major bump, not this change).
- The design doc has to be re-interpreted — e.g. if the correct reading is that `wilson_ci` must be required on *every* banner unconditionally.

**Never:**
- Do not infer "is a rate" heuristically from the value (0.0–1.0 range sniffing, id-substring matching like `"rate" in id`). The discriminator is explicit or there is no enforcement.
- Do not invent a rate-valued check to have something to stamp. No check in the codebase currently measures a rate (verified: every site in `verify.py`, `exports.py`, `export_oracle.py`, `export_verdict.py`, `runner.py`, `evidence.py`, `actor_run.py` measures volumes, counts, bools, status strings, or diagnosis text). Rates live on `banner.wilson_ci` and in `dev_rate.json`.
- Do not make the guard raise from inside `derive_verdict` — that function is documented as defensive and never-raising, and callers rely on it.
- Do not edit the deferred-work ledger.
- Do not add a rate discriminator to `ReportBanner`; `wilson_ci` already lives there.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| No rate declared (every report today) | report with checks that omit the discriminator, banner without `wilson_ci` | schema validates; guard returns normally | No error expected |
| Rate declared, CI present | a check with the rate discriminator, `banner.wilson_ci` a `WilsonCI` object | schema validates; guard returns normally | No error expected |
| Rate declared, CI absent | a check with the rate discriminator, banner has no `wilson_ci` key | schema rejects; guard raises | `ValueError` naming the offending check id |
| Rate declared, CI explicitly null | same, `banner.wilson_ci` is `None`/`null` | schema rejects; guard raises | `ValueError` — null is not "present" |
| Rate declared in `warnings` only | discriminator on a `warnings` entry, no `wilson_ci` | schema rejects; guard raises | §12.2 says "any check"; warnings are `Check`-typed |
| Non-rate discriminator value | discriminator set to a non-rate kind | schema validates without requiring `wilson_ci`; guard returns normally | No error expected |
| Malformed container | `checks` not a list, or a non-dict check entry | guard degrades safely, no raise (mirrors `derive_verdict`) | Schema catches the type error separately |

</intent-contract>

## Code Map

- `src/freecad_buddy/contracts/report.py` -- `Check` (:29-35, six fields, no kind marker), `ReportBanner.wilson_ci` (:26), `WilsonCI` (:14-19), `derive_verdict` (:68). Discriminator + guard land here.
- `scripts/gen_schemas.py` -- `REQUIRED_FIELDS` manifest (:54-79), `build_schema` (:203), `_register_def` (:191), self-consistency guard in `_properties_and_required` (:182-188), `check()` drift/orphan detection (:249). Conditional emission hooks here.
- `src/freecad_buddy/contracts/jsonschema/validation-report.schema.json` -- regenerated output; today has no `if`/`then`/`dependentRequired` anywhere.
- `tests/external/test_contracts.py` -- the §12 invariant suite. `_load` (:25), `_root_validator` (:29), `_def_validator` (:33), `test_schemas_regenerate_byte_identical` (:46), `test_validation_report_banner_required` (:190), `test_every_required_field_is_a_property` (:340), `derive_verdict` section (:502-563, helper `_ck` at :507). New tests go here, plain module-level functions.
- `benchmarks/runner.py` -- `_exit_case_reports` (:517-537) stamps `banner["wilson_ci"] = tier.wilson_ci` and satisfies §12.2 by hand today; its checks carry a diagnosis string, not a rate. Reference only — no change expected.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/contracts/report.py` -- add one optional discriminator field to `Check` marking its `measured` as a rate (a `Literal`-typed field, so the generated schema is a closed set rather than a free string), and add a module-level guard function that scans `checks` + `warnings` for a rate-marked entry and raises `ValueError` when `banner.wilson_ci` is absent or `None` -- gives the semantic "is a rate" fact a structural carrier and makes in-code assembly fail closed.
- [x] `scripts/gen_schemas.py` -- emit the Draft-2020-12 conditional for `ValidationReport` from a new explicit manifest constant (alongside `REQUIRED_FIELDS`), binding "some entry in `checks` or `warnings` has the rate discriminator" to "`banner.wilson_ci` required and not null"; extend the existing self-consistency guard so the manifest cannot name a field that is not an emitted property -- keeps the schema generated-not-hand-edited and drift-checkable.
- [x] `src/freecad_buddy/contracts/jsonschema/validation-report.schema.json` -- regenerate via `python scripts/gen_schemas.py` -- the on-disk schema must match the generator or `--check` fails.
- [x] `tests/external/test_contracts.py` -- add tests covering every row of the I/O matrix against both surfaces (`Draft202012Validator` for the schema, direct call for the guard), plus a test asserting the discriminator field is present in the generated `Check` `$def` -- the matrix is the contract; a rate-marked check without `wilson_ci` must be rejected by each surface independently.

**Acceptance Criteria:**
- Given the full external suite and the in-FreeCAD suite, when both are run, then every pre-existing test passes unchanged (the discriminator is optional and no current producer sets it).
- Given `scripts/gen_schemas.py --check`, when run after regeneration, then it exits 0 with no drift or orphan reported.
- Given the generated `validation-report.schema.json`, when inspected, then it contains a Draft-2020-12 conditional and the `Check` `$def` exposes the discriminator, and the other six wire schemas are byte-identical to before this change.
- Given a reviewer reading §12.2, when they ask "what enforces clause two", then both a schema conditional and a runtime guard can be named, each independently rejecting the violation.

## Spec Change Log

## Review Triage Log

### 2026-07-30 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 7: (high 1, medium 3, low 3)
- defer: 0
- reject: 2
- addressed_findings:
  - `[high]` `[patch]` `wilson_ci: {}` satisfied the new guarantee on both surfaces because `WilsonCI` was absent from the generator's `REQUIRED_FIELDS`, so its `$def` emitted no `required`; the real consumer (`benchmarks/harness/verdict.py:216`) needs `.r`. Added the manifest entry and a matching guard-side completeness check; empty and partial CIs are now rejected by both surfaces.
  - `[medium]` `[patch]` `contains` is a no-op on non-arrays, so a non-array `checks`/`warnings` made the antecedent vacuously true and produced a spurious "`wilson_ci` is a required property" on a `checks`-shaped bug. Added `"type": "array"` to each antecedent branch.
  - `[medium]` `[patch]` `required` is a no-op on non-objects, so the `then` clause did no work for a non-dict `banner` (masked only by `ReportBanner`'s independent type check, which would vanish if `banner` were ever widened to `ReportBanner | None`). Added `"type": "object"` to the `then` clause.
  - `[medium]` `[patch]` The guard matched `== "rate"` exactly, so a mis-cased or typo'd `measured_kind` failed open — significant because the in-FreeCAD world has no `jsonschema` and the guard is the sole enforcement there. The guard now rejects any value outside `MeasuredKind`, derived via `get_args`.
  - `[low]` `[patch]` `require_wilson_ci_for_rates(None)` raised `AttributeError`, unlike its never-raising sibling `derive_verdict`. Non-mapping input now degrades safely; only `ValueError` on a genuine violation.
  - `[low]` `[patch]` Generator manifest guards added: empty `when_array_fields` emitted meta-schema-invalid `{"anyOf": []}`, an off-enum `entry_value` emitted a `const` no instance could match, and a non-array field produced a misleading "entry field not in items" error.
  - `[low]` `[patch]` Inline comment on `measured_kind` stated a cross-field design rule; replaced with a terse shape fact per the project comment rules.
  - Rejected: "guard has no production caller" (the spec scopes this as a forward-looking mechanism — no rate producer exists to wire it into) and "enforcement keys off a declaration rather than detecting rates" (heuristic detection is explicitly forbidden by the intent contract and was the recorded human decision on DW-11).

### 2026-07-30 — Review pass 2
- intent_gap: 0
- bad_spec: 0
- patch: 8: (high 1, medium 2, low 5)
- defer: 3
- reject: 5
- addressed_findings:
  - `[high]` `[patch]` `require_wilson_ci_for_rates` raised `TypeError: unhashable type` on a check whose `measured_kind` was a `list`/`dict`, contradicting its own `:raises ValueError:` contract and its never-raising sibling `derive_verdict` — significant because the guard is the sole enforcement surface in the in-FreeCAD world, which has no `jsonschema`. The kind is now `isinstance(kind, str)`-tested before the frozenset membership probe, so any non-member (unhashable or not) yields the documented `ValueError`. `bool` still raises, since `True` is not a `str`.
  - `[medium]` `[patch]` The guard and the schema disagreed on a present-but-garbage CI: `{"rate": "x", "low": None, "high": [], "n": "z", "r": {}}` and an all-`None` CI both passed the guard silently while the schema rejected them. Key presence alone does not serve the real consumer (`benchmarks/harness/verdict.py:216` reads `wilson_ci["r"]` as a number). Added `_mistyped_wilson_ci_keys`: `n`/`r` must be `int`, `rate`/`low`/`high` `int|float`, `bool` excluded everywhere.
  - `[medium]` `[patch]` A `CONDITIONALS` entry keyed on a non-wire-root type (e.g. `"Check"`) was silently ignored — `_conditional` is only ever called with a root's name — so the rule vanished with no error. That is precisely the manifest-drift class the module docstring claims the guard catches. `generate()` now raises on any key outside the `WIRE_ROOTS` names.
  - `[low]` `[patch]` A `CONDITIONALS` spec missing a key (`then_required_field`, …) raised a bare `KeyError` instead of the self-describing manifest `ValueError` every other defect in that function produces. The spec key set is now validated up front against `_CONDITIONAL_SPEC_KEYS`.
  - `[low]` `[patch]` `_rate_check_ids` skipped any container that was not a `list`, so a rate check assembled in a tuple failed **open** — silently dropping enforcement in exactly the in-code-assembly scenario the guard exists for. Now accepts any non-`str`/`bytes` `Sequence`.
  - `[low]` `[patch]` `_ref_props` assumed its target was a `$ref`, so an inline-items array (`GeometryDiff.touched`) or a non-`$ref` object field (`ValidationReport.subject`) produced a misleading "field not in items/properties: []" — blaming the field when the real defect is the absent `$def`. It now raises naming that condition.
  - `[low]` `[patch]` `build_schema` blind-`update`d the root with the conditional, so a future second conditional form would silently clobber an existing root key. Added a disjointness check that raises on collision.
  - `[low]` `[patch]` `require_wilson_ci_for_rates` was annotated `report: dict` while the body degrades on any non-`Mapping` and the tests pass `None`/`str`/`int`/`list`/`object()`; annotation corrected to `Any`. `_WILSON_CI_KEYS` derived from `__annotations__` (values are `ForwardRef` strings under `from __future__ import annotations`, and inherited keys are excluded) — switched to `__required_keys__`, and the test that asserted `_WILSON_CI_KEYS == set(WilsonCI.__annotations__)` (true by construction, would survive the keys being renamed wholesale) now compares against the literal expected set.
  - Deferred (3): CI internal-coherence bounds, the `measured_kind: "rate"` ⇒ numeric-`measured` binding, and the structural one-rate-per-report limitation. All three are real but concern CI/measurement *coherence*, whereas this spec's contract is `wilson_ci` *presence*; each needs its own boundary decision. Logged as new ledger entries.
  - Rejected (5): "guard has no production caller" and "`benchmarks/runner.py` never sets `measured_kind`" (re-raised from pass 1; the spec's Design Notes scope this as an on-arrival mechanism and no rate producer exists — facts unchanged); "producer can opt out by omitting the discriminator" (that is the declared design, and the alternative is the heuristic detection the intent contract forbids); "`<unnamed>` collapses distinct offenders" and the two generator-test-isolation nits (cosmetic; `monkeypatch.setitem` restores correctly).

### 2026-07-30 — Review pass 3
- intent_gap: 0
- bad_spec: 0
- patch: 7: (high 2, medium 2, low 3)
- defer: 1
- reject: 5
- addressed_findings:
  - `[high]` `[patch]` The guard failed **open** on a check entry that was a `Mapping` but not a `dict` (`MappingProxyType`, `UserDict`): `_rate_check_ids` tested `isinstance(check, dict)`, so a frozen or proxied rate check was skipped and the report passed silently. This is the same fail-open class pass 2 fixed one line above for the *container* (`list` → `Sequence`) while leaving the *entry* narrowed — and the guard is the sole enforcement surface in the in-FreeCAD world, which has no `jsonschema`. Entry test widened to `Mapping`, matching the function's own `Mapping`-based contract; `_check_label` re-annotated to match.
  - `[high]` `[patch]` The two surfaces disagreed on `wilson_ci.n`/`r` arriving as an integral float (`30.0`): the schema accepted it (Draft 2020-12 defines `"integer"` as any number with zero fractional part) while `_mistyped_wilson_ci_keys` rejected it via `isinstance(value, int)`. Reachable from any real wire payload, since `json.dumps`/`loads` preserves `30.0`. The guard now accepts an integral float for the int-typed keys and rejects a fractional one (`29.5`), matching the schema in both directions.
  - `[medium]` `[patch]` The `then` clause constrained `wilson_ci` with `{"not": {"type": "null"}}` alone, so in isolation it accepted `{}`, `7`, `"nope"`, `[]`, and `False` as a Wilson CI — the schema half of the guarantee held only because `ReportBanner.wilson_ci` independently `$ref`s `WilsonCI`, exactly the "masked by an independent type check" reasoning pass 2 used to justify adding `"type": "object"` one level up. `_conditional` now emits the target field's own fragment with any null branch dropped (`{"$ref": "#/$defs/WilsonCI"}`), so the conditional carries the full interval requirement itself; verified the isolated `if`/`then` now rejects a partial CI.
  - `[medium]` `[patch]` `MeasuredKind` and `require_wilson_ci_for_rates` were absent from `contracts/__init__.py` while every other public name in `report.py` is re-exported, so the first rate producer following the established package-level import path (as `usecases/stats.py` does for `WilsonCI`) would not find the guard. Both added to the import block and `__all__`.
  - `[low]` `[patch]` The module docstring still claimed `derive_verdict` "is the one behavior-bearing helper here" after this change added a second raising public helper. Rewritten to name both.
  - `[low]` `[patch]` `_rate_check_ids` appended labels without de-duplication, so two rate checks sharing an `id` reported `['dup', 'dup']` and two unnamed ones `['<unnamed>', '<unnamed>']` — actively misleading about offender cardinality in a message documented as naming the offending ids. Now de-duplicated in first-seen order via `dict.fromkeys`.
  - `[low]` `[patch]` `_WILSON_CI_INT_KEYS` introduced for the integral-float fix is derived from `get_type_hints(WilsonCI)` rather than hand-copying the `n`/`r` split, closing the drift half that pass 2 left open (the key *set* tracked the TypedDict but the key *types* were a literal tuple). Generator/test docstrings carrying design rationale or review narration ("an empty antecedent enforces nothing", "only wire roots carry conditionals, so these entries would never be emitted", "the consumer reads wilson_ci['r'] as a number", "`True` is an int in Python but never a trial count") reduced to behavior statements per the project comment rule.
  - Deferred (1): `NaN`/`Infinity` passes both surfaces and serializes to invalid JSON. Distinct from the already-logged CI-bounds entry (those values are in-domain but incoherent; these are not real numbers and break serialization). Logged as a new ledger entry.
  - Rejected (5): "guard has no production caller" / "`benchmarks/runner.py` never sets `measured_kind`" (re-raised a third time; the spec's Design Notes own this scoping and no rate producer exists — facts unchanged); "the guard also raises on an unknown `measured_kind` with a valid CI present" (that widening is stated in its `:raises` contract and is the pass-2 fail-closed fix working as designed); "the conditional tests will break when a second `CONDITIONALS` entry lands" (speculative — no second entry exists, and the clash guard is what surfaces the shape change); "`_enum_members` does not follow a `$ref`" (unreachable today; `MeasuredKind` is a `Literal`, emitted inline); "`_mistyped_wilson_ci_keys` hardcodes the int/float split" (fixed as part of the low patch above rather than tracked separately).

## Design Notes

**Why a discriminator at all.** The original deferral was correct that rate-detection is semantic. A discriminator converts it to structural, which is the only thing a JSON Schema can act on. The human decision on DW-11 (2026-07-30) chose exactly this over heuristics.

**Why the clause has no producer to update today.** DW-11's decision text says to update "benchmarks/runner.py:491 and any check-building call site". That pointer is stale (the live site is `_exit_case_reports` at :517-537) and, more importantly, no check anywhere measures a rate — every construction site was inspected. So this change lands the mechanism and leaves the first rate-bearing check to set the discriminator when it appears. That is the honest outcome, not a gap: the invariant becomes enforced-on-arrival rather than documented-only.

**Conditional shape.** `wilson_ci` lives on `ReportBanner`, not on `Check`, so the conditional cannot be a local `dependentRequired` on `Check` — it must bind at the `ValidationReport` root, keying off "does any array entry carry the discriminator" and then constraining `banner`. Draft 2020-12's `contains` is the natural way to express the antecedent. Both `checks` and `warnings` are `Check`-typed and §12.2 says "any check", so both are in the antecedent.

**Two surfaces, deliberately.** The schema catches reports crossing the wire or read back off disk; the guard catches a report assembled in Python that never gets validated (the repo's existing pattern is test-time-only schema checks, so schema alone would leave in-process assembly unchecked). Neither is a substitute for the other.

## Verification

**Commands:**
- `uv run python scripts/gen_schemas.py` then `uv run python scripts/gen_schemas.py --check` -- expected: `gen_schemas --check OK`, exit 0.
- `uv run pytest tests/external/test_contracts.py -q` -- expected: all pass, including the new matrix tests.
- `uv run pytest tests/external -q` -- expected: no regression in any suite that builds or validates reports (`test_harness_g0`, `test_harness_g1`, `test_actor_run_g1`, `test_gate_g1_exit`, `test_react_backend_actor_run`, `test_mcp_surface`).
- `uv run python scripts/check_imports.py` -- expected: exit 0 (`contracts/` stays stdlib-only).
- `uv run ruff check .` and `uv run ruff format --check .` -- expected: clean.
- `git diff --stat src/freecad_buddy/contracts/jsonschema/` -- expected: only `validation-report.schema.json` changed.

**Manual checks (if no CLI):**
- In-FreeCAD suite (`tests/infc/`) has no `jsonschema` dependency; confirm the new guard is importable there by inspection — it must use only `typing`/builtins so `contracts.report` still imports under `FreeCADCmd`.

## Auto Run Result

Status: `done` (review pass 3)

**Change implemented.** §12.2 clause two — "`wilson_ci` present whenever any check `measured` is a rate" — is now mechanically enforced on two independent surfaces. `Check` carries an optional `measured_kind` `Literal` discriminator; `gen_schemas.py` emits a Draft-2020-12 `if`/`then` on the `ValidationReport` root from an explicit `CONDITIONALS` manifest, and `contracts/report.py` exposes `require_wilson_ci_for_rates` so a report assembled in Python fails closed. This pass hardened both surfaces so they agree on every input tested, and made the guard reachable by the package-level import path.

**Files changed:**
- `src/freecad_buddy/contracts/report.py` — `MeasuredKind`, `measured_kind` on `Check`, `require_wilson_ci_for_rates` + helpers; this pass widened the check-entry test to `Mapping`, accepted integral floats for the int-typed CI keys, de-duplicated offender ids, derived `_WILSON_CI_INT_KEYS` from `get_type_hints`, and corrected the module docstring.
- `src/freecad_buddy/contracts/__init__.py` — re-exports `MeasuredKind` and `require_wilson_ci_for_rates`.
- `scripts/gen_schemas.py` — `CONDITIONALS` manifest, `_conditional` emitter with manifest self-consistency guards; the `then` clause now reuses the target field's emitted fragment with the null branch dropped instead of a bare non-null assertion.
- `src/freecad_buddy/contracts/jsonschema/validation-report.schema.json` — regenerated (+87 lines); the only wire schema changed.
- `tests/external/test_contracts.py` — I/O-matrix coverage against both surfaces, plus this pass's regressions: integral-float counts accepted, fractional rejected, `MappingProxyType` entries scanned, offender ids de-duplicated, isolated `then` rejecting a partial CI, int-key set pinned against the schema, and package exports asserted.
- `_bmad-output/implementation-artifacts/deferred-work.md` — one new entry appended (`NaN`/`Infinity`); no existing entry modified (verified 5 additions, 0 deletions).

**Review findings:** 7 patches applied (2 high, 2 medium, 3 low), 1 deferred, 5 rejected. No intent gaps, no spec defects, no repair loopback. The two `high` findings were a fail-open in the guard on non-`dict` mappings and a genuine schema/guard divergence on `n: 30.0`.

**Verification performed:**
- `uv run python scripts/gen_schemas.py --check` → `gen_schemas --check OK`, exit 0.
- `uv run pytest tests/external/test_contracts.py -q` → 108 passed.
- `uv run pytest tests/external -q` → 445 passed, 4 warnings (pre-existing trimesh `RuntimeWarning`s, unrelated).
- `uv run python scripts/check_imports.py` → `check_imports OK`; `report.py` imports resolve to `__future__`, `collections.abc`, `typing`, and intra-package only, so `contracts/` stays stdlib-only.
- `git diff --stat src/freecad_buddy/contracts/jsonschema/` → only `validation-report.schema.json`.
- `uv run ruff check` / `format --check` on the changed files → clean. The 10 repo-wide `E501` errors and the residual `test_contracts.py` format diff are pre-existing: confirmed by stashing this change and re-running, and all `E501` sites are in `scripts/automation/` and `test_check_imports.py`, untouched here.
- Fresh-interpreter import of `contracts.report` resolves `get_type_hints(WilsonCI)` to `{'n', 'r'}`, so the new import-time derivation cannot fail under `FreeCADCmd`.
- Each fixed finding was reproduced against both surfaces before the fix and re-checked after, not inferred from the reviewers' reports.

**Residual risks:**
- The mechanism still has no production caller and no producer sets `measured_kind` — scoped by Design Notes as enforced-on-arrival. Raised and rejected in all three passes; unchanged.
- CI *coherence* remains unenforced: bounds/ordering, the `measured_kind: "rate"` ⇒ numeric-`measured` binding, one-rate-per-report, and now `NaN`/`Infinity`. All four are ledger entries awaiting their own boundary decision; this spec's contract is presence and member type only.
- `tests/infc/` was not executed (needs `FreeCADCmd`); the stdlib-only constraint was verified by import analysis and a clean-interpreter load instead.

