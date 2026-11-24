# Story 13-2: verify report

Head `a913b51` on `story/13-2-script-exec-role-docs` (worktree `D:\Work\Personal\Sources\freecad-buddy-wt-13-2`), base `bd122f2`. Quality bar: `quality-bar-13-2.md`. Verifier read files at the head commit with `git show` and in the worktree. No file edited except this report.

Path prefix: `A` = `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21`, `D` = `A/design`.

## Verdict

**FAIL** — 2 defects (F-1 medium, Q10; F-2 low, Q6). Both are document wording only. Q1-Q5, Q7-Q9 PASS.

## Commands and counts

| Check | Command | Result |
| --- | --- | --- |
| Status vocabulary | `uv run python scripts/check_status_vocab.py` (worktree) | `check_status_vocab OK`, exit 0 |
| Skill shape | `uv run python scripts/check_skill_shape.py` (worktree) | no output, exit 0 |
| Q4 grep, head | spec AC 1 pattern, `grep -cE` over the 9 files at `a913b51` | **0** lines |
| Q4 grep, base (falsify) | same pattern and files at `bd122f2` | **10** lines (spine 2, mcp-tools 4, SPEC 1, component 1, project-structure 1, sequence 1); 12 occurrences with `grep -o`. The check can go red. |
| `debug_`, head | `git grep -n debug_ a913b51` over spine + `design/` + `SPEC.md` | **0** |
| `debug_`, base | same at `bd122f2` | 4 (spine:375, mcp-tools:18, :196, :217) |
| `script_exec`, head | `git grep -n script_exec a913b51` over spine + `design/` | **56** hits; every hit not in the diff read (see Q10) |

The 9 files: `A/ARCHITECTURE-SPINE.md`, `D/mcp-tools-design.md`, `D/data-contracts-design.md`, `_bmad-output/specs/spec-freecad-buddy/SPEC.md`, `D/component-design.md`, `D/project-structure.md`, `D/sequence-diagrams.md`, `D/security-and-service-design.md`, `D/integration-mcp-freecad.md`.

## Per row

