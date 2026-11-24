# Epic 13 Context: MCP Usage Improvement

<!-- Compiled from SPEC-mcp-usage-improvement and the code at bd122f2. Line numbers verified against bd122f2. -->

## Goal

Typed tools cover the frequent FreeCAD operations, so `script_exec` becomes an escape route for rare work only. Evidence: one month of real modeling (2026-10-18 .. 2026-11-18, 1,221 calls) sent 34% of calls to `script_exec`; script mutations skip the AD-5 bracket (no diff, no TNP audit, no automatic transaction). Causes C-1 .. C-6 in `usage-evidence.md`.

Contract (read in full before any Story): `_bmad-output/specs/spec-mcp-usage-improvement/`

| File | Holds |
|------|-------|
| `SPEC.md` | CAP-1 .. CAP-9, constraints, non-goals, success signal |
| `tool-contracts.md` | Per-item contract T-1 .. T-14 (the build contract) |
| `keep-problem-try.md` | Keep items K-1 .. K-7 (must not regress), problems, priority order |
| `usage-evidence.md` | Numbers, quotes, causes; the method Story 20 automates |
| `stories.yaml` | 20 Stories |

Precedence: installed code > spine (`ARCHITECTURE-SPINE.md`) > `spec-freecad-buddy/SPEC.md` > design documents. For this epic the SPEC companions are the contract. Where `keep-problem-try.md` and `tool-contracts.md` disagree, `tool-contracts.md` wins (see plan, Contract check M-1, M-2).

Decision rule for every builder: decide by `docs/intent.md` and `spec-freecad-buddy/SPEC.md` plus this SPEC. Cite the clause.

## Capabilities (success criterion, lowest test level that proves it)

| CAP | Success criterion (short) | Lowest proving level | Stories |
|-----|---------------------------|----------------------|---------|
| CAP-1 | Replayed read-only script classes (bbox/volume, `isValid`, interference, slice) give equal values through `query_mass_properties`, `query_interference`, `query_section`; a failed boolean never reads as zero overlap | infc (`tests/infc/test_query_tools.py`) with a planted failed boolean; container UAT for the live path | 6, 7, 8 |
| CAP-2 | VarSet drives sketch constraints, feature lengths and an attachment offset; built, edited, read back, undone with typed tools only | infc for each tool; container UAT for the whole part (sketch constraint path and `.AttachmentOffset.Base` path) | 9, 10 |
| CAP-3 | Delete, placement write, rename, multi-object export each return a mutation diff and revert with `document_undo`; multi-body export passes `verify_export_*` with per-object volumes | infc (`test_feature_tools.py`, `test_export_tools.py`, `test_document_undo.py`); container UAT with a three-body document | 5, 11, 16 |
| CAP-4 | Script changing two objects returns `fingerprint_after` and `changed` naming both; one `document_undo` reverts it; `AttributeError` returns `INVALID_INPUT` `exec.python_error` | infc (new `test_script_exec.py` or in `test_mutation_protocol.py`); container UAT | 13 |
| CAP-5 | `verify_shape` schema rejects `{"type": "is_valid_solid"}`; omitted `object` on a multi-shape document returns `INVALID_INPUT`; datum-follows-sketch edit passes with no `REPOINTED` | external (schema with `jsonschema` Draft 2020-12 validator); infc (`test_verify_tools.py`, `test_tnp_guard.py`) | 14, 15 |
| CAP-6 | No `skills/**` text routes a covered operation to `script_exec`; `freecad-scripting-idioms` lists every gap; first tool load of a Claude Code modeling session holds sketch and feature tools; "is it done?" loads `verification-thinking` | `scripts/check_skill_shape.py` + grep for skills; the tool-loading and skill-loading criteria need a real agent session against the container (manual, no lower level exists) | 3, 4, 12, 19 |
| CAP-7 | Documents agree on the role of `script_exec`; `usage_report.py` prints the `usage-evidence.md` tables for a date range | grep over the named documents; external unit test with redacted fixture transcripts, then one real run on 2026-10-18..2026-11-18 | 2, 20 |
| CAP-8 | `value_repr` appears once in a `script_exec` result; `text` ≤5% of result chars over a test session | external (`tests/external/test_envelope_summary.py`); share measured with `scripts/automation/replay_result_sizes.py` over recorded transcripts | 1 |
| CAP-9 | Primitive-and-boolean part, a loft and a sweep built with `feature_part_primitive`, `feature_part_boolean`, `feature_loft`, `feature_sweep`, each with diff and undo | infc (`test_feature_tools.py`); container UAT | 17, 18 |

