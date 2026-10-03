---
title: 'Drop FreeCAD 1.0 support (FreeCAD 1.1 only)'
type: 'refactor'
created: '2026-10-03'
status: 'done'
baseline_commit: '4fd7a9b7aad91bef8997f5cc27aed2588d5ba090'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/project-structure.md'
  - '{project-root}/benchmarks/g3/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The project carries a FreeCAD 1.0.x "floor" leg: a CI matrix row, gates that require or compare two legs (G0.4, G3.E.3, AD-13 cross-leg frames), tests and a contract ban that exist only for 1.0, 1.0 enum spellings, and docs that state a 1.0 floor. The user decided (2026-10-03) to target FreeCAD 1.1 only.

**Approach:** Remove the 1.0.x leg and every 1.0-only path in code, CI, tests, gates, config and skills; re-define the two-leg gates for one 1.1 leg; move CI and the local env to FreeCAD 1.1.3 and re-score on it. Behaviour on 1.1 does not change.

**Decisions (2026-10-03):**
- **D1 — 1.1 only.** User instruction. The FreeCAD reference source (`docs/references/FreeCAD`) is pinned to tag `1.1.4`.
- **D2 — Keep Python 3.11.** The FreeCAD 1.1 Windows build bundles Python 3.11 and env `fcb` (1.1.0) runs 3.11.15, so `requires-python >=3.11` and ruff `py311` stay.
- **D3 — Keep the general shim probes** (exportBrep, VarSet/Spreadsheet). They are capability probes, not 1.0 branches, and no record proves 1.1 never takes the fallback.
- **D4 — FreeCAD 1.1.3 (1A).** conda-forge has no 1.1.4 build, so CI and the local `fcb` env run `freecad=1.1.3`, the nearest to the 1.1.4 reference source. Every scorer and registry score is re-run on it; `frames-reference.json` is regenerated only if a frame changes.
- **D5 — G3.E.3 on one leg (2A).** G3.E.3 reads "every built part's anchor frame equals the committed 1.1.x reference": a frame that changes between runs or after a FreeCAD update fails it. The CI frame check stays.
- **D6 — Planning artifacts go to correct course.** The user runs `bmad-correct-course` after this story to record the 1.1-only decision. This story edits no file under `_bmad-output/planning-artifacts/` or `_bmad-output/specs/`, no `docs/decisions/` ADR, `docs/intent.md` or `_bmad-output/project-context.md`; AD-11/AD-13 wording is corrected there.

## Boundaries & Constraints

**Always:**
- Every 1.1.x CI job, gate and test that passes today still passes.
- Historical records stay unedited: implementation specs, epic contexts, retros, reviews, research, sprint change proposals, `.memlog.md`, UAT run reports.
- `benchmarks/*/README.md` and gate wording describe the single 1.1.x leg.

**Never:**
- No change to measurement or tool behaviour on 1.1.
- No held-out read; no unseal.
- No removal of a capability probe (D3).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| G0.4 | only a green `G0.4.1.1.x.json` | G0.4 PASS | absent or red 1.1.x file → FAIL as today |
| G0.4 legacy | a `G0.4.1.0.x.json` present | ignored | — |
| G3.E.3 | 1.1.x evidence equals the reference | OK | drift → FAIL naming build and field; absent → `INVALID_INPUT` |
| Pattern mode | `mode: "length"` on 1.1 | refused, legal values `['Extent', 'Spacing']` | `ValidationError` as for any non-member |

</frozen-after-approval>

## Code Map

