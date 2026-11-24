---
title: 'script_exec observe-only bracket and error status'
type: 'feature'
created: '2026-11-24'
status: 'draft'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '28586faa3fb3c316b361e48df2a626ef0cf55a0e'
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `script_exec` (`usecases/script_exec.py`) runs raw: no transaction, no fingerprint, no `changed`. A script that raises gives `RECOMPUTE_ERROR` plus a GUI traceback notification. A script that raises `SystemExit` kills the RPC serve loop. CAP-4 and tool-contracts T-6 ask for the observe-only bracket that Story 13-2 wrote into AD-5. Eleven cases stay open in `deferred-work.md` (source spec `spec-13-2-script-exec-role-docs.md`). Each was measured in FreeCAD 1.1.4 (`freecadcmd`); results below.

**Approach:** Implement T-6 in `script_exec`: fingerprint, bridge transaction, script, recompute, commit, fingerprint. Rules for the open cases are in the matrix. No rollback, no post-verify, no TNP audit. AD-27 quarantine and the 30 s budget stay unchanged.

## Boundaries & Constraints

**Always:**
- Bracket order (T-6): `shim.enable_undo(doc)`, fingerprint before, remember it, record invalid objects, open transaction, run script, recompute (when Touched and `recompute` is not false), commit, close leaked transaction, fingerprint after, remember it, `new_errors`, `undo_steps`.
- The bracket binds `fingerprint` by name at import (`from ...fingerprint import fingerprint`). A script that patches the `fingerprint` module attribute (TC-08:430) cannot break the bracket.
- `shim.enable_undo` runs once, before the script. It never runs after: TC-05:279 and TC-08:837 set `UndoMode = 0` inside a script.
- The bracket never aborts and never rolls back (AD-5). The use case writes no audit line (decision 19); the adapters pass both digests to the `after` line.
- Result fields (flat, decision 18): `doc`, `stdout`, `value_repr`, `fingerprint_before` and `fingerprint_after` (bare digest strings), `changed`, `new_errors`, `undo_steps`.

**Never:** Add a status value. Bump RPC `contract_version`. Abort or restore a snapshot. Change `run_mutation` behaviour. Change other tools.

## I/O & Edge-Case Matrix

Measured = ran in `freecadcmd`; the probe scripts are listed in Implementation Notes after the run. "Rule" is the proposed behaviour.

