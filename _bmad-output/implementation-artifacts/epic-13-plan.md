# Epic 13 Plan: MCP Usage Improvement

Source: `_bmad-output/specs/spec-mcp-usage-improvement/` (SPEC, `tool-contracts.md`, `keep-problem-try.md`, `usage-evidence.md`, `stories.yaml`). Compiled context: `epic-13-context.md`. All `file:line` references verified at bd122f2.

## Readiness verdict

CONCERNS. The plan is implementable. 20 Stories trace to CAP-1 .. CAP-9 and every CAP has at least one Story. Gaps: 25 contract mismatches (section "Contract check"), 7 questions only the user can answer (section "Open questions"). None blocks Stories 1 to 4. Q-4 and Q-5 must be answered before Story 13; Q-6 before Story 5.

Terms used below:
- **AD-n**: decision record in `ARCHITECTURE-SPINE.md`.
- **AD-5 bracket**: snapshot, transaction, operation, recompute, post-verify, commit or proven rollback (`ARCHITECTURE-SPINE.md:77`).
- **Approval tier**: the level of planning document a Story edits — intent (`docs/intent.md`), PRD/SPEC (`spec-freecad-buddy/SPEC.md`), architecture (spine AD-n), technical design contract (`design/*.md`). Each change needs the user's approval at that level; the authorising clause is cited.
- **K-n**: keep item that must not regress (`keep-problem-try.md:17-29`).

## Story order

Order = `stories.yaml` order. No dependency forces a change. Reasons:

- `stories.yaml` already follows the priority order in `keep-problem-try.md:69-74` (P1 cheap, P1 tools, P2, P3).
- Every hard dependency points backward: 13 needs 2 (AD-5 amendment, `exec.python_error` code); 12 needs 6 to 11; 17 needs 16 (placement value shape, `tool-contracts.md:242` "`placement` (as T-4)"); 19 needs 16 to 18; 10 needs 9 for its UAT (expressions bind to VarSet properties).
- Story 3 rewrites the `script_exec` description (`hosts/tool_catalog.py:1064-1068`), and Story 13 rewrites it again ("Raw: no transaction…" becomes false). 3 before 13 keeps the second edit on top of the first.
- Story 15 before Story 16: a placement write to `AttachmentOffset` moves attached datums. If the TNP audit still flags expected moves, Story 16's UAT fails on the false positive Story 15 removes.
- Story 20 is independent. It stays last because its report measures the epic.

Parallel-eligible pairs (disjoint files): 1 with 2; 4 with 5; 20 with any Story. All tool Stories (5 to 11, 13, 14, 16 to 18) share `hosts/tool_catalog.py` and `mcp-tools-design.md`: run them one at a time.

```
1 ─┐
2 ─┼─────────────────────────────── 13
3 ─┘ (3 before 13: same description)
4
5
6 ─┬─ 12
7 ─┤
8 ─┤
9 ─┼─ 10
11┘
14
15 ── 16 ── 17 ─┬─ 19
         18 ────┘
20
```

## Stories

### 13-1 Result text without duplicated long strings

- Depends on: none.
- Files: `src/freecad_buddy/contracts/envelope.py:66-81`; `tests/external/test_envelope_summary.py`.
- Approval-tier changes: none. `mcp-tools-design.md:60` already describes the fallback as "a compact `key: value` flattening".
- Deferred work: none.
- Risks: a UAT runner check that reads a long string from `text` instead of `structured_content` breaks. The scenarios read `structured_content.value_repr` (`tests/uat/scenarios/tc-03-03.json:341` and others), so none found. `adapters/mcp_server.py:106-109` compares `text` with `summary_text(content)` to decide regeneration after rounding; the new rule keeps that comparison valid because both sides use the same function.

### 13-2 Align documents on the role of script_exec and amend AD-5

