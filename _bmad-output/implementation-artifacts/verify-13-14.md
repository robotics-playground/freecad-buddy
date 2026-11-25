# Story 13-14 verification: typed `verify_shape` check schema

Verifier: verifier-13-14. Date: 2026-11-24.
Artifact: commit `9a9a3e7b` (branch `story/13-14-verify-shape-schema`), base `28586faa`.
Copies: head detached worktree `fcb-verify-13-14` at `9a9a3e7b`; base detached worktree `fcb-verify-13-14-base` at `28586faa`. Both removed at the end.
Evidence: `tests/uat/run/13-14-r1/evidence/` in the main repo path.

## Verdict

**PASS with one finding (medium, test-case drift).** Code meets Q1-Q8. Two UAT test cases still expect the old behavior: TC-07-01 (one assertion) and TC-09-10 (four assertions). Each now fails when run. The product refuses the same inputs, but at the schema gate, not in the handler. See F1.

## Gates (head copy)

| Command | Result |
| --- | --- |
| `uv run --extra dev ruff check .` | All checks passed |
| `uv run --extra dev ruff format --check` on the 7 changed `.py` files | 7 files already formatted |
| `uv run --extra dev python scripts/check_imports.py` | `check_imports OK` |
| `uv run --extra dev python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `uv run --extra dev python scripts/check_provenance.py` | `check_provenance OK` |
| `uv run --extra dev python scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `uv run --extra dev python scripts/check_skill_shape.py` | exit 0 |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | 1 failed, 1970 passed, 4 skipped |
| failed test alone: `test_headless_two_process.py::test_should_time_out_within_a_second_of_the_budget_when_a_body_holds_the_gil` | 1 passed. It is a timing test. The full run shared the CPU with the freecadcmd scorers and the infc suite. |
| infc suite: `freecadcmd -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py`, `FREECAD_USER_HOME` = temp folder | `Ran 960 tests`, `OK (skipped=1)` |

Copy check: a probe under freecadcmd with the same environment imported `D:\Work\Personal\Sources\fcb-verify-13-14\src\freecad_buddy\usecases\verify.py`, and `_default_object` was present. The developer junction was not loaded.

Note: a first infc run reported 1 failure and 6 errors in `test_g0_import_safety`, `test_fault_score*` and `test_g2_planted_ops`. The cause was my shell: it still set `FREECAD_BUDDY_RUN_FAULT_SCORER=1` from the scorer runs. The rerun without that variable is the result above.

## R1-P1: scorers on base and head

Each scorer ran on both copies with the same environment: host freecadcmd, private cfg, `FREECAD_USER_HOME` = temp folder. `score_g3_replay.py --leg 1.1.x` ran under a Python 3.11.14 venv with `mcp`, `pyyaml`, `trimesh` and `lib3mf`, with FreeCAD `bin` on `PYTHONPATH` and `PATH`.

| Scorer | Base `28586faa` | Head `9a9a3e7b` | Per-case table base vs head |
| --- | --- | --- | --- |
| `g2/fault-injection/score_g2_infc.py` | exit 1, `BARS NOT MET` | exit 1, `BARS NOT MET` | identical, 34 lines; only the `wrote <path>` line differs |
| `g0/fault-injection/score_verify_shape.py` | exit 0, planted=11 detected=11, controls=1 flagged=0 | same | identical |
| `g3/fault-injection/score_g3_replay.py` | exit 0, planted=10 detected=10, controls=14 flagged=0 | same | identical |

`BARS NOT MET` is present on the base and it is the same on the head. Its cause is the three validators the scorer reports as `NOT SCORED`: `fingerprint` ("no fault case targets this validator"), `verify_sketch` (same reason), and `run_mutation` (2 planted cases not driveable on FreeCAD 1.1.x). The scored validators: `assertions` 8/8, false alarm 0; `audit_references` 3/3, false alarm 0. Values are the same on base and head.

