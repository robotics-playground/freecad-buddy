---
title: 'Story 3.2: Mutation Protocol Runtime'
type: 'feature'
epic: 3
story: '3-2-mutation-protocol-runtime'
created: '2026-07-31'
status: 'done'
baseline_revision: '9d2f068'
final_revision: '96314d7'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** Nothing in `src/` opens a FreeCAD transaction — grep for `openTransaction`/`abortTransaction`/`saveCopy` returns zero hits. Every Phase-2 mutation tool (Stories 3.3–3.7) is specified to execute through a single `run_mutation()` wrapper that does not exist, so no mutation can be attempted without risking an unverified document state, and G2.2/G2.3 have no runtime to measure.

**Approach:** Land `usecases/transaction.py` with `run_mutation()` implementing the AD-5 bracket exactly as `verification-design.md` §1.2 specifies — pre-state fingerprint + `saveCopy` snapshot outside the transaction, `openTransaction` → typed op → `recompute()` → `post_verify` → commit, or abort → `recompute()` → re-hash proof, escalating to snapshot restore on mismatch. Add the contracts-owned `mutation` result block and TNP verdict enum, `usecases/tnp_guard.py` at Layer 0 only (Layers 1–2 are Story 3.5), and wire real `fingerprint_before/after` into the audit record.

## Boundaries & Constraints

**Always:**
- The bracket order in `verification-design.md` §1.2 is normative and reproduced verbatim in behavior: snapshot/fingerprint/`saveCopy` happen **outside** the transaction; `doc.recompute()` runs after **every** `abortTransaction` and before any verification (R2 — undo skips recompute, so verifying first reads stale state).
- Rollback is proven by re-hash, never assumed (R4). Equal to `fp_before` → `rolled_back_verified`; unequal → restore from the `saveCopy` snapshot, recompute, re-assert equality → `rolled_back_via_snapshot`. The snapshot path is reported whenever taken.
- One transaction per call, id 0, never nested, never left open (R3/R5). The snapshot file is deleted only after commit or after verified rollback (R6).
- `post_verify` runs the §1.3 checklist in order, short-circuiting on first hard failure: (1) recompute clean via `isValid()`/`getStatusString()`, (2) `verify_shape` on touched shape-bearing objects, (3) `verify_sketch` requiring `FullyConstrained` where sketches are involved, (4) `tnp_guard.audit_references`.
- Every mutation writes an `AuditRecord` carrying real `fingerprint_before`/`fingerprint_after` digests and the rollback outcome — this closes the DW-2 gap that `audit_log.before/after` currently hardcode to `None`.
- Ring purity holds: `usecases/` is stdlib + FreeCAD App only, version-sensitive calls go through `shim.py`, and every new wire type lands in `contracts/` (AD-1/AD-12/AD-17). `scripts/check_imports.py` must stay green.
- A failed `post_verify` produces a human-readable explanation alongside the rollback record — a G2.2 pass rule, not a nicety.
- Status values come from the existing closed set in `contracts/status.py`. No new status strings.

**Block If:**
- The gate.yaml validator target `run_mutation@usecases.mutation.run_mutation` cannot be reconciled with `component-design.md:34`, which names the module `usecases/transaction.py`. Resolve by implementing `transaction.py` (the design doc is the binding contract) and correcting the `gate.yaml` target; HALT only if that correction is rejected by a check you cannot satisfy.
- Materializing a fault fixture would require inventing geometry whose expected values cannot be derived analytically from the committed G0 golden model it cites.

