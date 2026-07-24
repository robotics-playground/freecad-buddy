---
title: 'Harden the verify_shape fault scorer case.yaml flow-mapping parser (DW-31)'
type: 'refactor'
created: '2026-07-24'
status: 'done'
baseline_revision: 'b961b7fa7ccafb936f4d64e037d988c0594680f9'
final_revision: 'f74b75a026226583d07d094eea3f52d48d9f5e77'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** The in-FreeCAD `verify_shape` fault scorer parses `case.yaml` checks with a greedy `_CHECK_RE = re.compile(r"\{(fn:.*)\}")` (matches the LAST `}` on a line, breaks on multi-line flow mappings or a `}` inside a value) and a blind `.replace("rel"/"abs")` before `ast.literal_eval` on the `tol` value (corrupts any value whose text contains the substrings `rel`/`abs`). Both mis-parse legal check shapes.

**Approach:** Replace `_CHECK_RE` line-matching with a brace-balanced flow-mapping tokenizer that extracts each `{...}` block honoring nesting and quotes (so multi-line mappings and nested braces parse correctly), and parse the `tol` mapping with the existing `_split_top_level` + `_parse_scalar` primitives instead of the `.replace(...)+ast.literal_eval` hack. pyyaml stays external-process-only (AD-12); the scorer keeps parsing the fixed shape itself.

## Boundaries & Constraints

**Always:**
- Scorer stays stdlib-only, in-FreeCAD safe (no pyyaml, no third-party) — AD-12.
- Preserve the public surface used by callers: `score()`, `main()`, and `_load_case(path) -> {"id","expectation","checks","dir"}`. The `checks` list stays identical in structure/values for the committed fixtures.
- New/changed parse helpers keep parsing the fixed shape `{fn: <name>, expect: <scalar|[list]>, tol: {rel|abs: <float>}}` and any check under `assertions.checks:` — a check may span multiple lines, contain nested braces/brackets, and contain quoted strings.
- Existing `_split_top_level` and `_parse_scalar` are reused, not reinvented.

**Block If:**
- A committed fixture uses a check shape that cannot be expressed by a brace-balanced flow-mapping tokenizer (e.g. YAML block style, anchors/aliases) — HALT `blocked`, the fixture is out of the fixed-shape contract.

**Never:**
- Do not add pyyaml or any third-party YAML dependency, and do not move scoring to the external process (that is the DW-31 alternative, not this task).
- Do not change scoring math, the bars, `validators.yaml` rendering/merge, or the fixtures.
- Do not use `ast.literal_eval` on raw substring-mutated text.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Single-line check | `- {fn: expect_volume, expect: 6000, tol: {rel: 0.001}}` | `{"fn":"expect_volume","expect":6000,"tol":{"rel":0.001}}` | none |
| List expect | `- {fn: expect_bbox, expect: [10, 20, 30], tol: {rel: 0.001}}` | `expect` is `[10,20,30]`, `tol` is `{"rel":0.001}` | none |
| abs tolerance | `tol: {abs: 0.01}` | `{"abs":0.01}` | none |
| Multi-line flow mapping | check split across lines inside one `{...}` | parsed identically to single-line | none |
| Value containing `rel`/`abs` substring | e.g. `fn: expect_relief` or a quoted string `'abs path'` | substring NOT corrupted; `fn` == `expect_relief` | none |
| Nested brace inside value | `expect` or `tol` block with an inner `{...}` | brace balance keeps the whole block together | none |

</intent-contract>

## Code Map

- `benchmarks/g0/fault-injection/score_verify_shape.py` -- the scorer; holds `_CHECK_RE` (l50), `_parse_check` (l102, the `.replace` hack l112), `_load_case` (l118, the `_CHECK_RE.finditer` at l123), plus reusable `_split_top_level`/`_parse_scalar`.
- `benchmarks/g0/fault-injection/*/case.yaml` -- 12 committed fixtures; the fixed check shape. Do not edit.
- `tests/infc/test_fault_score.py` -- in-FreeCAD scoring test (outcome-level; runs `scorer.score()`).
- `tests/external/test_harness_g0.py` -- external harness test touching the g0 suite.