| # | Case | Measured in FreeCAD 1.1.4 | Rule |
|---|------|---------------------------|------|
| 1 | Normal write | `Box.Width = 5`: 1 undo entry `script_exec doc.Box.Width = 5`; one undo reverts it | `OK`, `changed` lists `Box`, `undo_steps` 1 |
| 2 | Read-only script | `commitTransaction()` on an empty transaction is a no-op (`Document.cpp:464-472`: acts only when the document holds a transaction). `openTransaction` only sets an application-wide name (`Document.cpp:330-340`); it stays set after the commit (`getActiveTransaction()` still `["noop", 2]`). The next unrelated change, by any tool or the GUI, joins it and takes its name. Also true for a Visibility-only script (`Visibility` is not recorded) and for `UndoMode 0` | After the commit, if `App.getActiveTransaction()` is still set, call `App.closeActiveTransaction()`. Result `undo_steps` 0, so one `document_undo` would revert an earlier step: the field and the `text` say so |
| 3 | Script aborts its own transaction | `abortTransaction()` reverts the script's changes so far; undo count unchanged | Observed, not an error: `changed` empty, `undo_steps` 0 |
| 4 | Script opens and commits its own transaction | Opening a new one commits the bridge transaction (`Document.cpp:363-365`): undo entries `own`, `script_exec ...`: 2 entries; one undo reverts only the last | `undo_steps` 2. Limit documented (decision 5) |
| 5 | Script commits the bridge transaction, then writes | Later writes sit outside any transaction: not recorded, `document_undo` never reverts them | Not detectable. Documented in the tool description and skill |
| 6 | Script calls `doc.undo()` | Reverts the script's pending change only; the earlier step stays | Observed: `changed` and `undo_steps` show it |
| 7 | Transaction name | FreeCAD stores any string unchanged: blank code gives `script_exec ` (trailing space); a 815-char name, a comment first line, a tab, `é` and an emoji are stored as given | Name = `script_exec ` + first non-blank line, stripped, cut to 80 characters (the Undo list stays readable); no non-blank line gives `script_exec` |
| 8 | Script changes only another document | `A.commitTransaction()` does nothing (A holds no transaction). B holds a pending transaction named after A's bridge name, `B.HasPendingTransaction` is true, and the application-wide transaction stays open. B's later changes join it. `document_undo` on B refuses (open transaction) | Same close step as case 2. Then B holds one entry named `script_exec ...` and `document_undo` on B reverts it. A: `changed` empty, `undo_steps` 0. Fix the AD-5 sentence, which says that change stays after the undo |
| 9 | `openTransaction` refused | It never raises: it returns silently while FreeCAD is transacting (`Document.cpp:330-336`); a `None` name raises `TypeError` | Not reachable with a string name; no code for it. With undo unavailable the script still runs, `undo_steps` 0 |
| 10 | `fingerprint_before` raises | Cannot be provoked in FreeCAD; `SerializerUnavailable` is the known cause | Script is not run. `SPEC_FAILED`, `detail.code` `exec.bracket_failed`, `data.phase` `fingerprint_before` (precedent: `_setup_failed_envelope`, `transaction.py:412`) |
| 11 | Recompute, commit or `fingerprint_after` raises after the script | Not provoked: a failing Python feature leaves `recompute()` returning 1 with state `Invalid`, no exception | Changes stay. `RECOMPUTE_ERROR`, `detail.code` `exec.bracket_failed`, `data.phase`, `fingerprint_after` null; `INVALID_INPUT` wins when the script also raised. Covered by unit tests with a faked failure |
| 12 | Script closes its document | `closeDocument` also clears the application-wide transaction. Every later access to `doc` raises `ReferenceError` | `OK`, `fingerprint_after` null, `changed` and `new_errors` empty, `text` names the closed document. The handle is stale: the registry reports it on the next call |
| 13 | `SystemExit`, `KeyboardInterrupt`, `GeneratorExit` | `except Exception` misses all three. A test listener (`tests/external/test_rpc_listener.py` fixtures) with a method that raises `SystemExit` sends no reply, and the next session's request gets none: the serve loop thread ends. A `RuntimeError` gives `RECOMPUTE_ERROR` | Catch `BaseException` around `exec`: `INVALID_INPUT`, `exec.python_error`, `data.exception` `SystemExit`. Bracket completes |
| 14 | Script raises `ValueError` after one write | Control for `RuntimeError` in the same listener: `RECOMPUTE_ERROR` and a traceback on `sys.stderr` (`rpc_dispatch.py:88-90`), the GUI notification cause | `INVALID_INPUT`, `exec.python_error`, `data.exception`, `data.traceback` (4000 chars), `changed` lists the partial change, entry recorded. No stderr write: closes `deferred-work.md:1918` (GUI check by the verifier) |
| 15 | New invalid object (`Box.Length = 0`) | `isValid()` false after recompute; digest unchanged (a failed shape keeps its last good shape) | `RECOMPUTE_ERROR`, message names `new_errors`, changes kept, `undo_steps` 1 |
| 16 | `recompute: false` | Object stays `Touched` after the call (`['Touched']`) | No recompute; `new_errors` read as left; documented (§5 rule 4) |
| 17 | `TIMEOUT` late return | `Marshal(ThreadExecutor)`, script sleeps 1.5 s, budget 0.5 s: caller gets `MarshalTimeout` at 0.51 s. During the run `HasPendingTransaction` is true. The body then finishes recompute and commit by itself: `changed` `Box`, `Late`; one undo reverts both | The late body commits. Nothing aborts it. Amend AD-27, which says "aborted with rollback proved", for `script_exec`. A script that never returns keeps its transaction open: `document_undo` refuses it. The late body writes no audit line (decision 19); `TIMEOUT` stays the record |
| 18 | `undo_steps` with a full stack | The undo stack holds 20 entries; a real write leaves the count at 20 | Count by aligning `UndoNames` before and after, not by subtracting counts (measured: 1, read-only 0). Repeated names on a full stack can undercount; documented |
| 19 | Both fingerprints registered | `document_undo expect_fingerprint=<before digest>` after a pad: `matches_pre_op` true with `remember(before)`, false without it (bytes differ, invariants equal) | `result_projection.remember` on both records |
| 20 | AD-32 framing key after a Visibility-only script | `fingerprint_after` equals `fingerprint_before` (digest ignores `Visibility`); the cache key is digest, camera, size (`framing.py:270-292`), so a Visibility-only script serves the old verdict | `script_exec` envelope skips the framing cache (`checked: computed`): one GUI projection per call. `feature_set_parameters {"Visibility"}` has the same gap: new deferred entry, not fixed here |
| 21 | RPC `contract_version` (AD-28) | `rpc_listener.py:135` and `rpc_client.py:154` default `"1"`; `git log -S` finds no bump, including `fcb.mutation/1` to `/2` | No bump. Frame unchanged; fields additive; `INVALID_INPUT` is existing vocabulary (`detail.code` separates it) |