- Depends on: none. `spec_checkpoint: true`.
- Files (documents only): `ARCHITECTURE-SPINE.md:69` (AD-4), `:77` (AD-5); `design/mcp-tools-design.md:196-200`, `:202-223` (counts table moves `script_exec` out of `debug_`), `:562-570` (§5 rules 4 and 7); `design/data-contracts-design.md:61-63`; `spec-freecad-buddy/SPEC.md:120`; plus the stale "raw" text in `design/component-design.md:43`, `design/project-structure.md:62`, `design/sequence-diagrams.md:453`, `design/integration-mcp-freecad.md:279`, `design/security-and-service-design.md:84` (M-3).
- Approval-tier changes:
  - Architecture AD-5: replace the raw-exec exception with the observe-only bracket. Authorised by `SPEC.md:64` and `tool-contracts.md:286-287`.
  - Architecture AD-4: "runs outside the AD-5 bracket (see AD-5)" becomes "runs in the observe-only bracket of AD-5". Authorised by `SPEC.md:52` (CAP-7: "AD-4 and AD-5 state the same role"); not named in T-11 (M-3).
  - PRD/SPEC: `spec-freecad-buddy/SPEC.md:120` "typed-tools-only mutation (AD-4)" → "typed tools first; `script_exec` for listed gaps (AD-4)". Authorised by `tool-contracts.md:291`.
  - Technical design: `mcp-tools-design.md` escape-route row, §5 rules 4 and 7; `data-contracts-design.md` `exec.python_error`. Authorised by `tool-contracts.md:288-290`, `:292`. The other five design files: authorised by `SPEC.md:50` (CAP-7 intent).
- Deferred work: may close `deferred-work.md:1714` (`script_exec` audit record shape in `security-and-service-design.md` §1 differs from code) if the Story corrects that section while it edits line 84. Recommend: include it; same file, same topic.
- Risks: the spine front matter `updated:` date and any design `status: final` front matter need a bump; check each file's convention.

### 13-3 Server instructions that put typed tools first

- Depends on: none (names the gap list Story 4 writes, by skill name only).
- Files: `src/freecad_buddy/adapters/mcp_server.py:231`; `src/freecad_buddy/hosts/gui_external/entry.py:55` (M-4); `src/freecad_buddy/hosts/tool_catalog.py:1064-1068`; one shared constant for the text (place it in `adapters/` or `hosts/` and import from both; `contracts/` also works since it is plain text); tests `tests/external/test_mcp_surface.py`, `tests/external/test_gui_external_proxy.py`.
- Approval-tier changes: none required. Optional: one sentence in `design/integration-mcp-clients.md` that the server sends `instructions`. Not authorised by the contract; leave out unless the user asks.
- Deferred work: none.
- Risks:
  - `SPEC.md:93` assumes Claude Code shows `instructions` before the first tool load. Unverified. CAP-6's tool-loading criterion can fail even with a correct server. The Story must state the result of the live check, not assume it.
  - The text must stay client-neutral (`SPEC.md:68`). `keep-problem-try.md:63` asks for "the exact `ToolSearch` select line"; that conflicts (M-1). Follow `tool-contracts.md:38-44`.
  - 250-word limit: test it in the external suite.

### 13-4 Skill routing to existing typed tools and the full gap list

- Depends on: none.
- Files: `skills/freecad-scripting-idioms/SKILL.md` (1,292 words, gap list at `:74-78`); `skills/code-cad-conversion/references/verification-kit.md:3` and its snippets (11 bbox/volume/`isValid` hits); `skills/verification-thinking/SKILL.md` (1,494 words); `skills/part-sourcing/SKILL.md:43-45`.
- Approval-tier changes: none (skills are content, AD-15 shape only).
- Deferred work: none.
- Risks:
  - Word budget: `freecad-scripting-idioms` has 208 words of headroom for the full gap list (the classes table `usage-evidence.md:126-146` holds 17 classes). Put the list in `references/` and keep a short pointer in the body if it does not fit.
  - `verification-thinking` has 6 words of headroom (R-12). Any routing text there needs a matching cut or a move to `references/`.
  - The gap list written here includes operations Stories 6 to 18 close. Stories 12 and 19 shrink it. Write it as a table so later Stories delete rows.

### 13-5 Multi-object STEP, 3MF and STL export

- Depends on: none. `done_checkpoint: true`. Q-6 must be answered first.
- Files: `src/freecad_buddy/usecases/exports.py:83-105`, `:141-188`, `:191-253`, `:302-388`; `src/freecad_buddy/usecases/shim.py` (multi-object STEP writer with product names, multi-object 3MF writer: FreeCAD `Import.export` / `Mesh.export` over object lists, behind the shim); `src/freecad_buddy/adapters/export_oracle.py`, `adapters/export_verdict.py:70` (per-object checks); `src/freecad_buddy/hosts/tool_catalog.py:1357-1395` (descriptions); tests `tests/infc/test_export_tools.py`, external oracle tests; UAT `tests/uat/testcases/TC-07-verification-and-export-pairing.md:442`, `:480` and their scenarios.
- Approval-tier changes:
  - Technical design: `verification-design.md` §6 (per-object volume checks). Authorised by `tool-contracts.md:190-191`.
  - `mcp-tools-design.md` §3.5 already says "omit = all visible solids"; code refuses today (`exports.py:98-104`). The Story makes code match the design (M-7).
