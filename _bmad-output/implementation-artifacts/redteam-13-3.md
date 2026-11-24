# Story 13-3: red team report

Diff: `905e038...010a92b` (branch `story/13-3-server-instructions`). Worktree `fcb-redteam-13-3` at `010a92b`, `uv sync --extra dev`, mcp 1.28.1. Container and ports 8765/18765 not used.
Quality bar: `quality-bar-13-3.md`. Known findings in `review-ledger-13-3.md` and the spec Review Triage Log are not reported again.

Repro files (scratchpad, not in repo): `rt133/test_rt_13_3.py` (RT-2, RT-3, RT-4 and the round-trip check), `rt133/mutate.py` (RT-1). Run from the worktree root with `uv run pytest <file> -q -s -p no:cacheprovider --rootdir .`.

## Reproduced

| Id | Severity | Q | File:line | Finding |
| --- | --- | --- | --- | --- |
| RT-1 | medium (false-pass test) | Q4 | `tests/external/test_mcp_surface.py:1366-1393` | The family test checks only the prefixes before the `:` of each `- ` line. A full tool name that does not exist, anywhere in the text, passes all instruction tests. Q4 says "no tool name that does not exist", and the quality bar gives that clause to this unit test. |
| RT-2 | low | Q3 | `scripts/automation/mcp_cache_proxy.py:435` (`write_text`), `:424` (`read_text`) | Text-mode write and read change line endings. An upstream text with `\r\n` comes back with an extra blank line on the next relay start. The relay does not pass the upstream text unchanged. The shipped `SERVER_INSTRUCTIONS` uses only `\n`, so the freecad-buddy text is not affected. The cua-driver text is not checked. |
| RT-3 | low | Q3 | `scripts/automation/mcp_cache_proxy.py:462-464` | The write is skipped when the upstream text equals the relay's in-memory copy (read at start). It does not look at the file. When another relay (second Claude Code session, same server) rewrote the shared file, this relay never corrects it, and the next start serves the other text. The tool cache (`tools == self._tools`) has the same pattern from before this Story. |
| RT-4 | low | Q3 | `scripts/automation/mcp_cache_proxy.py:437-445`, `:471-474` | When the text file cannot be replaced (a directory or a read-only file at the path), each refresh retries 10 times with `time.sleep` in the event loop: about 0.9 s per cycle, during which tool calls also wait. `_instructions` is not updated on failure, so the stall and a warning with traceback repeat every refresh (60 s). The tool cache still updates (the catch works). |

### RT-1 reproduction

`mutate.py` replaces `"mirror, datum)"` in `SERVER_INSTRUCTIONS` with `"mirror, datum) and feature_loft, query_section"`, then calls the three instruction tests of `test_mcp_surface.py`.

```
$ uv run python rt133/mutate.py
PASS; text names nonexistent tools: ['feature_loft', 'query_section']
```

A first mutation that adds the operations `loft, sweep, shell` to the `feature_` line also passed. No test compares the operations in a family line with `tool_specs()`. The shipped text is correct: I compared each operation in each family line with the 45 names of `tool_specs()` by hand, and every operation maps to a tool.

### RT-2 reproduction

`test_RT1_crlf_text_is_not_served_unchanged`: `CacheProxy` with a fake upstream whose `instructions` is `"line one\r\nline two"`, `refresh_once()`, then a new `CacheProxy` on the same cache with the upstream down.

```
E       AssertionError: assert 'line one\n\nline two' == 'line one\r\nline two'
```

The upstream cannot send a lone surrogate. The mcp client rejects it at JSON parse (`Invalid JSON: unexpected end of hex escape`), so `write_text` cannot raise `UnicodeEncodeError` and break the refresh.

### RT-3 reproduction

`test_RT2_file_changed_by_other_relay_is_not_corrected`: file holds `current text`; relay A starts (in-memory `current text`); the file is rewritten to `text from another upstream version` (as a second relay would); relay A refreshes against an upstream that sends `current text`; a new relay starts.

```
E       AssertionError: assert 'text from an...tream version' == 'current text'
```

### RT-4 reproduction

`test_RT3_unwritable_instructions_path_blocks_event_loop`: a directory at `fake.instructions.txt`, a 10 ms ticker task, three `refresh_once()` calls.

```
longest event-loop stall s 2.721 warnings 3 tool cache written True tmp left []
E       assert 2.7197899000020698 < 0.2
WARNING  mcp_cache_proxy:mcp_cache_proxy.py:473 could not update ...\cache\fake.instructions.txt
PermissionError: [WinError 5] Access is denied: '...fake.instructions.txt.<uuid>.tmp' -> '...fake.instructions.txt'
```

## Checks that held

| Q | Check | Result |
| --- | --- | --- |
| Q1, Q3 | Real `initialize` round trip in memory (`create_connected_server_and_client_session`): `build_server(...)` and a relay whose cache file holds the text, upstream down | both `InitializeResult.instructions == SERVER_INSTRUCTIONS` (test_RT4 passed) |
| Q2 | `StreamableHTTPSessionManager` builds options with `self.app.create_initialization_options()` (`mcp/server/streamable_http_manager.py:200,302`), the call the GUI proxy test reads | test is not a false pass |
| Q1 | Other `Server` construction in `src/`: only `mcp_server.py:256` and `gui_external/entry.py:56`. Headless H1 (`hosts/headless/entry.py:189`) calls `build_server` | covered |
| Q3 test double | `FastMCP(instructions=...)` passes the text to the low-level `Server` (`fastmcp/server.py:207`); `ClientSession.initialize()` returns `InitializeResult` with `instructions: str | None` (`types.py:698`) | fake matches the real SDK |
| Q4 | Shipped family lines vs `tool_specs()` (45 tools): every prefix and every named operation has a tool | holds |
| Q5 | Two T-10 sentences, four skill names | present |
| Q6 | 143 words, 1040 characters; no `ToolSearch`, `select:`, `mcp__`, client names | holds |
| Q7 | `gen_schemas.py --check` OK; the description text appears in no snapshot (only `tool_catalog.py` and an old spec) | holds |
| Q8 | `check_imports.py` OK; `ruff check` and `ruff format --check` on the 8 changed code files clean | holds |
| Regressions | `pytest` on the 3 changed test files: 120 passed. Full `tests/external`: see below | see below |

Full `tests/external` run (known unstable `test_managed_venv` test deselected): 1856 passed, 4 skipped, 1 deselected (145 s). No regression.

## Not reproduced

- low: no size limit on the cached text. A very large upstream text or a large file at the path is read whole at start and sent in `initialize`. No client limit was checked.
- low: a writable `.cache/mcp-proxy/` lets any local process put text into the agent context through `initialize`. Same trust level as the tool cache before this Story.
- low: the `sketch_` line ("create sketches; add, remove and constrain geometry") does not name `sketch_toggle_construction` or external geometry. T-10 asks for a purpose per family, not every operation.
- low: the text routes work ("Load these skills first", "make ... tools available") inside shipped code, close to the AD-35 rule. T-10 asks for exactly these lines, so it is not a defect here.
- Q9 (Claude Code shows the text before the first tool load) needs a live session: verifier scope.

## Verdict

PASS. No high finding: every quality-bar row holds for the shipped code. One medium is a false-pass test (RT-1, Q4 clause "no tool name that does not exist" is not tested). Three low relay findings.
