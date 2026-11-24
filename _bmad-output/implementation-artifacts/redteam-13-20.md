# Story 13-20: red team report

Diff: `b8fd4e0c...27d75a93` (branch `story/13-20-usage-report`). Own detached worktree at `27d75a93`, removed after the run.
Method: `bmad-code-review` lenses (blind adversarial, edge case, acceptance) applied inline.
Ledger items (R1-*, R1-D1, R1-D2, R1-A1) and the spec triage log are not re-reported.
Fixtures were synthetic and stayed in the scratchpad. Real transcripts were read only; this report holds counts and redacted shapes only.

Story gates run: `uv run pytest tests/external/test_usage_report.py tests/external/test_rpc_listener.py -q` gives `65 passed`; `check_imports OK`; `usage_report` is not referenced from `src/`, `scripts/build_addon.py` or `addon/` (Q6, Q8 hold).

Independent recount on the two evidence folders (own scanner, no import of `usage_report`), 2026-10-18..2026-11-18: 897 calls, 8 sessions, 896 results with a status, 1,074,339 result chars, 304,178 `text` chars (28.3%), `script_exec` OK 301 / RECOMPUTE_ERROR 11 / INVALID_INPUT 9 / TIMEOUT 4, 59 not-OK calls. All equal the report. No `tool_use.id` repeats across non-blob records (0 duplicates), 0 unparsable lines, every result is a plain string (1,052) or one text block (17), one spill in total (out of range).

## Reproduced

| Id | Severity | Q | Location | Defect |
|----|----------|---|----------|--------|
| RT-1 | medium | Q1 | `scripts/automation/usage_report.py:86-88` | Class "Loft, sweep, helix, thickness" never matches PartDesign features |
| RT-2 | medium | Q1 | `scripts/automation/usage_report.py:94` | Class "`script_exec` timeout" counts the timeouts of every tool |
| RT-3 | medium | Q1, Q3 | `scripts/automation/usage_report.py:49` (rule text at `:12`) | Calls of a server named other than `freecad-buddy` / `plugin_freecad-buddy_freecad-buddy` are dropped without a warning |
| RT-4 | medium | Q5 | `src/freecad_buddy/adapters/rpc_listener.py:271-273` | A deeply nested `rpc-*.json` makes bridge start raise `RecursionError` |
| RT-5 | low | Q1 | `scripts/automation/usage_report.py:57` | Attribute assignment after `;` on one line is read as read-only |
| RT-6 | low | Q3 | `scripts/automation/usage_report.py:268-271` | A result in a file that sorts before its `tool_use` file is lost |

### RT-1 Loft class misses PartDesign loft, pipe, helix, thickness

The pattern is `makeLoft|makeSweep|makeHelix|makeThickness|makePipe|Part::(?:Loft|Sweep|Helix|Thickness)`. PartDesign type names are `PartDesign::AdditiveLoft`, `PartDesign::SubtractiveLoft`, `PartDesign::AdditivePipe`, `PartDesign::AdditiveHelix`, `PartDesign::Thickness`; `Part::Loft` is not a substring of any of them.

Reproduction (synthetic, scratchpad `rt/repro.py`): one `script_exec` with code `body.newObject('PartDesign::AdditiveLoft', 'Loft')`.

```
RT-1: ['| PartDesign `newObject`/`addObject` | 1 |', '| Loft, sweep, helix, thickness | 0 |']
```

Real data (in range, 325 scripts): report class = 0. Scripts holding `PartDesign::(Additive|Subtractive)(Loft|Pipe|Helix)|PartDesign::Thickness` = 2 (one `AdditiveLoft`, one `SubtractiveLoft`). Scripts holding the bare word `Loft` = 14: 11 name an object `Loft_FloorCavity`, 3 name `Loft_FloorFacets`. This explains the "loft/sweep 0 vs 14 unexplained" part of R1-A1: the evidence 14 matched object names, the report regex matches no real loft creation, and the true value is 2. The `isValid` gap of R1-A1 is not a regex cause: `isValid` with or without `(` gives 122 in both cases, so that gap is data loss only.

### RT-2 "`script_exec` timeout" includes other tools

`FAILURE_CLASSES["`script_exec` timeout"]` is `marshaled call timed out` with no tool test. The triage applied a tool test to the `cannot write` class only.

Reproduction (synthetic): one `query_tree_summary` result `TIMEOUT: marshaled call timed out after 30 s`.

```
RT-2: ['| `query_tree_summary` | 1 | 0 | TIMEOUT 1 |', '| `script_exec` timeout | 1 | `TIMEOUT: marshaled call timed out after 30 s` |', ...]
```

Real data: the class shows 8. By tool: `script_exec` 4, `query_tree_summary` 4. The row label says `script_exec`, so half of the count is another tool.

### RT-3 Other server names are dropped