**Never:**
- Do not implement TNP Layer 1 (mapped-name diff) or Layer 2 (`getElementHistory`) — Story 3.5 owns them. Layer 0 (the `isValid()` error sweep) plus the capability-gated `UNSUPPORTED` posture is this story's scope, per the P0/P2 split at `component-design.md:33`.
- Do not implement `sketch_*`, `feature_*`, `preview_dry_run`, or the confirm gate (Stories 3.3/3.4/3.6/3.7).
- Do not open, read, or reference `benchmarks/g2/heldout/`.
- Do not report `PASS` from the TNP guard when `shim.element_map_available()` is false — `UNSUPPORTED`, never clean (AD-7).
- Do not capture expected assertion values from a verify tool; golden values are analytic (AD-13/AD-19).
- Do not use `ActiveDocument` as a target; every call takes an explicit handle.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy commit | Valid doc, op that recomputes clean and passes post_verify | `commitTransaction`; snapshot deleted; envelope `status=OK` with `mutation` block carrying `fingerprint_before`/`fingerprint_after`, `rolled_back=false`, `rollback_proven=null`; audit record written with both digests | No error expected |
| post_verify fails | Op leaves an object failing `isValid()` | abort → recompute → re-hash equals before → envelope non-OK (`SPEC_FAILED` or `RECOMPUTE_ERROR` per the failing check) with `rolled_back=true`, `rollback_proven="rolled_back_verified"`, and a human-readable explanation | Reported, not raised |
| Op raises | `op()` throws mid-transaction | Same abort/recompute/re-hash path; the exception message becomes the explanation; transaction never left open | Exception caught, mapped to closed-set status |
| #6031 hash mismatch | Abort + recompute leaves fingerprint ≠ before | Restore from `saveCopy`, recompute, re-assert equality → `rollback_proven="rolled_back_via_snapshot"`; the snapshot path is reported | If the restored hash still mismatches, return a non-OK envelope stating rollback could not be proven — never claim restored |
| Serializer tag mismatch | `fingerprints_equal` called across differing serializer tags | Propagates the existing `ValueError` from `contracts/fingerprint.py:35` | Never caught-and-ignored |
| No element map | `shim.element_map_available()` false | TNP audit returns `UNSUPPORTED` status with no per-ref `PASS`; the mutation is not failed by the guard on that basis alone | Recorded in the `tnp_audit` block |
| Sketch not fully constrained | Op involves a sketch left with non-zero DoF | post_verify step 3 hard-fails → rollback path; redundant-constraint warnings alone do not fail | Explanation names the sketch |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/transaction.py` -- NEW. `run_mutation()`, `post_verify()`, snapshot path helper. The only mutation path.
- `src/freecad_buddy/usecases/tnp_guard.py` -- NEW. `snapshot_references()` / `audit_references()`, Layer 0 + `UNSUPPORTED` gating only.
- `src/freecad_buddy/contracts/mutation.py` -- NEW. `MutationBlock`, `PostVerifyBlock`, `TnpAuditBlock`, `RefVerdict` literal `PASS|BROKEN|REPOINTED|DROPPED|UNSUPPORTED|RE_BASELINED`, `RollbackProof` literal. None of these exist today.
- `src/freecad_buddy/contracts/fingerprint.py:35` -- `fingerprints_equal(a, b)`, raises on serializer-tag mismatch. Reuse; do not reimplement comparison.
- `src/freecad_buddy/usecases/fingerprint.py:128` -- `fingerprint(doc) -> FingerprintRecord`. Reuse as-is.
- `src/freecad_buddy/usecases/verify.py:291,354,436` -- `verify_shape` / `verify_sketch` / `verify_recompute`, each `-> ResultEnvelope`; PASS ⇔ `status == "OK"` and `detail is None`. Called by `post_verify`.
- `src/freecad_buddy/usecases/documents.py:92,121` -- `DocumentRegistry`, and `with_document()` which **holds `self._lock`** — re-entrant use deadlocks. `run_mutation` must take the resolved document, not call back into `with_document`.
- `src/freecad_buddy/usecases/shim.py:85,95` -- `element_map_available()`, `element_map_version()`; add a transaction/undo probe here if one is needed, never a version-string check.
- `src/freecad_buddy/adapters/audit_log.py:67,73` -- `AuditSink.before/after` hardcode `fingerprint_before/after = None`; extend the signatures to accept real digests (DW-2).
- `src/freecad_buddy/contracts/jsonschema/` -- generated + drift-checked; regenerate after adding the mutation contract.
- `benchmarks/harness/assertions.py` -- NEW. `evaluate` entry point cited by `benchmarks/g2/gate.yaml:35-38` as `assertions@harness.assertions.evaluate`.
- `benchmarks/g2/gate.yaml:54` -- cites `run_mutation@usecases.mutation.run_mutation`; module is actually `transaction.py` (see Block If).
- `benchmarks/g2/fault-injection/rollback-boundary/` -- 4 cases (2 planted #6031 + 2 controls), all `fixture: pending`.
- `benchmarks/g0/fault-injection/non-manifold/case.yaml` -- the materialized-fixture shape to copy: `fixture: fixture.FCStd` + `provenance:` pointer.
- `benchmarks/_registry/provenance/g0-fault-non-manifold.yaml` -- manifest shape required for every committed `.FCStd`.
- `scripts/check_provenance.py:122,157` -- `_declares_pending_fixture`; flipping a fixture off `pending` requires the `.FCStd` **and** a provenance manifest or the check fails.
- `benchmarks/runner.py:75,88,318` -- `_FAULT_SCORERS` (no G2 entry), `_VALIDATOR_SOURCES`, `_collect_report` (G2 criteria fall through to `not_collected_report`).
- `tests/infc/test_document_lifecycle.py` -- pattern for in-FreeCAD stdlib-`unittest` tests; the mutation runtime must be tested here, not under pytest.

## Tasks & Acceptance

**Execution:**
- [ ] **Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)** -- Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md`; read `_bmad-output/project-context.md`; read `verification-design.md` §1 (normative bracket), §2 (fingerprint), §3 (TNP). Confirm every FreeCAD API used (`openTransaction`/`commitTransaction`/`abortTransaction`/`saveCopy`/`isValid`/`getStatusString`) against `docs/references/FreeCAD/` before writing code — never from memory.
- [x] `src/freecad_buddy/contracts/mutation.py` -- Add the `mutation` result block, `post_verify` block, `tnp_audit` block, verdict and rollback-proof literals as TypedDict/Literal, stdlib only -- the wire vocabulary must be contracts-owned before any producer exists (AD-17).
- [x] `src/freecad_buddy/contracts/jsonschema/` -- Regenerate via `scripts/gen_schemas.py` -- drift check fails CI otherwise.
- [x] `src/freecad_buddy/usecases/tnp_guard.py` -- Implement `snapshot_references()` / `audit_references()` with the §3.1 `RefRecord` shape, Layer 0 error sweep, `ElementMapVersion` capture, and the `UNSUPPORTED` gate on `shim.element_map_available()` -- `post_verify` step 4 needs a real call site now; Layers 1–2 land in 3.5 against this same signature.
- [x] `src/freecad_buddy/usecases/transaction.py` -- Implement `run_mutation()` + `post_verify()` per §1.2/§1.3 -- the keystone; every later Phase-2 tool executes through it.
- [x] `src/freecad_buddy/adapters/audit_log.py` -- Extend `before`/`after` to accept real fingerprint digests and a rollback block -- closes DW-2, which explicitly defers this to Story 3.2.
- [x] `benchmarks/harness/assertions.py` -- Implement `evaluate` over the eight `fn` names used by the G2 dev cases, reconciling the three declared extensions (`expect_solid_count`, `expect_sketch_fully_constrained`, `expect_sketch_geometry_count`) against the §7.2 vocabulary -- `gate.yaml` cites this path as the deterministic grader; without it every G2 criterion is `INVALID_INPUT`.
- [x] `benchmarks/g2/gate.yaml` -- Correct the `run_mutation` validator target to the real module path -- a citation that names a non-existent module cannot be verified.
- [x] `benchmarks/g2/fault-injection/rollback-boundary/` -- Materialize the 4 rollback-boundary fixtures: build each `.FCStd` through the new runtime, flip `fixture: pending`, add provenance manifests -- Story 3.1 recorded these as carry-overs that only the mutation runtime can plant; AC 2 depends on the #6031 case existing.
- [x] `tests/infc/test_mutation_protocol.py` -- stdlib `unittest` covering every row of the I/O matrix, including a forced hash-mismatch that exercises the snapshot-restore path and an injected `op()` exception -- the abort/re-hash path is the story's whole point and cannot be proven by inspection.
- [x] `tests/external/test_mutation_contract.py` -- pytest over the new contract types + schema drift -- contracts are stdlib-only and testable outside FreeCAD.
- [x] **Final Task: Quality Checks** -- Run `python scripts/check_imports.py`, `uv run python scripts/check_provenance.py`, `uv run pytest tests/external`, and the in-FreeCAD suite via `tests/run_tests.py`.