Hash reproduction:
- Base: after the scorers, `validators.yaml` differs from the base commit only in `run_id` and `date`. Every `validator_sha` reproduced. So the method is sound.
- Head: after the scorers, `validators.yaml` has no content difference from the commit (`git diff --ignore-cr-at-eol` is empty). The four `validator_sha` values the builder changed (`verify_shape`, `assertions`, `verify_sketch`, `spec_assertions`) come from the scorers, not from a hand edit.
- No sensitivity, false alarm or Wilson value changed. `spec_assertions` `run_id` `g3r-2026-11-24-1.1.x` is the scorer default, `g3r-<date>-<leg>`.

R1-P1: **close**.

## Mutants

Each mutant was applied to the head copy, tested, then reverted with `git checkout -- src`. A clean rerun of `tests.infc.test_verify_tools` gave 63 ran, 0 fail.

| Id | Mutation | Red tests |
| --- | --- | --- |
| (a) | `tool_catalog.py`: drop `expect_volume` from the `oneOf` comprehension | `test_Should_accept_the_minimal_check_When_the_fn_is_in_the_vocabulary[expect_volume]`, `test_Should_agree_with_the_use_case_When_a_table_key_is_given[expect_volume-tol]`, `test_Should_accept_the_check_in_both_schema_and_use_case_When_it_is_valid[check3]`, `test_Should_accept_every_stored_benchmark_check_When_validated_against_the_schema` (4 failed) |
| (b) | `tool_catalog.py` `_check_branch`: `required` without `direction` | `test_Should_reject_the_check_When_a_required_key_is_missing[expect_extent-direction]`, `test_Should_agree_with_the_use_case_When_a_required_key_is_missing[expect_extent-direction]` |
| (b2) | `contracts/assertions.py`: delete the `expect_extent` row from `CHECK_REQUIRED_KEYS` | `test_Should_agree_with_the_use_case_When_a_table_key_is_given[expect_extent-tol]`. The required-key tests lose their parameter, but the agreement test catches the change. |
| (c) | `verify.py` `read_shape`: `obj = list(document.Objects)[0]` (old "omit = first object") | infc: `..._on_three_shapes` FAIL; `..._on_twelve_shapes`, `..._measure_the_only_shape_object...`, `..._body_with_a_sketch_and_a_pad` ERROR |
| (d) | `verify.py` `_default_object`: drop the `_ORIGIN_TYPE_IDS` filter | infc: `test_should_refuse_when_object_is_omitted_on_a_body_with_a_sketch_and_a_pad`, `test_should_keep_the_earlier_error_when_object_is_omitted_on_an_empty_body` |
| (e) | `tool_catalog.py`: the `is_valid_solid` branch without `required` and without `additionalProperties: false` | `test_Should_reject_the_check_When_it_is_not_a_closed_vocabulary_check[check0]` (the `{"type": "is_valid_solid"}` case) plus `[check2]`, `[check3]`, `test_Should_reject_a_key_the_fn_does_not_take...[is_valid_solid]`, `test_Should_agree_with_the_use_case_When_a_key_outside_the_table_is_given[is_valid_solid]` |

All mutants were killed.

## Quality bar

| Q | Result | Proof |
| --- | --- | --- |
| Q1 | PASS | Live `tools/list`: `checks.items.oneOf` has 15 branches (14 fns; `hole_spacing` has 2). `{"type":"is_valid_solid"}` and `expect_genus` are refused live. Mutants (a) and (e). |
| Q2 | PASS | Per-fn accept and reject tests. Required keys enforced: mutants (b) and (b2); live `{"fn":"expect_extent","expect":5}` refused. |
| Q3 | PASS | Agreement tests walk `CHECK_OPTIONAL_KEYS` and `CHECK_REQUIRED_KEYS` against `validate_check`. Mutant (b2) is caught only by these tests. The value rules are still written twice (R1-D1, deferred). |
| Q4 | PASS | infc tests for 1, 3 and 12 objects, Body+Sketch+Pad, empty Body, and no-shape documents. Live L2 below. Mutants (c) and (d). |
| Q5 | PASS for code; see F1 | `check_imports OK`. Stored G0 and G3 checks validate (corpus test). TC-07 and TC-09 inputs that the old schema admitted are now refused at the schema gate. These are T-7 cases (unknown or malformed check), but two UAT test cases were not updated. |
| Q6 | PASS | `check_provenance OK`. Hashes reproduced by the scorers on both copies (R1-P1). |
| Q7 | PASS | `mcp-tools-design.md` §3.3 replaces the "omit = the document's first object" line and adds "Check schema" and "Object resolution". `verification-design.md` §5 adds the subject rule. Both match the code: first 10 candidates then `+K more`, origin types excluded, `detail.objects`. Nit: the §3.3 sentence "`detail.code = verify_shape.object_required` the message ..." is missing "and". |
| Q8 | PASS, with a limit | See "Live results". The client gets `isError: true` and one text block: `Input validation error: {'type': 'is_valid_solid'} is not valid under any of the given schemas`. It quotes the rejected check, so the caller can find it. It does not say which key is wrong. The fix is in the tool description and in `items.description`: the description lists the keys of each fn, and the tool text says "Each check is {fn, expect, ...} with only the keys its fn takes". This is readable enough for an agent to correct the call. R1-D2 stays deferred. |

