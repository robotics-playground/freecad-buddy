# Story 13-20 verification: usage report and bridge hygiene

Verifier: verifier-13-20. Date: 2026-11-24.
Artifact: commit `27d75a93455e369c11d8b672b149a16bee9ef3c1` on `story/13-20-usage-report` (base `b8fd4e0c`).
Verify copy: detached worktree `D:\Work\Personal\Sources\fcb-verify-13-20` at `27d75a93` (removed after the run).
Live evidence: `D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\13-20-r1\`.

## Verdict

**PASS on the code**, with one low defect in the report (D-1) and one test gap (G-1). Neither blocks.
Q2 (reproduce `usage-evidence.md` totals) cannot pass as written: the source transcripts are partly
deleted. The report and my independent scan agree exactly on the present data. R1-A1 stays open
for the user.

## 1. Gates (in the copy)

| Command | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run python scripts/check_status_vocab.py` | OK |
| `uv run python scripts/gen_schemas.py --check` | OK |
| `uv run ruff format --check` on the 6 changed Python files | 6 files already formatted |
| `uv run pytest tests/external -q` | **1896 passed, 4 skipped**, 0 failed (225 s). No flaky test failed this run. |
| `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg <scratch>\run_lifecycle.py` (runs `infc.test_document_lifecycle`) | **Ran 39 tests, OK** |

Import proof for the infc run: the wrapper puts the copy's `src` first and drops cached
`freecad_buddy` modules. It printed
`IMPORTED documents from: D:\Work\Personal\Sources\fcb-verify-13-20\src\freecad_buddy\usecases\documents.py`
and `HAS constant: True`. So the installed `Mod/FreeCADBuddy` copy did not shadow the test.

## 2. Mutants

Each mutant was applied to the copy, the named tests were run, and the file was restored with
`git checkout`. `git status` was clean after each.

| Id | Mutation | Red tests | Result |
| --- | --- | --- | --- |
| a | `rpc_listener.py`: `if pid == os.getpid() or pid_alive(pid):` → `if pid == os.getpid():` (sweep deletes a live-pid file) | `test_Should_keep_the_discovery_file_When_its_pid_is_alive`, `test_Should_keep_the_discovery_file_When_pid_alive_rejects_its_pid_as_out_of_range` | killed |
| b | `rpc_listener.py`: unlink the file in the `except (OSError, ValueError, AttributeError)` branch (deletes corrupt JSON) | `test_Should_keep_the_discovery_file_When_it_is_unreadable_or_has_no_integer_pid` | killed |
| b2 | `rpc_listener.py`: unlink the file when `pid` is not an int | same test as b | killed |
| c | `usage_report.py`: `folder.glob("*/subagents/*.jsonl")` → `"*/no-subagents/*.jsonl"` (drops subagent transcripts) | `test_Should_count_a_subagent_call_in_its_parent_session_When_it_lives_in_a_subagents_folder` | killed |
| d | `usage_report.py`: `if item["id"] in scan.seen:` → `if False and ...` (no dedup by `tool_use.id`) | `test_Should_count_a_call_once_When_a_resumed_session_repeats_its_tool_use_id`, `test_Should_pair_a_result_with_its_call_When_the_result_is_in_a_later_file`, `test_Should_ignore_tool_searches_outside_the_range_and_repeated_ones_When_counting_loads` | killed |
| e1 | date filter `<= until` → `< until` | `test_Should_include_both_boundary_days_When_the_range_is_inclusive` | killed |
| e2 | date filter `since <=` → `since <` | same test | killed |
| e3 | date filter on the UTC+7 date instead of the UTC date: `since <= (call.timestamp.astimezone(timezone.utc) + local).date() <= until` | none | **survived** (G-1) |
| f | `documents.py`: constant back to `"unknown or stale document handle: {doc}"` (infc via freecadcmd) | `test_unknown_handle_maps_to_invalid_input`, `test_stale_handle_after_close_maps_to_invalid_input`, `test_a_handle_to_a_document_closed_outside_the_registry_is_invalid_input` | killed |