## Tasks & Acceptance

**Execution:**
- [x] `benchmarks/g0/fault-injection/score_verify_shape.py` -- Add a brace-balanced flow-mapping extractor (e.g. `_iter_flow_mappings(text) -> list[str]`) that scans the whole `assertions.checks:` region and yields each top-level `{...}` block, tracking brace/bracket depth and skipping braces inside `'`/`"` quotes; replace the `_CHECK_RE.finditer` call in `_load_case` with it. Remove `_CHECK_RE` and the `import re` use for it (keep `re` only if still used for `id`/`expectation`). In `_parse_check`, parse the `tol` value with `_split_top_level` + `_parse_scalar` (build the dict from `k: v` parts) instead of `.replace("rel"/"abs")` + `ast.literal_eval`; drop the now-unused `import ast`. -- Removes both brittle spots while preserving parsed output for the fixtures.
- [x] `tests/infc/test_fault_score_parser.py` -- New in-FreeCAD `unittest` test (the scorer module's top-level `from freecad_buddy.usecases import verify` pulls FreeCAD, so this test must live in the `tests/infc/` world, run under `FreeCADCmd tests/run_tests.py`; a pytest external test can't import the module). Import the scorer, call `scorer._parse_check(...)` / the new extractor on hand-authored strings, and assert the I/O & Edge-Case Matrix rows: single-line, list expect, abs tol, multi-line mapping, a `fn`/string value containing `rel`/`abs` substrings, and a nested-brace value. -- Locks the parser against the DW-31 regressions.

**Acceptance Criteria:**
- Given the 12 committed fixtures, when `scorer.score()` runs (via `tests/infc/test_fault_score.py`), then sensitivity ≥ 0.95, false_alarm ≤ 0.05, no `MISSED`, no `FALSE_ALARM` — identical to before the change.
- Given a check whose `fn` or a quoted value contains the substring `rel` or `abs`, when parsed, then the value is returned uncorrupted (no injected quotes, no `ast` mutation).
- Given a check written as a multi-line flow mapping or containing a nested `{...}`/`[...]`, when parsed, then it yields the same dict a single-line equivalent would.
- Given the scorer source after the change, when grepped, then `_CHECK_RE`, `.replace("rel"`, and `ast.literal_eval` no longer appear.

## Spec Change Log

_No spec amendments — all review findings were resolved as in-diff patches._

## Review Triage Log

### 2026-07-24 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 0, medium 4, low 1)
- defer: 0
- reject: 3
- addressed_findings:
  - `[medium]` `[patch]` Inline `#` comment containing `{` produced a phantom check (`_iter_flow_mappings` had no comment awareness) — added depth-zero `#`-to-end-of-line comment skipping.
  - `[medium]` `[patch]` Malformed `tol` value (not brace-wrapped) was silently sliced by `[1:-1]` into garbage — added a brace-wrap guard that raises `ValueError`.
  - `[medium]` `[patch]` Unbalanced/underflowing braces silently dropped later checks — added a post-scan `depth != 0 or quote` guard that raises `ValueError`.
  - `[medium]` `[patch]` `checks:`-anchor miss silently fell back to scanning the whole document — now raises `ValueError` when no `checks:` region exists.
  - `[low]` `[patch]` `_parse_scalar` list branch used a naive `.split(",")` asymmetric with the correct `_split_top_level` three lines away — reused `_split_top_level`.
  - Rejected (out of fixed-shape contract or not caused by this change): full quote-threading of `_split_top_level` for string-with-comma `expect` (scalar-only per `verify.py`, no such fixture); unanchored `expectation:` regex (pre-existing, not this diff); unknown/duplicate-key handling in `_parse_check` (pre-existing loop behavior).

## Design Notes

The extractor is a small char scanner, not a regex: walk `text`, and once inside `assertions.checks:`, accumulate a block whenever `depth` transitions 0→>0 on `{`, incrementing on `{`/`[`, decrementing on `}`/`]`, ignoring bracket chars inside a `'`/`"` quoted run, and emitting the buffered block when `depth` returns to 0. This is the same depth/quote discipline `_split_top_level` already uses for commas — reuse the pattern. `tol` then parses via the same top-level split:

```python
inner = value.strip()[1:-1]  # drop the { }
check["tol"] = {
    k.strip(): _parse_scalar(v) for k, _, v in
    (p.partition(":") for p in _split_top_level(inner)) if k.strip()
}
```

`_split_top_level` currently ignores quotes; the extractor must handle quotes so a `}`/`,` inside a quoted string can't unbalance depth. Keeping the fixed-shape assumption (`fn`/`expect`/`tol` keys) is fine — DW-31 asks for robustness against those substrings and multi-line mappings, not full YAML.

## Verification

**Commands:**
- `python -c "import ast,sys; ast.parse(open('benchmarks/g0/fault-injection/score_verify_shape.py').read())"` -- expected: parses clean (syntax check without FreeCAD).
- `ruff check benchmarks/g0/fault-injection/score_verify_shape.py` -- expected: clean (no unused `re`/`ast` import left behind).
- `FreeCADCmd tests/run_tests.py` (or the project's in-FreeCAD runner) -- expected: both `test_fault_score.py` (scoring unchanged) and the new `test_fault_score_parser.py` (edge-case rows) green.

**Manual checks (if no CLI):**
- `grep -nE "_CHECK_RE|\.replace\(.rel|ast\.literal_eval" benchmarks/g0/fault-injection/score_verify_shape.py` returns nothing.

## Auto Run Result

Status: done

**Summary:** Replaced the two brittle spots in the in-FreeCAD `verify_shape` fault scorer's hand-rolled `case.yaml` parser (DW-31): the greedy `_CHECK_RE = re.compile(r"\{(fn:.*)\}")` and the blind `.replace("rel"/"abs") + ast.literal_eval` on the `tol` value. Checks are now extracted by a brace-balanced, quote- and comment-aware char scanner (`_iter_flow_mappings`) and `tol` parses via the existing `_split_top_level` + `_parse_scalar` primitives. pyyaml stays external-process-only (AD-12). Review hardened the new parser to fail loud (`ValueError`) on out-of-shape input rather than degrade silently.

**Files changed:**
- `benchmarks/g0/fault-injection/score_verify_shape.py` — removed `import ast` and `_CHECK_RE`; added `_iter_flow_mappings` (depth/quote/comment-aware, raises on no-`checks:` region or unterminated block); `_parse_check` tol branch now uses `_split_top_level`+`_parse_scalar` with a brace-wrap guard; `_parse_scalar` list branch reuses `_split_top_level`; `_load_case` iterates the new extractor.
- `tests/infc/test_fault_score_parser.py` — new stdlib-`unittest` (in-FreeCAD world) test: single-line, list-expect, abs-tol, substring-safety, malformed-tol-raises, multi-line, nested-brace, real-fixture value assertion, inline-comment-brace, no-checks-raises, unterminated-raises.

**Review findings:** 5 patches applied (4 medium, 1 low) — all closing the same silent-degradation posture (comment-brace phantom check, malformed-tol slice, brace underflow, anchor-miss whole-doc fallback, naive list split). 3 rejected (out of fixed-shape contract or pre-existing). 0 intent_gap, 0 bad_spec, 0 deferred.

**Verification performed:**
- Old-vs-new parser output compared across all 12 committed fixtures: **0 mismatches** (scoring provably unchanged).
- All 11 parser test bodies executed standalone against the extracted pure helpers: **pass**.
- `ruff check` both files: clean. Syntax check both files: clean. Forbidden-token grep (`_CHECK_RE`/`.replace("rel"`/`ast.literal_eval`/`import ast`): empty.

**Residual risk / unverified:** `FreeCADCmd` is not on PATH in this environment, so `FreeCADCmd tests/run_tests.py` (the real `scorer.score()` run against the `.FCStd` fixtures + the new test under FreeCAD) was **not executed here**. The scoring path is unaffected because the parser's output is byte-identical to the previous parser on every committed fixture; the new tests exercise only pure string helpers. CI's in-FreeCAD leg is the authoritative gate for the live run.