**Acceptance Criteria:**
- Given any typed op wrapped by `run_mutation`, when post-verify fails or an exception raises, then abort → recompute → re-hash proves restoration, escalating to `saveCopy` restore on mismatch; the result envelope reports `rolled_back` plus the proof path; and an audit record is written carrying both fingerprints.
- Given the #6031-pattern fault case, when executed, then the hash-mismatch path fires and the snapshot restore re-verifies — the planted fault is caught, and its paired clean control is not.
- Given a document where `shim.element_map_available()` is false, when a mutation completes, then the `tnp_audit` block reports `UNSUPPORTED` and no reference reports `PASS`.
- Given a successful mutation, when the envelope is inspected, then the snapshot file no longer exists on disk and no transaction is left open.

## Spec Change Log

## Review Triage Log

### 2026-07-31 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 12: (high 4, medium 8)
- defer: 7: (high 2, medium 5)
- reject: 11: (low 11)
- addressed_findings:
  - `[high]` `[patch]` `hole_spacing` called `float()` on a list `expect`, so `g2-dev-032-pattern` crashed with a `TypeError` reported as a geometry failure — rewrote `_measure_hole_spacing` to accept a scalar or per-direction pitch list.
  - `[high]` `[patch]` `hole_spacing` measured gaps between consecutively-sorted holes, so a correct rectangular pattern was graded against a diagonal — now grades nearest-neighbour distance per hole and requires every declared pitch to be matched and every measured gap to be declared.
  - `[high]` `[patch]` the commit path deleted the snapshot before taking the after-fingerprint, so a raising `fingerprint()` destroyed the only pre-mutation copy of a committed document — fingerprint now precedes deletion.
  - `[high]` `[patch]` `_delete_snapshot` unlinked every file in the target's parent directory with no prefix guard, so a non-reserved path had its directory contents removed — now removes only the single file unless the directory carries the reserved snapshot prefix.
  - `[medium]` `[patch]` `run_mutation` discarded `shim.enable_undo`'s result, so a document whose undo could not be enabled reported a snapshot-path rollback indistinguishable from the #6031 defect — the unavailability is now recorded in the explanation.
  - `[medium]` `[patch]` `post_verify` overwrote `fully_constrained` on each sketch, so a constrained last sketch masked an unconstrained earlier one — now reports the conjunction across every touched sketch.
  - `[medium]` `[patch]` `verify_shape`/`verify_sketch` raise `ValidationError` for an unknown or shapeless object, which escaped `post_verify` — both calls now map that to a failing block naming the object.
  - `[medium]` `[patch]` `tests/external/test_mutation_contract.py` imported `benchmarks` only via `sys.path` leaked from an alphabetically-earlier test module, so it failed when run alone — added the repo-root bootstrap used by the other harness tests.
  - `[medium]` `[patch]` `_MISSING_PREFIX` was declared and test-pinned but never read, so a `?`-marked unresolved element was recorded as a healthy indexed name — `_split_subname` now strips the prefix and flags the entry, and a new missing-element sweep reports it `BROKEN`.
  - `[medium]` `[patch]` the Layer-0 validity sweep was skipped entirely on the `UNSUPPORTED` path, so an outright-broken object went unreported on a build lacking an element map — the sweep now runs on both paths.
  - `[medium]` `[patch]` an audit-sink write failure propagated out of the bracket and could leave a transaction open — audit writes are now contained.
  - `[medium]` `[patch]` `_graded_shape` tested membership with `obj in objects`, relying on FreeCAD proxy `__eq__` being identity — now matches on immutable `Name`.