| Q | Verdict | Evidence |
| --- | --- | --- |
| Q1 | PASS (named sections) | AD-4 `A/ARCHITECTURE-SPINE.md:69` "`script_exec` runs agent-supplied Python inside FreeCAD for the operations no typed tool covers … runs in the observe-only bracket of AD-5". AD-5 `:77` "Exception: `script_exec` runs in an observe-only bracket …". `D/mcp-tools-design.md:86` (§1.4 exception), `:196-200` (escape-route row "(listed gaps)"), `:566` rule 3 "Typed tools first", `:567` rule 4, `:570` rule 7. `D/data-contracts-design.md:64,71`. `SPEC.md:120` "typed tools first, `script_exec` for listed gaps (AD-4), … hash-proven rollback for typed tools and an observe-only bracket for `script_exec` (AD-5/6)". Same role everywhere in these sections. Other text in the same files still says "typed tools only": see F-1. |
| Q2 | PASS | Spine `:77`: "fingerprint before → bridge transaction opened first (named `script_exec <first code line>`) → agent code → `recompute()` unless the call sets `recompute: false` → `commitTransaction` → fingerprint after, `changed` (AD-6) and `new_errors` …. It runs no post-verify and no TNP audit". Own-transaction limit (decision 5): "FreeCAD commits the active transaction when a new one opens, which splits the undo history". `fingerprint_before` (decision 9): rule 7 `D/mcp-tools-design.md:570` result list. `recompute: false` (decision 4): `:567`, `:570`. Note N-1. |
| Q3 | PASS | `D/mcp-tools-design.md:567`: "`OK`; `RECOMPUTE_ERROR` when new objects are in error …; `INVALID_INPUT` with `detail.code` `exec.python_error` (`data.exception`, `data.traceback`) when the script raised, partial changes kept and listed in `changed` …; `TIMEOUT` as AD-27". Same in spine `:77`, `D/data-contracts-design.md:71`, `D/integration-mcp-freecad.md:102`. No new status: `check_status_vocab OK`. |
| Q4 | PASS | 0 at head, 10 at base (table above). |
| Q5 | PASS | `debug_` 0 at head over spine + design + SPEC. `git grep -i debug` at head finds only unrelated text (spine:53 "debug/troubleshoot fallback", `D/data-contracts-design.md:251` "display/debug aid", `D/project-structure.md:249`, `D/integration-mcp-clients.md:53`). Remaining `debug_` hits are under `A/reviews/` (dated review records, not spine or design). |
| Q6 | **FAIL** | AD-5 ends "A `TIMEOUT` follows AD-27." (`:77`), but the same rule adds an abort rule that covers TIMEOUT: see F-2. |
| Q7 | PASS | Sample `D/security-and-service-design.md:49-54` keys = code. `before` (`src/freecad_buddy/adapters/audit_log.py:52-67,84-85`): `schema, ts, actor, event, tool, params_digest, doc{handle}, code, fingerprint_before`. `after` (`:135-139`): same + `fingerprint_after, verify_verdict, rollback`. `actor` default `"operator"` (`:39`). `before` for exec has no fingerprint: `rpc_listener.py:434-436` and `mcp_server.py:278-280` call `audit.before(event, name, doc, params)` with no fingerprint. `verify_verdict` = envelope status: `mcp_server.py:247` passes `envelope.get("status")`. Note N-2. |
| Q8 | PASS | `D/mcp-tools-design.md:60` "A string longer than 80 characters, or holding a line break, renders as `key: <N chars>`". Code at `905e038` `src/freecad_buddy/contracts/envelope.py:43` `INLINE_STRING_LIMIT = 80`; `:88-91` `if isinstance(value, str) and (len(value) > INLINE_STRING_LIMIT or _LINE_BREAK.search(value)): lines.append(f"{key}: <{len(value)} chars>")`. `_LINE_BREAK` (`:47`) = every `str.splitlines` boundary, so "line break" is correct. |
| Q9 | PASS | Added design/spine/SPEC lines (42) scanned for `implement|now |no longer|previous|was |used to|changed from|story|13-|today|formerly|replac`: every match is pre-existing words on a rewritten line ("Implementation-ready", "today only `query_tree_summary`"). No narration, no "implemented" claim. Dates: spine `updated: '2026-11-24'` (`:10`); `date: '2026-11-24'` in all 7 edited design files; `SPEC.md` has none. |
| Q10 | **FAIL** | AD-6, AD-27, AD-28: no contradiction found (N-3, N-4). Unedited `script_exec` hits read: spine:63; component:83,194; data-contracts:183; integration-mcp-clients:70; integration-mcp-freecad:56,60,144,279,299; mcp-tools:135,219,562,564,566; project-structure:333; security §1 lines 15-44, 61-63, 87-90, 114-128; sequence:25,462,467,469. None of them contradicts. But text in two edited files, outside the `script_exec` grep, still states the old "typed tools only" role: F-1. |

## Defects

### F-1 (medium, Q10/CAP-7): "typed tools are the only AI mutation path" remains

Pre-existing text, not in the spec task list, in two files this Story edited. It contradicts AD-4 at head (`A/ARCHITECTURE-SPINE.md:69`: `script_exec` "runs agent-supplied Python … for the operations no typed tool covers", on by default) and the same file's own row `D/security-and-service-design.md:89` ("Typed tools first, `script_exec` only where none covers the operation"). The spec Q4 pattern does not match these phrasings, so the grep stays at 0.

| Location | Current text | Fix wording |
| --- | --- | --- |
| `D/security-and-service-design.md:17` | "typed tools are the sole AI mutation path, reached only over MCP" | "typed tools are the AI mutation path, with `script_exec` only for operations no typed tool covers, all reached only over MCP" |
| `D/security-and-service-design.md:110-111` (mermaid) | `llm -->\|MCP, typed tools only\| typed`, `unatt -->\|MCP, typed tools only\| typed` | `llm -->\|MCP, typed tools first; script_exec for gaps\| typed`; `unatt` edge: `\|MCP, typed tools; script_exec only if opted in\|` |
| `D/security-and-service-design.md:131` | "**typed tools as the only AI mutation path, reached only over MCP (AD-4, AD-35)**" | "**typed tools first and `script_exec` for listed gaps, both reached only over MCP (AD-4, AD-35)**" |
| `D/mcp-tools-design.md:110` | "AD-4 makes the typed tool list the entire AI mutation surface, so an unlisted shipped tool is an inventory defect" | "AD-4 makes the typed tool list plus `script_exec` the entire AI mutation surface, so an unlisted shipped tool is an inventory defect" |

