# Story 13-13: red team report

Head: fba56e57 (`story/13-13-script-exec-bracket`). Diff attacked: 7549c1d4...fba56e57, last fix batch 2c925827...fba56e57 first.
Method: `bmad-code-review` lenses (adversarial, edge case, verification gap), run by the red team alone. Every claim below has a probe that ran under host `freecadcmd.exe` 1.1.4 with private `-u`/`-s` cfg files and a private `FREECAD_USER_HOME`, against an exported copy of fba56e57 (`freecad_buddy` imported from the copy, printed in each output).

Probe folder: `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\17c8e5ee-89aa-4e27-ba05-1fe1774e804a\scratchpad\redteam-13-13\probes\`
Command (Git Bash, from that folder; `S` = the `redteam-13-13` folder; the copy worktree was removed after the run, so re-create it with `git -C D:/Work/Personal/Sources/freecad-buddy-wt-13-13 worktree add --detach "$S/copy" fba56e57` first):

```bash
FREECAD_USER_HOME="$S/fchome" "/c/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" \
  -u "$S/cfg/user.cfg" -s "$S/cfg/system.cfg" "$S/probes/run_probe.py" probe_<x>.py
```

Outputs: `out_a.txt` … `out_d.txt` in the probe folder.

## Reproduced

| Id | Severity | Q | file:line | Probe |
| --- | --- | --- | --- | --- |
| RT-1 | high | Q3 | `src/freecad_buddy/usecases/script_exec.py:93`, `:104` | `probe_c.py` test C1 (real listener); `probe_a.py` P2, `probe_d.py` D1 (dispatch) |
| RT-2 | medium (product) | Q1, Q2 | `src/freecad_buddy/usecases/script_exec.py:79-84`, `:293-294` | `probe_a.py` P1 |
| RT-3 | medium (product) | Q1 (contract: "one `document_undo` reverts the script") | `src/freecad_buddy/usecases/script_exec.py:68-84`; `tool_catalog.py:1442-1443` | `probe_b.py` U1 |
| RT-4 | low | Q6 | `src/freecad_buddy/usecases/script_exec.py:278` | `probe_a.py` P3 |
| RT-5 | low (test double) | Q2 (G1 test) | `tests/infc/test_script_exec_bracket.py:788-817` | `probe_b.py` F1 |
| RT-6 | low | Q2 | `src/freecad_buddy/usecases/script_exec.py:293-294` | `probe_a.py` P5, P6 |

### RT-1 (high, Q3): a `SystemExit` from `repr(result)` or `str(exception)` escapes after the commit and stops the listener

The fix batch guards the two post-commit text conversions, but only against `Exception`:

```python
# script_exec.py:91-94  (_describe)
    try:
        text = str(exc)
    except Exception:  # noqa: BLE001 - a hostile __str__ must not break the envelope
# script_exec.py:102-104  (_value_repr)
    try:
        return repr(value), None
    except Exception as exc:  # noqa: BLE001 - the change is committed; report, never raise
```

The script runs under `except BaseException` (`:251`), so AC3 holds for a `SystemExit` the script raises. A `SystemExit` raised by a script-defined `__repr__` or `__str__` is raised after the commit, outside that guard. `MethodRegistry._invoke` catches only `Exception` (`rpc_dispatch.py:184`), the marshal re-raises `BaseException` on the listener thread (`marshal.py:77`), and `_serve_loop` catches only `Exception` (`rpc_listener.py:357`). The serve thread ends. The change is committed.

Inputs:
- `class H:\n    def __repr__(self):\n        raise SystemExit(3)\nresult = H()\ndoc.Box.Width = 5`
- `class E(Exception):\n    def __str__(self):\n        raise SystemExit(4)\ndoc.Box.Width = 5\nraise E()`

Output, `probe_c.py` (real `script_exec` handler behind real `RpcListener` and `RpcClient`, one dedicated executor thread as the Qt main thread):

```
test_C1_next_call_served_after_a_result_whose_repr_raises_system_exit ... listener connection dropped during script_exec: connection closed
    FACT first WORKER_CRASHED listener connection dropped
    FACT second TIMEOUT listener read timed out
