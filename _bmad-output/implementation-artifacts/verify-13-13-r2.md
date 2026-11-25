# Verify 13-13 round 2 at 73b9fe0f

Verifier: verifier-13-13. Date: 2026-11-25. Commit: `73b9fe0f` (worktree clean before the run). Batch under test: `fba56e57..73b9fe0f` (`src/freecad_buddy/usecases/script_exec.py`, `hosts/tool_catalog.py` description, `mcp-tools-design.md` §script_exec item 4).

**Verdict: FAIL on one Medium defect (D1, RT-3 fix incomplete).** All other checks pass: gates green, 11 of 11 mutants killed, red-team rows RT-1, RT-2, RT-4 and RT-6 closed, container cases pass.

## 1. Gates

| Gate | Result |
| --- | --- |
| ruff, check_imports, check_status_vocab, gen_schemas --check, check_skill_shape, check_provenance | all OK |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | **2117 passed, 6 skipped, 0 failed** (191.5 s) |
| `freecadcmd ... tests/run_tests.py`, private cfg and `FREECAD_USER_HOME` | **Ran 1320 tests, OK (skipped=1)**; AC5 `30 objects x 406 faces took 3.83 s` |

## 2. Mutants

`git archive 73b9fe0f` into `scratchpad/verifier-13-13/rt2/copy` (removed after). Runner: `test_script_exec_bracket.py` only (66 tests), baseline 66/66 OK.

| Mutant | Result |
| --- | --- |
| M1 `document.commitTransaction()` skipped | KILLED, 2 failures |
| M2 `shim.commit_active_transaction` no-op | KILLED, 5 failures + 1 error |
| M3 `_value_repr` guard removed | KILLED, the exception ended the test process |
| M4a / M4b undo alignment cut to one side | KILLED, 4 / 2 failures |
| M5 script `except BaseException` -> `Exception` | KILLED, the process ended |
| N1 `_describe` narrowed to `Exception` | KILLED, the process ended |
| N2 `_value_repr` narrowed to `Exception` | KILLED, the process ended |
| N3 `_CapturedOutput.close` calls `super().close()` | KILLED, 1 error (`test_Should_return_the_printed_text_When_the_script_closes_stdout`) |
| N4 full-stack-unknown branch removed | KILLED, 1 failure (`..._When_the_stack_is_full_of_one_name`) |
| N5 undid-entries note removed | KILLED, 1 failure (`test_Should_note_that_document_undo_cannot_restore_When_the_script_calls_doc_undo`) |

## 3. Red-team probes and new attacks

Red-team `probe_a..probe_d` copied and run against the 73b9fe0f copy (outputs `scratchpad/verifier-13-13/rt2/out_a..d.txt`). The probes assert the pre-fix contract, so P1, U1 and F1 fail by design. I checked each row against the new contract with my own probes (`tests/uat/run/13-13-r2/evidence/probe_v.py`, `probe_v2.py`, outputs `out_v.txt`, `out_v2.txt`).

