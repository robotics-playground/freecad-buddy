# Story 13-9 verification: VarSet parameters and `query_parameters`

Verifier: verifier-13-9 (claude-opus-5-5). Date: 2026-11-24.
Artifact: commit `feac4bfd` on `story/13-9-varset-parameters`, base `28586faa`.
Copies: detached worktree `fcb-verify-13-9` at `feac4bfd` (gates, mutants, container build), second worktree `fcb-verify-13-9-base` at `28586faa` (envelope comparison). Both removed after the run.
Evidence: `tests/uat/run/13-9-r1/` in the main repo (`evidence/`, `scripts/`).

## Verdict

**PASS.** Q1..Q8 hold. All gates pass. Six of six named mutants turn a named test red. The CAP-2 live run in the `fcb-desktop` container passes: a VarSet drives a sketch constraint, a pad length and an attachment offset; an edit changes the geometry and shows it in `mutation.changed`; one `document_undo` restores the VarSet values and the geometry, with the fingerprint equal to the pre-edit digest. No product defect found. Three notes below (N1..N3), none blocks.

## Gates (copy at `feac4bfd`)

| Command | Result |
| --- | --- |
| `uv run --extra dev ruff check .` | All checks passed |
| `uv run --extra dev python scripts/check_imports.py` | OK |
| `uv run --extra dev python scripts/check_status_vocab.py` | OK |
| `uv run --extra dev python scripts/gen_schemas.py --check` | OK |
| `uv run --extra dev python scripts/check_skill_shape.py` | exit 0 |
| `uv run --extra dev python scripts/check_provenance.py` | OK |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | 1870 passed, 6 skipped, 1 failed (see N1) |
| `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py`, `FREECAD_USER_HOME=<tmp>` | Ran 995, OK (skipped=1), exit 0 |

Source check: a probe under the same `freecadcmd` setup printed `PKG D:\Work\Personal\Sources\fcb-verify-13-9\src\freecad_buddy\__init__.py`, so the infc suite ran the copy's `src`, not the installed addon. Every mutant run printed the same path.

Base external run (`28586faa`): 1866 passed, 4 skipped, 0 failed.

**N1 (pre-existing unstable test, not this Story).** `tests/external/test_mcp_cache_proxy.py::test_should_answer_both_calls_when_two_parallel_calls_meet_a_lost_session` failed once in the full head run. Alone on head: 2 pass, 1 fail of 3. Alone on base `28586faa`: 3 pass, 1 fail of 4. The Story does not touch `scripts/` or that test. It is a timing-dependent test that fails on the base too; record it beside the known unstable test in the Environment block.

## Other tools unchanged (`run_mutation` `state_probe`, `rpc_dispatch` `exc.code`)

1. Full suites: infc 995 OK and external green except N1, on head.
2. Envelope comparison. `scripts/envdiff.py` builds the production catalog (`tool_catalog.build_inline_handlers`, auto-approve on), builds a fully constrained rectangle sketch, and sends 13 calls through `MethodRegistry.dispatch` on both copies: `feature_pad` (OK), `feature_set_parameters` (OK, and refused), `feature_pad` negative length, `feature_fillet` bad edge, `query_object` unknown, `query_tree_summary`, `query_parameters`, `document_undo` (OK), `query_mass_properties`, `script_exec` raising `ValueError`, unknown tool, `feature_parameters_define` name `W`. Timing, session, path and traceback keys masked; doc handles normalized. Result: the 11 calls to existing tools are identical byte for byte, mutation blocks and fingerprint digests included. Only the two new tools differ (unknown method on base; OK and `parameters.unit_symbol_name` on head). Evidence: `evidence/env-base.json`, `evidence/env-head.json`.
3. `exc.code` reach. In `src/`, only `ParameterRefusal` (`features.py:1899`) sets `code`. Probe under FreeCAD 1.1.4: `Base.FreeCADError`, `ValueError`, `RuntimeError`, `TypeError`, `AttributeError` and the real exceptions from `getObject(...)` on a missing name, `addObject("Bogus::Type")` and `openDocument` of a missing path carry no `code` attribute. `src/` uses no `xml.etree`/`expat`/`urllib` (whose errors carry an integer `code`). So no existing error changes its `detail.code`.

## Mutants

Driver: `scripts/mutants.py` (exact-string patch, run `infc.test_feature_parameters` + `infc.test_query_tools.QueryParametersTest` = 42 tests under `freecadcmd`, plus `tests/external/test_parameters_contract.py` and `test_mcp_surface.py`, then restore). Unmutated baseline: 42 run, 0 fail. `src` clean after the run. Raw: `evidence/mutants.txt`.

