---
title: 'DW-26: Bound query_dependencies whole-document edges array'
type: 'feature'
created: '2026-07-24'
status: 'done'
review_loop_iteration: 0
baseline_revision: '4187555353dd50cf484d607123d065dfc40b691d'
final_revision: '400bdd5'
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md'
warnings: []
---

<intent-contract>

## Intent

**Problem:** `query_dependencies` whole-document mode (`usecases/queries.py` l429-433) emits every object's `OutList` as one uncapped `edges` array, so a very large assembly yields an unbounded response that can overflow a model's context. The per-object mode and every sibling `query_*` tool bound their output; only whole-doc dependencies does not.

**Approach:** Add a `max_edges` cap parameter (default a generous bound that Phase-0 docs never hit) to `query_dependencies`. When the collected edge count exceeds the cap, truncate the array and emit an explicit truncation signal (`total_edges`, `returned_edges`, `truncated`) so a consumer knows the response is partial and can scope down with per-object mode. Update the `mcp-tools-design.md` §3.3 contract to match.

## Boundaries & Constraints

**Always:**
- Whole-doc structured output stays a superset of today's shape — `edges` remains a list of `{from, to}` in the same document-object / `OutList` order; add-only fields.
- Per-object mode (`object` given) is unchanged: no cap, no new fields.
- `max_edges` is a positive integer; reject `max_edges < 1` with `ValidationError`.
- Truncation is deterministic: keep the first `max_edges` edges in iteration order.
- `summarize_dependencies` one-line text reflects truncation when it occurs.
- Register the new `max_edges` param in `hosts/tool_catalog.py` query schema and keep `gen_schemas` drift-clean.

**Block If:**
- The design owner's intent for the default cap value or pagination-vs-cap shape turns out to be contested by another authoritative artifact beyond `mcp-tools-design.md` §3.3 — HALT `blocked`, condition `contested dependencies cap contract`.

**Never:**
- No full offset/limit pagination cursor — a single forward cap plus truncation flag is the whole scope (`query_tree_children` owns paging semantics elsewhere; do not touch it).
- Do not change per-object output, `query_tree_summary`, or any other tool.
- Do not alter edge ordering or the `{from, to}` edge shape.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Under cap | doc with total edges ≤ `max_edges` | `{edges:[…all…], total_edges:N, returned_edges:N, truncated:false}` | No error |
| Over cap | doc with total edges > `max_edges` | `edges` holds first `max_edges`; `total_edges` = full count; `returned_edges` = `max_edges`; `truncated:true` | No error |
| Default cap | `max_edges` omitted | Uses default bound (2000); truncation fields present | No error |
| Invalid cap | `max_edges=0` or negative | raises `ValidationError` | ValidationError bubbles |
| Per-object mode | `object` given | unchanged `{object, in_list, out_list}`; no cap fields | No error |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/queries.py` -- `query_dependencies` (l411-437) whole-doc branch builds the uncapped `edges`; `summarize_dependencies` (l67-73) one-line text.
- `src/freecad_buddy/hosts/tool_catalog.py` -- `query_dependencies` input schema (l462-473); add `max_edges` property.
- `tests/infc/test_query_tools.py` -- `test_query_dependencies_object_and_whole_doc` (l103); infc unittest under FreeCADCmd.
- `tests/external/test_tool_summaries.py` -- `summarize_dependencies` unit tests (edge_count, single_object).
- `_bmad-output/planning-artifacts/architecture/.../design/mcp-tools-design.md` -- §3.3 `query_dependencies` contract to update.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/queries.py` -- add `max_edges: int = 2000` param to `query_dependencies`; validate `>= 1` (raise `ValidationError` otherwise); in whole-doc branch collect all edges, set `total_edges`, slice to `max_edges`, set `returned_edges` and `truncated`, add those three fields to `structured`; update docstring. -- bound whole-doc response.
- [x] `src/freecad_buddy/usecases/queries.py` -- extend `summarize_dependencies` so the whole-doc branch appends a truncation note when `truncated` is true (e.g. `"N dependency edge(s) (truncated from M)."`). -- surface truncation in one-line text.
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- add `max_edges` `{type: integer, minimum: 1, default: 2000}` to the `query_dependencies` input schema properties; refresh the tool description to mention the whole-doc cap. -- expose the param over MCP.
- [x] `tests/infc/test_query_tools.py` -- extend `test_query_dependencies_object_and_whole_doc` (or add a sibling) to assert whole-doc under-cap emits `truncated:false` with `total_edges == returned_edges == len(edges)`, and a `max_edges=1` call on a multi-edge doc emits `truncated:true`, `returned_edges == 1`, `len(edges) == 1`, and `total_edges` = full count; assert `max_edges=0` raises `ValidationError`. -- cover the I/O matrix.
- [x] `tests/external/test_tool_summaries.py` -- add a `summarize_dependencies` case for the truncated whole-doc dict. -- lock the summary text.
- [x] `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md` -- update §3.3 `query_dependencies` to document `max_edges` input and the `total_edges`/`returned_edges`/`truncated` output fields. -- keep design contract authoritative (CLAUDE.md §10).