The module docstring rule (`:12`) says "a call is a `tool_use` whose name contains `freecad-buddy`". The code uses `mcp__(?:plugin_freecad-buddy_)?freecad-buddy__(.+)` with `fullmatch`, so `mcp__freecad-buddy-docker__*` (the UAT server name in this repo) gives 0 calls and no warning.

Reproduction (synthetic): one `mcp__freecad-buddy-docker__document_list` call.

```
RT-3: - 0 calls in 0 sessions (0 transcript files with subagents) between 2026-10-18 and 2026-11-18.
```

Real data: `uv run python scripts/automation/usage_report.py --since 2026-01-01 --until 2026-12-31 D--Work-Personal-Sources-freecad-buddy` prints `- 0 calls in 0 sessions`, while 110 lines in that folder's top-level transcripts hold `freecad-buddy-docker__` tool names (1,218 name occurrences incl. blobs over all files). The evidence folders use only the two matched names, so the Q2 numbers are not affected. A later success-signal run in a project whose server has another name reports 0 with no message.

### RT-4 Nested JSON crashes bridge start

`_sweep_orphan_discovery` catches `(OSError, ValueError, AttributeError)`. `json.loads` raises `RecursionError` (a `RuntimeError`) on deep nesting. `bind()` (`rpc_listener.py:186`) calls the sweep after the socket is bound; `start_bridge` (`hosts/gui_addon/bootstrap.py:187`) does not catch, so the bridge does not start and the own discovery file is not written. Before this Story, bind never read other files.

Reproduction (scratchpad `rt/bindcrash.py`, uses the test helpers of `tests/external/test_rpc_listener.py`): `rpc-99999999.json` holds `"[" * 200000`, then `RpcListener(...).start_threaded()`.

```
start_threaded raised RecursionError ; own discovery file written: ['rpc-99999999.json']
```

Trigger needs a crafted or corrupt file in the user's own FreeCAD data folder; no normal writer produces it. Q5 says unreadable JSON is kept; the file is kept, but the bridge start fails.

Also checked and correct: with the real `pid_alive` (no monkeypatch), a file of a live child process is kept and a file of an exited child process is deleted (`real live kept: True real dead deleted: True`).

### RT-5 One-line statements hide a mutation

`_MUTATION` uses `^[^#\n=]*\w\.\w+\s*=[^=]`. The prefix stops at the first `=` of the line, so `o = doc.getObject('A'); o.Placement = App.Placement()` is read-only.

```
RT-4: ['- `script_exec`: 1 calls = 100%. Read-only 1 (100% of calls), mutating 0.', '| Placement or `AttachmentOffset` write | 1 |']
```

(label `RT-4:` in the scratch output is this RT-5 case.) Real data: 7 in-range scripts are counted read-only and also in "Placement or `AttachmentOffset` write". Redacted line shape: `w=w.w(w); w=w.w.w(); w.w=w.w`. Read-only 191 would be at most 184.

### RT-6 Result read before its call is lost

`pending` is filled only by a `tool_use`; a `tool_result` met first is dropped. Files are read in sorted path order, so a result in `aaa.jsonl` for a `tool_use` in `bbb.jsonl` gives no status.

```
RT-5: ['| `document_list` | 1 | 0 | no status 1 |']
```

(label `RT-5:` in the scratch output is this RT-6 case.) Not seen in real data: 0 repeated ids, every result has its call in the same file. Low.

## Not reproduced

| Id | Severity | Claim | Why not reproduced |
|----|----------|-------|--------------------|
| NR-1 | low | Pid reuse race: the sweep reads `rpc-P.json` of dead pid P, a new FreeCAD gets pid P and writes the same path, then the sweep unlinks the new live file | Window is between `pid_alive` and `unlink` (microseconds); no reliable reproduction |
| NR-2 | low | On POSIX (the `fcb-desktop` container) an `rpc-x.json` that is a FIFO or a symlink to `/dev/zero` blocks or exhausts memory in `read_text` at bridge start | Not run: no container or Linux run in this task |
| NR-3 | low | Session count depends on UUID sort order when a resumed file repeats lines (the first file in sort order owns shared calls) | Real data has 0 repeated ids; effect not observable |
| NR-4 | low | Stale-handle text: no product emitter of the old text remains; `src/` has one constant used at `documents.py:393,408`; UAT scenarios and TC files carry the new text. Old text remains only in test doubles (`tests/external/test_framing.py:68`, `test_framing_contract.py:176`, `test_framing_envelope.py:74`, `test_render_probe.py:68`, `test_view_fit.py:144`, `test_run_mcp_e2e.py:46`) | Already rejected in the triage log; Q4 holds |

## Verdict

FAIL. Four open product mediums (RT-1, RT-2, RT-3, RT-4); no high. Q2 numbers are reproduced exactly by an independent scan; RT-1 corrects one cause in R1-A1 (loft) and shows the `isValid` gap is data loss only.
