# Story 13-2 triage: round 2 (verifier + red team)

Base: a913b51 on `story/13-2-script-exec-role-docs`. Sources: `verify-13-2.md` (F-1, F-2), `redteam-13-2.md` (RT-1 .. RT-15). Both in `D:\Work\Personal\Sources\freecad-buddy\_bmad-output\implementation-artifacts\`. Each source row gives proposed wording; use it unless a row below says otherwise.

All rows are inside the user-approved direction (decision 14): they make the documents state the approved bracket precisely. Documents only.

| Id | Source | Required fix |
| --- | --- | --- |
| F-2 + RT-1 | verifier, red team (high) | AD-5 (spine:77) and `mcp-tools-design.md:567` rule 4: the "no abort, no rollback, changes stay" sentence covers only a call that returns within its time budget. A `TIMEOUT` follows AD-27 and nothing more (decision 15). No sentence may give a keep-or-abort rule for a late return. |
| F-1 | verifier (medium) | Remove the remaining "typed tools are the sole/only AI mutation path" wording: `security-and-service-design.md:17`, `:110-111` (diagram labels), `:131`; `mcp-tools-design.md:110`. Use the verifier's wording. |
| RT-7 | red team (medium) | `mcp-tools-design.md:110`: `script_exec` is the one shipped tool outside `tool_specs()` (registered from `SCRIPT_EXEC_SPEC`); any other unlisted shipped tool is an inventory defect. Combine with F-1 in one sentence. |
| RT-2 | red team (medium) | Rule 7: the result fields are present for every call that ran the script (`OK`, `RECOMPUTE_ERROR`, `INVALID_INPUT` with `exec.python_error`). A refusal before execution and a `TIMEOUT` carry none. |
| RT-3 | red team (medium) | `integration-mcp-freecad.md:102`: `script_exec` catches its script's exception inside the bracket and returns `INVALID_INPUT` `exec.python_error` itself; `dispatch` never sees that exception. |
| RT-4 | red team (medium) | Every claim that `changed` lists "the changes" / "partial changes" (data-contracts-design.md:71, mcp-tools-design.md:567, security-and-service-design.md:89, AD-5) says instead: `changed` lists the objects whose geometry changed (AD-6); a property-only change (VarSet, spreadsheet, expression, Label) does not appear in it. The security NOT-defended reason must not rest on the false claim. |
| RT-5 | red team (medium) | AD-5 and rule 4: the bracket observes and reverts only the `doc` document. A script that changes another document is outside the bracket: one `document_undo` on `doc` does not revert it, and FreeCAD transactions are application-wide (`Document.cpp:330-340`, `AutoTransaction.cpp:132-172`). State this as a limit next to the own-transaction limit (decision 5 pattern: document, do not refuse). Story 13-13 measures and handles the open-transaction-in-another-document case at its spec checkpoint; add that case to the existing 13-13 deferred entry. |
| RT-6 | red team (medium) | `verification-design.md` §1: add a short subsection "Observe-only bracket (`script_exec`) — AD-5 exception" that names which §1 rules do not apply (no saveCopy snapshot R6, no post-verify, no rollback, a script's own transaction is tolerated, not nested) and which do (bridge opens the transaction first, one transaction per call, commit). Bump its date. |
| RT-8 | red team (medium) | Rule 7 fingerprint shape — leader decision 18: `fingerprint_before` and `fingerprint_after` are top-level bare digest strings, like the other flat lifecycle tools, so the AD-32 framing cache key (`hosts/tool_catalog.py:1469-1484`) keeps working. Remove "shaped as in the §1.4 mutation block". |
| RT-10 | red team (low) | Audit writer — leader decision 19: the adapter keeps writing the `before`/`after` pair as today; the `after` line takes both fingerprints from the result. The use case writes no audit line. Fix `sequence-diagrams.md:474` and security §1 to say this. |
| RT-9 | red team (low) | `security-and-service-design.md:57`: use the red team's wording (order, not "ahead of execution"). |
| RT-11 | red team (low) | `data-contracts-design.md:185,190` comments: use the red team's wording. Leave `actor` (deferred entry "Audit records carry"). |
| RT-12 | red team (low) | Add `AD-5` to `ad-refs` of `integration-mcp-freecad.md` and `project-structure.md`. |
| RT-13 | red team (low) | `sequence-diagrams.md:473`: "recompute (unless `recompute: false`)". |
| RT-14 | red team (low) | `data-contracts-design.md:71`: "`INVALID_INPUT` means the call made no change, except for `script_exec`: …". |
| RT-15 | red team (low) | Rule 7 result list starts with `doc` (the code returns it today; AD-28 forbids a removal). |

## Not fixed, with the reason

- Verifier notes N-1..N-6: non-blocking; the AD-28 `contract_version` question goes to Story 13-13 (add it to the 13-13 deferred entry).
- Red team "Not reproduced" items: no reproduction.

## After the fixes

1. Commit on your branch (Conventional Commits, no trailer).
2. Run `bmad-build`'s three review lenses again as fresh subagents (round 2), on the diff a913b51..HEAD, with the quality bar `quality-bar-13-2.md`. Patch high/medium; commit.
3. Re-run the Q4 grep plus a new grep for `sole AI mutation|only AI mutation|typed tools only|entire AI mutation surface` over spine + `design/` (expected: only the RT-7 sentence with its exception). Report counts.
4. Reply with the head SHA, lens ids and counts.