- Deferred work: none open. Prior fixes this Story relies on: DW-34 (Euler check accepts multi-body, `deferred-work.md:293`), DW-40 (3MF oracle checks every mesh object, `:341`).
- Risks:
  - K-1 (export + verify pair) must not regress: the single-object path keeps its numbers.
  - K-4 changes on purpose: the "export supports a single object" message disappears; TC-07 encodes it and must be updated in this Story.
  - STL per-object volume is not recoverable from one merged mesh (M-8, Q-6).
  - Fingerprint and export volumes come from solids (AD-6); a body with no solid in the selection needs a defined result (refuse with `INVALID_INPUT` "object has no shape", as `_require_shape` does today).

### 13-6 query_mass_properties for several objects

- Depends on: none.
- Files: `src/freecad_buddy/usecases/queries.py:570-621`; `src/freecad_buddy/hosts/tool_catalog.py:1252`; `mcp-tools-design.md:131` row; tests `tests/infc/test_query_tools.py`.
- Approval-tier changes: technical design `mcp-tools-design.md` row and §3 schema. Authorised by `tool-contracts.md:10-11`, `:51-59`.
- Deferred work: DW-28 (done) defines today's non-solid handling; keep it.
- Risks: the `solids` field duplicates `counts.solids` (M-5). The no-shape record shape is not specified (M-9).

### 13-7 query_interference tool

- Depends on: none.
- Files: new function in `src/freecad_buddy/usecases/queries.py` (or a new `usecases/measure.py`); `hosts/tool_catalog.py` spec and `READ_ONLY_PROFILE` (`:1030-1046`); `mcp-tools-design.md` §2 and §3; tests `tests/infc/test_query_tools.py`.
- Approval-tier changes: technical design new row and schema. Authorised by `tool-contracts.md:10-11`, `stories.yaml:162-163`. Intent: `docs/intent.md:323` lists "interference detection across parts" under Phase 5 Assemblies (M-20). No intent edit needed if the Story reads it as object-pair measurement, which `SPEC.md:33` (CAP-1) states.
- Deferred work: none.
- Risks: `Shape.common` on large compounds can exceed the 60 s query budget; cap pairs at 100 (contract) and measure one large case. The failed-boolean rule is the safety property (AD-35: numbers only) — plant it in infc.

### 13-8 query_section tool

- Depends on: none (same files as 13-7; run after it).
- Files: as 13-7.
- Approval-tier changes: technical design new row and schema. Authorised by `tool-contracts.md:10-11`, `:86-95`.
- Deferred work: none.
- Risks: polyline output size. Cap `max_points` at 5,000 (contract) and keep the spine rule "text payloads are summarized, never raw dumps".

### 13-9 VarSet parameters and query_parameters

- Depends on: none.
- Files: new `feature_parameters_define` (place in `usecases/features.py` so `preview_op_table` finds it, or extend the table); new `query_parameters` in `usecases/queries.py`; `usecases/shim.py:133-149` (VarSet probe); `hosts/tool_catalog.py`; `mcp-tools-design.md:138` (planned → shipped) and a new row.
- Approval-tier changes: technical design rows and schemas. Authorised by `tool-contracts.md:99-126`, `:149-152`.
- Deferred work: DW-21 (done) covers the probe document.
- Risks:
  - The unit-symbol list is open-ended in the contract ("`mm`, `deg`, `in`, …"). Take it from FreeCAD's expression lexer `docs/references/FreeCAD/src/App/Expression.l`, not from memory. `skills/parametric-patterns/SKILL.md:41` names `W`, `T`, `A`, `V`, `N`, `C`, `K`; the code list must cover those.
  - `varset_available()` false (a build without `App::VarSet`): refuse with `INVALID_INPUT`. CI runs 1.1.3 only, so this path is reached only by a fake.

### 13-10 feature_set_expression tool

- Depends on: 9 (UAT needs VarSet properties).
- Files: new function in `usecases/features.py`; `hosts/tool_catalog.py`; `mcp-tools-design.md`; infc tests; container UAT for `.Constraints.<name>` and `.AttachmentOffset.Base.z`.
- Approval-tier changes: technical design new row. Authorised by `tool-contracts.md:128-147`.
- Deferred work: none.
- Risks:
  - A circular dependency must roll back with proof (AD-5). FreeCAD can refuse the binding at `setExpression` time instead of at recompute; both paths need a test.
  - Binding an expression changes `ExpressionEngine`, which the TNP guard reads (`tnp_guard.py:275`). The written-value exemption (decision 014) must cover the bound path, or every bind flags itself.

