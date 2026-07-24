---
title: 'DW-14: enforce license fields for non-hand-authored provenance manifests'
type: 'feature'
created: '2026-07-24'
status: 'done'
baseline_revision: 'b83312e33295becca58cd2c2adcd72dc67333335'
final_revision: '29858b853160319529a0e48d98e48054bfaea3d0'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** `scripts/check_provenance.py` validates only that `source.kind` is in the closed set. A future non-hand-authored artifact (`freecad-parts-library`, `freecad-wiki-tutorial`, `hf-verified-permissive`) would pass the AD-16 gate with no license/attribution recorded, exactly the copyright-contamination risk AD-16 exists to prevent.

**Approach:** Add a conditional check to `check_tree`: when a manifest's `source.kind != hand-authored`, require non-empty `source.url`, `source.license`, and `source.attribution`. Purely additive — all 17 current manifests are `hand-authored` and unaffected.

## Boundaries & Constraints

**Always:** Match the existing `check_tree` violation style (`f"{rel} -- rule"`, appended to `violations`). Keep stdlib + `yaml` only (script already imports `yaml`). Field names come from design §1.2: `url`, `license`, `attribution` under `source`. Check keys off the same `source` dict already read for `kind`.

**Block If:** Design §1.2 required-field set turns out to disagree with the intent (it does not — §1.2 lists exactly url/license/attribution). No unattended decisions expected.

**Never:** Do not require license fields for `hand-authored` kind (those carry `real_world_basis`, already policy). Do not add fields to any existing manifest. Do not edit the deferred-work ledger. Do not touch orphan/duplicate/missing-fixture logic.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Hand-authored manifest | `source.kind: hand-authored`, no url/license/attribution | No violation | n/a |
| Non-hand-authored complete | `kind: freecad-parts-library` + url + license + attribution all non-empty | No violation | n/a |
| Non-hand-authored missing all | `kind: freecad-parts-library`, no url/license/attribution | One violation per missing field naming the manifest | Reported, not raised |
| Non-hand-authored empty field | `kind: hf-verified-permissive`, `license: ""` | Violation for the empty field | Reported, not raised |
| Unknown kind | `kind: bogus` | Existing closed-set violation fires; license check must not crash | Reported, not raised |

</intent-contract>

## Code Map

- `scripts/check_provenance.py` -- `check_tree` walks artifacts and validates each manifest's `source.kind`; the new conditional license check goes here, keyed off the same `source` dict.
- `benchmarks/_registry/provenance/*.yaml` -- 17 manifests, all `source.kind: hand-authored` (verified); reference for manifest shape, not edited.
- `tests/external/test_harness_g0.py` -- houses `check_provenance` failure-path tests (imports `check_provenance`, uses `check_tree` on copied/synthetic trees); new tests added here alongside existing ones.
- `_bmad-output/.../design/validation-harness-design.md` §1.2 -- authoritative required-field list for non-hand-authored sources.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/check_provenance.py` -- in `check_tree`, after the `source.kind` closed-set check, when `kind != "hand-authored"` require non-empty string `url`, `license`, `attribution` under `source`; append one `f"{rel} -- source.<field> required for non-hand-authored kind '<kind>'"` violation per missing/empty field. Only evaluate when `kind` is a valid string in the closed set (skip when `source` is not a dict or `kind` already flagged, to avoid double-reporting/crash). Update the module docstring's "Additionally flags" list.
- [x] `tests/external/test_harness_g0.py` -- add tests covering the I/O matrix rows: a synthetic non-hand-authored manifest missing license fields is flagged (one assertion per field), a complete non-hand-authored manifest is clean, and the real tree stays clean (existing `test_check_provenance_clean_on_real_tree` already asserts this — verify it still passes). Build the synthetic manifest by copying the real tree and adding a manifest+fixture pair, mirroring the existing `tmp_path` copytree pattern.

**Acceptance Criteria:**
- Given the real 17-manifest tree, when `check_tree(BENCHMARKS)` runs, then it returns `[]` (no regression — all manifests are hand-authored).
- Given a manifest with `source.kind: freecad-parts-library` and no `url`/`license`/`attribution`, when `check_tree` runs, then the result contains a violation for each of the three missing fields naming that manifest's artifact path.
- Given a manifest with `source.kind: freecad-parts-library` and all three fields non-empty, when `check_tree` runs, then no license-field violation is emitted for it.

## Design Notes

Field names are fixed by design §1.2 (AD-16 manifest shape):

```yaml
source:
  kind: freecad-parts-library
  url: https://github.com/FreeCAD/FreeCAD-library/...
  license: CC-BY-3.0
  attribution: "Original part by <author>, FreeCAD Parts Library"