## Acceptance criteria (story spec)

| AC | Result |
| --- | --- |
| `{"type":"is_valid_solid"}` fails the schema; a valid check of each of the 14 fns passes | PASS: schema tests, mutants (a) and (e), live L1 |
| Omitted `object` on 2+ shape-bearing objects returns `INVALID_INPUT` naming the count | PASS: infc tests, live L2 (`document has 3 shape objects`) |
| `contracts/` has no non-stdlib import | PASS: `check_imports OK`; the diff adds only frozensets and dicts |

## Live results (container `fcb-desktop`, FreeCAD 1.1.4, addon built from the head copy)

The setup used the head copy: `build_addon.py --release`, then `docker compose ... up -d --build`, then `fcb-freecad start`. `/healthz` returned `freecad_pid: 711`. A raw MCP client (`mcp` SDK, streamable HTTP to `http://127.0.0.1:18765/mcp`) recorded the exact results in `evidence/live-mcp-transcript.json`.

| Call | Received |
| --- | --- |
| L1 `verify_shape {doc, checks:[{"type":"is_valid_solid"}]}` | `isError: true`, no `structuredContent`, text `Input validation error: {'type': 'is_valid_solid'} is not valid under any of the given schemas` |
| L1b `checks:[{"fn":"expect_extent","expect":5}]` | `isError: true`, text `Input validation error: {'fn': 'expect_extent', 'expect': 5} is not valid under any of the given schemas` |
| L2 `verify_shape {doc}` on Body+Sketch+Pad (built with typed tools, rectangle 20 x 10, pad 5) | `isError: true`, `status: INVALID_INPUT`, `detail: {code: "verify_shape.object_required", message: "object is required: document has 3 shape objects: Body (Body), Sketch (Sketch), Pad (Pad)", objects: ["Body","Sketch","Pad"]}`, `structured_content: {}` |
| L3 `verify_shape {doc, object:"Pad", checks:[is_valid_solid true, expect_volume 1000 tol abs 0.01, expect_extent 5 dir [0,0,1], expect_solid_count 1]}` | `status: OK`, `verdict: OK`. All 4 checks passed. Measured volume 1000.0, extent 5.0, solids 1. |

The same L1 and L2 calls through this session's `mcp__freecad-buddy-docker__verify_shape` tool returned the same text. Environment note, not a product defect: the cache proxy still served the old `checks.items: {type: object}` schema to this Claude Code session. So the session client did not validate the input, and the server refused it. A client that connected before a rebuild sees a stale schema until it reconnects.

Screenshot `evidence/gui-body-sketch-pad.png`, after `view_fit_viewport`: the Model tree shows `V1314 > Body`, and the 3D view shows one closed box. Its edges read as roughly 20 : 10 : 5. `addon.log` has 0 `ERROR` or `Traceback` lines. The document was closed, then FreeCAD was stopped and the stack taken down with `docker compose ... down`.

## Findings

### F1 (medium, test-case drift; not a product defect): UAT cases still expect handler refusals

The new per-fn schema refuses these inputs at the schema gate. The cases still expect a handler envelope. Live proof: `evidence/live-mcp-stale-uat-cases.json`. Each call returns `isError: true`, no `structuredContent`, and text `... is not valid under any of the given schemas`.