### 13-11 document_object_delete tool

- Depends on: none.
- Files: new use case (`usecases/documents.py` or `usecases/features.py`); `hosts/tool_catalog.py` including `preview_op_table` (`:986-1004`, reads only `sketches`/`features` modules); `usecases/tnp_guard.py:740-748`; `mcp-tools-design.md:123`.
- Approval-tier changes: technical design row planned → shipped, §3 schema. Authorised by `tool-contracts.md:156-165`.
- Deferred work: DW-94 (done, `deferred-work.md:1031`) made a deleted reference target grade `BROKEN`; this Story relies on that for the dependents rule.
- Risks (R-11): the TNP audit grades a vanished owner `BROKEN` (`tnp_guard.py:740-748`). A delete removes owners on purpose, so without an exemption keyed to the delete set every delete of an object that owns a reference fails post-verify and rolls back. The exemption must be keyed to the delete set the op wrote, in the style of decision 014, never to "owner was touched". Shares `tnp_guard.py` with Story 15.

### 13-12 Skill routing to the new measure, parameter and delete tools

- Depends on: 6, 7, 8, 9, 10, 11. `done_checkpoint: true`.
- Files: `skills/parametric-patterns/SKILL.md:38-40`; `skills/verification-thinking/SKILL.md`; `skills/code-cad-conversion/references/verification-kit.md`; gap list in `skills/freecad-scripting-idioms`.
- Approval-tier changes: none.
- Deferred work: none.
- Risks (R-12): `verification-thinking` is at 1,494 of 1,500 words. Move a section to `references/` first.

### 13-13 script_exec observe-only bracket and error status

- Depends on: 2 (AD-5 amendment, detail code), 3 (description edit order). `spec_checkpoint: true`. Q-4 and Q-5 must be answered first.
- Files: `src/freecad_buddy/usecases/script_exec.py:19-68`; `src/freecad_buddy/adapters/rpc_dispatch.py:153-157` (or catch inside the use case); `src/freecad_buddy/hosts/tool_catalog.py:1051-1072`; `usecases/transaction.py` (reuse fingerprint and `changed` helpers, not `run_mutation`); `skills/freecad-scripting-idioms/SKILL.md:57` ("It runs raw"); UAT test cases that use `script_exec` as a fixture (TC-05, TC-06, TC-08, TC-12, TC-13).
- Approval-tier changes: none new; implements the AD-5 amendment from Story 2.
- Deferred work (related, not closed): `deferred-work.md:599` (exec body holds the registry lock for its whole run; fingerprints add to that time), `:611` (GUI exec body has no budget), `:1742` (`ThreadExecutor` bound has no production host), `:1918` (failing `script_exec` posts a traceback as a GUI notification — check whether the `exec.python_error` path still posts it; close it here if the new path suppresses it), `:1722` (audit `actor: operator` for agent scripts).
- Risks:
  - Fixtures break (Q-4): `TC-06-render-and-gui-visual-fidelity.md:515`, `TC-12-gui-workflows.md:437`, `TC-13-gui-mcp-parity.md:909` need a document left Touched by `script_exec`; an automatic recompute removes that state. `TC-13-gui-mcp-parity.md:408` breaks a pad through `script_exec` and expects `OK`; with `new_errors` it returns `RECOMPUTE_ERROR`.
  - Fixtures that monkeypatch bridge internals through `script_exec`: `TC-08-preview-confirm-and-undo.md:430` replaces `fingerprint.fingerprint` with a function that raises. If `script_exec` reads `fingerprint` at call time, its own fingerprint-after raises inside the planting call. `TC-05-mutation-protocol-and-rollback.md:482`, `:711` patch `tnp_guard.snapshot_references` (not used by the observe-only bracket; safe).
  - Own transactions (Q-5): FreeCAD commits the active transaction when a new one opens (`docs/references/FreeCAD/src/App/Document.cpp:363-365`). A script that opens and commits its own transaction splits the undo history; "one `document_undo` reverts the whole script" holds only for scripts that open none.
  - Timeout: the bridge transaction is open when `TIMEOUT` fires. AD-27 says the in-flight op may still run; define what the late return does (commit, or abort) and keep the document suspect either way.
  - Cost: two fingerprints per call, including the 230 read-only scripts per month (`usage-evidence.md:97`). Measure on a 30-object document against the 30 s budget.
  - `INVALID_INPUT` with partial changes kept is a new meaning; elsewhere `INVALID_INPUT` means "nothing ran" (`mcp-tools-design.md:560`). The `detail.code` separates them; the skill and description must say so (M-10).