| Mutant | Change | Red tests (named) |
| --- | --- | --- |
| a | `transaction._prove_rollback.state_restored` returns `True` (no state comparison) | `RollbackTest.test_Should_restore_from_the_snapshot_When_the_abort_leaves_the_varset_changed`, `RollbackTest.test_Should_not_prove_the_rollback_When_the_snapshot_restore_leaves_the_varset_changed` |
| b | drop `W` from `_EXPRESSION_RESERVED_NAMES` | `DefineTest.test_Should_refuse_with_the_unit_symbol_code_When_a_name_is_a_lexer_unit_or_constant` (symbol `W`), external `test_Should_cover_every_symbol_the_skill_names_When_the_skill_lists_unit_symbols` |
| b2 | drop `kWh` (a symbol in no test list), with `Expression.l` copied into the copy | external `test_Should_list_every_ascii_unit_and_constant_of_the_lexer_When_checking_reserved_names` |
| c | remove `if millimetres < 0` | `DefineTest.test_Should_refuse_naming_the_parameter_When_a_field_is_malformed` subtest `negative length` |
| d | `document.recompute()` at the start of `query_parameters.read` | `QueryParametersTest.test_Should_leave_the_document_untouched_When_read` |
| e | the three `< _MAX_PARAMETER_ROWS` checks made `True` | `test_Should_cut_a_list_at_500_rows_and_say_so_When_a_varset_holds_more`, `test_Should_cut_the_spreadsheet_and_binding_lists_at_500_rows_When_a_document_holds_more` |
| f | `rpc_dispatch._error_envelope` sets `"code": status` | 37 subtests: every coded refusal test (`unit_symbol`, `reserved`, `type_conflict`, `not_a_varset`, `duplicate`, `bound`) |

**N2 (test isolation, low).** In b and c, more subtests turn red than the mutant explains (b: all 22 unit-symbol subtests; c: 12 of 17 malformed subtests). Cause: subtests share one document; once a mutant lets one write through, the VarSet `Params` exists and `assertIsNone(self.varset())` fails in each later subtest. The first red subtest is the correct one; the rest are a cascade. Not a defect in the product. A fresh fixture per subtest would make the red set exact.

**N3 (gate coverage, low).** The lexer-list external tests skip when the `docs/references/FreeCAD` submodule is not checked out (it is not in a fresh worktree, so they skipped in the gate run). Mutant b2 (`kWh` dropped) is caught only when the submodule is present; without it, no infc test fails, because the infc parser test checks only that listed names fail to parse (extras), not that every lexer symbol is listed. The builder logged this as triage row 24; the residual gap is a missing symbol in a checkout without the submodule.

## Acceptance map

| Item | Evidence | Result |
| --- | --- | --- |
| Q1 create/add/update, output `varset`, `added`, `updated` on OK | infc `DefineTest` create/update/mixed; live `define` added `[width, height, shift]`, `edit` updated the three | PASS |
| Q2 rollback proven by property read-back (decision 32) | infc `RollbackTest` 4 tests; mutant a red | PASS |
| Q3 coded refusals before the bracket, lexer list test, no-VarSet build | infc refusal tests assert `detail.code`, message and 0 snapshots minted; external lexer tests (with submodule); mutants b, b2, f red; live `W` → `parameters.unit_symbol_name`, float on length → `parameters.type_conflict`, `Pad` → `parameters.not_a_varset` over MCP | PASS (N3) |
| Q4 value types, integer bound, no silent clamp | infc malformed and limits tests; mutant c red; live `-1 mm` → `INVALID_INPUT` "must not be negative" | PASS |
| Q5 `document_undo` reverts one call; `preview_dry_run` reaches it | infc undo tests and preview-table test; live undo `matches_pre_op: true` | PASS |
| Q6 `query_parameters` reads VarSet, aliased cells, bindings; cap 500; null + reason; no recompute; read-only profile | infc `QueryParametersTest` 15 tests; mutants d, e red; external profile test; live query lists 3 rows and 3 bindings | PASS |
| Q7 VarSet change that drives geometry appears in `changed` | infc pad-bound test; live `edit.mutation.changed` = Body, Pad, Profile | PASS |
| Q8 design doc rows, schemas, counts; skill line 41; AD-1; AD-28 | design diff read: `query_` 11 shipped, `feature_` 12, `tool_specs()` 49 (live `list_tools` = 50 with `script_exec`); `check_imports` OK; tools new, so additive | PASS |
| Spec AC1 lexer name refused, every lexer ASCII symbol listed | as Q3 | PASS |
| Spec AC2 Box/feature takes the bound VarSet value | infc; live pad length follows `Params.height` | PASS |
| Spec AC3 gates pass | table above | PASS (N1 pre-existing) |
| Decision 33 deviations | `bound_by_expression`, length ≥ 0, angle ±360, reserved attribute/pseudo names, `state_probe`, `exc.code`: each seen in code and tests | as accepted |