Low, same cause: `D/security-and-service-design.md:92` "LLM free-form exec as mutation path (AD-4)" → "free-form exec replacing a typed tool that exists (AD-4)" (spine:68 "Prevents" wording).

### F-2 (low, Q6): AD-5 pre-decides no abort for a late TIMEOUT return

`A/ARCHITECTURE-SPINE.md:77`: "it never aborts or rolls back after the script returns: the changes stay on every outcome that returns". A timed-out script also returns, later. AD-27 (`:249`) says the session waits "until the in-flight op returns and its AD-5 transaction is aborted with rollback proved". Read together, AD-5 now says "no abort" for that late return, which decision 15 leaves to Story 13-13 (deferred entry `deferred-work.md` 13-2 item names this exact case).

Fix wording (spine `:77`): "it never aborts or rolls back when the script finishes inside the time budget: the changes stay on `OK`, on a Python exception (`INVALID_INPUT`, `detail.code` `exec.python_error`) and on new errors (`RECOMPUTE_ERROR`)." Keep "A `TIMEOUT` follows AD-27." Same scope words in `D/mcp-tools-design.md:567`: "No post-verify, TNP audit or rollback: the changes stay." → "No post-verify or TNP audit, and no rollback when the script finishes inside the time budget: the changes stay."

## Notes (not defects)

- N-1 (Q2): T-6 step 4 says "Recompute when the document is touched"; spine `:77` says `recompute()` unless `recompute: false`. FreeCAD recompute of an untouched document recomputes nothing, so the effect is the same. Quality bar Q2 uses the spine wording.
- N-2 (Q7): The sample `after` line shows digests. Today the code writes `null` for exec (no bracket); digests arrive with the Story 13-13 bracket. The `deferred-work.md:1716` resolution says so.
- N-3 (AD-28): `recompute` input and `fingerprint_before`/`changed`/`new_errors` result fields are additive. A script exception moves from `RECOMPUTE_ERROR` (code today, `rpc_dispatch.py:153-157`) to `INVALID_INPUT`: no enum change, but a field-semantic change; Story 13-13 must decide whether RPC `contract_version` bumps (AD-28 "bumped on any frame or field semantic change").
- N-4 (integration:102): the `exec.python_error` mapping sits in the `dispatch` mapping list. Rule 4 (`D/mcp-tools-design.md:567`) says the bracket still recomputes, commits and fingerprints after the exception, so the use case must catch it, not `dispatch`. Text is user-approved and the status fact is true; Story 13-13 should place the catch in the use case.
- N-5: `D/mcp-tools-design.md:219` "24 AI-visible … plus `script_exec`" reads as if `script_exec` is not AI-visible; the total row `:216` is now "(typed tools)". Optional: "24 typed tools … plus `script_exec`".
- N-6: `D/component-design.md:83` (`rpc_dispatch.py` row) lists the error mapping without `exec.python_error`. Omission only.

## Round 2

Head `313e4bf` (commits `f38a027` triage fixes, `313e4bf` lens round 2 patches). Diff read as `git diff a913b51 313e4bf`. Triage: `triage-13-2-r2.md`.

### Verdict

**PASS**. Every triage row is closed. Q1-Q10 PASS. The round-2 patches add no blocking contradiction. Four low notes (R2-N1..R2-N4) follow; the bar does not require them.

### Commands and counts (at `313e4bf`)

| Check | Result |
| --- | --- |
| `uv run python scripts/check_status_vocab.py` | `check_status_vocab OK`, exit 0 |
| `uv run python scripts/check_skill_shape.py` | exit 0 |
| Q4 pattern, 9 files | **0** (base `bd122f2`: 10) |
| Q4 pattern, spine + all `design/` | 1: `D/verification-design.md:37` heading "Observe-only bracket (`script_exec`) — AD-5 exception". New and correct term (spine:77 "Exception: `script_exec` runs in an observe-only bracket"). File is not one of the 9. |
| `debug_`, spine + `design/` + SPEC | **0** |
| `sole AI mutation\|only AI mutation\|typed tools only\|entire AI mutation surface`, spine + `design/` | **1**: `D/mcp-tools-design.md:110` "AD-4 makes the typed tool list plus `script_exec` the entire AI mutation surface; `script_exec` is the one shipped tool outside `tool_specs()` …" (the expected RT-7 sentence) |