**G-1 (test gap, low).** `tests/external/test_usage_report.py:97-111` asserts only
`assert len(target.calls) == 2`. Under UTC+7 the four fixture calls shift by one day each:
`before` (`2026-10-17T23:59:59Z`) enters and `last` (`2026-11-18T23:59:59Z`) leaves, so the count
stays 2. The test does not detect a filter on the local date. A fix asserts the ids
(`{"first", "last"}`). The product code is correct (`usage_report.py:315-319` filters on the UTC date).

## 3. Acceptance map (quality bar Q1..Q8)

| Q | Verdict | Evidence |
| --- | --- | --- |
| Q1 tables | PASS | Report run below prints totals, per-tool outcome, typed tools with 0 calls, script classes, failure classes, tool loading, `text` share. 26 unit tests pass. |
| Q2 reproduce evidence totals | **Cannot pass on present data; differences listed with causes** (section 4). Not a code defect. | Report = independent scan on every count I compared. |
| Q3 not inflated or lost | PASS | Mutants c, d, e1, e2 killed. Spill read: `test_Should_read_the_status_from_the_spill_file...`, persisted format, tree-summary spill tests pass. Boundary rule stated in the module doc (`usage_report.py:16-18`). Gap G-1. |
| Q4 stale-handle message | PASS | One constant `_STALE_HANDLE_MESSAGE` (`documents.py:42-44`) used at `documents.py:393` and `:408`. Mutant f killed. Live MCP text matches (section 5). Old exact text remains only in test doubles (`test_framing.py:68` and 4 similar) and in history run folders `tests/uat/run/2026-10-03-04/`; TC-09:617 uses the substring as a negative check, still valid. |
| Q5 sweep rule | PASS | Mutants a, b, b2 killed. Live: dead pid file deleted, pid 1 and corrupt file kept, own file written (section 5). |
| Q6 dev tool not shipped | PASS | After `build_addon.py --release`: no `usage*` entry in `dist/freecad_buddy-0.1.1-py3-none-any.whl` or `dist/FreeCADBuddy-0.1.1.zip`, no `usage_report` file under `dist/`; `grep -rn usage_report src` is empty. |
| Q7 fixtures redacted | PASS | All transcripts are synthetic, written to `tmp_path`; no fixture file; no project name or user path in the two test files. |
| Q8 rings | PASS | `check_imports OK`; `rpc_listener.py` (adapters) imports `usecases.process.pid_alive`: inward. |

## 4. Independent recount (Q2)

Folders, from `usage-evidence.md` Method/Scope: `D--Work-3D-Printers-Ender-3V2---Klipper` and
`D--Work-Personal-Sources-3d-print-models-funny-character` under `C:\Users\thuan\.claude\projects`
(read only).

My scan: own stdlib script (does not import `usage_report`). It walks every `*.jsonl` under each
folder with `rglob`, parses each line, takes `tool_use` items whose name contains
`freecad-buddy`, keys them by `tool_use.id`, and keeps the earliest UTC timestamp. Session = the
top-level file stem or the first folder name. Range by UTC date, inclusive.

Report command (from the copy):
`uv run python scripts/automation/usage_report.py --since 2026-10-18 --until 2026-11-18 D--Work-3D-Printers-Ender-3V2---Klipper D--Work-Personal-Sources-3d-print-models-funny-character`
(and `--since 2000-01-01 --until 2099-12-31` for all dates).

| Count | My scan, range | Report, range | Evidence | My scan, all dates | Report, all dates |
| --- | --: | --: | --: | --: | --: |
| Unique freecad-buddy calls | 897 | 897 | 1,221 | 1,069 | 1,069 |
| Sessions | 8 | 8 | 10 | 10 | 10 |
| Transcript files with calls | 12 | 12 | 18 | 14 | 14 |
| `script_exec` calls | 325 (36.2%) | 325 (36%) | 410 (34%) | 402 (37.6%) | 402 (38%) |
| `isValid(` scripts | 122 | 122 | 163 | 132 | 132 |
| Bounding box / volume scripts | 214 | 214 | 284 | — | — |
| Loft class, report regex | 0 | 0 | 14 | 0 | 0 |
| Scripts that create `PartDesign::AdditiveLoft` / `SubtractiveLoft` | 2 | not counted | — | 2 | not counted |
| Scripts with the word loft/sweep/helix/thickness (any case) | 35 | — | — | 42 | — |
| `text` share | — | 28% | 26% | — | 36% |