- `.github/workflows/ci.yml:84` matrix row `1.0.0/3.11`; `:110-135` leg expressions `matrix.freecad == '1.0.0' && '1.0.x' || '1.1.x'`; `:139-154` `g0-verdict` downloads both legs; `:68` unquoted step name (already quoted in the working tree).
- `benchmarks/runner.py:89-91` `_REQUIRED_G0_4_LEGS = ("1.0.x", "1.1.x")`, `:361-412` `_ingest_g0_4`, `:713-715` and `:1375` `--frames-evidence` help text.
- `benchmarks/g0/emit_ci_evidence.py:1-7`, `benchmarks/g0/gate.yaml:32-33` -- G0.4 wording.
- `benchmarks/g3/fault-injection/score_g3_replay.py:6-7,68,356,379,498` `LEGS`; `score_g3_validators.py:16,431-452` `frames_status`; `benchmarks/g3/gate.yaml:48,51,63`; `benchmarks/g3/README.md:33,39,54-61,94,309`.
- `src/freecad_buddy/usecases/features.py:57-63` `_PATTERN_EXTENT_MODES`/`_PATTERN_OFFSET_MODES` (drop `length`, `angle`, `offset`); comments at `features.py:410,1265,1310`, `contracts/feature.py:16-18`, `usecases/shim.py:21-23,221-223,419`.
- `tests/external/test_feature_contract.py:289-310` 1.0-floor property ban and two-leg tests; `tests/infc/test_document_lifecycle.py:164-166`; `tests/infc/test_feature_tools.py:627,1202`; `tests/infc/test_assertion_primitives.py:695-696`; `tests/external/test_g3_replay.py:343-413,570-608`; `tests/external/test_gate_verdict.py:320-361`; `tests/external/test_g3_benchmark.py:167`.
- `addon/package.xml:6` `<freecadmin>1.0</freecadmin>`; `skills/*/SKILL.md` frontmatter `freecad-versions: ['1.0', '1.1']` (15 files).
- Out of scope (D6), for the correct-course run: `ARCHITECTURE-SPINE.md:125,393,394,449` (AD-11, AD-13 wording); `design/project-structure.md:202-210,247`; `design/integration-mcp-freecad.md:248-253`; `design/data-contracts-design.md:36,105`; `design/skills-structure-design.md:66,104,168`; `_bmad-output/specs/spec-freecad-buddy/phase-gates.md:28,65` and `SPEC.md:22,122`; `epics.md:114,275,483-484,654`; `_bmad-output/project-context.md:20-21,77,79`; `docs/intent.md:150,352`.
- Local envs: `C:/Users/thuan/micromamba/envs/fcb` (FreeCAD 1.1.0, py3.11) is rebuilt on `freecad=1.1.3`; `fcb10` (FreeCAD 1.0.0) is removed. Recreate `fcb` as CI does: `python=3.11 freecad=1.1.3`, then `pip install --no-deps -e .` and `"mcp>=1.28,<2" pytest jsonschema pyyaml`.

## Tasks & Acceptance

**Execution:**
- [x] `.github/workflows/ci.yml` -- one headless leg `{freecad: "1.1.3", python: "3.11"}`; leg expressions become the literal `1.1.x`; `g0-verdict` downloads the one leg; keep the step-name quoting.
- [x] `benchmarks/runner.py`, `benchmarks/g0/emit_ci_evidence.py`, `benchmarks/g0/gate.yaml` -- G0.4 requires only `1.1.x`; a `G0.4.1.0.x.json` file is ignored.
- [x] `benchmarks/g3/fault-injection/score_g3_replay.py`, `score_g3_validators.py`, `benchmarks/g3/gate.yaml`, `benchmarks/g3/README.md` -- `LEGS = ("1.1.x",)`; G3.E.3 per D5; wording for one leg.
- [x] `src/freecad_buddy/usecases/features.py`, `contracts/feature.py`, `usecases/shim.py` -- drop the 1.0 spellings `length`, `angle`, `offset` and the "supported builds differ" comments.
- [x] `tests/external/test_feature_contract.py`, `tests/infc/test_document_lifecycle.py`, `tests/infc/test_feature_tools.py`, `tests/infc/test_assertion_primitives.py`, `tests/external/test_g3_replay.py`, `tests/external/test_gate_verdict.py`, `tests/external/test_g3_benchmark.py` -- remove 1.0-only tests and two-leg cases; keep one-leg equivalents for every I/O row.
- [x] `addon/package.xml` -- `<freecadmin>1.1</freecadmin>`; `skills/*/SKILL.md` -- `freecad-versions: ['1.1']`.
- [x] Local envs -- rebuild `fcb` on 1.1.3 (D4); remove `fcb10`.
- [x] Re-score on 1.1.3: G0 `score_verify_shape.py`, G2 `score_g2_infc.py`, G3 `score_g3_replay.py --leg 1.1.x` (writes `validators.yaml`); compare frames with `frames-reference.json` and regenerate it only on a real change, stating which frames moved.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- append a resolution entry for the FreeCAD 1.0 suite failures and the unparseable `ci.yml`; existing entries are not edited.

