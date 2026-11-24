# Story 13-9: red team report

Head `feac4bfd` (branch `story/13-9-varset-parameters`), base `28586faa`. Own worktree, removed after the run.
Probes ran in host `freecadcmd.exe` 1.1.4 with a private `-u`/`-s` cfg and `FREECAD_USER_HOME` set to a temp folder. Each probe printed `features.__file__` from the worktree `src`, so it tested the Story code and not the installed addon.
The probe scripts were in `scratchpad\redteam-13-9\` (`probe_fc.py`, `probe_fc2.py`, `probe_fc3.py`, `probe_tool.py`, `probe_undo.py`, `probe_undo2.py`). Each one writes `<script>.out`.
Run command: `"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -u <S>\user.cfg -s <S>\system.cfg <S>\<script>` with `FREECAD_USER_HOME=<S>\home`.

Ledger rows and the spec triage rows 1-27 are not reported again.

## Reproduced

| RT | Severity | Q | File:line | Finding |
| --- | --- | --- | --- | --- |
| RT1 | high | Q5 | `usecases/features.py:2082` (`setattr(target, name, spec["value"])`) | `document_undo` after a define that writes a string parameter with its current value reverts the PREVIOUS transaction. In the probe, that deleted a user object. |
| RT2 | high | Q5 | `usecases/features.py:2079` (`target.setGroupOfProperty(name, spec["group"])`) | `document_undo` does not revert the `group` and `description` that a define update changed. It returns `OK` and `matches_pre_op: True`. |
| RT3 | high | Q4 | `usecases/features.py:1995` (`if not isinstance(value, str):`) | A string value that holds `\x00` is cut at the NUL with no error, and the status is `OK`. |
| RT4 | medium | outside the rows (shared code, attack 2) | `adapters/rpc_dispatch.py:96` (`"code": getattr(exc, "code", None) or status,`) | Any exception that has a `code` attribute now sets `detail.code`. With `script_exec`, `detail.code` becomes an int (`5`, `404`), which the envelope schema refuses, or a bound method, which `json.dumps` cannot encode. |
| RT5 | medium | Q3 | `usecases/features.py:2032`, `:2150` | The tool accepts and creates a VarSet whose object Name is a unit symbol (`W`, `mm`, `e`). An expression `W.width` then fails to parse. This is the failure that the parameter-name refusal is there to prevent. |
| RT6 | medium | Q3 | `usecases/features.py:1931`; `usecases/transaction.py:148` | A parameter named `Shape` is not refused. It opens the bracket, makes the VarSet look shape-bearing to `post_verify`, and always rolls back as `SPEC_FAILED`: `AttributeError: 'str' object has no attribute 'Volume'`. |
| RT7 | low | Q2 | `usecases/features.py:2101` (`value = repr(getattr(target, prop))`) | A VarSet that holds an `App::PropertyPythonObject` gives a repr with a memory address. After a correct snapshot restore, the state probe does not match. The result is `SPEC_FAILED` with `rolled_back: False`, and the snapshot is kept, but the state is actually restored. |
| RT8 | low | Q8 / shared | `usecases/transaction.py:400` | The `RollbackNotProven` message now says "or the pre-mutation property state" for every tool, also for tools that have no state probe. The explanation text changes for all other tools. |

### RT1: undo reverts the wrong transaction (high, Q5)

FreeCAD records no undo transaction when a `PropertyString` gets its current value again (`UndoCount` stays the same). The tool still reports `OK` with `updated: ['note']`. The next `document_undo` then reverts whatever the user did before.

Reproduction (`probe_undo2.py`): define `note="rev A"`. The user commits a transaction that adds `UserBox`. Define `note="rev A"` again. Call `document_undo`.

```
define#1 OK; user box committed; UndoCount 2
define#2 (same string) OK updated=['note']; UndoCount 2
document_undo -> OK; UserBox still present: False; note='rev A'
```

`probe_undo.py` shows the same for a string parameter whose define changes only the group and description: `string same-value define -> OK UndoCount 2 -> 2 | undo -> OK | after undo: w = 'A'`. Here the undo reverted the earlier `B` back to `A`. Length and bool parameters do add a transaction (`2 -> 3`).

