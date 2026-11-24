---
title: 'Align documents on the role of script_exec and amend AD-5'
type: 'chore'
created: '2026-11-23'
status: 'done'
baseline_commit: 'bd122f2459a9854b9b92856e25ce3cb5a386ca7a'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/SPEC.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Spine AD-4 and AD-5, `spec-freecad-buddy/SPEC.md:120` and six design files describe `script_exec` as raw: outside the AD-5 bracket, no fingerprint, no rollback, in the operator-only `debug_` group. CAP-7 of the usage-improvement SPEC wants all documents to state one role: typed tools first, `script_exec` for listed gaps, run in an observe-only bracket. Deferred item `deferred-work.md:1714` records that the `script_exec` audit record shape in `security-and-service-design.md` §1 differs from the code.

**Approach:** Edit documents only. Replace the raw-exec wording with the observe-only bracket of `tool-contracts.md` T-6 (with decisions 4, 5, 9 of `epic-13-decisions.md`), give `script_exec` its own escape-route row, add the `exec.python_error` detail code, and correct the audit sample. Documents describe the target contract; Story 13 implements it.

## Boundaries & Constraints

**Always:** Target-contract wording only, no change-log narration, no "implemented" claim. Caveman + ASD-STE100 for new text; code, field names and tables keep normal form. Bump each edited file's front-matter date to `2026-11-24` (spine: `updated`; SPEC.md has none). Observe-only bracket = fingerprint before, bridge transaction opened first, run, recompute unless `recompute: false`, commit, fingerprint after, `changed`, `new_errors`; no post-verify, TNP audit, abort or rollback; changes kept on every outcome.

**Decisions (user, 2026-11-24):** remove `debug_` from the wire-prefix lists (`ARCHITECTURE-SPINE.md:375`, `mcp-tools-design.md:18`). AD-5 says only `A TIMEOUT follows AD-27`; Story 13-13 decides commit or abort. Edit `integration-mcp-freecad.md:102`, not `:279`. `SPEC.md:120` gets both clauses. Add one sentence at `mcp-tools-design.md:60`: a string longer than 80 characters or holding a line break renders `key: <N chars>` in the `summary_text` fallback.

**Never:** No code, skill or test edits. No edit of `docs/intent.md`. No new status (AD-17 set stays closed). No reopening of decisions 4, 5, 9.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Script ran clean | `script_exec` | `OK`, result holds stdout, value_repr, fingerprint_before, fingerprint_after, changed, new_errors | N/A |
| New objects in error | script leaves errors | `RECOMPUTE_ERROR`, names them, changes kept | N/A |
| Script raised | Python exception | `INVALID_INPUT`, `detail.code: exec.python_error`, `data.exception`, `data.traceback`, partial changes kept | The one `INVALID_INPUT` where code ran |
| Own transaction | script opens one | FreeCAD commits the bridge transaction first; undo history splits | Limit documented, not refused |
| Timeout | over 30 s | `TIMEOUT`, document suspect (AD-27) | Late-return behavior left to Story 13 |

</frozen-after-approval>

## Code Map

Root `A` = `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21`; `D` = `A/design`.
- `src/freecad_buddy/usecases/script_exec.py:1-5,52` -- today raw, `"fingerprint_after": None`; read-only evidence, not edited.
- `src/freecad_buddy/adapters/audit_log.py:62-66,135-139` -- exec record: `schema, ts, actor:"operator", event:"exec", tool, params_digest, doc:{handle}, code`; `after` adds `fingerprint_before/after, verify_verdict, rollback`. Basis of the audit sample.
- `src/freecad_buddy/adapters/rpc_dispatch.py:153-157` -- today a script exception becomes `RECOMPUTE_ERROR`; target is `INVALID_INPUT` (Story 13).
- `A/ARCHITECTURE-SPINE.md:69,77` -- AD-4, AD-5.
- `D/mcp-tools-design.md:196-200,217,86,567,570` -- heading, row, counts, §1.4, §5 rules 4 and 7.