### 13-14 Typed verify_shape check schema

- Depends on: none.
- Files: `src/freecad_buddy/hosts/tool_catalog.py:1304-1331`; `src/freecad_buddy/usecases/verify.py:239-245`; `src/freecad_buddy/contracts/assertions.py:12-26` (if the vocabulary moves, M-6); `src/freecad_buddy/usecases/assertions.py:65-79`; `mcp-tools-design.md:309-347` §3.3 ("omit = the document's first object", `:314`).
- Approval-tier changes: technical design `mcp-tools-design.md` §3.3 and `verification-design.md` §5. Authorised by `tool-contracts.md:219-226`, `SPEC.md:44-46`.
- Deferred work: none.
- Risks:
  - Benchmarks, graders and UAT cases that call `verify_shape` without `object` on a multi-object document change from a measurement to `INVALID_INPUT`. Grep `benchmarks/` and `tests/uat/` before the change.
  - `jsonschema` `oneOf` error text is long; the MCP client sees the validation failure before dispatch. Check what the client shows (one live call).

### 13-15 TNP audit accepts expected re-attachment moves

- Depends on: none. `spec_checkpoint: true`.
- Files: `src/freecad_buddy/usecases/tnp_guard.py:661-706`; `tests/infc/test_tnp_guard.py` (36 cases); `verification-design.md:228-249` §3.2; possibly a new note beside `docs/decisions/014-tnp-intended-target-is-what-the-op-wrote.md`.
- Approval-tier changes: technical design `verification-design.md:235`. The design already excuses "the mutation's intended target"; T-8 widens that to a reference whose support object and mapped element are unchanged while a driving value moved it. Authorised by `tool-contracts.md:230-234`, `SPEC.md:46`.
- Deferred work: DW-70 (done) made `REPOINTED` reachable; this Story narrows one of its paths.
- Risks (M-15): K-6 must not regress. The witness check (`tnp_guard.py:693`) is the only Layer-1 detector of a re-point that keeps the mapped name. A rule of "same support, same mapped name → PASS whatever the witness" disables it. The Story's spec checkpoint must show the cause first and a rule that still flags the planted witness-move case in `test_tnp_guard.py` and the five TNP-provoking G2 scenarios (`docs/intent.md:260`).

### 13-16 feature_set_parameters writes placement and strings

- Depends on: 15 (see order). `done_checkpoint: true`.
- Files: `src/freecad_buddy/usecases/features.py:1704-1789`; `src/freecad_buddy/hosts/tool_catalog.py:794`; `mcp-tools-design.md:188` row; `skills/freecad-scripting-idioms/SKILL.md:74-78` text "It cannot write a placement" (gap row removed in Story 19).
- Approval-tier changes: technical design row text. Authorised by `tool-contracts.md:167-176`.
- Deferred work: none.
- Risks: the `Visibility` display-state carve-out (`mcp-tools-design.md:104`, last sentences) must stay limited to `Visibility`; a `Label` write is not display state. `Placement` of an attached object is recomputed from its attachment; a write to `Placement` there is silently overwritten — refuse or document.

### 13-17 Part primitive and Part boolean tools

- Depends on: 16. `spec_checkpoint: true`.
- Files: new functions (place in `usecases/features.py` for preview, or extend `preview_op_table`); `hosts/tool_catalog.py`; `docs/intent.md:250-254`; `mcp-tools-design.md:174-188`; `skills/tool-selection/SKILL.md` routes are Story 19.
- Approval-tier changes:
  - Intent: `docs/intent.md` Phase 2 operation list adds Part primitives and booleans. Authorised by `tool-contracts.md:265`, `stories.yaml:256-257`, `SPEC.md:56-58` (CAP-9).
  - Technical design: `mcp-tools-design.md` §2 `feature_` table and counts. Authorised by `tool-contracts.md:265-266`.