- `tests/uat/testcases/TC-07-verification-and-export-pairing.md:69`: "an unknown assertion `fn` is refused — verify: ... `[{ fn: "expect_genus", expect: 0 }]` returns `INVALID_INPUT` with message `unknown assertion fn: 'expect_genus'`". Received: schema rejection, no envelope.
- `tests/uat/testcases/TC-09-error-contract-and-fault-injection.md:415-441` (TC-09-10):
  - The Given (line 420) says items are `{type: object}` and cites `hosts/tool_catalog.py:1313`.
  - "the deeply nested `fn` is refused by the handler, not the schema" — it is now refused by the schema.
  - "a non-object check ... whose text names `'expect_volume' is not of type 'object'`" — the text is now `'expect_volume' is not valid under any of the given schemas`.
  - "nested-`tol` call returns ... `INVALID_INPUT` ... `expect_volume.tol.rel must be a non-negative number`" — it is now a schema rejection.
  - "the two object items reach the handler" — they no longer reach it.

Reproduction: start the container from `9a9a3e7b` and send the four inputs to `verify_shape`. Any handle works, because the schema runs before dispatch. A UAT gate run of TC-07-01 or TC-09-10 grades FAIL on these lines. The builder updated TC-12 but did not update these two cases. The safety intent still holds: each input is refused and the server keeps running. I did not edit the files.

### Accepted, no action

- R1-D1 and R1-D2 stay deferred, as recorded.
- §3.3 grammar nit (Q7 row).
- The external-suite timing test failed under load and passed alone. It is pre-existing and unrelated to this diff.

## Round 2 (head `ec3282c3`)

Scope: triage `triage-13-14-r2.md`, rows RT-1, F1+RT-2, RT-3 and RT-4. Copy: fresh detached worktree `fcb-verify-13-14` at `ec3282c3`, removed at the end. No container was needed: the updated UAT text was checked against the live results captured in round 1.

### Verdict

**PASS.** All four rows are fixed and proven. F1 is closed. No new finding.

### Gates

| Command | Result |
| --- | --- |
| `ruff check .` · `check_imports` · `gen_schemas --check` · `check_provenance` · `check_status_vocab` | All OK |
| `ruff format --check` on the 10 changed `.py` files | 9 formatted. `benchmarks/runner.py` would be reformatted at line 984 (`--exit is only defined ...`). This is outside the diff and is already on base `28586faa`. |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | 1979 passed, 1 failed, 4 skipped. The failure is `test_mcp_cache_proxy.py::test_should_answer_both_calls_when_two_parallel_calls_meet_a_lost_session`. Run alone, the file gives 33 passed, so I take it as unstable, not caused by this change. |
| infc suite (freecadcmd, private cfg, `FREECAD_USER_HOME` temp, scorer flag unset) | `Ran 961 tests`, `OK (skipped=1)`. Round 1 ran 960; the new test is the integral-float test. |

### RT-1: `contracts/assertions.py` hashed

- `contracts/assertions.py` is now in all five lists: `runner.py` (verify_shape, assertions, spec_assertions), `score_verify_shape.py`, `score_g2_infc.py`, `score_g2_validators.py` and `score_g3_replay.py`.
- Committed tree: the runner hash equals the committed `validator_sha` for `verify_shape`, `assertions` and `spec_assertions`. All three are CURRENT.
- Table edit in the copy (`"expect_volume": frozenset({"tol", "direction"})`):
  - The runner hashes change: `verify_shape` d66cbe4222b0 -> 859833a9611d, `assertions` b417250ab76e -> 58c78bcc12df, `spec_assertions` ec64cb67c715 -> 0c643093fa48.
  - All three read STALE.
  - `check_provenance` still says OK. It checks manifests, not hashes. The runner currency check (`check_validator_currency`, leg-b) is the gate that catches the edit.