The success signal (`SPEC.md:84-86`: ≤15% `script_exec` share in the next month) cannot be measured inside the epic. It needs a month of real use after the epic. See plan, open question Q-3.

## Constraints (from `SPEC.md:60-73`)

- AD-4: typed tools first; `script_exec` stays registered and on by default.
- Every new mutation tool runs the AD-5 bracket: use `usecases/transaction.py:555` `run_mutation` (through `usecases/features.py:343` `_feature_mutation` for `feature_*` tools). No tool hand-rolls `openTransaction`.
- AD-5 amendment for `script_exec` (Story 2 writes it, Story 13 builds it): observe-only bracket — automatic transaction, fingerprint, `changed`, `new_errors`; no rollback, no TNP gate.
- AD-17 status set stays closed. New failure kinds use `detail.code` (dotted namespace, `data-contracts-design.md:61-63`), for example `exec.python_error`.
- AD-28: schema changes additive. `verify_shape` keeps `object` optional.
- AD-1 rings: `contracts/` stdlib only; FreeCAD through `usecases/shim.py`; imports inward only. `scripts/check_imports.py` enforces ring order.
- Server text client-neutral: no client-specific tool-loading text (for example no `ToolSearch` select line) in the server.
- AD-35: no shipped code holds a plan or replays a recipe; measuring tools return numbers and per-check verdicts, never a "part is done" verdict.
- AD-15: each `SKILL.md` keeps 4 sections and ≤1,500 body words (`scripts/check_skill_shape.py`, `MAX_WORDS = 1500`, body = text after front matter, split on whitespace).
- Every new or changed tool is proven in the `fcb-desktop` container UAT, never on the host.
- K-1 .. K-7 (`keep-problem-try.md:17-29`) must not regress.

Non-goals (`SPEC.md:75-82`): removing `script_exec`; recipe or replay tool; ellipse or B-spline sketch geometry; helix and thickness tools; Phase 5 work (assemblies, STEP import, TechDraw, part sourcing tools); routing logic in the server.

## Shared conventions for new tools (`tool-contracts.md:8-15`)

- Register in `hosts/tool_catalog.py:1075` `tool_specs()`; implementation in `usecases/`; add a row in `mcp-tools-design.md` §2 and a schema in §3 in the same Story, and update the counts table (`mcp-tools-design.md:202-223` (§ "Counts & G0.2"); `tool_specs()` returns 45 at bd122f2, verified).
- Multi-object input refuses an unknown name with `INVALID_INPUT` "unknown object: <name>" before any work.
- Results: silent on pass, loud on fail; no request echo; compact JSON.
- Output schema: every structured tool shares `_RESULT_ENVELOPE_SCHEMA` (`adapters/mcp_server.py:74`). The per-tool `outputSchema-result` blocks in `tool-contracts.md` are design-level shapes. Prove them in tests; there is no per-tool output schema to register.
- New read-only `query_*` tools: decide membership of `READ_ONLY_PROFILE` (`hosts/tool_catalog.py:1030-1046`) in the Story; the read-only assistant profile holds every read-only `query_`/`verify_` tool today.
- New mutation tools become `preview_dry_run` operations only when `preview_op_table()` (`hosts/tool_catalog.py:986-1004`) finds them. It reads functions by name from module `sketches` or `features` only. A tool in a new module is not previewable until the table is extended. `document_object_delete` must be previewable (`mcp-tools-design.md` §3.8, `tool-contracts.md:165`).
- Confirm gate: new mutation tools accept optional `confirm` (`$defs.Confirm`, `mcp-tools-design.md` §4) and go through the same gate as existing `feature_*` tools.

## Per-Story contract pointers (verified at bd122f2)