- Deferred work: closes `deferred-work.md:1654` (no MCP tool makes a `Part::Common`; agents split print pieces with base-feature copies). Close it in Story 19 when `design-decomposition` routes to the tool.
- Risks: `feature_*` handlers call `_require_partdesign()` (`features.py:83`); Part tools need only `Part`. The AD-6 fingerprint and `changed` list must include document-level `Part::*` objects (they do today: fingerprint covers shape objects by `Name`).

### 13-18 Loft and sweep tools

- Depends on: none hard; after 17 for file order.
- Files: `usecases/features.py`; `hosts/tool_catalog.py`; `mcp-tools-design.md`.
- Approval-tier changes: technical design rows. Authorised by `tool-contracts.md:253-263`.
- Deferred work: none.
- Risks: `spine: Selector | sketch name` is a union; JSON Schema `oneOf` of a selector object and a string. Sweep `mode` names map to `PartDesign::AdditivePipe.Mode` values; check the enumeration names in FreeCAD source before writing the map.

### 13-19 Skill routing to Part, loft, sweep and placement tools

- Depends on: 16, 17, 18.
- Files: `skills/code-cad-conversion/SKILL.md:28`, `:44-49`, `:134` and `references/generator-kit.md`; `skills/design-decomposition/SKILL.md:66-70`; `skills/tool-selection/SKILL.md:38-43`, `:58-67`; gap list.
- Approval-tier changes: none.
- Deferred work: closes `deferred-work.md:1654` together with Story 17.
- Risks: `code-cad-conversion` (1,416 words) changes its core method from "generator file run by `script_exec`" to typed tools; keep the generator route for shapes typed tools cannot make (`tool-contracts.md:274`), and the T-14 traced-outline route.

### 13-20 Usage report and bridge hygiene

- Depends on: none. `done_checkpoint: true`.
- Files: new `scripts/automation/usage_report.py` (reuse the transcript rules of `scripts/automation/session_metrics.py`); `src/freecad_buddy/usecases/documents.py:390`, `:405`; `src/freecad_buddy/adapters/rpc_listener.py:233-258`; `usecases/process.py:12`; UAT `TC-02` cases that match the stale-handle message exactly.
- Approval-tier changes: none.
- Deferred work: closes `deferred-work.md:1865` (orphan `rpc-<pid>.json` files).
- Risks: `pid_alive` answers True on access denied and on Windows pid reuse (`deferred-work.md:1778`); the sweep then keeps a few orphans. Acceptable; do not delete a file whose pid answers alive. The report reads transcripts outside the repo (`~/.claude/projects/...`); fixtures in tests must be redacted.

## Re-slice proposals

No re-slice is required. One optional proposal:

- **RS-1: split Story 13.** 13a: a Python exception returns `INVALID_INPUT` `exec.python_error` (`rpc_dispatch.py:156` today maps it to `RECOMPUTE_ERROR`; 8 cases in `usage-evidence.md:153`). 13b: the observe-only bracket. Evidence: 13a needs only Story 2's detail code and touches no fixture; 13b carries Q-4, Q-5 and the UAT fixture rewrite. Splitting lets 13a ship early and keeps 13b's checkpoint focused. Cost: one more Story key.

## Contract check

Each claim in `stories.yaml` and `tool-contracts.md` checked against the code at bd122f2 and the design documents. Claims not listed here match (for example `exports.py:91-93`, `tool_catalog.py:1064-1068`, `tool_catalog.py:1313`, `rpc_dispatch.py:144-157`, `script_exec.py:30-61`, `verify.py:241-245`, `mcp-tools-design.md:123`, `:196-200`, `spec-freecad-buddy/SPEC.md:120`, every cited skill line). No new tool name already exists: `tool_specs()` returns 45 names, none of the 10 new or planned names among them.

