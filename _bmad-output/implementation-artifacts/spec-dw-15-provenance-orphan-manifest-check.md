---
title: 'DW-15: check_provenance flags orphan manifests (manifest->artifact reverse coverage)'
type: 'feature'
created: '2026-07-24'
status: 'done'
baseline_revision: 'a1f4ff107bd7fa85b95ada6fcd6d5f02ef1b27e5'
final_revision: '68a8686f2482c8cc8d908eec81443864d0aac2ca'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** `check_provenance.check_tree` walks artifacts->manifest only (every `.FCStd` must have a manifest), but never the reverse. A `_registry/provenance/*.yaml` whose declared `artifact` id no longer resolves to a live `.FCStd` (fixture renamed/deleted) is silently accepted — the AD-16 gate misses the orphan.

**Approach:** Add a manifest->artifact reverse pass in `check_tree`: for each loaded manifest, if `<benchmarks_root>/<artifact_id>.FCStd` does not exist, append an orphan violation. Add a unit test that plants an orphan (delete a fixture, keep its manifest) and asserts the flag.

## Boundaries & Constraints

**Always:** Reverse pass uses the already-loaded `manifests` dict from `_load_manifests` (no second yaml walk). Orphan check resolves `<root>/<artifact_id>.FCStd` — the same `.FCStd`-suffix convention `_artifact_id` uses. Excluded dirs (`heldout/`) already never produce manifests, so no special-casing needed. Existing artifact->manifest, duplicate-id, missing-fixture, and source.kind checks stay byte-identical. Match existing violation-string style (`path -- rule`).

**Block If:** A manifest's `artifact` id resolves to a non-`.FCStd` fixture on the real tree (would make every manifest look orphaned) — investigation shows all 47 manifests map to `<id>.FCStd`, so this does not trigger; if it does at implementation time, HALT.

**Never:** Do not change `_iter_artifacts`, `_check_missing_fixtures`, `_load_manifests`, or the CLOSED_SOURCE_KINDS set. No new CLI flags. Do not edit the deferred-work ledger. Do not relax or reorder existing violations.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Clean tree | Every manifest artifact_id has a live `.FCStd` | No orphan violation (real tree stays exit 0) | No error expected |
| Orphan manifest | Manifest declares `artifact: g0/golden-models/box-10-20-30`, that `.FCStd` deleted | Violation `<manifest-rel> -- orphan manifest (artifact '<id>' has no matching .FCStd)` | Flagged, not crashed |
| Rename churn | Fixture moved, manifest still points at old id | Old id flagged as orphan (and new `.FCStd` flagged as no-manifest by existing pass) | Both flagged |

</intent-contract>

## Code Map