| Story | Contract | Code it changes today | AD-n |
|-------|----------|-----------------------|------|
| 13-1 Result text without duplicated long strings | `tool-contracts.md:17-31` T-13 | `contracts/envelope.py:66-81` `summary_text`; scalar line `:80` `lines.append(f"{key}: {value}")`. `adapters/mcp_server.py:106-109` regenerates a generated `text` after rounding (keeps working). `usecases/script_exec.py:67` uses `mirror_text` (alias, `envelope.py:84-86`) | AD-17, AD-28 (no schema change), spine convention "Tool results" |
| 13-2 Align documents, amend AD-5 | `tool-contracts.md:284-292` T-11, `:193-217` T-6 | Documents only: spine AD-5 `ARCHITECTURE-SPINE.md:77` ("Exception: `script_exec` runs raw…"), AD-4 `:69` ("runs outside the AD-5 bracket"); `mcp-tools-design.md:196-200` (`debug_` heading), `:562-570` §5 rules 4 and 7; `spec-freecad-buddy/SPEC.md:120`; `data-contracts-design.md:61-63` (detail codes). Also stale "raw" text: `component-design.md:43`, `project-structure.md:62`, `sequence-diagrams.md:453`, `integration-mcp-freecad.md:279`, `security-and-service-design.md:84` (plan M-3) | AD-4, AD-5, AD-17 |
| 13-3 Server instructions | `tool-contracts.md:33-47` T-10 | `adapters/mcp_server.py:231` `Server(name)` (headless/stdio); `hosts/gui_external/entry.py:55` `Server("freecad-buddy-gui-external")` (GUI HTTP proxy, the user path; plan M-4). mcp 1.28.1 low-level `Server(name, version, instructions)` supports it. `script_exec` description `hosts/tool_catalog.py:1064-1068` | AD-4, AD-3, AD-35 |
| 13-4 Skill routing step one + gap list | `tool-contracts.md:268-282` T-1, T-14 | `skills/freecad-scripting-idioms/SKILL.md:74-78` (2 gaps only); `skills/code-cad-conversion/references/verification-kit.md:3`; `skills/part-sourcing/SKILL.md:43-45` (import path); `skills/parametric-patterns/SKILL.md:38-40` stays until Story 12 | AD-15, AD-35 |
| 13-5 Multi-object export | `tool-contracts.md:178-191` T-5; `mcp-tools-design.md:373-404` §3.5 | `usecases/exports.py:83-105` `_resolve_export_object` (refusal `:91-93`; no-selection refusal `:98-104`); `:165` `shape.exportStep(path)`; `:227` `mesh.write(path)`; `:302` `verify_export_step`; mesh oracles `adapters/export_oracle.py`, verdict `adapters/export_verdict.py:70`; specs `hosts/tool_catalog.py:1357-1395` | AD-9, AD-20, AD-28 |
| 13-6 `query_mass_properties` objects | `tool-contracts.md:51-59` | `usecases/queries.py:570-621`; no-shape raise `:586-587`; record already holds `counts.solids` (`:167`, `:617`; plan M-5); spec `hosts/tool_catalog.py:1252` | AD-6 (shape_metrics from solids), AD-28 |
| 13-7 `query_interference` | `tool-contracts.md:61-84` | New in `usecases/queries.py` (or a new usecase module); spec in `hosts/tool_catalog.py`; row in `mcp-tools-design.md` §2 `query_` table `:125-138` | AD-13, AD-35 |
| 13-8 `query_section` | `tool-contracts.md:86-95` | New, same files as 13-7 | AD-13, spine convention "Text payloads are summarized, never raw dumps" |
| 13-9 VarSet parameters + `query_parameters` | `tool-contracts.md:99-126`, `:149-152` | New. `usecases/shim.py:133` `varset_backend()`, `:147` `varset_available()`; planned row `mcp-tools-design.md:138`. Unit-symbol list source: FreeCAD `docs/references/FreeCAD/src/App/Expression.l` | AD-5, AD-11, AD-28 |
| 13-10 `feature_set_expression` | `tool-contracts.md:128-147` | New mutation tool. Expression bindings are read by the TNP guard (`usecases/tnp_guard.py:275` `_expression_records`) | AD-5, AD-7 |
| 13-11 `document_object_delete` | `tool-contracts.md:156-165` | New. Planned row `mcp-tools-design.md:123`. TNP audit grades a vanished owner `BROKEN` (`usecases/tnp_guard.py:740-748`), so deleted owners need an exemption (plan risk R-11). Preview table `hosts/tool_catalog.py:986` | AD-5, AD-6, AD-7, AD-10, AD-20 |
| 13-12 Skill routing step two | `tool-contracts.md:268-282` | `skills/parametric-patterns/SKILL.md:38-40`; `skills/verification-thinking/SKILL.md` (1,494 words, 6 to spare; plan R-12); `skills/code-cad-conversion/references/verification-kit.md` | AD-15 |
| 13-13 `script_exec` observe-only bracket | `tool-contracts.md:193-217` T-6 | `usecases/script_exec.py:19-68` (`:53` exec under registry lock, `:60` `fingerprint_after: None`); error mapping `adapters/rpc_dispatch.py:153` (`TypeError/ValueError/KeyError` → `INVALID_INPUT`), `:156` (other → `RECOMPUTE_ERROR`); spec `hosts/tool_catalog.py:1051-1072`; bounded exec `:1532-1544`; undo `usecases/documents.py:583` | AD-4, AD-5 (amended), AD-6, AD-17, AD-27 |
| 13-14 Typed `verify_shape` schema | `tool-contracts.md:219-226` T-7 | Schema `hosts/tool_catalog.py:1313` (`"items": {"type": "object"}`); first-object default `usecases/verify.py:239-245`; vocabulary split: `contracts/assertions.py:12-26` (11 fns) + `usecases/verify.py:184-188` (3 more); per-fn keys `usecases/assertions.py:65-79` `_KEYS` (plan M-6) | AD-13, AD-28 |
| 13-15 TNP expected moves | `tool-contracts.md:228-234` T-8 | `usecases/tnp_guard.py:661-706` `_grade_entry`, witness check `:693`; design `verification-design.md:235`; decision `docs/decisions/014-tnp-intended-target-is-what-the-op-wrote.md` | AD-7 |
| 13-16 `feature_set_parameters` placement and string | `tool-contracts.md:167-176` | `usecases/features.py:1728-1749` `_property_family` (no family for placement/string), `:1752-1789` `_parameter_value` (refusal `:1766-1767`), `:1792` `feature_set_parameters`; spec `hosts/tool_catalog.py:794` | AD-5, AD-28 |
| 13-17 Part primitive and boolean | `tool-contracts.md:236-251`, `:265-266` | New. Placement value shape from Story 16. `docs/intent.md:250-254` Phase 2 list; `mcp-tools-design.md:174-188` `feature_` table | AD-1, AD-5, AD-6 |
| 13-18 Loft and sweep | `tool-contracts.md:253-263` | New `feature_*` in `usecases/features.py` (keeps them previewable) | AD-5, AD-7 |
| 13-19 Skill routing step three | `tool-contracts.md:268-282` | `skills/code-cad-conversion/SKILL.md:28,44-49,134`; `skills/design-decomposition/SKILL.md:66-70`; `skills/tool-selection/SKILL.md:38-43,58-67` | AD-15 |
| 13-20 Usage report and hygiene | `tool-contracts.md:294-301` T-12 | New `scripts/automation/usage_report.py` (reuse rules of `scripts/automation/session_metrics.py`); stale handle `usecases/documents.py:390`, `:405`; discovery file `adapters/rpc_listener.py:233-258` (`:246` `rpc-<pid>.json`), liveness `usecases/process.py:12` `pid_alive` | AD-25, AD-35 |