```

The check keys on `kind != "hand-authored"` (not an allow-list) so any of the three non-hand-authored closed-set kinds is covered. "Non-empty string" means `isinstance(v, str) and v.strip()` — an empty or whitespace `license: ""` must still flag. When `source` is not a dict or `kind` is not in the closed set, the existing closed-set violation already fires; skip the license check there so a bad manifest yields one clear violation, not a cascade or a `AttributeError`.

## Verification

**Commands:**
- `python scripts/check_provenance.py` -- expected: prints `check_provenance OK`, exit 0 (real tree unaffected).
- `uv run pytest tests/external/test_harness_g0.py -q` -- expected: all tests pass, including new license-field tests and the unchanged clean-tree test.

## Review Triage Log

### 2026-07-24 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 3: (high 0, medium 1, low 2)
- defer: 1: (high 0, medium 0, low 1)
- reject: 8: (high 0, medium 0, low 8)
- addressed_findings:
  - `[medium]` `[patch]` I/O matrix "empty/whitespace field" row (`license: ""`) had no test; the `.strip()` branch was uncovered. Added `test_check_provenance_flags_non_hand_authored_blank_license_field`.
  - `[low]` `[patch]` I/O matrix "unknown kind must not crash license check" row untested. Added `test_check_provenance_unknown_kind_does_not_crash_license_check`.
  - `[low]` `[patch]` I/O matrix "hand-authored stays clean" row only covered incidentally by the real-tree test. Added direct `test_check_provenance_clean_on_hand_authored_without_license_fields`.

## Auto Run Result

Status: done

**Change:** Extended `scripts/check_provenance.py` `check_tree` to require non-empty `source.url`/`source.license`/`source.attribution` when a manifest's `source.kind` is a closed-set kind other than `hand-authored`, closing the AD-16 gap (DW-14). Purely additive — all 17 current manifests are `hand-authored`, so the real tree stays clean.

**Files changed:**
- `scripts/check_provenance.py` — added the conditional license-field check (an `elif` on the existing closed-set branch) and a docstring bullet.
- `tests/external/test_harness_g0.py` — added 5 tests: missing-all-fields flagged per field, complete-manifest clean, blank/whitespace field flagged, unknown kind does not crash the license check, hand-authored-without-fields stays clean.

**Review findings:** patch 3 (1 medium, 2 low) — all three were I/O-matrix rows the initial test task left uncovered (empty/whitespace field, unknown-kind no-crash, hand-authored-stays-clean); added as tests. defer 1 (low). reject 8 (scope-expansion or noise: `license_checked` enforcement, placeholder-string validation, per-field violation grouping, test-style nits — all outside the intent contract).

**Deferred (for orchestrator to record; ledger not edited per invocation):**
- summary: `check_provenance.py` does not enforce §1.2's "mandatory for hand-authored" `real_world_basis` field on `hand-authored` manifests.
- evidence: Design validation-harness-design §1.2 marks `real_world_basis` mandatory for `hand-authored`; the gate validates neither it nor §1.2's `license_checked` sign-off field. Pre-existing gap, out of DW-14 scope (DW-14 covers non-hand-authored license fields only); all 17 current manifests carry `real_world_basis` so nothing regresses now.

**Verification:**
- `uv run python scripts/check_provenance.py` → `check_provenance OK`, exit 0.
- `uv run pytest tests/external/test_harness_g0.py -q` → `29 passed`.
- `uv run ruff check scripts/check_provenance.py tests/external/test_harness_g0.py` → `All checks passed!`.

**Residual risk:** None for shipped artifacts (zero non-hand-authored manifests exist today). The new gate is exercised only by synthetic test manifests until the first real non-hand-authored artifact lands.