- `scripts/check_provenance.py` -- `check_tree` (l141-160) walks artifacts->manifest; `_load_manifests` (l45-69) returns `{artifact_id: manifest}`. Add reverse pass here.
- `tests/external/test_harness_g0.py` -- section (c) l134-176 holds all `check_provenance` failure-path tests (copytree + mutate + assert substring). Add orphan test here.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/check_provenance.py` -- in `check_tree`, after the existing artifact->manifest loop, iterate `sorted(manifests.items())` and for each `artifact_id` whose `<benchmarks_root>/<artifact_id + ".FCStd">` is not a file, append `f"{manifest-path-rel} -- orphan manifest (artifact '{artifact_id}' has no matching .FCStd)"`. Manifest path comes from re-resolving under `_registry/provenance`; simplest is to carry the manifest source path. -- reverse coverage for DW-15.
- [x] `scripts/check_provenance.py` -- to name the offending manifest file in the violation, extend `_load_manifests` to record each artifact's source manifest path (e.g. return `{artifact_id: (manifest_dict, manifest_path)}` OR keep a parallel `dict[str, Path]`), used only by the orphan pass. Keep the existing `manifests[artifact_id]` dict shape usable by the source.kind loop (adjust that access if the shape changes). -- lets the orphan violation cite the manifest, matching `path -- rule` style.
- [x] `tests/external/test_harness_g0.py` -- add `test_check_provenance_flags_orphan_manifest(tmp_path)`: copytree BENCHMARKS, delete a golden `.FCStd` (e.g. `g0/golden-models/box-10-20-30.FCStd`) while leaving its manifest, assert some problem contains `orphan manifest` and the artifact id. Delete the matching fixture's manifest is NOT done (that would be the no-manifest case). -- unit test with planted orphan.

**Acceptance Criteria:**
- Given the real committed `benchmarks/` tree, when `check_tree(BENCHMARKS)` runs, then it returns `[]` (no orphan false-positive; existing clean-tree test still passes).
- Given a copy where a golden `.FCStd` is deleted but its manifest remains, when `check_tree(copy)` runs, then a violation containing `orphan manifest` and that artifact id is present.
- Given a copy where a manifest is deleted (existing test), when `check_tree` runs, then the `no provenance manifest` violation still fires unchanged (no regression to artifact->manifest direction).

## Design Notes

Reverse pass reuses the loaded manifests — no second yaml parse. Naming the manifest file in the violation requires knowing its path; the cheapest change is a parallel `dict[str, Path]` (artifact_id -> manifest_path) returned from `_load_manifests`, leaving `manifests[artifact_id]` (the dict) untouched so the source.kind loop needs no edit.

Golden example (violation string):
```
_registry/provenance/g0-golden-box-10-20-30.yaml -- orphan manifest (artifact 'g0/golden-models/box-10-20-30' has no matching .FCStd)
```

## Verification

**Commands:**
- `python -m pytest tests/external/test_harness_g0.py -k check_provenance -q` -- expected: all provenance tests pass incl. new orphan test
- `python scripts/check_provenance.py` -- expected: prints `check_provenance OK`, exit 0 (real tree has no orphan)
- `python scripts/check_imports.py` -- expected: exit 0 (no ring violation introduced)

## Review Triage Log

### 2026-07-24 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 1: (high 0, medium 1, low 0)
- defer: 1: (high 0, medium 1, low 0)
- reject: 6
- addressed_findings:
  - `[medium]` `[patch]` Orphan reverse pass did not skip `_EXCLUDED_DIRS` (heldout/), unlike every other walk in the module; a sealed `heldout/` manifest whose `.FCStd` is absent from the working tree would false-orphan. Added `if any(part in _EXCLUDED_DIRS for part in Path(artifact_id).parts): continue` before the file check. Latent (no heldout `.FCStd` exists today); patched for symmetry with `_iter_artifacts`/`_check_missing_fixtures`.

## Auto Run Result

**Summary:** Added manifest->artifact reverse coverage to `check_provenance.check_tree`. A `_registry/provenance/*.yaml` whose declared `artifact` id has no matching live `<root>/<id>.FCStd` (orphan, e.g. after a fixture rename/delete) is now flagged, closing DW-15. Forward artifact->manifest, duplicate-id, missing-fixture, and source.kind checks unchanged.

**Files changed:**
- `scripts/check_provenance.py` — `_load_manifests` returns a parallel `{artifact_id: manifest_path}` dict; `check_tree` runs a reverse pass (skipping `_EXCLUDED_DIRS`) that flags orphan manifests. Docstring "Additionally flags" list gained the orphan line.
- `tests/external/test_harness_g0.py` — added `test_check_provenance_flags_orphan_manifest` (delete a golden `.FCStd`, keep its manifest, assert `orphan manifest` flagged).

**Review findings:** 1 patch applied (heldout exclusion for the reverse pass — medium, latent). 1 deferred (non-`.FCStd` manifests, e.g. export-fault `.stl`/`.3mf`/`.step` or text cases, would false-orphan; no such manifest exists today — all 47 map to `.FCStd`). 6 rejected (double-flag redundancy where both messages are true positives; test-strength/message-pinning nits within house style; id-shape/case-sensitivity/sort-order traps shared with the pre-existing forward check; parallel-dict design smell chosen by spec).

**Verification:**
- `python -m pytest tests/external/test_harness_g0.py -k check_provenance -q` → `6 passed, 18 deselected`
- full `test_harness_g0.py` → `24 passed` (no regression)
- `python scripts/check_provenance.py` → `check_provenance OK`, exit 0
- `python scripts/check_imports.py` → `check_imports OK`, exit 0

**Residual risks:** Reverse pass assumes every provenance manifest maps to a `.FCStd`. True for all 47 current manifests; a future non-`.FCStd` (export-fault / text-case) manifest would false-orphan — captured as deferred work.