**Acceptance Criteria:**
- Given `grep -rniE "1\.0\.x|1\.0\.0|floor leg" .github src tests benchmarks addon skills scripts pyproject.toml` (excluding `heldout`, `gate-artifacts`, `tests/uat/run`), when run, then no hit remains that describes a 1.0 leg or 1.0 support.
- Given env `fcb` on FreeCAD 1.1.3, when the in-FreeCAD suite, the external suite and the three scorers run, then all pass except the 5 known G1 grader-hash tests, and `runner faults G3 --frames-evidence` reports G3.E.3 and G3.E.4 OK.
- Given `.github/workflows/*.yml`, when parsed as YAML, then each parses and `ci.yml` has one headless leg.

## Implementation Notes

- Local env deviation, approved: conda-forge has no win-64 `freecad=1.1.3` build for Python 3.11 (builds: py310, py312, py313, py314), so `fcb` runs FreeCAD 1.1.3 on Python 3.12.14. CI (linux-64) keeps `{freecad: 1.1.3, python: 3.11}`; `requires-python >=3.11` and ruff `py311` are unchanged (D2). `fcb10` is removed.
- The `render` CI job also moved from `python=3.12 freecad=1.1.0` to `python=3.11 freecad=1.1.3`, so every CI job runs the D4 build.
- Pattern modes accept only `Extent` and `Spacing` (folded `extent`, `spacing`); `mode: "length"` is refused with `mode 'length' is not one of ['Extent', 'Spacing']` (new in-FreeCAD test).
- G0.4 requires only `1.1.x`; a `G0.4.1.0.x.json` file is not read (test). G3.E.3 reads "every built part's anchor frame equals the committed 1.1.x reference". No frame moved on 1.1.3, so `frames-reference.json` is unchanged.
- `validators.yaml`: only `spec_assertions` changed (sha `e4abcf2bff12`, run `g3r-2026-10-03-1.1.3`), because editing `score_g3_replay.py` staled it. G0 `verify_shape` re-scored 11/11 and G2 `assertions` 8/8, with unchanged shas.
- Verified by the lead on FreeCAD 1.1.3: in-FreeCAD suite 672 run, OK (1 skipped); `pytest tests/external` 1202 passed, 5 failed (known G1 grader-hash); G3 replay 10/10, 0/14, frames OK; `runner faults G3 --frames-evidence` G3.E.3 and G3.E.4 OK; `check_imports`, `gen_schemas --check`, `check_provenance`, ruff on touched files and YAML parse of the three workflows OK. The acceptance grep leaves one hit, `tests/external/test_gate_verdict.py:347`, the test that proves a 1.0.x G0.4 file is ignored (I/O row "G0.4 legacy").
- A stray empty file `1.28` at the repository root, written by an unquoted `mcp>=1.28` shell redirect during the env rebuild, was deleted.

