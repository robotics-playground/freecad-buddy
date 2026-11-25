# Story 13-14: quality bar

Base: 28586faa. Plan: builder-13-14 plan + `spec-13-14-typed-verify-shape-check-schema.md` (wt-13-14), approved 2026-11-24.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | `verify_shape` `checks.items` is a `oneOf` per `fn`, generated from `contracts/assertions.py` tables; the schema rejects `{"type": "is_valid_solid"}` and an unknown `fn` | T-7; CAP-5 | schema test; gen_schemas |
| Q2 | Every one of the 14 fns validates with its documented keys and types; required keys (`expect_extent.direction`, `distance`/`angle_between` `select_a`+`select_b`) are enforced by the schema | T-7; M-6 | test per fn (valid + one invalid each) |
| Q3 | The schema and the use case agree: no fn/key the schema accepts is rejected by the use case, and the reverse (tables are the single source) | M-6 | test that walks the tables against `usecases/assertions.py` |
| Q4 | Omitted `object` on a document with more than one shape-bearing object → `INVALID_INPUT` with a `detail.code`, message names the count and the candidate objects; exactly one → that object; zero → today's path | T-7; CAP-5; decision 10 (`object` stays optional) | infc tests (0, 1, 3 objects; Body+Sketch+Pad) |
| Q5 | `contracts/` stays stdlib only; AD-28 additive (no accepted call that validated before is now rejected except the T-7 cases) | AD-1, AD-28 | check_imports; schema regression test on existing benchmark/UAT calls |
| Q6 | `check_provenance.py` passes (validator hashes refreshed by the documented procedure, not by hand) | CI gate | `uv run python scripts/check_provenance.py` |
| Q7 | `mcp-tools-design.md` §3.3 (incl. the old "omit = first object" line) and `verification-design.md` §5 match the code | T-7 | read |
| Q8 | What an MCP client sees for a `oneOf` failure is readable (one live call) | plan 13-14 risk | verifier container call |

Levels marked RUN: Unit, Integration (freecadcmd). UAT: one live call by the verifier.
