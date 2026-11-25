# Story 13-13 build report

Branch `story/13-13-script-exec-bracket` (worktree `wt-13-13`). Spec: `spec-13-13-script-exec-bracket.md`, status done. Baseline `7549c1d4` (merge of `feat/epic-13-mcp-usage-improvement` @ 3df33fbd, no conflicts).

## Result

`script_exec` runs in the observe-only bracket (T-6): fingerprint, one transaction named `script_exec <first line>`, script under `except BaseException`, recompute when Touched, commit, commit of any leaked application-level transaction, fingerprint. Result: `doc, stdout, value_repr, fingerprint_before, fingerprint_after, changed, new_errors, undo_steps`. A raising script gives `INVALID_INPUT` `exec.python_error` and keeps its changes; no stderr write. Failed phases give `SPEC_FAILED` or `RECOMPUTE_ERROR` with `exec.bracket_failed`. New `recompute` input. Framing read for `script_exec` is fresh. The exec `after` audit line carries both digests. AD-27 and AD-5 sentences, skill and design text, UAT fixtures and deferred work updated.

## Commits

First commit `7fb24f1d`; the patch commit is on the branch head (`git log -2`). No push, no merge.

## Deviations from the spec / plan (all reported in the plan message except 3 and 4)

1. Close step is the commit form through new `shim.commit_active_transaction()` (accepted by the leader).
2. `changed` entries use the `ChangedObject` shape of `run_mutation`.
3. `invalid_objects` is NOT promoted in `transaction.py`: a bytes-level hash of that file pins the G2 `run_mutation` validator score (`benchmarks/runner.py:138`, test `test_leg_b_is_current_for_the_committed_g2_scores` fails after any edit). `script_exec.py` imports `_invalid_objects` under an alias, with a comment.
4. The framing test lives in `tests/external/test_framing_envelope.py` (fakes exist there), not `tests/infc/test_framing.py`.
5. Baseline commit in the spec moved to the merge head.

## Review (three opus lenses, effort high; round 1)

| Lens | Session id | Findings |
|------|------------|----------|
| Blind Hunter | a9f5fa9a96c918734 | 15 |
| Edge Cases Hunter | a17955ea4efab105b | 12 |
| Verification Gap Finder | ab6a30dde35796e38 | 5 + 1 other |

Triage table: spec section `## Review Triage Log` (23 grouped rows). Patched: transaction left open after a failed recompute (all three lenses), unguarded pre and post reads, traceback cut and bridge frame, undo-count on removal, undo-off note, schema and wiring tests, `remember` test, four stale UAT runner scenarios, doc gaps. Rejected: AD-27 release wording (approved text fixed), hostile `repr`, weak-test nits, AC3 through the real listener. Deferred: framing cache after a non-OK Visibility script, `usage_report.py` failure class. No fix round after the patches (bmad-build loops only on spec findings).

## Deferred work (deferred-work.md)

- Resolved: 13-2 entry; `:1918` code part (GUI check left to the verifier); `:599` figures noted.
- Added: `feature_set_parameters` Visibility framing gap (blocker none; unblock: fresh read or key component); late body after TIMEOUT writes no audit line (blocker: no hook; unblock: callback or AD-27 recovery Story); `usage_report.py` class for the new status (blocker: message-only `Call`; unblock: read `detail.code`).

## Tests run

- `ruff check .` all passed; `check_imports` OK; `check_status_vocab` OK; `gen_schemas --check` OK; `check_skill_shape` clean (SKILL.md 1496 words of 1500).
- `uv run --extra dev pytest tests/external -q` (Git Bash): 2117 passed, 6 skipped.
- freecadcmd `tests/run_tests.py` (private cfg, private `FREECAD_USER_HOME`): Ran 1295 tests, OK (skipped=1). New file `tests/infc/test_script_exec_bracket.py`: 41 tests; cost test printed `script_exec on 30 objects x 406 faces took 4.08 s` (full run) and 5.7 to 5.9 s (alone), budget 30 s.
- Mutants: abort instead of commit in the close step fails the case-8 tests (Q7); early return after a failed recompute fails its test; `fresh=False` fails the wiring test.
- Matrix audit: cases 1-19 have infc tests (5 by `document_undo`, 8 other document, 9 undo off, 10-12 faked, 13 `SystemExit` x3, 14, 15 box and pad, 16, 17 `Marshal` timeout, 18 full stack, 19 recall); 20 external framing; 21 no contract bump (no version test touched). Case 7 tab, `é`, emoji not tested (name function is pure slicing).

## Not verified (verifier, container)

Q15: live write then `document_undo`, `INVALID_INPUT` and bridge stays up, GUI undo list shows one named entry, no GUI notification badge for a failing script (`:1918`), `recompute: false` over MCP, the changed UAT fixtures and four runner scenarios (tc-02-06, tc-09-17, tc-09-18, tc-12-07), TC-08 fixtures with `closeActiveTransaction`, TC-03 edit-mode read-only probe with `recompute: false`. Behaviour measured in the unit run: `doc.undo()` alone in a script records one entry (`undo_steps` 1).

## Files

Source: `src/freecad_buddy/usecases/{script_exec,shim,framing}.py`, `hosts/tool_catalog.py`, `adapters/{rpc_dispatch,rpc_listener,mcp_server}.py`. Tests: `tests/infc/test_script_exec_bracket.py`, `tests/external/{test_rpc_listener,test_mcp_surface,test_framing_envelope,test_framing_contract}.py`. Skills: `freecad-scripting-idioms` (SKILL.md, gap-list), `code-cad-conversion` generator-kit. Design: spine AD-5 and AD-27, mcp-tools-design §5, verification-design §1.1.1, security-and-service §1, data-contracts, sequence-diagrams §8. UAT: TC-02, 03, 04, 05, 06, 08, 10, 12, 13 and four scenario JSON files.

## Review round 2 (fix diff 7fb24f1d..296f11f9)

Lenses (opus, high): Blind ac63858f9075cceee (9 findings), Edge a3d35b8def0d6ba58 (9), Gap a57eeae352a00d1da (2 + 3 other). Triage: spec `## Review Triage Log`, rows R2-1 to R2-12.
- Medium, patched (tests red first): a failing `document.commitTransaction` left the transaction open and lost the second failure; `undo_steps` overcounted after `doc.undo()` on a deeper stack (round-1 fix was incomplete); one failed observe read reported `undo_steps` 0 with a false note.
- Low, patched: pre-script read phase `observe_before`; closed-document commit guarded; tail-cut test now reaches 4000 characters; SyntaxError keeps no bridge frame; `observe` phase documented.
- Deferred: `closeActiveTransaction` under a GUI command guard (maybe-false, UAT probe settles it); `openTransaction` committing another caller's open transaction and `UndoMode 0` set by the script. Rejected: commit-then-write note (spec case 5), nested call, hostile repr.
- Gates after round 2: pytest tests/external 2117 passed, 6 skipped; freecadcmd Ran 1304 OK (skipped 1); bracket file 50 tests; AC5 timing 4.34 s; ruff, check_imports, check_status_vocab, gen_schemas --check, check_skill_shape clean.