**Acceptance Criteria:**
- Given a document whose total `OutList` edge count exceeds `max_edges`, when whole-doc `query_dependencies` runs, then `edges` holds exactly `max_edges` entries in original order, `total_edges` is the full count, `returned_edges == max_edges`, and `truncated` is true.
- Given `max_edges` omitted on a Phase-0-sized document, when whole-doc `query_dependencies` runs, then `truncated` is false and `returned_edges == total_edges == len(edges)`.
- Given `max_edges < 1`, when `query_dependencies` runs, then a `ValidationError` is raised.
- Given the design contract update, when `gen_schemas` / drift checks run, then no schema drift is reported and `check_imports` passes.

## Design Notes

Cap-not-cursor: DW-26's own reason defers "a bound/pagination if size becomes a concern". Minimal sufficient bound is a forward cap + truncation flag; a consumer that hits the cap scopes down via per-object mode. Default `2000` is generous — Phase-0 docs are tiny, so `truncated` stays false in practice while the worst-case assembly response stays bounded. Fields are add-only, so existing consumers and the `test_query_dependencies_object_and_whole_doc` shape assertions keep passing.

Note: DW-26's ledger text says `query_tree_summary` "caps at `max_nodes`" — it does not (design §3.2 is explicitly "not a flat node cap"; it bounds by depth/filter). The mirrored pattern taken here is the *shape* of a bounded response with a `total`/`returned` count pair plus an explicit signal, not a literal `max_nodes` field.

## Verification

**Commands:**
- `python tests/run_tests.py` -- expected: infc suite green, including the extended dependency test (runs under FreeCADCmd).
- `python -m pytest tests/external/test_tool_summaries.py -q` -- expected: summary tests pass.
- `python scripts/gen_schemas.py --check` -- expected: no schema drift.
- `python scripts/check_imports.py` -- expected: ring-boundary clean.

## Review Triage Log

### 2026-07-24 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 3: (high 0, medium 1, low 2)
- defer: 0
- reject: 10
- addressed_findings:
  - `[medium]` `[patch]` Non-integer / `bool` `max_edges` passed directly to `query_dependencies` (bypassing the MCP JSON-schema `integer` guard, e.g. from tests/RPC) reached the bare `< 1` check and then `edges[:max_edges]`, crashing with a raw `TypeError` (`1.5`, `None`) or silently slicing to one edge (`True`). Added an `isinstance(int)`/`not bool` guard raising `ValidationError` before the `< 1` check.
  - `[low]` `[patch]` `test_query_dependencies_object_and_whole_doc` only asserted `edges[0]` identity under truncation, leaving the load-bearing truncation *ordering* unpinned. Strengthened to assert `capped["edges"] == whole["edges"][:1]`, added a `max_edges=2` prefix check `two["edges"] == whole["edges"][:2]`, and added `max_edges=1.5`/`max_edges=True` `ValidationError` cases.
  - `[low]` `[patch]` `test_summarize_dependencies_truncated` used a weak `"1" in out and "5" in out` substring assertion. Tightened to an exact-string equality on `"1 dependency edge(s) (truncated from 5)."`.

## Auto Run Result

Status: done

**Summary:** Bounded `query_dependencies` whole-document mode. It now accepts a `max_edges` cap (default 2000), returns the first `max_edges` edges in document/`OutList` order, and emits `total_edges`/`returned_edges`/`truncated` so a consumer knows when the response is partial. Per-object mode and edge shape/order are unchanged. Fields are add-only.

**Files changed:**
- `src/freecad_buddy/usecases/queries.py` — added `max_edges` param + integer/`>=1` validation to `query_dependencies`; whole-doc branch slices to the cap and emits the three truncation fields; `summarize_dependencies` appends a truncation note.
- `src/freecad_buddy/hosts/tool_catalog.py` — registered `max_edges` `{integer, minimum 1, default 2000}` in the `query_dependencies` input schema; refreshed the tool description.
- `tests/infc/test_query_tools.py` — extended the dependency test: under-cap `truncated:false`, `max_edges=1`/`=2` prefix + truncation, `max_edges=0`/`1.5`/`True` reject.
- `tests/external/test_tool_summaries.py` — added an exact-string truncated-summary case.
- `_bmad-output/planning-artifacts/.../design/mcp-tools-design.md` — added §3.2.1 documenting the `max_edges` input and truncation output fields, updated the tool-table row.

**Review findings breakdown:** 3 patches applied (1 medium type-guard, 2 low test-strengthening); 0 deferred; 10 rejected (out-of-scope compute/memory bounding, `maximum`-cap opt-out, redundant-field and clamp-vs-reject design choices fixed by the in-contract spec, ledger-status/stale-`max_nodes` items the bundle forbids me to edit, and cosmetic sentinel/defensiveness notes).

**Verification performed (all after patches):**
- `freecadcmd tests/run_tests.py` — `Ran 106 tests ... OK (skipped=1)`.
- `uv run python -m pytest tests/external/test_tool_summaries.py -q` — `23 passed`.
- `uv run python scripts/gen_schemas.py --check` — `gen_schemas --check OK`.
- `uv run python scripts/check_imports.py` — `check_imports OK`.
- `uv run ruff check` + `ruff format --check` on all four changed source/test files — clean.
- Typecheck: project has no mypy/pyright gate configured (ruff-only); no typecheck run applicable.

**Residual risks:** None material. `max_edges` has no upper bound by design (a caller asking for more edges opts out of the cap; the default protects the unaware consumer). Compute cost is unchanged — the cap bounds response size, not the in-memory edge-list build, matching DW-26's stated scope.