**Cost (two fingerprints, 30 s budget):**

| Document | `fingerprint` cold | warm, nothing changed | after one edit | two cold (worst) |
|----------|-------------------|----------------------|----------------|------------------|
| 32 objects (box, cylinder, cut, fillet) | 0.21 s | 0.001 s | 0.027 s | 0.41 s |
| 184 objects | 0.99 s | 0.004 s | 0.018 s | 1.98 s |
| 30 objects, 406 faces each | 3.46 s | n/a | 0.09 s | 6.9 s |

Typical call: 0.03 to 0.1 s. Worst: 6.9 s of 30 s. Touched scan 0.06 ms, invalid scan 0.04 ms. The fingerprints run inside the registry lock (`deferred-work.md:599`): the added time is the same figures. Keep 30 s.

## UAT fixtures that change

Fix = add `recompute: false` (decision 4) unless stated. Text "opens no transaction, so `document_undo` does not revert it" is stale in each file and is corrected.

| Fixture | Why it breaks | Fix |
|---------|---------------|-----|
| TC-06:503, TC-12:418, TC-13:911 | Expect the pad `Touched` after the call | `recompute: false` (case 16) |
| TC-02:269 | Breaks the Pad, expects a later `document_recompute` to find the error | `recompute: false`; else `script_exec` itself returns `RECOMPUTE_ERROR` |
| TC-13:410 | Breaks the Pad with its own `recompute()`, expects `OK` | Expect `RECOMPUTE_ERROR`, `new_errors` `["Pad"]`; `value_repr` still names the state |
| TC-10:470 | Adds a feature whose `execute` sleeps 130 s; the bracket recompute runs it inside `script_exec` and times out | `recompute: false` |
| TC-08:843, :846 | Box creation and `Length = 0` become undo entries; the later `document_undo` expectations (`undone` is `buddy: ...`, second undo gives empty stack, `Box` in `errors`) fail | Start each script with `FreeCAD.closeActiveTransaction()` (measured: no entry, `undo_steps` 0, later undo leaves `Box2` invalid); `:846` also `recompute: false` |
| TC-08:430 | Plants a raising `fingerprint.fingerprint` | None: the bracket binds by name (measured: `OK` with the module attribute raising) |
| TC-05:434, :482, :711 | Patch `transaction.fingerprint`, `tnp_guard.snapshot_references` | None: the bracket uses neither |
| TC-05:279, :311, TC-08:837 | Set `UndoMode 0` and patch `shim.enable_undo` | None while `enable_undo` runs only before the script and `False` is tolerated |
| TC-12:361, :385 | Read `UndoNames`; first entry must start `buddy: ` | None, and only because of the case-2 close step: without it the leaked name hijacks the next GUI change |

## Open Questions

- New result field `undo_steps` (T-6 lists none): needed for cases 2, 4, 8. Options: add it (recommended; additive under AD-28) / leave the cases to the `text` only.
- Cache bypass for the framing read after `script_exec` (case 20): options: bypass (recommended; one projection per call) / leave the stale verdict and record a deferred entry.
- Status for a failed bracket phase (cases 10, 11, 12): options: `SPEC_FAILED` before the script, `RECOMPUTE_ERROR` after, `OK` with null fingerprint when the document is gone (recommended; keeps the closed status set) / `INVALID_INPUT` for a closed document.
- AD-27 sentence (case 17) is an architecture-tier edit in `ARCHITECTURE-SPINE.md`: approve the wording "for `script_exec` the late return commits; nothing aborts it".