### RT2: undo leaves group and description changed (high, Q5)

`abortTransaction` and `undo` do not record `setGroupOfProperty` or `setDocumentationOfProperty`. Raw probe (`probe_fc.py`, B4): `after abort: NewF present: False group L: OtherGroup doc L: other doc L: 10.0 mm`.

Through the tool (`probe_tool.py`, T5): define `height=5 mm`, group `Size`, description `orig`. Then define `height=7 mm`, group `Changed`, description `changed`. Then call `document_undo(expect_fingerprint=<digest before>)`.

```
T5 update -> OK
T5 undo -> OK matches_pre_op: True
T5 after undo: height 5.0 mm group Changed doc changed
```

The rollback path is not affected. The state probe sees the group change and restores from the snapshot: T4 `RECOMPUTE_ERROR`, after the call `group Size doc orig`, and C3 `rollback_proven rolled_back_via_snapshot`. Decision 32 holds for the bracket. Undo has no such proof.

### RT3: NUL cuts the string with no error (high, Q4)

`probe_tool.py` T1: `{"name": "note", "type": "string", "value": "rev A\x00 DO NOT SHIP"}`

```
T1 NUL string -> {'status': 'OK', ..., 'added': ['note'], ...}
T1 stored value: 'rev A'
```

The raw probe gives the same result: `B3 NUL setattr -> 'a'`. JSON carries the NUL as `\u0000`.

### RT4: `exc.code` leaks into other tools' envelopes (medium)

The base used `"code": status`. In the head, a `script_exec` body that raises a stdlib exception with a `code` attribute changes the envelope (`probe_tool.py`, section A, through `MethodRegistry.dispatch`):

```
A ParseError -> status RECOMPUTE_ERROR detail.code 5 int | json ok
A HTTPError -> status RECOMPUTE_ERROR detail.code 404 int | json ok
A code-method -> status RECOMPUTE_ERROR detail.code <bound method E.code of E('boom')> method | json.dumps FAILS TypeError: Object of type method is not JSON serializable
```

Schema check (`uv run --extra dev python`, `jsonschema.validate` against `contracts/jsonschema/result-envelope.schema.json`): `INVALID: 404 is not of type 'string' ['detail', 'code']`.

`rpc_listener._write_frame` (`adapters/rpc_listener.py:490`) calls `json.dumps` without a fallback. For the method case, the connection handler would crash ("connection handler crashed") and the client would get no reply. That end-to-end result was not run (it needs a listener port).

Fix direction: read `code` only from `ParameterRefusal` (or `ValidationError`), and only when it is a `str`.

### RT5: VarSet named after a unit symbol (medium, Q3)

`probe_tool.py` T6:

```
T6 varset=W -> OK None | expression FAILS: Failed to parse expression 'W.width'
T6 varset=mm -> OK None | expression FAILS: Failed to parse expression 'mm.width'
T6 varset=e -> OK None | expression FAILS: Failed to parse expression 'e.width'
```

The raw probe B6 shows the same for `pi` and `deg`, and shows that `A1` parses. A workaround exists: `<<W>>.width` refers to the object by its Label. The tool description does not say this.

### RT6: parameter `Shape` (medium, Q3)

`probe_fc3.py` / `probe_fc3b.py` (`first=1.0`, then `Shape`):

```
Shape -> SPEC_FAILED mutation.spec_failed proof rolled_back_verified varset exists False | n/a
Shape -> SPEC_FAILED mutation.spec_failed proof rolled_back_verified msg AttributeError: 'str' object has no attribute 'Volume' varset exists False | n/a
```

The rollback is correct. But the name is never refused before the bracket, and the call can never succeed. A VarSet that already holds a `Shape` property (added through `script_exec`) makes every later define on that VarSet fail. The same probe showed that Python keywords and the names `Placement`, `Proxy`, `A1` and `x__` define and parse correctly.

### RT7: Python-object property makes a good rollback look unproven (low, Q2)