Present data: calls on UTC days 2026-10-26 (17), 11-04 (134), 11-09 (217), 11-11 (10), 11-12 (26),
11-13 (39), 11-14 (272), 11-15 (169), 11-18 (13), 11-21 (172). First call 2026-10-26. No call on
2026-10-18. Calls per folder (all dates): Ender 254, funny-character 815.

Other notes: 748 `tool_use` occurrences sit in `api-request-blob` records with no timestamp. Both
tools skip them; they repeat earlier calls. Report and scan agree on every count above, with
different ownership rules (first file in sorted order vs earliest timestamp).

### Causes of the differences

1. **Deleted transcripts (main cause).** The evidence covered 18 transcript files and 10 sessions in
   range; 12 files and 8 sessions remain. The earliest present call is 2026-10-26; the evidence
   names an Ender session of 2026-10-18 that loaded sketch and feature tools, and that session is
   gone. 324 calls (1,221 − 897) and 85 scripts (410 − 325) are missing. The ratios stay close:
   `isValid` 163/410 = 40% vs 122/325 = 38%.
2. **Range vs all dates.** Two of the 10 present sessions have calls only on 2026-11-21, after the
   range (172 calls). So the all-date total (1,069) differs from the range total (897).
3. **Loft class 0 vs 14.** Present scripts do contain loft work: 2 scripts create
   `PartDesign::SubtractiveLoft` / `PartDesign::AdditiveLoft` (session `8fded3b4`, 2026-11-14). The
   report regex does not match them (D-1). The remaining gap to 14 cannot be explained from present
   data: the evidence regex is not recorded, and a loose word match gives 35, mostly object names
   such as `Loft_FloorCavity`. The deleted sessions are the likely source; this is not provable now.
4. **`text` share 28% vs 26%.** Different call set (cause 1). Not a method difference I could find.

### D-1 (report defect, low)

`scripts/automation/usage_report.py:86-88`:

```python
"Loft, sweep, helix, thickness": re.compile(
    r"makeLoft|makeSweep|makeHelix|makeThickness|makePipe|Part::(?:Loft|Sweep|Helix|Thickness)"
),
```

`Part::(?:Loft|...)` never matches the PartDesign type names `PartDesign::AdditiveLoft`,
`PartDesign::SubtractiveLoft`, `PartDesign::AdditivePipe`, `PartDesign::AdditiveHelix`,
`PartDesign::Thickness`. Reproduction: on the range above the class prints `0`, while 2 in-range
`script_exec` scripts call `body.newObject('PartDesign::SubtractiveLoft', ...)` /
`'PartDesign::AdditiveLoft'`. Effect: the class that SPEC uses as capability-gap evidence
under-counts PartDesign lofts, sweeps and helixes. Not fixed (verifier role).

## 5. Bridge hygiene, live (container `fcb-desktop`)

Setup from the copy: `uv run python scripts/build_addon.py --release`, then
`docker compose -f tests/close-loop/docker/compose.yaml up -d --build`. The installed
`Mod/FreeCADBuddy/freecad_buddy/adapters/rpc_listener.py` holds `_sweep_orphan_discovery`.
Discovery folder: `FreeCAD.getUserAppDataDir()/freecad-buddy` (`rpc_listener.py:59-68, 230-232`) =
`/home/cua/.local/share/FreeCAD/v1-1/freecad-buddy`.