## Shared modules (merge-conflict risk)

One Story at a time is the default. These files are touched by several Stories; serialize work on them and rebase before review.

| File | Stories | Note |
|------|---------|------|
| `hosts/tool_catalog.py` | 3, 5, 6, 7, 8, 9, 10, 11, 13, 14, 16, 17, 18 | Every new tool spec. Story 3 and Story 13 both rewrite the `script_exec` description (`:1064-1068`) |
| `mcp-tools-design.md` | 2, 5, 6, 7, 8, 9, 10, 11, 14, 16, 17, 18 | Rows, §3 schemas, counts table |
| `usecases/features.py` (1,838 lines) | 10, 16, 17, 18 (and 9 if placed there) | `preview_op_table` reads `feature_*` functions from this module only |
| `usecases/queries.py` | 6, 7, 8, 9 | `query_*` implementations |
| `usecases/tnp_guard.py` | 11, 15 | Delete exemption and expected-move rule; both change audit grading |
| `skills/freecad-scripting-idioms/SKILL.md` (1,292 words) | 4, 12, 19 | Gap list written in 4, shrunk in 12 and 19 |
| `skills/verification-thinking/SKILL.md` (1,494 words) | 4, 12 | 6 words of headroom; new text goes to `references/` |
| `skills/code-cad-conversion/**` (1,416 words) | 4, 12, 19 | |
| `adapters/mcp_server.py` | 1 (indirect), 3, 13 (suspect and audit paths) | |
| `tests/uat/testcases/*.md` and `tests/uat/scenarios/*.json` | 5 (TC-07:442, :480), 13 (TC-05, TC-06, TC-08, TC-12, TC-13 fixtures), 14, 20 (TC-02 stale-handle text) | Test cases encode today's behaviour; update in the Story that changes it |

## Test pyramid and gates

Levels, lowest first:

1. External unit — `uv run pytest tests/external -q` (no FreeCAD). Contracts, schemas, envelope text, report script, adapters with fakes.
2. In-FreeCAD — `"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` (private temp cfg files). Tool behaviour on real documents. Check which copy of the package a test imports (installed `Mod/FreeCADBuddy` shadows `src`).
3. Headless e2e — `scripts/automation/run_mcp_e2e.py`, `run_mcp_edge_cases.py` from the host `uv` env against the container. Use for a new tool's wire path (schema, envelope, audit).
4. Container UAT — `fcb-desktop` only. Build `uv run python scripts/build_addon.py --release`, then `docker compose -f tests/close-loop/docker/compose.yaml up -d --build`, then `docker exec -u cua fcb-desktop fcb-freecad start`. Rebuild after any change under `src/`. Visual check is mandatory (screenshot of the real FreeCAD window, not only the MCP render).