### Triage rows

| Id | Closed | Evidence at `313e4bf` |
| --- | --- | --- |
| F-2 + RT-1 | yes | spine:77 "it never aborts or rolls back a call that finishes inside its time budget: the changes stay on `OK`, on a Python exception … and on new errors … A `TIMEOUT` follows AD-27." `D/mcp-tools-design.md:567` "no rollback for a call that finishes inside its time budget". `D/verification-design.md:39` "for a call that finishes inside its time budget the bracket aborts nothing …; a `TIMEOUT` follows AD-27". No sentence gives a keep-or-abort rule for a late return (see R2-N1). |
| F-1 | yes | `D/security-and-service-design.md:17` "typed tools are the AI mutation path, with `script_exec` only for operations no typed tool covers, all reached only over MCP"; `:110-111` labels "typed tools first; script_exec for gaps" and "typed tools; script_exec only if opted in"; `:131` "typed tools first and `script_exec` for listed gaps, both reached only over MCP"; `:92` "free-form exec replacing a typed tool that exists (AD-4)"; `D/mcp-tools-design.md:110`. |
| RT-7 | yes | `D/mcp-tools-design.md:110`, one sentence with F-1. `SCRIPT_EXEC_SPEC` exists: `tool_specs()` docstring in `hosts/tool_catalog.py` says "excluding ``script_exec`` (gated via ``SCRIPT_EXEC_SPEC``)". |
| RT-2 | yes | `D/mcp-tools-design.md:570` "The fields are present for every call that ran the script (`OK`, `RECOMPUTE_ERROR`, `INVALID_INPUT` with `exec.python_error`). A refusal before execution and a `TIMEOUT` carry none of them." |
| RT-3 | yes | `D/integration-mcp-freecad.md:102` "`script_exec` catches its script's exception inside the bracket and returns `INVALID_INPUT` with `detail.code` `exec.python_error` itself (AD-5), so `dispatch` never sees that exception; `script_exec` logs the traceback to stderr as `dispatch` does". Agrees with rule 4: the bracket still commits and fingerprints after the exception. |
| RT-4 | yes | spine:77, `D/data-contracts-design.md:71`, `D/mcp-tools-design.md:567`: "`changed` lists the objects whose geometric invariants differ (AD-6); a property-only change … is not listed". `D/security-and-service-design.md:89` NOT-defended reason: "reports its geometry changes in `changed` (AD-6; a property-only change is not listed)". Grep `changes listed\|listed in \`changed\`\|returns its changes`: 0. |
| RT-5 | yes | spine:77 and `D/mcp-tools-design.md:567`: "a script that changes another document is outside the bracket: one `document_undo` on `doc` does not revert that change, because `document_undo` undoes one document". Source check: `Document::undo` (`docs/references/FreeCAD/src/App/Document.cpp:157`) works on one document, and `usecases/documents.py:653` calls `document.undo()`. The 13-13 deferred entry in `deferred-work.md` adds "a script that changes only another document …". See R2-N2. |
| RT-6 | yes | `D/verification-design.md:37-39` §1.1.1 names R1 (applies), one transaction and commit (apply), R2 (see R2-N3), R3 (not as written), R4 and R6 (do not apply), no post-verify or TNP audit, R5 (bridge transaction only; own transaction tolerated, not nested). Date `'2026-11-24'` (`:4`). The R3 claim matches source: `Document::openTransaction` calls `GetApplication().setActiveTransaction(name)` (`Document.cpp:330-340`), which commits every document and takes a new application ID (`AutoTransaction.cpp:132-172`). |
| RT-8 | yes | `D/mcp-tools-design.md:570` "both fingerprints are top-level bare digest strings, as in the other flat lifecycle tools …, so the AD-32 framing cache key keeps reading `fingerprint_after`". "Shaped as in §1.4" now covers only `changed` entries. Code: the framing key reads `structured.get("fingerprint_after")` as `str` (`hosts/tool_catalog.py:1482-1483`); `document_undo` returns bare digests (`usecases/documents.py:676-677`). See R2-N4. |
| RT-10 | yes | `D/security-and-service-design.md:57` "The adapter (the MCP server, or the RPC listener in GUI mode) writes the `before` and `after` lines around the call, and the use case writes none". `D/sequence-diagrams.md:471` `MCP->>Audit: append-only before record …`, `:475` `MCP->>Audit: append-only after record: status and both fingerprints from the result`. Agrees with today's writer (`mcp_server.py:278-280`, `rpc_listener.py:434-436`). |
| RT-9 | yes | `:57` "written before the bracket takes its fingerprint, so `fingerprint_before` is `null` there; the `after` line takes both fingerprints from the result, and they are `null` when the result carries none". |
| RT-11 | yes | `D/data-contracts-design.md:185` "sha256 hex" (code `hashlib.sha256(...).hexdigest()`, `audit_log.py:33`, no prefix); `:190` "envelope status of the call (the post-verify verdict for a bracketed mutation)". `actor` untouched. |
| RT-12 | yes | `ad-refs` has `AD-5` in `D/integration-mcp-freecad.md` and `D/project-structure.md` front matter. |
| RT-13 | yes | `D/sequence-diagrams.md:473` "recompute (unless recompute: false)". |
| RT-14 | yes | `D/data-contracts-design.md:71` "`INVALID_INPUT` means the call made no change, except for `script_exec`: …". |
| RT-15 | yes | `D/mcp-tools-design.md:570` result starts with `"doc"`; code returns `"doc": handle` (`usecases/script_exec.py:55-56`). |
| N-1..N-6 | routed | The AD-28 `contract_version` question is in the 13-13 deferred entry ("whether the RPC `contract_version` bumps …"). |