`probe_fc2.py` C2: the VarSet holds `ref` (`PropertyLink`) and `blob` (`PropertyPythonObject`). A failing update with a group change goes down the snapshot path.

```
C2 repr ref: <Part::Feature> repr blob: <probe_fc2.Blob object at 0x000001DAB4CA8610>
C2 failing define -> SPEC_FAILED rolled_back False rollback_proven None
C2 after: height 5.0 mm group Size snapshot kept C:\...\FCB_TMP_snap_iao8f7vm\c2.FCStd
```

The real state was restored (`5.0 mm`, `Size`). The error goes in the safe direction: the tool reports less than it achieved, never a false "verified". I deleted the snapshot folder that the probe left.

### RT8: message text for all tools (low)

`transaction.py:400` now writes `... pre-mutation fingerprint {digest} or the pre-mutation property state` on every unproven rollback, also for tools with `state_probe=None`. Seen in the code only. The other branches of `_prove_rollback`, `run_mutation` and `_feature_mutation` behave as in the base when `state_probe` and `report` are `None`. I read them for this check.

## Checked, no defect

- Rollback proof, decision 32. A failure after recompute (a bound `Box.Height` set to 0) restores the value, group and description, and reports `rolled_back_via_snapshot` (T4, C3). A repr of `Quantity` keeps full precision (`10.0000001 mm` differs from `10.0 mm`), so the probe does not miss small changes. A new VarSet whose define fails is removed (`Shape` case: `varset exists False`).
- A lone surrogate `\ud800` in a string never reaches FreeCAD. It is refused as `INVALID_INPUT` before the bracket (T2: width stays 10 mm, no `note`). A direct `setattr` gives `OSError Access violation` in raw FreeCAD (B2), so the early refusal matters. Whether a later change could move the digest step after the write was not tested.
- Unicode string `Ø 12 µm — 漢字 😀`: stored, and read back by `query_parameters`, equal to the input (T3).
- Integer bounds: `2**31` raises in FreeCAD on Windows (B7), and the tool refuses it. `-2**31` is accepted by FreeCAD but refused by the tool. That is conservative and harmless.
- Lexer list: function names (`sin`, `max`, `sum`, `and`, `not`, ...), `A1`, `inf`, `nan`, `_x` and `__` parse as `VS.<name>`. Only `min` fails, and it is in the list (B5).
- `query_parameters`: the fingerprint is the same before and after the call (Q). Pressure is read as `2500.0 kPa`, which is FreeCAD's `2500 kg/(mm*s^2)`. A dimensionless quantity gives `0.0`, unit null. A cell error gives a reason. A Vector gives null with a reason. A sheet with 3000 aliases: query in 0.01 s, 500 rows, `totals.spreadsheet_parameters: 3000`, `truncated: True`.
- The Story tests: 42 infc tests (`test_feature_parameters` plus the parameter classes of `test_query_tools`) pass in the worktree. `tests/external/test_parameters_contract.py`: 5 passed and 2 skipped. The two lexer tests skip because the `docs/references/FreeCAD` submodule is not checked out, which is also true in CI (`actions/checkout@v4`, no `submodules:`). Triage row 24 covers this.

## Not reproduced (low)

- With RT4's method-valued `code`, the RPC client gets no reply and the session drops. Inferred from `rpc_listener.py:490` and `:308`. No listener was run.
- `query_parameters` reports a spreadsheet value that is stale against its `contents` (`=5 in` with value `76.2 mm`), with no marker. Triage row 15 covers it (deferred).
- `query_parameters` does not list a non-aliased spreadsheet cell formula that reads a VarSet. Cell formulas are not `ExpressionEngine` entries, so this matches the spec text. A reader looking for every consumer of a parameter misses them (probe Q: `bindings []` with `A3 = VS.dist * 2`).
- No test of a Linux build (the container was not used).

## Verdict

**FAIL.** Three rows break. Q5: RT1, where undo can delete unrelated user work, and RT2. Q4: RT3. The rollback bracket itself (Q2, decision 32) held in every real failure I could force.