Gates every Story runs: `uv run ruff check .` · `uv run python scripts/check_imports.py` · `uv run python scripts/check_status_vocab.py` · `uv run python scripts/gen_schemas.py --check` · `uv run python scripts/check_skill_shape.py` · `uv run pytest tests/external -q` · infc suite. `uv run ruff format --check` only on changed files. Known unstable: `tests/external/test_managed_venv.py::test_Should_start_an_external_interpreter_When_freecad_set_pythonhome` (fails in full run, passes alone).

Per Story (the lowest level that proves each success line is in **bold**):

| Story | External | infc | e2e | Container UAT |
|-------|----------|------|-----|---------------|
| 1 | **`summary_text` table rows (≤80, >80, newline, dict, list); `script_exec` envelope holds `value_repr` once**; text share via `replay_result_sizes.py` | — | — | one `script_exec` call, inspect `text` |
| 2 | grep: no "never an AI surface", "runs raw", "typed-tools-only" left in the named documents | — | — | — |
| 3 | **`initialize` result carries `instructions` ≤250 words in both servers (stdio `build_server`, GUI `build_proxy_server`); no `ToolSearch` text** | — | instructions over the wire | Claude Code session check of CAP-6 tool loading (manual) |
| 4 | **`check_skill_shape.py`; grep: no covered operation routed to `script_exec`** | — | — | — |
| 5 | oracle per-object checks with fixture files | **multi-object STEP/3MF/STL write and verify, per-object volume mismatch names the object** | — | **three-body document, one file per format, verify OK** |
| 6 | schema: exactly one of `object`/`objects` | **records in input order, `is_valid`, no-shape record** | — | yes |
| 7 | schema | **overlap, touch (distance 0), clearance, planted failed boolean → `boolean_failed: true`, `common_volume: null`** | — | yes |
| 8 | schema | **plane hit, plane miss (`wires: 0`), polylines capped with `truncated`** | — | yes |
| 9 | schema, name pattern | **create, add, update, unit-symbol refusal, type clash refusal, undo** | — | with Story 10 |
| 10 | schema | **bind, clear, batch in one transaction, parse error names `<object>.<path>`, circular → rollback** | — | **CAP-2 part: sketch constraint path and `.AttachmentOffset.Base` path** |
| 11 | schema | **dependents refused, `with_dependents` deletes and lists, Body deletes Group and Origin, undo, preview** | — | yes |
| 12 | **`check_skill_shape.py`; grep** | — | — | — |
| 13 | **dispatch mapping: Python error → `INVALID_INPUT` `exec.python_error`** | **two-object script → `changed` both, one undo reverts; new error → `RECOMPUTE_ERROR` keeps changes; script with own transaction; timeout path unchanged** | — | **CAP-4 live; re-run the TCs that use `script_exec` fixtures** |
| 14 | **Draft 2020-12 validation: `{"type": "is_valid_solid"}` rejected, every `fn` branch accepts its valid shape** | **omitted `object` on 2-shape document → `INVALID_INPUT`** | — | yes |
| 15 | — | **datum-follows-sketch reproduction passes; support change and mapped-element change stay `REPOINTED`; the 36 existing `test_tnp_guard.py` cases stay green** | — | yes |
| 16 | schema | **Placement and AttachmentOffset with omitted keys kept; `Label` rename returns stored label; undo** | — | yes |
| 17 | schema | **each primitive kind; cut/fuse/common with several tools; Body-feature input refused; empty result rollback** | — | **CAP-9 part** |
| 18 | schema | **additive and subtractive loft and sweep, undo** | — | **CAP-9 part** |
| 19 | **`check_skill_shape.py`; grep** | — | — | — |
| 20 | **report over redacted fixture transcripts reproduces known tables; stale-handle text; orphan sweep keeps live pid file** | — | — | stale-handle path; orphan files removed at start |

## Environment

Read `_bmad-output/implementation-artifacts/epic-13-status.md#Environment` before any command. Shared resources: container `fcb-desktop`, image `fcb-desktop:local`, ports 6901 and 18765 (owner: current Story's verifier, one Story at a time); `tests/uat/run/` new run folders only; `dist/addon/` written only by `build_addon.py`. Never write the developer `%APPDATA%\FreeCAD\v1-1\user.cfg`.
