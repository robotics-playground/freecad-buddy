# Sprint Change Proposal — Design-Artifact Reconciliation (2026-07-24)

## 1. Issue Summary

Several changes shipped to `main` during this session diverged from or extended the authoritative planning artifacts. Per the project operating model (CLAUDE.md §10: "Approved implementation changes a design contract → update authoritative design artifact in same work"), the design docs required reconciliation with the shipped, tested implementation. The divergences were discovered while driving the live GUI against a real 201-object PCB assembly and during the tree/envelope ergonomics build.

## 2. Impact Analysis

**Epic impact:** none — no scope change; the code was already implemented, reviewed, and tested. This is documentation reconciliation, not a replan.

**Artifact conflicts identified and resolved:**

| Change | Authoritative doc (was stale) | Reconciled to |
|--------|-------------------------------|---------------|
| Tree tool redesign | `mcp-tools-design.md §3.2` — `max_nodes`/flat `nodes`/`truncated` | depth/root/filters, nested `tree`, `children`/`links`, sparse nodes, `visibility`, inline `error` |
| `query_tree_children` role | drill-down after summary | intra-node pagination (offset/limit); summary owns depth/root/filter navigation |
| Envelope `text` | `mcp-tools-design.md §1.3` — "human mirror, server-derived" (JSON dump) | per-tool one-line summary; compact `summary_text` fallback; never a JSON re-dump |
| Screenshot dirty-doc | §3.9 — strict non-mutating, hard-fail implied | renders dirty docs with `render.dirty_document: true`; guard skipped for self-unstable docs |
| Render size | 1024/800/600 across 5 docs | `1920×1920` default + cap |
| G1 eval size | "10 broken-doc cases" | tiered n=10→n=30 (decision 008) |

**Technical impact:** doc-only. Code (screenshot fix, 1920 default, tree/envelope rewrite, tiered eval) already on `main`, tests green (external 351, infc 86).

## 3. Recommended Approach

**Direct Adjustment** — update the authoritative design artifacts in place to match the approved, shipped implementation. No rollback, no MVP change. Effort: doc edits only; risk: low (no behavior change, code already verified); timeline: same-session, complete.

## 4. Detailed Change Proposals (applied)

**`mcp-tools-design.md`:**
- §3.2 `query_tree_summary` — replaced input (`depth`/`root`/`filters`) + output (nested `tree` with sparse nodes, `children`/`links` partition, `visibility`, `returned_nodes`).
- Tool table — `query_tree_children` repurposed to intra-node pagination; `query_screenshot` note gains dirty-doc + ≤1920 px.
- §1.3 envelope — `text` redefined as per-tool summary (+ output-schema field description).
- §3.9 `query_screenshot` — dirty-document render paragraph added; `dirty_document` output field added; width/height → 1920.
- §L78 render budget → ≤1920 px.

**`integration-mcp-freecad.md`:** §6 `render_offscreen` default `width=1920, height=1920`.

**`component-design.md`, `data-contracts-design.md`, `integration-mcp-clients.md`, `verification-design.md`:** render-budget references 1024 → 1920.

**`validation-harness-design.md`:** dev-set broken-doc count 10 → 30 (tiered, decision 008).

**`docs/tests/test-plan.md` §8:** added dirty-doc render behavior, 1920 size, MSAA/AA note; annotated the Visibility limitation with the new `visibility`/`visible_only` tree affordance.

**Already reconciled earlier this session (verified no residual):** SPEC.md, phase-gates.md, epics.md, intent.md, decision 008 (tiered eval); sprint-status.yaml (`epic-2: done`).

## 5. Implementation Handoff

**Scope: Minor** — documentation reconciliation of already-shipped, tested code. No developer implementation task follows; the code is complete on `main`. The updated design artifacts are now the current contract for any future work touching the tree, envelope, render, or G1 eval surfaces.

**Success criteria (met):** every authoritative design doc that described the changed surfaces now matches the shipped implementation; no stale 1024/`max_nodes`/JSON-mirror/n=10-only reference remains (verified by grep sweep); tests remain green.