| Row | Result |
| --- | --- |
| RT-1 next call served | CLOSED. `probe_c` C1 (repr raises `SystemExit`): first `OK`, second `OK`; `probe_d` D1 (exception `__str__` raises `SystemExit`): envelope returned, nothing escaped. Live: `value_repr` `<repr failed: SystemExit: 7>` with status `OK`; `E: <str failed>` with `INVALID_INPUT`; same FreeCAD pid after both |
| RT-2 null + note | CLOSED. 20 entries all `script_exec import Part`, then a write: `undo_steps` null, note `undo_steps null: the undo list is full of identical entries, so the count is unknown` |
| RT-3 note | PARTLY CLOSED, see D1. Two earlier entries, script undoes one: note present (`probe_b` U1, infc `:912`). Script undoes every earlier entry: no note |
| RT-4 stdout kept | CLOSED. `print('kept line')`, then `sys.stdout.close()`: status `OK`, `stdout` `'kept line\n'`, fingerprints present (live too: `stdout: <10 chars>`) |
| RT-6 note | CLOSED. `doc.clearUndos()` and `doc.UndoMode = 0` after a write: `undo_steps` 0 with `undo_steps 0: the script switched undo off or emptied the undo list, so document_undo cannot revert earlier steps` |
| Redo after `document_undo`, script calls `doc.redo()` | `undo_steps` 2 (`['script_exec doc.redo()', 'script_exec doc.Box.Height = 13', ...]`): the redo restores its entry and the bracket adds one more. One `document_undo` gives `matches_pre_op` false. The count is right and the docs say `undo_steps` > 1 splits the history. No defect |
| Script `doc.undo()` then `doc.redo()` | `undo_steps` 1, `changed` [] (an empty extra entry). No defect |
| Script undoes two of three entries, then writes | `undo_steps` 1 and the undid note. PASS |
| Script undoes an entry with its own name, then writes | `undo_steps` 0 and the "earlier step" note; `document_undo` gives `matches_pre_op` false. This is the documented repeated-name limit (`script_exec.py` `_added_undo_steps` docstring). Low, no new defect |
| `__repr__` returns a 5,000,000-character string | `OK`, `value_repr` 5,000,000 characters, no cap. Behavior from before the Story (`7549c1d4` `script_exec.py:59` `repr(value)`). Low observation |
| `__repr__` returns an `int` | `OK`, `value_repr` `<repr failed: TypeError: __repr__ returned non-string (type int)>` with the note. PASS |
| `KeyboardInterrupt` in a FeaturePython `execute` during the bracket recompute | FreeCAD turns it into an object error: `RECOMPUTE_ERROR` `new_errors` [K], nothing escaped. PASS |
| `KeyboardInterrupt` during the commit (script patches `shim.commit_active_transaction` to raise) | The exception escapes `MethodRegistry.dispatch` (`_close_bracket` catches `Exception` only, `script_exec.py:258-271`; dispatch catches `Exception` only, `rpc_dispatch.py:_invoke`). After it: no open transaction, the write committed, the next call `OK`. It needs a script that patches bridge code, and the tool is not a sandbox. Low observation, not a Story defect |

### D1 (Medium): no note when a script undoes every earlier entry

- Case: a script calls `doc.undo()` until the undo list from before the call is empty (with or without a write after).
- Expected (triage T3, tool description `tool_catalog.py:1444`): "not when the script calls doc.undo() itself: a note says so".
- Observed (freecadcmd, `out_v2.txt`): `E1 before ['script_exec doc.Box.Height = 12'] after ['script_exec doc.undo()'] status OK undo_steps 1 undid_note False zero_note False matches_pre_op False`. Same result for two entries both undone (E2) and for `doc.undo()` alone (E3).
- Observed live (container, `tests/uat/run/13-13-r2/evidence/out-r2-e1.json`): `undo_and_write` `OK`, `undo_steps` 1, no note; then `document_undo` text `Undid 'script_exec doc.undo()' on V1313E1: did NOT restore the pre-op state (63e89b1f981c -> 07a23484713e).`
- Cause: `script_exec.py:186-188`:

  ```python
  def _undid_entries(before: list[str], after: list[str], added: int) -> bool:
      return after[added:] != before[: len(after) - added]
  ```

  When `after[added:]` is empty, both sides are `[]`, so lost entries always count as "the oldest entries a full stack drops", even on a stack far below 20.
- Suggested fix: allow dropped oldest entries only on a full stack, for example `kept = len(after) - added; return after[added:] != before[:kept] or (len(before) < _FULL_UNDO_STACK and kept < len(before))`, plus an infc test with one earlier entry (the current test `:912` uses two entries and undoes one).

## 4. Container (run `tests/uat/run/13-13-r2/`)

Setup: `build_addon.py --release`, `compose up -d --build` from wt-13-13; mount `D:\...\freecad-buddy-wt-13-13 -> /repo`; installed `script_exec.py` SHA-256 `c5a441d9...` = `git show 73b9fe0f:...`; first `fcb-freecad start` aborted (known), second start gave `freecad_pid` 746.