| Step | Observed | Evidence |
| --- | --- | --- |
| Before `fcb-freecad start`, plant 3 files | `rpc-999999.json` (pid 999999, `kill -0` fails: no such process), `rpc-1.json` (pid 1 = `supervisord`, live), `rpc-777777.json` (`not json`) | `01-planted-before-start.txt` |
| Start FreeCAD | `/healthz`: `freecad_pid` 636 | `02-healthz.json` |
| After start | `rpc-999999.json` **absent**; `rpc-1.json` **present**; `rpc-777777.json` **present**; own `rpc-636.json` written, mode `-rw-------` | `03-after-start.txt` (tokens redacted) |
| Stale handle over MCP (Python `mcp` client to `http://127.0.0.1:18765/mcp`) | Never-issued handle on `document_close`: `INVALID_INPUT`, message `unknown or stale document handle: fcb-doc:does-not-exist; call document_list for the current handles`. Same on `query_tree_summary` as text `INVALID_INPUT: unknown or stale document handle: fcb-doc:does-not-exist; call document_list for the current handles`. After `document_create {label: Verify1320}` and `document_close`, the closed handle `fcb-doc:uXLW0DqdHiQ8SwH0xyQKVA` gives the same new message on `document_close`, `query_object`, `query_tree_summary`. | `05-mcp-stale-handle-attempt2.txt` (attempt 1, `04-...`, used a wrong `name` input for `document_create`; its never-issued checks are the same) |
| `addon.log` | dispatch lines carry the new message; no error, traceback or segfault in `addon.log` or `/tmp/freecad.log` | `06-addon-log.txt` |
| Visual check | Screenshot after the calls: FreeCAD 1.1.4 main window, Model tree empty, only the Start tab (the created document is closed), no error dialog. First-run welcome panel is the normal fresh-profile view. | `07-desktop-after-calls.png` |
| `fcb-freecad stop` | own `rpc-636.json` removed; `rpc-1.json` and `rpc-777777.json` stay | `08-after-stop.txt` |

Teardown: `fcb-freecad stop`, `docker compose ... down`. Container and network removed; port 18765 closed.

## 6. Notes outside the bar

- The live pid kept in the run is pid 1 (`supervisord`). I did not record its owner. If it is root,
  `os.kill(1, 0)` from user `cua` takes the `PermissionError` path of `pid_alive`, not the plain
  success path. A same-user live pid was not planted live; the unit test covers it with
  `pid_alive` monkeypatched.
- Rejected and deferred items in the spec triage (R1-D1 stat race, R1-D2 spill path with a space) were
  not re-judged.

## 7. Commands and scripts

- Recount script: `<scratchpad>\recount.py` (stdlib only, run with `uv run python -I`).
- Mutation helper: `<scratchpad>\mutate.py` (exact single-occurrence string replace).
- infc wrapper: `<scratchpad>\run_lifecycle.py`; private cfg in `<scratchpad>\fccfg\`.
- MCP client: `<scratchpad>\mcp_stale.py`.

## Round 2 (head `3864c166afabba8db1466489cbb9bb3f2c2aabd1`)

Fixes under test: `8392d7f5` (triage fixes) and `3864c166` (lens fixes), against
`triage-13-20-r2.md` (RT-1 .. RT-6, G-1). Fresh detached copy at `3864c166`, removed after the run.
Scratch: `<scratchpad>\verifier-13-20\`.

### Verdict

**PASS.** Every fix has a test that goes red when the fix is reverted. The report and my
independent scan agree on every count, including the new class counts. No new defect found.

### Gates

| Command | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run ruff format --check` on the 4 changed Python files | 4 files already formatted |
| `uv run pytest tests/external -q` | **1920 passed, 4 skipped**, 0 failed (209 s) |

### Revert each fix → its test goes red

Each revert was applied to the copy, the test file was run, and the file was restored (`git status` clean).

| Row | Revert | Red tests |
| --- | --- | --- |
| RT-1 | loft regex back to `...\|Part::(?:Loft\|Sweep\|Helix\|Thickness)` | `test_Should_match_the_loft_class_When_the_code_creates_a_partdesign_or_part_loft_shape` |
| RT-2 | drop `tool="script_exec"` from the `script_exec` timeout class | `test_Should_count_a_timeout_in_the_row_of_its_own_tool_When_a_typed_tool_times_out` |
| RT-3 | `_TOOL_NAME` back to `mcp__((?:plugin_freecad-buddy_)?freecad-buddy)__(.+)` | `test_Should_count_a_call_of_every_server_When_its_name_contains_freecad_buddy` |
| RT-4a | per-file `except Exception` → `except OSError` | `test_Should_bind_and_write_the_own_file_When_a_discovery_file_is_nested_too_deep`, `test_Should_keep_the_discovery_file_When_pid_alive_rejects_its_pid_as_out_of_range` |
| RT-4b | size / regular-file guard → `if False:` | `test_Should_keep_the_discovery_file_When_it_is_larger_than_a_discovery_record` |
| RT-4c | `except OSError` around `directory.glob` → `except ZeroDivisionError` | `test_Should_not_raise_When_the_discovery_directory_cannot_be_listed` |
| RT-5 | `_is_mutating` back to the round-1 `^[^#\n=]*\w\.\w+\s*=[^=]` MULTILINE regex | 9 cases of `test_Should_count_the_script_as_mutating_When_the_code_assigns_an_attribute` (incl. `o = doc.getObject('A'); o.Placement = P`, `o.Length += 1`), 2 cases of `..._read_only_When_the_code_assigns_no_attribute` (`print(f'{o.Length=}')`, `print('a; b.c = 1')`), `test_Should_scan_statements_When_the_code_does_not_parse` |
| RT-5b | statement fallback for unparsable code → `False` | `test_Should_scan_statements_When_the_code_does_not_parse` |
| RT-6 | `elif call_id not in known_ids:` → `elif False:` (no orphan results) | `test_Should_pair_a_result_with_its_call_When_the_result_file_sorts_before_the_call_file`, `test_Should_pair_a_tool_search_result_with_its_call_When_the_result_file_sorts_first` |
| RT-6b | ToolSearch orphan pairing → `if False:` | `test_Should_pair_a_tool_search_result_with_its_call_When_the_result_file_sorts_first` |
| G-1 (e3) | date filter on the UTC+7 date | `test_Should_include_both_boundary_days_When_the_range_is_inclusive` (now asserts `{"tool_first", "tool_last"}`) |
| G-1 (e1) | `<= until` → `< until` | same test |

