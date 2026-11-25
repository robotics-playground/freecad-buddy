# Story 13-14: red team report

Diff: `28586faa...9a9a3e7b` (branch `story/13-14-verify-shape-schema`). Own worktree at `9a9a3e7b`, removed after the run. Quality bar: `quality-bar-13-14.md`. Ledger items are not re-reported.

Scratch scripts: `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\50958ed8-8fcb-4d26-a32d-c7025b2780ae\scratchpad\redteam-13-14\` (`$S` below). Every command ran in the worktree root. freecadcmd ran with `-u`/`-s` private cfg and `FREECAD_USER_HOME=$S\fchome`.

## Reproduced

### RT-1 · medium · Q6 · provenance hash does not cover the moved key tables

The Story moves the per-fn key tables from `usecases/assertions.py` into `src/freecad_buddy/contracts/assertions.py:39` (`CHECK_OPTIONAL_KEYS`) and `:57` (`CHECK_REQUIRED_KEYS`). `validate_check` and `_validate_shape_check` decide accept/refuse from these tables. No validator source list hashes `contracts/assertions.py`:

- `benchmarks/runner.py:103` `_VALIDATOR_SOURCES` (`verify_shape` :104, `assertions` :129, `spec_assertions` :149)
- `benchmarks/g0/fault-injection/score_verify_shape.py:50`
- `benchmarks/g2/fault-injection/score_g2_infc.py:82`, `score_g2_validators.py:39`
- `benchmarks/g3/fault-injection/score_g3_replay.py:72`

Result: an edit to the tables changes what the validators accept, but `validator_sha` stays CURRENT. Before this diff, the same edit was in `usecases/assertions.py`, which every list hashes. The diff opened this gap.

Reproduction (scratch copy of `src/` and `benchmarks/`, heldout excluded; product files in the worktree not touched):
```
uv run --extra dev python $S/sources.py
uv run --extra dev python $S/hashprobe.py $S/copy
sed -i 's/"expect_volume": frozenset({"tol"}),/"expect_volume": frozenset(),/' $S/copy/src/freecad_buddy/contracts/assertions.py
uv run --extra dev python $S/hashprobe.py $S/copy
```
Output:
```
verify_shape hashes contracts/assertions.py: False [...usecases\verify.py, ...usecases\fingerprint.py, ...usecases\assertions.py, ...contracts\numbers.py]
assertions hashes contracts/assertions.py: False [...]
spec_assertions hashes contracts/assertions.py: False [...]
{'verify_shape': 'd696390f60bb', 'assertions': 'ba3b206046ae', 'spec_assertions': '4433db5216cc'} | check accepted
{'verify_shape': 'd696390f60bb', 'assertions': 'ba3b206046ae', 'spec_assertions': '4433db5216cc'} | check refused: expect_volume does not take ['tol']
```
Same hashes, different verdict on `{"fn":"expect_volume","expect":6000.0,"tol":{"rel":0.001}}`. Fix: add `contracts/assertions.py` to the five lists, then re-run the scorers.

### RT-2 · medium · Q5/Q7 · UAT TC-07-01 and TC-09-10 expect use-case refusals that the schema now takes first

The new `oneOf` refuses these checks at the MCP gate (`Input validation error: ...`, `isError` true, `structuredContent` null). The handler never runs. The Story updated TC-12 only. Stale steps:

- `tests/uat/scenarios/tc-07-01.json:182-190` (scripted runner): step `unknown_fn` asserts `status == INVALID_INPUT` and `detail.message == "unknown assertion fn: 'expect_genus'"`. `tests/uat/runner/mcp_client.py:29-32` turns a schema refusal into `{"text":..., "is_error": true}`, so `status` is absent and the step FAILs.
- `tests/uat/testcases/TC-07-verification-and-export-pairing.md:69`: same expectation.
- `tests/uat/testcases/TC-09-error-contract-and-fault-injection.md:421` still says the items are `{type: object}` (`hosts/tool_catalog.py:1313`). Lines 438, 440 and 441 expect the nested `fn` and the nested `tol` to reach the handler with an envelope. Line 439 expects the text `'expect_volume' is not of type 'object'`.

Reproduction (real `build_server` + real `verify_shape` inputSchema, stub handler that records dispatch):
```
uv run --extra dev python $S/mcp_path.py $S/audit.jsonl
```
Output:
```
TC-07-01 unknown fn: reached_handler=False isError=True structuredContent=None text="Input validation error: {'fn': 'expect_genus', 'expect': 0} is not valid under any of the given schemas"
TC-09-10 nested fn: reached_handler=False isError=True structuredContent=None text="Input validation error: {'fn': {'a': {'a': ...}}} is not valid under any of the given schemas"
TC-09-10 nested tol: reached_handler=False isError=True structuredContent=None text="Input validation error: {'fn': 'expect_volume', 'expect': 6000, 'tol': {'rel': {'deep': {'deeper': 0.001}}}} is not valid under any of the given schemas"
TC-09-10 non-object: reached_handler=False isError=True structuredContent=None text="Input validation error: 'expect_volume' is not valid under any of the given schemas"
```
The refusal is correct T-7 behavior. The defect is the test suite: one scripted scenario now fails, and the manual case asserts behavior that no longer exists. Corpus sweep (`$S/corpus.py`) found `tc-07-01.json` as the only stored `verify_shape` check refused outside G2's own sketch vocabulary.

### RT-3 · low · Q5 (AD-28) · `expect_solid_count` `expect: 1.0` was accepted before, now refused after the schema accepts it

Base `usecases/verify.py:144` did `expected = int(expect)`. Head `src/freecad_buddy/usecases/verify.py:182` requires `isinstance(expect, int)`. JSON Schema 2020-12 `"type": "integer"` accepts `1.0`, so the call passes the MCP gate and the use case refuses it. A client that sends `1.0` (Python `json.dumps(1.0)`) got OK before and gets `INVALID_INPUT` now. The ledger rejected the `count_cylindrical_holes` case of this class, but that fn already refused floats on base. This fn did not.
```
uv run --extra dev python -c "<schema validate + verify._validate_shape_check on json.loads('{\"fn\":\"expect_solid_count\",\"expect\":1.0}')>"
```
```
schema: accepted
use case: ValidationError expect_solid_count.expect has the wrong shape: 1.0
base use case: int(1.0) = 1 (base verify.py:144 expected = int(expect))
```

### RT-4 · low · Q8 · the schema gate hides the use case's specific messages, and `items.description` does not show which keys are required

This is narrower than the ledger's "oneOf text unreadable" item. The agent now sees only the generic text for checks that used to get a specific message: `select: "Face3"` used to get the AD-13 hint (`sub-element index selector 'Face3' is banned (AD-13); use a geometric query`), and a missing direction used to get `expect_extent needs 'direction'`. The description that replaces those messages does not mark a required key. It also lists `select` together with `select_a`/`select_b` for `hole_spacing`, but the schema refuses that combination.
```
uv run --extra dev python $S/errtext.py
```
```
{"fn": "expect_extent", "expect": 10} -> Input validation error: {...} is not valid under any of the given schemas
{"fn": "hole_diameter", "expect": 5, "select": "Face3"} -> Input validation error: {...} is not valid under any of the given schemas
```
Description: `... expect_extent {expect, direction, tol}; ... hole_spacing {expect, pattern, select, select_a, select_b, tol} ...`.

## Not reproduced (checked, no defect)

- **Schema vs use case (Q2/Q3).** `$S/fuzz.py` mutates every key of all 14 fns over 45 values plus absent keys: 5128 checks. Only 6 disagreements came out, all in the known int/float class (`2.0`, `-0.0`, `1e308` for `count_cylindrical_holes`/`expect_solid_count`). That class is in the ledger, plus RT-3. No disagreement on null, tol forms, select forms, zero vectors, extra keys or the `hole_spacing` pair/pitch forms.
- **Object rule (Q4).** `$S/objrule.py` under freecadcmd 1.1.4, on 13 document types. Box only, Box + empty sketch, Box + Sheet + VarSet, Box + LCS: the tool measures Box. Body+Sketch+Pad: refused, 3 names. Compound of two boxes: refused, 3. Body in App::Part: refused, 4. Mesh only: earlier error. Origin features in 1.1.4 are `App::Line`/`App::Plane`/`App::Point`, so the exclusion holds, LCS children included. Two refusals are safe but stricter than the doc text suggests: `App::Part` holding one Box counts as 2 (the `App::Part` has a Shape), and `Part::DatumPlane` counts as a shape object. An empty Body + loose sketch measures the sketch, which the ledger rejected as edge.
- **Previously valid calls (Q5).** `$S/corpus.py` checks the stored check lists in `benchmarks/`, `tests/` and `skills/` (heldout not opened): 254 checks, 74 files, all accepted except G2's harness-only sketch fns and RT-2. Every `verify_shape` step in `tests/uat/scenarios/*.json` passes `object`, except two: tc-02-15 uses a fake handle and tc-09-03 has no doc. Both are intended refusals. `run_mcp_e2e.py:210`, `run_mcp_edge_cases.py:210`, `score_verify_shape.py:216` and `score_g3_replay.py:259` pass `object`. Internal callers `features.py:318` and `transaction.py:270` pass `object`.
- **Honest refresh (Q6).** I re-ran `score_verify_shape.py` and `score_g2_infc.py` on base and on head. The per-case tables are identical. Rates: verify_shape 11/11 detected, 0/1 false alarm. G2 rates are identical too. The head run reproduces the committed `validators.yaml` exactly, except line endings. `score_g2_infc` exits 1 with `BARS NOT MET` on base too, so R1-P1 is pre-existing. The diff changes no `case.yaml` or expectation (only `validators.yaml` under `benchmarks/`). `$S/currency.py`: every changed `validator_sha` is CURRENT. The STALE set (`verify_export_stl`/`3mf`, `verify_render_tone`) is the same on base. `score_g3_replay` was not re-run: it needs a Python 3.11 venv with `mcp`. Its hash is CURRENT.
- **AD-1 (Q5).** `check_imports OK`. `contracts/assertions.py` adds only `frozenset`/`dict` literals.
- **gen_schemas (Q1).** `gen_schemas --check OK`. Note: `gen_schemas.py` does not emit tool input schemas. The `oneOf` is built at import time in `hosts/tool_catalog.py`, so the quality bar's "checked by gen_schemas" for Q1 checks nothing. The schema test covers Q1.
- **Envelope path.** `detail.objects` is allowed by `result-envelope.schema.json` `ErrorDetail`. `MethodRegistry._invoke` passes the returned envelope through unchanged.
- **Gates at head.** `pytest tests/external`: 1971 passed, 4 skipped. In a `-x` run, `test_mcp_cache_proxy.py::test_should_answer_both_calls_when_two_parallel_calls_meet_a_lost_session` failed once. It passed alone and in the full re-run, so it is unstable and not related to this diff. infc `run_tests.py`: 960 tests, OK (skipped=1).

## Verdict

**FAIL.** No high finding. There are two open medium findings: RT-1 (provenance gap created by this diff) and RT-2 (scripted UAT scenario tc-07-01 now fails; TC-07-01 and TC-09-10 describe behavior the schema removed). Close both and the Story passes on this red team's evidence.