### 2026-07-31 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 2: (high 1, medium 1)
- defer: 3: (medium 1, low 2)
- reject: 22: (medium 10, low 12)
- addressed_findings:
  - `[high]` `[patch]` `params_digest` was declared on `MutationBlock` and pinned by a contract test but never written by `_mutation_block`, so every emitted block omitted the key and a consumer reading it raised `KeyError` — `run_mutation` now digests `params` with the audit sink's exact serialization and threads it through all three block call sites.
  - `[medium]` `[patch]` `test_assertions_grade_every_declared_g2_fn` compared `SUPPORTED_FNS` against a hand-typed literal copy of itself, so a case introducing an ungraded `fn` stayed green — the test now reads the `fn` names out of the committed G2 `case.yaml` files (skipping sealed `heldout/`), verified by injecting a bogus `fn` and watching it fail.

## Design Notes

The bracket is transcribed from `verification-design.md` §1.2 — treat that pseudocode as the specification, not as inspiration. Two traps it encodes that are easy to lose:

```python
doc.abortTransaction()
doc.recompute()              # R2 — MUST precede any verification; undo skips recompute
if fingerprints_equal(fingerprint(doc), fp_before):
    proof = "rolled_back_verified"
else:
    restore_from_snapshot(doc, snap_path)   # close + reopen from saveCopy
    doc.recompute()
    proof = "rolled_back_via_snapshot"      # reported whenever taken (G2.3)
```