### Sweep on the host (RT-4, real `pid_alive`, no monkeypatch)

`<scratchpad>\verifier-13-20\sweep_host.py` calls `RpcListener._sweep_orphan_discovery` on a temp
folder with 4 files:

```
LOG freecad_buddy.rpc_listener WARNING discovery sweep kept rpc-11111111.json after RecursionError
before ['rpc-11111111.json', 'rpc-12468.json', 'rpc-22222222.json', 'rpc-31256.json']
after  ['rpc-11111111.json', 'rpc-12468.json', 'rpc-22222222.json']
dead deleted: True | live kept: True | nested kept: True | oversize (dead pid) kept: True
```

`rpc-31256.json`: exited child pid → deleted. `rpc-12468.json`: parent shell pid (live) → kept.
`rpc-11111111.json`: `"[" * 50_000` → `RecursionError` caught, one log line, kept, sweep went on.
`rpc-22222222.json`: dead pid padded to 64 KiB + 1 → kept. FIFO case not run: Windows host has no
FIFO; the guard is `path.is_file()` (`rpc_listener.py` `_sweep_one`). Container not started.

### Recount (2026-10-18..2026-11-18, the two evidence folders)

Own scan `recount2.py` (stdlib, no `usage_report` import): server = the `mcp__<server>__` part
containing `freecad-buddy`; dedup by `tool_use.id`, earliest UTC timestamp; mutating = the
call-name regex or any `ast.Attribute` in `Store` context; loft = `makeLoft|makeSweep|makeHelix|
makeThickness|makePipe|(Part|PartDesign)::\w*(Loft|Pipe|Helix|Sweep|Thickness)`; timeout = result
text holds `marshaled call timed out`, `"status": "TIMEOUT"` or starts `TIMEOUT:`.

| Count | My scan | Report | Leader expects |
| --- | --: | --: | --: |
| Calls / sessions | 897 / 8 | 897 / 8 | — |
| Servers | `plugin_freecad-buddy_freecad-buddy` 698, `freecad-buddy` 199 | same | — |
| `script_exec` | 325 | 325 | — |
| Read-only / mutating | 184 / 141 | 184 / 141 | 184 |
| Loft class | 2 | 2 | 2 |
| `isValid` | 122 | 122 | — |
| Timeouts | `script_exec` 4, `query_tree_summary` 4 | `script_exec` timeout class 4; `query_tree_summary` row `TIMEOUT 4` | 4 |

Docker-named server: the evidence folders hold no `freecad-buddy-docker` call. Over all dates of
`D--Work-Personal-Sources-freecad-buddy` (76 transcripts name it), my scan gives
`freecad-buddy-docker` 727 calls, 2 sessions, 76 `script_exec` (read-only 47, mutating 29),
`isValid` 5; the report prints `Servers: freecad-buddy-docker 727.`, 727 calls in 2 sessions,
76 `script_exec`, read-only 47, mutating 29, `isValid` 5. Match.