## Code Map

- `src/freecad_buddy/usecases/script_exec.py:19-68` -- replace the raw exec with the bracket; add `recompute` parameter.
- `src/freecad_buddy/usecases/transaction.py:182` (`_invalid_objects`, private: promote to a public name) -- reused for `new_errors`; `result_projection.changed_objects`, `remember` -- reused. No other change to the module.
- `src/freecad_buddy/hosts/tool_catalog.py:1051-1085` -- `recompute` in `input_schema`, handler passes it, description rewritten (own-transaction limit, `undo_steps`, statuses); `with_framing` gets a bypass for `script_exec`.
- `src/freecad_buddy/adapters/rpc_listener.py:437-449`, `src/freecad_buddy/adapters/mcp_server.py:300-318` -- the `exec` `after` line takes `fingerprint_before` and `fingerprint_after` from the result (`audit_log.py:129` already accepts them).
- `src/freecad_buddy/contracts/envelope.py` (`summary_text` use) -- no change expected; check `text` of the new fields.
- `skills/freecad-scripting-idioms/SKILL.md:57` ("It runs raw") -- reverse (decision 5); `references/gap-list.md` rows that say no transaction.
- Design text: `ARCHITECTURE-SPINE.md` AD-27 and the AD-5 other-document sentence; `mcp-tools-design.md` §5 rules 4 and 7 (other document, `undo_steps`, close step); `verification-design.md` §1.1.1; `security-and-service-design.md` §1 (after line fingerprints); `data-contracts-design.md` (`exec.bracket_failed`).
- Tests: `tests/infc/` new `test_script_exec_bracket.py` (cases 1-19); `tests/external/` listener, dispatch and audit cases; fixtures in `tests/uat/testcases/` above.
- `deferred-work.md` -- resolve the 13-2 entry, `:1918` (after the GUI check), note `:599` figures; add entries for the Visibility gap and the missing late-body audit line.

## Tasks & Acceptance

**Execution:**
- [ ] `script_exec.py` -- bracket and rules 1-19 -- implements T-6
- [ ] `tool_catalog.py` -- `recompute` input, description, framing bypass
- [ ] `rpc_listener.py`, `mcp_server.py` -- exec `after` line carries both digests
- [ ] skill and design text -- reverse "runs raw"; AD-5 other-document sentence; AD-27 wording
- [ ] `tests/infc/test_script_exec_bracket.py`, `tests/external/*` -- one test per matrix row `test_Should_<outcome>_When_<condition>`
- [ ] `tests/uat/testcases/*` -- fixtures table
- [ ] `deferred-work.md` -- as in Code Map

**Acceptance Criteria:**
- Given a script that writes one property, when run, then `OK`, `changed` names the object, `undo_steps` is 1 and one `document_undo` with `expect_fingerprint` = `fingerprint_before` gives `matches_pre_op` true.
- Given a read-only script, when run, then `App.getActiveTransaction()` is `None` afterwards and `undo_steps` is 0.
- Given a script that raises `SystemExit`, when run through the listener, then the reply is `INVALID_INPUT` `exec.python_error` and the next call is served.
- Given a script that breaks a pad, when run, then `RECOMPUTE_ERROR` with `new_errors` and the change kept.
- Given a 30-object document of 406-face shapes, when `script_exec` runs, then the call stays under 30 s.

## Implementation Notes

Probe scripts (scratch, not committed): `p1_txn.py`, `p2_empty.py`, `p3_multi.py`, `p4_sysexit.py`, `p5_undo.py`, `p5b_undo.py`, `p6_cost.py`, `p6b_heavy.py`, `p7_rules.py`, `p8_full.py`, `p9_late.py` under the builder scratchpad. Re-run them before the final report.

## Verification

**Commands:**
- `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run python scripts/check_status_vocab.py`, `uv run python scripts/gen_schemas.py --check`, `uv run python scripts/check_skill_shape.py`
- `uv run pytest tests/external -q` (Git Bash) -- expected: pass except the known unstable test
- `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` -- expected: all pass