`DocumentRegistry.with_document()` holds a non-reentrant lock, so `run_mutation` must receive the already-resolved document object from inside that callback rather than re-resolving a handle itself — otherwise the first mutation deadlocks.

The `mutation` block field names are fixed by `epic-3-context.md` and must match the audit vocabulary exactly (`fingerprint_before`, `fingerprint_after`, `verify_verdict`, `params_digest`); Story 3.6's diff reuses these identifiers, so introducing a synonym here breaks it downstream.

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: `check_imports OK` (proves no FreeCAD/Qt/third-party leak into the wrong ring)
- `uv run pytest tests/external` -- expected: all pass, no regression against the 621-passing baseline
- `python tests/run_tests.py` under `FreeCADCmd` -- expected: the new `test_mutation_protocol` cases pass on the FreeCAD leg
- `uv run python scripts/check_provenance.py` -- expected: `check_provenance OK` with the rollback-boundary fixtures no longer `pending`
- `uv run python scripts/gen_schemas.py` -- expected: byte-identical regeneration (no drift)

**Manual checks (if no CLI):**
- Inspect the audit JSON-lines output after a forced-failure mutation: the record must carry non-null `fingerprint_before` and `fingerprint_after` and a rollback block naming the proof path.

## Auto Run Result

Status: done

### Implemented change

`run_mutation()` lands as `usecases/transaction.py` — the single path every Phase-2 mutation
executes through. Outside the transaction it fingerprints the document, snapshots references and
writes a `saveCopy` snapshot to a reserved-prefix temp directory; then one transaction (never
nested, never left open) wraps the typed op, `recompute()` and `post_verify`. On pass it commits;
on failure or exception it aborts, recomputes, and proves restoration by re-hash, escalating to
snapshot restore when the hash differs and refusing to claim restoration when neither path proves
it. `tnp_guard.py` ships Layer 0 plus the capability-gated `UNSUPPORTED` posture; Layers 1-2 are
Story 3.5 and slot in behind unchanged signatures. `contracts/mutation.py` owns the new wire
vocabulary, and the audit record now carries real fingerprint digests (closing DW-2).

### Files changed