| ID | Kind | Claim | Evidence | Proposed resolution |
|----|------|-------|----------|---------------------|
| M-1 | Companion conflict | `keep-problem-try.md:63` T-10: instructions carry "the exact `ToolSearch` select line" | `SPEC.md:68` forbids client-specific tool-loading text; `tool-contracts.md:38-44` has none | Follow `tool-contracts.md` |
| M-2 | Companion conflict | `keep-problem-try.md:61` T-7: "make `object` required" | `SPEC.md:66` and `tool-contracts.md:224` keep it optional (AD-28) | Follow `tool-contracts.md` |
| M-3 | Incomplete document list | T-11 (`tool-contracts.md:286-292`) lists AD-5, `mcp-tools-design.md`, `SPEC.md:120`, `data-contracts-design.md` | AD-4 `ARCHITECTURE-SPINE.md:69` says "runs outside the AD-5 bracket"; also `component-design.md:43`, `project-structure.md:62`, `sequence-diagrams.md:453`, `integration-mcp-freecad.md:279`, `security-and-service-design.md:84` say raw | Story 2 edits all of them under CAP-7 (`SPEC.md:50-52`) |
| M-4 | Wrong location | T-10: instructions in `adapters/mcp_server.py` | GUI mode builds its own server at `hosts/gui_external/entry.py:55`; `mcp_server.py:231` serves headless only | Story 3 sets `instructions` in both, from one constant |
| M-5 | Duplicate value | T-2 adds `"solids": int` to each record | Record already holds `counts.solids` (`queries.py:167`, `:617`); CAP-8 (`SPEC.md:54`) "every value appears once" | Add only `is_valid`; leader may decide (no user question) |
| M-6 | Vocabulary source | T-7: `oneOf` "generated from `contracts.ASSERTION_FNS`" | `ASSERTION_FNS` holds 11 fns (`contracts/assertions.py:12-26`); `expect_solid_count`, `expect_valid`, `expect_watertight` live in `usecases/verify.py:184-188`; per-fn keys in `usecases/assertions.py:65-79` | Move the 3 fns and the key table into `contracts/assertions.py` (stdlib data, AD-1 allows), generate from there |
| M-7 | Behaviour change hidden as "already specified" | T-5: "as §3.5 already specifies (omit = all visible solids)" | Code refuses a multi-object document with no selection (`exports.py:98-104`); UAT `TC-07:480` asserts that refusal | Implement §3.5; update TC-07 in Story 5 |
| M-8 | Infeasible check | T-5: "`verify_export_*` compares per-object volume" for all three formats | STL is "one merged mesh" (`tool-contracts.md:188`); a merged mesh has no object boundaries, and touching bodies fuse into one component | Q-6 |
| M-9 | Unspecified shape | T-2: no-shape object → `"shape": null` | Today's record has no `shape` key; single `object` path raises (`queries.py:586-587`) | Record `{name, shape: null}` for `objects`; `object` path unchanged |
| M-10 | Status meaning | T-6: Python error → `INVALID_INPUT` with partial changes kept | Elsewhere `INVALID_INPUT` means no execution (`mcp-tools-design.md:560`) | Keep (closed status set); `detail.code` and description state "changes kept" |
| M-11 | Missing field | T-6 result adds `fingerprint_after`, not `fingerprint_before` | `document_undo` proves restoration only with `expect_fingerprint` (`documents.py:597-616`) | Add `fingerprint_before` (additive) so CAP-4's undo is provable; leader may decide |
| M-12 | Order ambiguity | T-6 step 2: "If the script did not open a transaction, the bridge opens one" | The bridge must open before the script runs; it cannot know. FreeCAD commits the active transaction on a new open (`Document.cpp:363-365`) | Bridge always opens first; Q-5 for scripts that open their own |
| M-13 | Fixture conflict | T-6 step 4: recompute when the document is touched | UAT fixtures need a Touched document (`TC-06:515`, `TC-12:437`, `TC-13:909`) | Q-4 |
| M-14 | Rationale broken | T-7: "the same fail-closed rule as export" | After Story 5, export with no selection exports all visible solids, so export no longer fails closed | Keep the T-7 rule; drop the comparison in the design text |
| M-15 | Design conflict | T-8: PASS when support and mapped element are unchanged and only placement follows a driving change | Witness move is the Layer-1 re-point detector (`tnp_guard.py:693`, `verification-design.md:235`); decision 014 keys exemptions to the written value only | Story 15 spec checkpoint; rule must keep the planted witness-move cases flagged |
| M-16 | Missing requirement | T-4 delete runs under AD-5 | TNP audit grades a vanished owner `BROKEN` (`tnp_guard.py:740-748`), so a delete fails its own post-verify | Story 11 adds a delete-set exemption |
| M-17 | Design default | `mcp-tools-design.md:314` "omit = the document's first object" | T-7 changes this for multi-shape documents | Story 14 updates §3.3 |
| M-18 | No per-tool output schema | T-2 gives `outputSchema-result` blocks | All structured tools share `_RESULT_ENVELOPE_SCHEMA` (`mcp_server.py:74`); per-tool result schemas do not exist (related DW-9) | Treat as design shapes; prove in tests |
| M-19 | Preview reach | T-4: delete "allowed as a `preview_dry_run` operation"; new `feature_*` tools assumed previewable | `preview_op_table()` reads functions only from modules `sketches` and `features` by name (`tool_catalog.py:998-1003`) | Place new mutation functions in `features.py`, or extend the table; Story 11 extends it for delete |
| M-20 | Intent placement | CAP-1 interference between objects | `docs/intent.md:323` lists "interference detection across parts" under Phase 5 Assemblies; SPEC non-goal excludes Phase 5 assemblies | Object-pair measurement is not assembly work; no intent edit unless the user wants the line moved |
| M-21 | Read-only profile | New `query_*` tools | `READ_ONLY_PROFILE` (`tool_catalog.py:1030-1046`) is a hand list; contract is silent | Add the three read-only tools; keep mutation tools out |
| M-22 | Line number | `usage-evidence.md:231` and `keep-problem-try.md:47`: `envelope.py:76-77` | The scalar line is `envelope.py:79-80` | Cosmetic; no action |
| M-23 | Unverified assumption | `SPEC.md:93`: Claude Code shows `instructions` before the first tool load | Not verified in the repo | Story 3 records the live result |
| M-24 | Out-of-repo cause | C-1 cites `funny-character AGENTS.md:25,70,132-138` and Ender `CLAUDE.md:168` | Those files are in the user's other projects; no Story changes them | Q-7 |
| M-25 | Scope note | `usage-evidence.md:254-256`: `content[0]` repeats the body | T-13 changes only `text`; Claude Code reads only `structuredContent` when present (memory `claude-code-reads-structured-content-only`) | No action in this epic |