- Review pass 1 patches: linear and polar `Spacing` pattern tests; the retired-`length` test reads the live enumeration and follows the naming rule; `_mode_drives_offset` docstring; README provenance line for the frame reference (recorded on 1.1.0, re-checked unchanged on 1.1.3); single-leg wording in `g2/gate.yaml`, `runner.py` and `ci.yml`. Final lead run on FreeCAD 1.1.3: in-FreeCAD 674 run, OK (1 skipped); external 1202 passed, 5 failed (known G1); G3 replay 10/10, 0/14, frames OK; G3.E.3 and G3.E.4 OK; static checks and YAML parse OK.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-10-03). Layers: blind-hunter (BH), edge-case-hunter (EC), verification-gap (VG).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| VG1 / BH6 | No test drives `mode="Spacing"`, linear or polar, after the offset-mode set narrowed to `spacing` | medium | Every `feature_pattern` test uses `Extent`, no mode, or a non-member; a broken `_PATTERN_OFFSET_MODES` passes all tests | patch |
| BH3 / BH4 | New test hard-codes `['Extent', 'Spacing']` and its name breaks `Should <outcome> When <condition>` | low | The neighbouring tests read the live enumeration; CLAUDE.md §9 naming rule | patch |
| BH7 | `_mode_drives_offset` docstring still describes several spellings | low | Sets now hold one member each; direct correction | patch |
| BH8 | Nothing in the repo says the frame reference was re-checked on 1.1.3 | low | `frames-reference.json` records `1.1.0`; one README line closes it | patch |
| BH11 | Two-leg wording left (`g2/gate.yaml:64` "matrix legs", `runner.py:89` "matrix legs", "ONE run dir/report") | low | Direct text corrections | patch |
| BH13 | Minimum FreeCAD version raised without a breaking-change marker | low | `package.xml` `freecadmin` 1.0 -> 1.1 narrows support | patch (commit footer) |
| BH1 | CI env solve for `freecad=1.1.3 python=3.11` unverified | false | VG layer ran `micromamba search` on linux-64: a `python_abi 3.11` build exists | reject |
| BH2 | Literal `1.1.x` labels and a one-row matrix | low | A FreeCAD bump is a deliberate edit of the same file; fix adds structure | reject |
| BH5 | Polar `angle` and `offset` spellings not tested as refused | low | Same `_checked_enum` path as the tested `length`; one case covers it | reject |
| BH9 | README G3.E.3 wording differs from `phase-gates.md` | low | D6: `phase-gates.md` is corrected by the correct-course run that follows this story | reject |
| BH10 | Patch omits `deferred-work.md`, the FreeCAD pin, and `test_g3_benchmark.py:167` | false | `deferred-work.md` was excluded from the review patch on purpose; the FreeCAD reference is its own git checkout; `test_g3_benchmark.py` needed no edit (its G3.E.3 expectation already reads one leg) | reject |
| BH12 | Run id `g3r-2026-10-03-1.1.3` breaks the `<leg>` naming | low | Cosmetic; the id is free text | reject |
| BH14 | Resolution entry links old entries in prose only | low | The ledger forbids editing existing entries | reject |
| EC1 | Manual install on FreeCAD 1.0 gives a misleading mode error | low | 1.0 is unsupported (D1); the call still fails loudly | reject |

## Verification

**Commands:**
- `micromamba run -n fcb FreeCADCmd tests/run_tests.py` -- expected: OK on FreeCAD 1.1.3.
- `uv run pytest tests/external` -- expected: only the 5 known G1 grader-hash failures.
- `micromamba run -n fcb python benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x --frames-check benchmarks/g3/fault-injection/frames-reference.json` -- expected: exit 0, 10/10, 0/14.
- `uv run python -m benchmarks.runner faults G3 --frames-evidence <run dir>` -- expected: G3.E.3 and G3.E.4 OK.
- `uv run ruff check . ` on touched files, `check_imports`, `gen_schemas --check`, `check_provenance`, YAML parse of every workflow -- expected: pass.