### Quality bar at `313e4bf`

| Q | Verdict | Evidence |
| --- | --- | --- |
| Q1 | PASS | Round 1 evidence holds. Round 2 did not change the role words in AD-4 (spine:69), §5 rule 3 or SPEC.md:120. F-1 leftovers removed. |
| Q2 | PASS | spine:77 step order unchanged; rule 7 keeps `fingerprint_before` and `recompute`. |
| Q3 | PASS | Statuses unchanged; `check_status_vocab OK`. |
| Q4 | PASS | 0 over the 9 files. |
| Q5 | PASS | `debug_` 0. |
| Q6 | PASS | F-2 closed (row above). |
| Q7 | PASS | Sample keys unchanged; the writer text now agrees with the code (adapter writes both lines). |
| Q8 | PASS | `D/mcp-tools-design.md:60` unchanged since round 1. |
| Q9 | PASS | Round-2 added design lines scanned for narration words: the only matches are existing text ("today" in the `tool_specs()` sentence, "undo history"). `verification-design.md` date bumped. Narration is only in the spec Review Triage Log and `deferred-work.md`, which are history records. |
| Q10 | PASS | Cross-read AD-5, AD-6, AD-27, §5 rules 4 and 7, verification §1.1.1, data-contracts:71/185/190, security §1/§4/§5/§6, sequence §8, integration:102. No contradiction that changes behaviour; notes below. |

### Notes (low, not required by the bar)

- R2-N1: short summaries still say "no rollback" without the time-budget scope: `D/component-design.md:43`, `D/mcp-tools-design.md:200`, `D/security-and-service-design.md:89`, `D/sequence-diagrams.md:453`. They describe the bracket shape (it has no rollback step; AD-27 recovery is a separate mechanism), so they set no late-return rule. Optional: "no rollback (TIMEOUT: AD-27)".
- R2-N2: spine:77 "The bracket observes and reverts only the document named by `doc`". The bracket never reverts; `document_undo` does. Optional wording: "The bracket observes only the document named by `doc`, and one `document_undo` reverts only that document: …".
- R2-N3: `D/verification-design.md:39` "R2 applies after the script: the bracket recomputes". R2 (`:31`) is the recompute after an abort or undo, before verification. The post-script recompute is the AD-5 step, not R2. Optional: drop "R2 applies after the script:" and keep "The bracket recomputes after the script (unless …)".
- R2-N4: AD-6 (spine:85) says "Tool results carry the `digest` and serializer tag". The rule 7 bare digests (decision 18) follow the shipped `document_undo`/`document_recompute` shape, which already drops the tag. The drift between AD-6 and the lifecycle tools existed before this Story. Also "geometric invariants" (spine:77, data-contracts:71, rule 4) versus the AD-6 term "mass-property invariants": same meaning; the AD-6 term is optional.