## Open questions for the user

Only questions the evidence cannot settle.

- **Q-1 Integration branch.** Options: (a) build on `fix/uat-gate-1-failures`; (b) new branch `feat/epic-13-mcp-usage-improvement` from bd122f2; (c) from `main` after `fix/uat-gate-1-failures` merges. Recommendation: (b). Epic 13 is a new capability, not a UAT fix, and (b) does not wait on a merge.
- **Q-2 Meaning of `spec_checkpoint` and `done_checkpoint` in `stories.yaml`.** Options: (a) `spec_checkpoint` = the user approves the Story spec before code; `done_checkpoint` = the user reviews the result and the container UAT batch of the Stories since the last done checkpoint; (b) both are leader-only review points. Recommendation: (a). The spec checkpoints sit on the Stories that change the spine or intent (2, 17) or carry semantic risk (13, 15); the done checkpoints (5, 12, 16, 20) end natural groups.
- **Q-3 Success-signal targets and epic close.** `SPEC.md:97` asks to accept ≤15% `script_exec`, ≤5% read-only scripts, zero multi-object refusals, ≤5% `text`. The signal needs one month of real use after the epic. Options: (a) accept the targets, close the epic on CAP-1 .. CAP-9, and record the signal as an action item for about 2026-12-23 with `usage_report.py`; (b) hold the epic open for the month. Recommendation: (a).
- **Q-4 `script_exec` automatic recompute vs fixtures that need a Touched document.** Options: (a) recompute as T-6 says and rewrite the Touched fixtures (no other MCP route leaves a document Touched, so those checks become NOT RUN); (b) never recompute, so `fingerprint_after` and `new_errors` read stale shapes when a script forgets `doc.recompute()`; (c) as (a) plus an optional input `recompute: false` (additive, AD-28) for the fixtures. Recommendation: (c). It keeps the contract for agents and keeps the render and dirty-document checks runnable.
- **Q-5 Scripts that open their own transaction.** FreeCAD commits the active transaction when a new one opens, so one `document_undo` cannot revert such a script. Options: (a) document the limit in the tool description and in `freecad-scripting-idioms`, and tell agents not to open transactions in `script_exec`; (b) also report the number of undo steps the script made (new field); (c) refuse code that calls `openTransaction`. Recommendation: (a). The skill text from Epic 12 that tells agents to open their own transaction (`skills/freecad-scripting-idioms/SKILL.md:57`) is reversed in the same Story.
- **Q-6 Per-object verification for STL.** Options: (a) STL verifies the total volume only; STEP and 3MF verify per object; (b) STL verifies per connected component, which fails for touching bodies. Recommendation: (a).
- **Q-7 Project instruction files outside this repository.** Cause C-1 includes `AGENTS.md` and `CLAUDE.md` in the user's two modeling projects, which route work to `script_exec`. The success signal depends on them. Options: (a) the user updates them after Stories 12 and 19, using the gap list; (b) leave them. Recommendation: (a).