| Case | Result |
| --- | --- |
| Write + `document_undo` with `expect_fingerprint` | PASS. `write` `OK`, `changed` [Box], `undo_steps` 1; `document_undo` `Undid "script_exec doc.getObject('Box').Length = 25" on V1313R2: restored the pre-op state (273eefd0a4f2 -> 07a23484713e).`, `matches_pre_op` true; Length 10 mm |
| Failing script, bridge stays up | PASS. `SystemExit(3)` and `ValueError` after a write give `INVALID_INPUT` `exec.python_error` (the write is kept, `undo_steps` 1); repr raises `SystemExit` gives `OK` with `<repr failed: SystemExit: 7>`; `__str__` raises `SystemExit` gives `INVALID_INPUT` `E: <str failed>`; closed stdout keeps its text. `/healthz` pid 746 before and after; the next call is served |
| GUI after the failing scripts | PASS. Desktop capture: no dialog, no notification count in the status bar (`r2-after-failing-scripts-desktop.png`) |
| D1 live reproduction | FAIL as described above (`out-r2-e1.json`) |

Teardown: `fcb-freecad stop`; `compose down` from wt-13-13; `docker ps` shows no `fcb-desktop`. UAT files left uncommitted: `tests/uat/run/13-13-r2/`.

## Round 3 at 87d9cc49 (host only)

Batch: `dcacd4c7` (D1 fix) and `87d9cc49` (stack-length boundary). Only `script_exec.py` `_undid_entries` changed in `src/`:

```python
remaining = after[added:]
expected = min(len(before), _FULL_UNDO_STACK - added)
return remaining != before[: len(remaining)] or len(remaining) < expected
```

**Verdict: PASS. D1 is closed.**

| Check | Result |
| --- | --- |
| Static gates (ruff, check_imports, check_status_vocab, gen_schemas --check, check_skill_shape, check_provenance) | all OK |
| `pytest tests/external -q` | first full run: 1 failed, 2116 passed, 6 skipped. The failure is `test_mcp_cache_proxy.py::test_should_answer_both_calls_when_two_parallel_calls_meet_a_lost_session`, the known intermittent test. Alone it failed once and then passed 3 times. A second full run had the same single failure. The batch does not touch `scripts/` or the proxy |
| `freecadcmd tests/run_tests.py` (private cfg and `FREECAD_USER_HOME`) | Ran 1323 tests, OK (skipped=1) |
| D1 reproduction (`probe_v2.py`) | E1 (undo the only entry, then write), E2 (undo both entries, then write), E3 (`doc.undo()` alone): `undid_note True`. E4 (undo of an entry with the script's own name) stays the documented repeated-name limit: `undo_steps` 0, "earlier step" note |
| Boundary (`probe_v3.py`) | no note: 19+2 (`before 19 after 20 undo_steps 2`), 20+1, 18+2, 20+2, 3+1. Note: 19 entries then undo + write, 20 entries then undo + write |
| Mutant: old `_undid_entries` condition | RED, 2 failures (`..._When_the_script_undoes_every_earlier_entry_and_writes`, `..._When_the_script_undoes_the_only_earlier_entry_and_writes`) |
| Mutant: `min(...)` bound removed (`expected = len(before)`) | RED, 1 failure (`test_Should_not_note_an_undo_When_the_script_adds_two_entries_to_a_stack_of_19`) |

Limit (Low, not measured): the rule assumes a stack of 20 entries. In the GUI the size comes from the preference `MaxUndoSize` (`Gui/Document.cpp:540`, default 20), and Python cannot read it. With a smaller value, a write on a full stack would get the undid note when it should not. The `undo_steps` null rule and the documented overcount already assume 20.

Probe files: `tests/uat/run/13-13-r2/evidence/probe_v2.py` (round 2 copy) and `scratchpad/verifier-13-13/rt2/probes/probe_v3.py`; the mutant copy was removed.
