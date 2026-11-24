# Story 13-3: verification report

Verifier: verifier-13-3 (claude-opus-5-5). Date: 2026-11-24.
Artifact: commit `010a92b9409cdffec053f1319c1758260156b72d` (branch `story/13-3-server-instructions`, base `905e038`).
Copy: `git worktree add --detach D:\Work\Personal\Sources\fcb-verify-13-3 010a92b`, `uv sync --extra dev`. Every gate, mutant, build and container start ran from this copy. Copy removed at the end.
Evidence folder: `tests/uat/run/13-3-r1/evidence/` (main repo).

**Verdict: PASS.** All nine quality-bar rows pass. No product defect found. Four observations below; none blocks.

## Gates (in the copy, HEAD 010a92b)

| Command | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `uv run python scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `uv run ruff format --check` on the 8 changed Python files | 8 files already formatted |
| `uv run pytest tests/external -q` | **1857 passed, 4 skipped**, 0 failed (188.9 s). The known unstable tests did not fail in this run. |

## Mutants (in the copy; each reverted with `git checkout` after the run)

| Mutant | Change | Test that went red |
| --- | --- | --- |
| (a) | `entry.py:56` `Server("freecad-buddy-gui-external")` (no `instructions=`) | `test_gui_external_proxy.py::test_Should_carry_the_shared_instructions_When_the_gui_proxy_server_initializes` (1 failed, 4 passed) |
| (b) | delete line `"- view_: fit the 3D viewport.",` in `mcp_server.py` | `test_mcp_surface.py::test_Should_list_exactly_the_families_with_a_real_tool_When_the_instructions_are_parsed` |
| (c) | insert `Use ToolSearch.` into the first T-10 sentence line | `test_mcp_surface.py::test_Should_hold_no_client_specific_text_When_the_instructions_are_read[ToolSearch]` |
| (d) | `mcp_cache_proxy.py:400` `instructions=None` | `test_mcp_cache_proxy.py::test_Should_serve_cached_upstream_instructions_When_a_later_proxy_starts_with_the_upstream_down` and `::test_Should_serve_the_new_text_When_the_upstream_instructions_change` |

All four mutants were killed. Final `git status` in the copy showed no source change.

## Acceptance criteria map

| AC / Q | Code | Test |
| --- | --- | --- |
| Q1 headless server sends `instructions` | `src/freecad_buddy/adapters/mcp_server.py:59` (`SERVER_INSTRUCTIONS = "\n".join(`), `:256` `Server(name, instructions=SERVER_INSTRUCTIONS)` | `test_mcp_surface.py:1329` |
| Q2 GUI proxy sends the same text | `src/freecad_buddy/hosts/gui_external/entry.py:56` `Server("freecad-buddy-gui-external", instructions=SERVER_INSTRUCTIONS)` | `test_gui_external_proxy.py:127`; live E2E below |
| Q3 relay passes the text | `scripts/automation/mcp_cache_proxy.py:194` `self.instructions = initialized.instructions or None`; `:400` `instructions=self._instructions`; `:422` `_read_instructions`; `:462` `_cache_instructions`; `:479` call in `refresh_once` | `test_mcp_cache_proxy.py:628`, `:642`, `:655`, `:669`; live E2E below |
| Q4 nine family lines, each with a real tool | `mcp_server.py:59-81` | `test_mcp_surface.py:1366`; live tool list below |
| Q5 two T-10 sentences + four skill names | `mcp_server.py:59-81` | `test_mcp_surface.py:1396` |
| Q6 ≤250 words, client-neutral | 143 words (live count) | `test_mcp_surface.py:1341`, `:1355` (`ToolSearch`, `select:`, `mcp__`, `Claude`, `Cursor`, `Codex`, `Gemini`) |
| Q7 `script_exec` pointer only | `src/freecad_buddy/hosts/tool_catalog.py:1068` `"its source. Before using it, check the typed tool families in the server instructions."`. `git show 010a92b` shows this one-line change only in `tool_catalog.py`. | `test_mcp_surface.py:1414` |
| Q8 AD-1 rings | `entry.py` (hosts) imports `adapters.mcp_server`: inward | `check_imports OK` |
| Q9 Claude Code sees text before first tool load | n/a | live UAT below |

## Live checks

Setup from the copy: `uv run python scripts/build_addon.py --release` (wheel `freecad_buddy-0.1.1`; unzipped wheel holds `SERVER_INSTRUCTIONS` in `adapters/mcp_server.py` and `hosts/gui_external/entry.py`), `docker compose -f <copy>\tests\close-loop\docker\compose.yaml up -d --build` (image `fcb-desktop:local` rebuilt; `/repo` mount = copy, read-only), `docker exec -u cua fcb-desktop fcb-freecad start`. Healthz: `{"service":"freecad-buddy-mcp-proxy","freecad_pid":572,"session_id":"55ea598f77083fdb"}`.
Client: scratch script (`mcp`'s `ClientSession`; `streamablehttp_client` for HTTP, `stdio_client` for the relay) sends `initialize` + `tools/list` and writes the result to JSON.

| Q | Check | Result | Evidence |
| --- | --- | --- | --- |
| Q2 | `initialize` to `http://127.0.0.1:18765/mcp` | `serverInfo.name` `freecad-buddy-gui-external`; `instructions` 143 words; byte-equal to `SERVER_INSTRUCTIONS` of the copy (`proxy==src True`); 46 tools | `initialize-container-proxy.json` |
| Q4 | Live tool names per family | `document_` 7, `query_` 8, `verify_` 6, `export_` 3, `verify_export_` 3, `sketch_` 8, `feature_` 11, `preview_` 1 (`preview_dry_run`), `view_` 1 (`view_fit_viewport`). `script_exec` listed. | same file, `tool_names` |
| Q7 | Live `script_exec` description tail | `... Every call is audit-logged with its source. Before using it, check the typed tool families in the server instructions.` | relay tool cache (scratch) |
| Q3 | Relay start 1, fresh private cache dir `--cache-dir <scratchpad>\relay-cache` | `instructions` `null`, 0 tools (expected: no cache yet). After the first refresh the cache dir holds `freecad-buddy-docker.instructions.txt` (1054 bytes) and `freecad-buddy-docker.json`. | `initialize-relay-start1.json`, `relay-start1.stderr.txt` |
| Q3 | Relay start 2, same cache dir | `instructions` 143 words, equal to `SERVER_INSTRUCTIONS` (`relay2==src True`); 46 tools. Cache file equal to the source text (`cachefile==src True`). | `initialize-relay-start2.json`, `relay-cache-instructions.txt` |
| Q9 | Headless Claude Code, direct HTTP. `claude -p "<plate 60x40x5 with 10 mm hole; first quote server instructions or say NO SERVER INSTRUCTIONS SEEN; list loaded vs deferred tools; then build>" --mcp-config <http json> --strict-mcp-config --output-format stream-json --verbose --max-turns 6 --max-budget-usd 2 --model sonnet --allowedTools mcp__freecad-buddy-docker ToolSearch` | Init: server `freecad-buddy-docker` `connected`, 46 server tools, all deferred. First reply, before any tool call, quotes the full instruction text verbatim. First tool load (`ToolSearch select:`) holds 18 typed tools: `document_create`, `document_save`, `feature_body_create`, `feature_pad`, `feature_pocket`, `feature_hole`, `sketch_create`, `sketch_add_geometry`, `sketch_add_constraint`, `sketch_set_datum`, `query_tree_summary`, `query_sketch_info`, `query_mass_properties`, `query_screenshot`, `verify_shape`, `verify_sketch`, `verify_recompute`, `view_fit_viewport`. No `script_exec`. Then it loaded the four named skills and used only typed tools. Run ended `error_max_turns` at turn 7 (cost 0.28 USD). | `q9-claude-http.jsonl`, `q9-claude-http.stderr.txt` |
| Q9 | Headless Claude Code, through the relay (stdio, private cache dir, second start). `--max-turns 2`, no tool calls asked | Init: `connected`, 46 tools. Reply quotes the full instruction text verbatim and plans to load the `sketch_`, `feature_`, `query_`, `verify_` families first. Result `success`, 0.11 USD. | `q9-claude-relay.jsonl` |
| GUI | cua-driver `get_window_state` on FreeCAD (pid 572, window 37748829) | 658 elements (AT-SPI tree present). Window title `* plate_with_hole - FreeCAD 1.1.4`; tree shows `plate_with_hole` > `PlateBody` from the Q9 session; the 3D view is empty because that session stopped at the turn limit before a view fit. | `freecad-window.png` |

## Observations (no defect)

1. **Relay first start sends no text** (Q3). Live start 1 returned `instructions: null`. This is the cache-first design that the ledger rejected as R1-R2 and that `tests/close-loop/README.md` documents. Effect: on a fresh clone, the first Claude Code session through the relay does not see the instructions; the second does.
2. **Q9 prompt was primed.** The prompt asked the model to quote any server instructions. The quote proves the text is in the model context before the first tool load. It does not prove unprompted use. The tool choice of the first load was the model's own: 18 typed tools, no `script_exec`.
3. **Family sentence omits `document_`.** The relay-session model said "The server instructions do not name `document_create` and `document_recompute`" in the "Before a build" sentence. The text follows T-10 word for word (`tool-contracts.md:40-41`), so this is a contract wording point for the planner, not a code defect.
4. **Q4 "no tool that does not exist" is tested by prefix only.** The only full tool name in the text is `script_exec`. It exists in the live list (ScriptExec on). With ScriptExec off the text names a tool the server does not list; the ledger rejected this as R1-R1.

## Teardown

- `fcb-freecad stop`: window close timed out (the Q9 document was unsaved), helper killed pid 572; `status` then showed no FreeCAD pid.
- `docker compose -f <copy>\tests\close-loop\docker\compose.yaml down`: container and network removed. `docker ps` shows no `fcb-desktop`.
- Screenshot copied out of the copy's run folder (`cmp` equal), then `git worktree remove --force D:\Work\Personal\Sources\fcb-verify-13-3`. `git worktree list` no longer shows it.
- Not touched: `wt-13-2`, `wt-13-4`, host port 8765, `%APPDATA%\FreeCAD\v1-1\user.cfg`.
- Image `fcb-desktop:local` now carries 13-3 (010a92b).

## Round 2 (red-team fix round)

Artifact: commit `f4782e7d2d6acce4f38889a1fa1887817c3f8ae7` (`fix(mcp): keep relay instructions cache byte-exact and off the event loop`). Triage: `triage-13-3-rt.md`. Fresh copy: `git worktree add --detach D:\Work\Personal\Sources\fcb-verify-13-3 f4782e7`, `uv sync --extra dev`. Copy removed at the end.

**Verdict: PASS.**

### Gates (in the copy)

| Command | Result |
| --- | --- |
| `uv run pytest tests/external -q` | **1861 passed, 4 skipped**, 0 failed (181.4 s). Round 1 had 1857; the 4 new tests account for the change. |
| `uv run ruff check .` | All checks passed |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run ruff format --check` on the 3 changed files | 3 files already formatted |

### Proof per row (each change reverted with `git checkout` after the run)

| Row | Change applied in the copy | Test that went red |
| --- | --- | --- |
| RT-1 | Red-team mutation: preview_ line becomes `"- preview_: dry-run a mutation before it is applied. See feature_loft, query_section.",` | `test_mcp_surface.py::test_Should_name_only_tools_that_exist_When_a_tool_shaped_token_is_in_the_instructions` (1 failed, 11 passed). The old family-line test stayed green, which confirms the gap RT-1 closed. |
| RT-2 | Revert to `read_text(encoding="utf-8")` and `_replace_file(...)` without `newline=""` | `test_mcp_cache_proxy.py::test_Should_serve_the_text_unchanged_When_the_upstream_text_has_crlf_line_endings` |
| RT-3 | Revert to the in-memory compare (`self._instructions` set in `__init__`, `if instructions == self._instructions`, updated after a write) | `test_mcp_cache_proxy.py::test_Should_correct_the_file_When_another_relay_rewrote_it_after_this_relay_started` |
| RT-4 | Revert `await asyncio.to_thread(self._cache_instructions)` to `self._cache_instructions()` | `test_mcp_cache_proxy.py::test_Should_keep_the_event_loop_responsive_When_the_instructions_path_cannot_be_replaced` |

Each reverted run: 1 failed, 7 passed in the instructions-related relay tests. Final `git status` in the copy showed no source change.

### Container

Not run. The round changes only `scripts/automation/mcp_cache_proxy.py` (cache file I/O; the relay runs on the host, not in the image) and tests. `src/` is unchanged, so the image and the round-1 live results (container proxy `initialize`, two relay starts, Q9) stand.

### Observation (no defect)

RT-4 is fixed by moving the blocking write to a thread. When the path cannot be replaced, each refresh still spends the retry time (about 0.9 s) in that thread and logs one warning. The event loop stays free, as the triage asked; the retry itself is not suppressed.