- Mutant: I removed the 3 new `_SRC / "contracts" / "assertions.py"` lines from `runner.py`. Then `test_Should_change_the_validator_hash_When_the_check_key_tables_are_edited[verify_shape|assertions|spec_assertions]` failed: 3 red.
- Scorer check: `score_verify_shape.py` on the head copy wrote `validators.yaml` with no content difference from the commit. So `verify_shape` d66cbe4222b0 is reproduced, and the scorer list order matches the runner. Result: planted=11 detected=11, controls=1 flagged=0.
- Limit: the new test covers the runner lists only. If a scorer list differed from the runner, the scorer would write a hash that the runner reads as STALE. The leg-b check catches that, so this is acceptable.

### F1 + RT-2: UAT cases (checked against round-1 live results in `tests/uat/run/13-14-r1/evidence/live-mcp-stale-uat-cases.json`)

| Case | New expectation | Round-1 live result | Match |
| --- | --- | --- | --- |
| `TC-07...md:69` | `isError`, `structuredContent` null, text matches `Input validation error: .*expect_genus.* is not valid under any of the given schemas` | `Input validation error: {'fn': 'expect_genus', 'expect': 0} is not valid under any of the given schemas`, no `structuredContent` | yes |
| `scenarios/tc-07-01.json` step `unknown_fn` | `is_error` equals `true`; `text` regex as above | The runner's `mcp_client.to_result` gives `{"text", "is_error"}` for a result with no `structuredContent`. The `regex` operator exists in `run.py` `check_expect`. The live text matches. | yes |
| `TC-09...md` TC-09-10, nested `fn` | text starts `Input validation error:` and ends `is not valid under any of the given schemas` | `Input validation error: {'fn': {'a': ...}} is not valid under any of the given schemas` | yes |
| TC-09-10, non-object item | text starts `Input validation error: 'expect_volume' is not valid under any of the given schemas` | same text | yes |
| TC-09-10, nested `tol` | protocol rejection at the schema gate | `Input validation error: {... 'tol': {'rel': {'deep': ...}}} is not valid under any of the given schemas` | yes |
| TC-09-10, "none of the three reaches the handler" | `isError` set, `structuredContent` null on each | all three: `isError: true`, no `structuredContent` | yes |

- The TC-09-10 Given and Design Ref now cite `mcp-tools-design.md` §3.3 and `_VERIFY_SHAPE_CHECKS_SCHEMA`.
- Search of `tests/uat`, `skills`, `benchmarks`, `scripts` and the design docs: no other `verify_shape` expectation still names `unknown assertion fn`, `tol.rel must be` or `is not of type 'object'`.
- The remaining `is not of type 'object'` matches are for other tools: `tc-03-05` and `tc-03-18` (`sketch_add_geometry` radius) and `tc-08-15` (`feature_pad` confirm). This change does not affect them.

### RT-3: integral float accepted

- Change: `usecases/verify.py` `_validate_shape_check` (`expect_solid_count`) and `usecases/assertions.py` `_validate_expect` (`count_cylindrical_holes`) accept a float with `is_integer()`. The schema's `"integer"` already admits `1.0`.
- Revert mutant: `git apply -R` of the two use-case hunks.
  - `test_Should_accept_an_integral_float_When_the_fn_takes_an_integer[check0]` and `[check1]` fail: 2 red.
  - infc `test_should_measure_the_solid_count_when_expect_is_an_integral_float` errors with `ValidationError: expect_solid_count.expect has the wrong shape: 1.0`.
- `1.5`, `True` and `"1"` are still refused by the schema and by the use case (`test_Should_refuse_a_non_integral_expect_When_the_fn_counts_solids`).

### RT-4: description

Generated `checks.items.description` on the head, with 15 branches:

> {fn, expect, ...}; * marks a required key; a fn takes only the keys listed: angle_between {expect*, select_a*, select_b*, tol}; ... expect_extent {expect*, direction*, tol}; ... hole_spacing {expect*, pattern, select, tol}; hole_spacing {expect*, pattern, select_a*, select_b*, tol}; ... is_valid_solid {expect*}. Select geometry by a query such as {hole: {diameter}} or {face: {normal}}; sub-element names such as Face3 are banned (AD-13).

- Required keys are marked.
- Both `hole_spacing` forms are listed.
- The AD-13 index-selector hint is present.
- `fn` is not starred, but the header `{fn, expect, ...}` names it. This is acceptable.