**Created**
- `src/freecad_buddy/contracts/mutation.py` — mutation/post-verify/TNP blocks, verdict and rollback-proof literals; stdlib only
- `src/freecad_buddy/contracts/jsonschema/mutation.schema.json` — generated wire schema
- `src/freecad_buddy/usecases/transaction.py` — the AD-5 bracket, `post_verify`, snapshot helpers
- `src/freecad_buddy/usecases/tnp_guard.py` — `snapshot_references`/`audit_references`, Layer 0 + missing-element sweep
- `benchmarks/harness/assertions.py` — deterministic grader over the eight declared G2 `fn` names
- `benchmarks/g2/fault-injection/rollback-boundary/build_rollback_fixtures.py` + 4 `fixture.FCStd`
- `benchmarks/_registry/provenance/g2-fault-rollback-*.yaml` (4) — required manifests
- `tests/infc/test_mutation_protocol.py` — 23 in-FreeCAD cases covering every I/O-matrix row
- `tests/external/test_mutation_contract.py` — 28 contract/schema/import-discipline cases

**Modified**
- `src/freecad_buddy/contracts/__init__.py` — export the mutation symbols
- `src/freecad_buddy/usecases/shim.py` — `enable_undo(doc)` capability probe (writes then reads back)
- `src/freecad_buddy/adapters/audit_log.py` — `before`/`after` accept real digests and a rollback block
- `scripts/gen_schemas.py` — register the new wire root
- `benchmarks/g2/gate.yaml`, `benchmarks/g2/README.md` — grader path is live; vocabulary reconcile recorded
- 4 `rollback-boundary/*/case.yaml` — validator target corrected, fixtures materialized
- `tests/external/test_g2_benchmark.py` — accepts a materialized fixture when `.FCStd` + manifest exist

### Review findings

12 patches applied (4 high, 8 medium) — see Review Triage Log. 7 deferred as DW-70..DW-76.
11 rejected as noise. No intent gaps, no spec defects.

The four high-severity patches: `hole_spacing` crashed on a list `expect` and measured diagonal
gaps (two of the 40 dev cases were ungradeable); the commit path destroyed the snapshot before
taking the after-fingerprint; and `_delete_snapshot` emptied whatever directory it was pointed at
with no prefix guard.

### Verification

- `python scripts/check_imports.py` — `check_imports OK`
- `uv run pytest tests/external` — `650 passed, 5 warnings` (pre-change baseline 622)
- `freecadcmd tests/run_tests.py` — `Ran 165 tests` / `OK (skipped=1)` (baseline 142)
- `uv run python scripts/gen_schemas.py --check` — `gen_schemas --check OK`
- `uv run python scripts/check_provenance.py` — `check_provenance OK`
- `uv run ruff check` on the new/changed modules — `All checks passed!`
- `uv run pytest tests/external/test_mutation_contract.py` alone — passes (the reviewed
  `sys.path`-leak defect is fixed and re-verified in isolation)