## Tasks & Acceptance

**Execution** (before text is the current line; after text is final):
- [x] `A/ARCHITECTURE-SPINE.md:69` (AD-4) -- replace `` `script_exec` runs outside the AD-5 bracket (see AD-5), is never a `preview_dry_run` operation `` with `` `script_exec` runs in the observe-only bracket of AD-5, is never a `preview_dry_run` operation ``.
- [x] `A/ARCHITECTURE-SPINE.md:77` (AD-5) -- replace the final two sentences (`Exception: script_exec runs raw. … its own transaction.`) with: `Exception: script_exec runs in an observe-only bracket: fingerprint before → bridge transaction opened first (named script_exec <first code line>) → agent code → recompute() unless the call sets recompute: false → commitTransaction → fingerprint after, changed (AD-6) and new_errors (objects in error after the run that were not in error before). It runs no post-verify and no TNP audit, and it never aborts or rolls back: the changes stay on every outcome, including a Python exception (INVALID_INPUT, detail.code exec.python_error) and new errors (RECOMPUTE_ERROR). The agent checks the result with the verify_* tools. One document_undo reverts the whole script, provable with expect_fingerprint against fingerprint_before, only when the script opens no transaction of its own: FreeCAD commits the active transaction when a new one opens, which splits the undo history. A TIMEOUT follows AD-27.` Spine front matter `updated: '2026-11-24'`.
- [x] `D/mcp-tools-design.md:196-200` -- heading `### \`debug_\` — operator-only (AD-4; never an AI surface)` → `### Escape route — \`script_exec\` (AD-4)`; row purpose `…raw, outside the AD-5 bracket; see §5` → `…for listed gaps; observe-only AD-5 bracket (automatic transaction, fingerprint, changed, new_errors, no rollback); see §5`.
- [x] `D/mcp-tools-design.md:217` -- row `` `debug_` (operator-only) | 1 | … `` → `` `script_exec` (escape route, outside `tool_specs()`) | 1 | — | — | — | 1 | 1 ``.
- [x] `D/mcp-tools-design.md:86` (§1.4) -- after `…re-hash-proven rollback) and returns a common \`mutation\` block inside \`result\`:` insert before it: `Exception: script_exec (Mut = yes) runs the observe-only bracket of §5 rule 4.`
- [x] `D/mcp-tools-design.md:567` (§5 rule 4) -- replace `**Raw.** No AD-5 bracket, fingerprint, or rollback (AD-5 exception).` with `**Observe-only bracket (AD-5).** The bridge fingerprints, opens its transaction before the script runs, recomputes unless recompute is false, commits, fingerprints again and lists changed and new_errors. No post-verify, TNP audit or rollback: changes stay. Statuses: OK; RECOMPUTE_ERROR when new objects are in error (message names them); INVALID_INPUT with detail.code exec.python_error (data.exception, data.traceback) when the script raised, partial changes kept and listed in changed (the one INVALID_INPUT where the code ran; detail.code tells it from a refusal before execution); TIMEOUT as AD-27. A script that opens its own transaction splits the undo history, so one document_undo then reverts only the last part.` Keep the rest of rule 4 (`mutating=True`, TIMEOUT marks the document suspect, audit pair).
- [x] `D/mcp-tools-design.md:570` (§5 rule 7) -- replace `result { "stdout", "value_repr", "fingerprint_after" }` with `input { "doc": handle, "code": string, "recompute"?: boolean (default true) }; result { "stdout", "value_repr", "fingerprint_before", "fingerprint_after", "changed", "new_errors" }` (fingerprints and changed as the §1.4 mutation block). Front matter `date: '2026-11-24'`.
- [x] `D/mcp-tools-design.md:18`, `A/ARCHITECTURE-SPINE.md:375` -- delete `` `debug_` `` from both prefix lists.
- [x] `D/data-contracts-design.md:61-62,63` -- add `"exec.python_error"` to the `code` examples; after the `WORKER_CRASHED` sentence add: `INVALID_INPUT means no execution, except script_exec: it returns INVALID_INPUT with code "exec.python_error" when the agent script raised after it started; data holds exception and traceback, and the partial changes stay in the document and in changed (AD-5).` Date bump.
- [x] `_bmad-output/specs/spec-freecad-buddy/SPEC.md:120` -- `typed-tools-only mutation (AD-4)` → `typed tools first, script_exec for listed gaps (AD-4)`; and `uniform mutation protocol with hash-proven rollback (AD-5/6)` → `uniform mutation protocol with hash-proven rollback for typed tools, observe-only bracket for script_exec (AD-5/6)`.
- [x] `D/component-design.md:43` -- `raw (AD-5 exception)` → `observe-only AD-5 bracket (no rollback)`. Date bump.
- [x] `D/project-structure.md:62` -- `on by default, raw, audit-logged (AD-4)` → `on by default, observe-only AD-5 bracket, audit-logged (AD-4)`. Date bump.
- [x] `D/sequence-diagrams.md:453` -- `Raw: no AD-5 bracket.` → `Observe-only AD-5 bracket: no rollback.`; diagram note `no fingerprint or rollback — the agent checks with verify_* afterwards` → `fingerprint_before, fingerprint_after, changed and new_errors; no rollback — the agent checks with verify_* afterwards`; add `Note over U: fingerprint → bridge transaction → run → recompute → commit → fingerprint` after the audit arrow. Date bump.
- [x] `D/security-and-service-design.md:84` -- Phase 2 row: after `AD-5 transaction + verify + proven rollback per mutation` insert `; script_exec runs the observe-only bracket (fingerprint, changed, no rollback)`; in the NOT-defended cell `every script_exec call is audited with its source` → `every script_exec call is audited with its source and its changes are listed`.
- [x] `D/security-and-service-design.md:42-52` (§1 item 3, closes `deferred-work.md:1714`) -- replace the `exec_call`/`exec_result` sample with two real `fcb.audit-record/1` lines: `{"schema":"fcb.audit-record/1","ts":"...","actor":"operator","event":"exec","tool":"script_exec","doc":{"handle":"<doc handle>"},"params_digest":"<sha256 hex>","code":"<full source>","fingerprint_before":null}` and `{…same keys…,"fingerprint_before":"<digest>","fingerprint_after":"<digest>","verify_verdict":"OK","rollback":null}`; add: `The before line is written ahead of execution, so it holds no fingerprint. verify_verdict holds the envelope status. actor is the sink's configured actor; the record carries no client identity.` Drop `code_sha256` and `caller`. Date bump.
- [x] `D/mcp-tools-design.md:60` -- after `compact \`key: value\` flattening (\`summary_text\`)` add: `A string longer than 80 characters, or holding a line break, renders as \`key: <N chars>\`, because structured_content already carries it.`
- [x] `D/integration-mcp-freecad.md:102` -- after `anything unexpected → RECOMPUTE_ERROR with detail.unexpected=true` add `; a Python exception raised by script_exec code is INVALID_INPUT with detail.code exec.python_error (AD-5)`. Date bump. `:279` is not edited.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md:1714` -- add `  resolution: resolved by spec-13-2-script-exec-role-docs: security-and-service-design.md §1 shows the code's record shape (event exec, params_digest, code, doc handle, actor operator).` Related `:1722` (actor) stays open.