## CAP-2 live run (container `fcb-desktop`)

Build from the copy: `uv run python scripts/build_addon.py --release`, `docker compose -f tests/close-loop/docker/compose.yaml up -d --build`, `docker exec -u cua fcb-desktop fcb-freecad start` (first start ran before the desktop session; second start OK). `healthz`: `freecad_pid` 617. `list_tools` over MCP: 50 tools, both new tools present. Client: `scripts/cap2b_live.py` over `http://127.0.0.1:18765/mcp`. Transcript: `evidence/cap2d-transcript.json`, summary `evidence/cap2d-summary.txt`.

Steps, all typed tools except one:

1. `document_create` `CAP2d_VarSet`; `feature_parameters_define` `Params` width 20 mm, height 10 mm, shift 5 mm (group `Placement`) → OK, added 3.
2. `feature_body_create`; `feature_datum` plane `Lift` on `XY_Plane` (`ObjectXY`); `sketch_create` `Profile` on `Lift` `Face1`; `sketch_add_geometry` rectangle 20 x 8 with named DistanceX `width`; `feature_pad` 10 mm → OK.
3. **`script_exec`, used ONLY for the expression binding** (`feature_set_expression` is Story 13-10, not built): `Profile.Constraints.width = Params.width`, `Pad.Length = Params.height`, `Profile.AttachmentOffset.Base.x = Params.shift`.
4. `query_parameters`: 3 VarSet rows (`height 10 mm`, `shift 5 mm`, `width 20 mm`), 3 bindings, `truncated` false. `query_mass_properties Pad`: volume 1600 mm³, bbox x 5..25, y 0..8, z 0..10.
5. `feature_parameters_define` width 30, height 15, shift 8 → OK, `updated` [width, height, shift]; `mutation.changed` Body, Pad (volume 3600, com [23, 4, 7.5]) and Profile; `post_verify.passed` true; `tnp_audit` CLEAN; `touched` [Params]; fingerprint `b48d7205…` → `0fcf115c…`.
6. `query_parameters`: 30 / 15 / 8. Mass: volume 3600 = 30 x 8 x 15; bbox x 8..38, z 0..15. The constraint, the pad length and the attachment offset all followed the VarSet.
7. `document_undo` once with `expect_fingerprint` = the edit's `fingerprint_before`: `undone` "buddy: define parameters on Params", `fingerprint_after` `b48d7205…` (equal to pre-edit), `matches_pre_op` true, `errors` []. `query_parameters` back to 20 / 10 / 5; mass back to 1600 mm³, bbox x 5..25, z 0..10.
8. Refusals over MCP, each `INVALID_INPUT` with `detail.code`: `W` → `parameters.unit_symbol_name`; `width` as float → `parameters.type_conflict`; `-1 mm` → no code, "must not be negative"; `varset: Pad` → `parameters.not_a_varset`. `query_parameters` after them: unchanged 20 / 10 / 5.

Visual check: `evidence/freecad-after-undo.png` (pad 20 x 8 x 10 beside the datum plane; tree shows `Params` and `Body`) and `evidence/freecad-after-edit.png` (the same view after a second edit to 30/15/8: longer, taller box, shifted along X past the datum plane), both from `cua-driver get_window_state` on the FreeCAD window. That second edit was undone (`evidence/visual-undo.json`: `matches_pre_op` true). `addon.log`: no `ERROR` or `Traceback` lines (`evidence/addon-log-errors.txt`).

Earlier attempt `CAP2_VarSet` (`evidence/cap2-transcript.json`): sketch on the base XY plane is unattached (`MapMode` `Deactivated`), so its `AttachmentOffset` had no effect on the geometry. That is a fixture choice, not a product defect; the run above attaches the sketch to a datum. Two other attempts failed on selector syntax before any parameter call (`geometric` selectors and a `mapped_name` selector without `mapped_name` are refused by `feature_datum`/`sketch_create`, as designed).

Teardown: `fcb-freecad stop` (window close timed out, process killed by the helper), `docker compose ... down`; no `fcb-desktop` container left. Port 8765 and `%APPDATA%\FreeCAD\v1-1\user.cfg` not touched.

## Product defects

None found.