Verified independently of the implementation report: the gate.yaml/`transaction.py` module
conflict resolution was re-grepped (the stale target was in the four case files, not `gate.yaml:54`
as the spec's Code Map said), and the `float([15.0, 15.0])` crash was reproduced directly.

### Residual risks

- **Only the FreeCAD 1.1.x leg was exercised.** The 1.0.x blocking CI leg is unverified locally.
- **`UndoMode` contradicts the source checkout.** `DocumentPyImp.cpp` shows a dead shim; the
  installed 1.1.1 build has it live and defaulting to `0` headless, where `abortTransaction`
  restores nothing. Handled by a read-back capability probe rather than a version check, but the
  divergence means the 1.0.x leg may behave differently again.
- **A `CLEAN` TNP verdict is not yet evidence** that references survived — only Layer 0 runs
  (DW-70). Silent re-points remain invisible until Story 3.5.
- **The snapshot-restore path returns an unrebound document** (DW-71); the first mutation tool
  call site must rebind or it will act on a closed document.
- **Nothing scores G2 yet** (DW-72/DW-73): no fault scorer, no `validators.yaml` rows, and the
  `planted_op` identifiers are unimplemented. No G2 pass rate should be quoted until they land.
- `followup_review_recommended: true` — the patch volume and the four high-severity fixes span
  three modules and touch data-loss ordering and destructive deletion, which warrants an
  independent pass.

---

## Auto Run Result — follow-up review pass (2026-07-31)

Status: done

### Scope

This run was the independent follow-up the previous pass recommended
(`followup_review_recommended: true`). No implementation work: the spec entered at `status: done`,
so the pass re-reviewed the committed diff `9d2f068..HEAD` rather than re-deriving code.

### Review findings

2 patches applied (1 high, 1 medium), 3 deferred (DW-77..DW-79), 22 rejected. No intent gaps, no
spec defects, no repair loopback.

- **`params_digest` was dead on the wire (high).** `MutationBlock` declared it and
  `test_mutation_block_uses_the_shared_audit_field_names` pinned its presence in the type hints,
  but `_mutation_block` never wrote the key, so every emitted block omitted it and a consumer doing
  `block["params_digest"]` raised `KeyError`. `epic-3-context.md` fixes this identifier as shared
  with Story 3.6's diff, so the gap would have surfaced there as a missing field rather than a bug.
  `run_mutation` now computes the digest with the byte-identical serialization
  `adapters/audit_log._digest` uses, and passes it through all three block construction sites.
- **The G2 `fn` coverage test was a tautology (medium).** `test_assertions_grade_every_declared_g2_fn`
  asserted `declared <= SUPPORTED_FNS` where `declared` was a hand-typed copy of `SUPPORTED_FNS`,
  so a case introducing an assertion the grader cannot measure kept the test green — exactly the
  decay the docstring claimed to prevent. It now reads the `fn` names out of the committed G2
  `case.yaml` files, skipping the sealed `heldout/` tree.

Most rejected findings were re-reports of defects the previous pass already fixed (the snapshot
deletion ordering, the `_delete_snapshot` prefix guard, the sketch `fully_constrained` conjunction)
or demands for TNP Layer 1 behaviour that this story's **Never** section assigns to Story 3.5.

### Files changed

- `src/freecad_buddy/usecases/transaction.py` — `_params_digest()` helper; `params_digest` threaded into `_mutation_block` and all three call sites
- `tests/external/test_mutation_contract.py` — coverage test reads real case files instead of a literal copy
- `src/freecad_buddy/contracts/jsonschema/mutation.schema.json` — regenerated (no drift; byte-identical)
- `_bmad-output/implementation-artifacts/deferred-work.md` — DW-77..DW-79 appended

Also removed a stray `</content></invoke>` fragment that a prior write had left in this spec file
between the Verification section and the first Auto Run Result.

### Verification

- `python scripts/check_imports.py` — `check_imports OK`
- `uv run pytest tests/external` — `650 passed, 5 warnings`
- `freecadcmd tests/run_tests.py` — `Ran 165 tests` / `OK (skipped=1)`
- `uv run python scripts/gen_schemas.py` then `git status` on `contracts/jsonschema/` — no drift
- `uv run python scripts/check_provenance.py` — `check_provenance OK`

Both patches were verified by falsification rather than by a green suite, since neither defect was
covered by an existing assertion:

- `params_digest` was probed under `FreeCADCmd` on a real document across both bracket exits: the
  commit path and the proven-rollback path each emit the digest, the two agree, and the value
  matches an independently computed `sha256` of the audit sink's serialization.
- The coverage test was falsified by appending `fn: expect_bogus_never_implemented` to
  `benchmarks/g2/dev/g2-dev-001-sketch/case.yaml`, confirming it fails, then restoring the file
  (`git diff` clean afterwards).

### Residual risks

- **The bracket is only partly exception-guarded (DW-77).** `saveCopy`, both `fingerprint()` calls
  outside the `try`, `commitTransaction` and the post-abort `recompute` can each escape
  `run_mutation` with no envelope and a leaked snapshot directory. Unreachable through any current
  caller, but every Story 3.3–3.7 tool inherits it.
- **The 1.0.x CI leg remains unverified locally** — unchanged from the previous pass.
- **DW-70 through DW-76 remain open**; this pass did not re-verify them and did not modify their
  entries.
- `followup_review_recommended: false` — two localized fixes, one adding a field that was already
  contract-declared and one tightening a test. Neither changes mutation behaviour or the wire
  shape, and both were verified by direct falsification.