**Acceptance Criteria:**
- Given the nine named files, when the pattern `outside the AD-5 bracket|AD-5 exception|runs raw|raw, outside|, raw,|Raw\. No|\*\*Raw\.\*\*|Raw: no|typed-tools-only|never an AI surface|operator-only` is grepped, then the count is 0 (before: 10).
- Given AD-4, AD-5, `mcp-tools-design.md` §5, SPEC.md:120, when read together, then each states typed tools first, `script_exec` for listed gaps, and the same observe-only bracket, with `recompute: false`, `fingerprint_before` and the own-transaction limit.
- Given `check_status_vocab.py` and `check_skill_shape.py`, when run, then both pass.
- Given the diff, when scanned, then it holds no history narration and no "implemented" claim.

## Implementation Notes

Implemented directly from this spec (documents only). `integration-mcp-freecad.md:279` unchanged by decision. Dates set to the run date 2026-11-24.

## Spec Change Log

## Review Triage Log

| Lens | Finding | Verdict | Route and evidence |
|------|---------|---------|--------------------|
| blind | `script_exec` has no wire prefix | low | patch: one-tool exception in both prefix lists |
| blind | AI-visible total omits `script_exec` | low | patch: total renamed "(typed tools)" |
| blind | undo proof vs byte-exact digest | false | `documents.py` `expect_fingerprint` matches on geometric invariants when a record is held |
| blind, edge | own-transaction, abort, empty-transaction, name rule, TIMEOUT late return | medium | defer to 13-13 (new deferred entry); patch: AD-5 wording "after the script returns" removes the AD-27 clash |
| blind, edge | `recompute: false` meaning | medium | patch: rule 4 sentence |
| blind, edge | status precedence | medium | patch: rule 4 sentence |
| blind | `INVALID_INPUT` changes AD-17 meaning and skills | low | false for AD-17 (no such clause in spine); skills excluded by intent ("no skill edits"), Story 13-13 owns them |
| blind, edge | result fields on non-OK | medium | patch: rule 7 "with every status except TIMEOUT" |
| blind | flat result vs `mutation` block | low | patch: rule 7 "flat" |
| blind | no call id in audit pair | low | pre-existing for every tool; fix adds a field; rejected |
| blind, edge | audit "changes listed", digests null in code | medium | patch: security row wording; deferred-work resolution wording |
| blind | "listed gaps" has no list | low | rejected: the list is the `freecad-scripting-idioms` gap list (CAP-6, Story 13-4); wording user-approved |
| blind | `ad-refs` stale | low | patch: AD-27, AD-5, AD-17, AD-4 added |
| blind | diagram lacks `after` audit | low | patch |
| edge | other documents unobserved | low | patch: "observes only the document named by `doc`" |
| edge | audit optional keys | low | rejected: `script_exec` requires `doc` |
| edge | spec date mismatch | low | patch |
| gap | docs ahead of code | low | rejected: plan order (13-13 after 13-2) fixed; docs describe target by decision |

Round 2 (verifier F-1, F-2, red team RT-1 to RT-15, commit f38a027): all closed. Lenses r2: blind a514bb1be440bd744, edge ae7c7e212565e4c50, gap aa3b62d1f4c361223. Patched: `changed` wording (AD-6 invariants), undo-proof limit for property-only change, R3 not applicable, `document_undo` reason, audit after-line nulls and writer, stderr traceback, rule 4 sentence order, verification-design TIMEOUT scope. Deferred to 13-13 entry: bracket failure modes, closed document and `SystemExit`, `remember` of fingerprints, framing key after Visibility-only script. Rejected: security "defended" wording and boundary text (verifier wording; text pre-existing), trust diagram node, SPEC.md:120 detail (one-line constraint; AC 2 names sections, not that line), sample digests (target contract).

## Design Notes

Token count of this spec exceeds 1600: one goal, many before/after lines the user must approve. Keep full.

## Verification

**Commands:**
- `uv run python scripts/check_status_vocab.py` -- expected: OK
- `uv run python scripts/check_skill_shape.py` -- expected: exit 0
- the grep above over the nine files -- expected: 0 matches
- `git diff --stat` -- expected: only the files named above plus this spec