FAIL
test_C2_control_next_call_served_after_a_script_raising_system_exit ...
    FACT first INVALID_INPUT
    FACT second OK
ok
```

Output, `probe_a.py` P2 and `probe_d.py` D1 (`MethodRegistry.dispatch`):

```
FACT escaped SystemExit(3) width 5.0 mm
FACT active transaction None
FACT escaped SystemExit(4) width 5.0 mm undo ['script_exec class E(Exception):'] active None
```

Context: R2-12 rejected "hostile `__repr__`" as low when it produced an error envelope. The fix batch now adds a guard and a test for a hostile `__str__` (`test_Should_return_invalid_input_When_the_script_error_has_a_str_that_raises`). The guard is incomplete. The result is a dead bridge, not an error envelope: the next call is not served until FreeCAD restarts. Fix: catch `BaseException` in `_describe` and `_value_repr`. `traceback.format_exception` (`:313`) also calls `str()` on the exception, through `_safe_string`, which catches only `Exception`. Guard that call too.

### RT-2 (medium, Q1/Q2): on a full stack of identical names, a script that writes reports `undo_steps` 0 and a false note

`_added_undo_steps` returns 0 when `after == before`. That happens when all 20 entries already carry the new call's name, for example 20 earlier scripts whose first line is `import Part`. The documented limits say a full stack can only overcount. The same text is in the docstring `:74-77`, in `mcp-tools-design.md` rule 4 and in the tool description: "high, up to 20, on a full stack".

Input: 21 calls of `import Part\ndoc.Box.Width = doc.Box.Width.Value + 1`, then one more.

```
FACT stack size 20 distinct names ['script_exec import Part']
FACT status OK undo_steps 0
FACT text '...undo_steps: 0\nvalue_repr: None\nundo_steps 0: this call recorded no undo step, so document_undo would revert an earlier step'
FACT width before/after call 41.0 mm 42.0 mm
FACT document_undo matches_pre_op True width after undo 41.0 mm
AssertionError: 0 != 1
```

The call recorded a step: one `document_undo` reverts it and `matches_pre_op` is true. The result says the opposite. A caller who trusts the note does not undo the script, or undoes it and believes it reverted an earlier step. A script that opens its own transaction on the same stack also reads low (it adds 2 and the count is 1). Possible fix: read `document.HasPendingTransaction` before the bracket's commit. When it is true, at least one entry was added, whatever the names say.

### RT-3 (medium, Q1 and contract): a script that calls `doc.undo()` reports `undo_steps` 1, and one `document_undo` does not revert it

The tool description (`tool_catalog.py:1442-1443`) says "a commit, so one `document_undo` reverts the script". AD-5 makes one exception: a script that opens its own transaction. A script that calls `doc.undo()` opens none. The entry the bridge records holds only the bridge's recompute, so `document_undo` cannot bring back the step the script undid.

Input: `doc.Box.Length = 11`, `doc.Box.Height = 12` (two calls), then `doc.undo()`.

```
FACT names before ['script_exec doc.Box.Height = 12', 'script_exec doc.Box.Length = 11'] after ['script_exec doc.undo()', 'script_exec doc.Box.Length = 11']
FACT status OK undo_steps 1 changed ['Box']
FACT text '...undo_steps: 1\nvalue_repr: None'
FACT Height after script 10.0 mm
FACT document_undo matches_pre_op False Height after undo 10.0 mm
```

`undo_steps` 1 and no note tell the caller that one `document_undo` reverts the call. It does not (`matches_pre_op` false). The existing test `test_Should_count_one_added_step_When_the_script_undoes_one_and_records_one` pins the count only, never the revert. The suffix alignment at `:82` is the sign that entries were removed. When it decides the count, add a note that `document_undo` cannot revert this call, and state the exception in the tool description and in AD-5. Control: `doc.redo()` gives `undo_steps` 2, which is accurate (`probe_b.py` U2).

### RT-4 (low, Q6): `sys.stdout.close()` in the script makes the post-commit `buffer.getvalue()` raise

This is the same class as R3-B1: an unguarded read after the commit. `ValueError` falls into the `INVALID_INPUT` branch of `rpc_dispatch.py:181`, with an empty result.

```
FACT status INVALID_INPUT detail {'code': 'INVALID_INPUT', 'message': 'I/O operation on closed file', ... line 278, in _run_bracket\n    "stdout": buffer.getvalue() ...}
FACT structured {}
FACT width 5.0 mm undo top ['script_exec doc.Box.Width = 5']
```

The result has no fingerprints and no `undo_steps`. The audit `after` line has no digests. The status reads as "nothing ran", but the change is committed. It is low because the script must close the process stdout.

### RT-5 (low, test double): `_RaisingDocument` defeats `shim.enable_undo`'s read-back

`shim.enable_undo(proxy)` sets `UndoMode` on the proxy object, because `__setattr__` is not delegated. It then reads the value back from the proxy, so it reports undo on while the real document stays at `UndoMode` 0. The recompute, commit and both-fail tests set `self.document.UndoMode = 1` first. `test_Should_report_null_undo_steps_and_no_zero_note_When_the_undo_list_read_raises` does not, and `document_create` does not enable undo. That test runs with undo off on the real document: the write is not recorded.

```
FACT enable_undo(proxy) True real UndoMode 0
FACT status RECOMPUTE_ERROR real UndoNames [] Width 5.0 mm
AssertionError: True != False
```

No false pass found: the test's assertions (`undo_steps` None, no zero note) do not depend on the recording. Fix: delegate `__setattr__` for non-underscore names in `_RaisingDocument`, or set `UndoMode = 1` in that test as the other proxy tests do.

### RT-6 (low, Q2): the zero-step note is false when the script empties the undo list

After `doc.clearUndos()` (P5) or `doc.UndoMode = 0` (P6) the stack is `[]`. The note says "so document_undo would revert an earlier step", but `document_undo` refuses ("nothing to undo" or "UndoMode 0").

```
P5: FACT status OK undo_steps 0 ... undo names [] ... 'undo_steps 0: this call recorded no undo step, so document_undo would revert an earlier step'
P6: FACT status OK undo_steps 0 ... FACT UndoMode 0 names []
```

## Not reproduced (held under attack)

- Q2/Q7, application-level transaction set by the script (`App.setActiveTransaction("mine")`, also with persist `True`): closed, no pending transaction, a later write is not joined (P7, P7b).
- Q7, a pending transaction in another document before the call: kept (`other.Box.Width` 6, one entry `user`, nothing active) (Q7). The document's own pending transaction before the call: committed, `undo_steps` 1, `matches_pre_op` true (Q7b).
- A script that writes `doc` and another document: one entry each, `document_undo(doc)` reverts only `doc`, `matches_pre_op` true (P4). The other document stays `Touched`, because the bracket recomputes only `doc` (P4b, by design: AD-5 observes only `doc`).
- Q1, `matches_pre_op` true after one `document_undo` for: delete object, add object, `recompute: false`, a document already `Touched` by an earlier `recompute: false` call, Body + Sketch + Pad built in one script (P8a-e).
- Fix-batch text paths: the `kept` note on a Label-only change then raise is absent, not false (P9). The changes are kept and `changed` is empty by the AD-5 definition.
- Q10 (code reading, no new probe): the headless front never ends the worker after a `TIMEOUT` (`hosts/headless/entry.py:88-94`). The GUI listener serializes on the main thread. Nothing in the timeout paths calls `abortTransaction` or `close_pending_transaction` for `script_exec`.
- Hostile cases with an `Exception` (not `BaseException`) inside `__repr__`/`__str__`: handled (covered by the batch tests).

## Verdict

**FAIL.** Reproduced: 1 high (RT-1, Q3: the listener stops serving) and 2 product mediums (RT-2 and RT-3, wrong `undo_steps` or wrong revert claim). Lows: RT-4, RT-5, RT-6.
