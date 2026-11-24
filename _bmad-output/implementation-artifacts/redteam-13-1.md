# Story 13-1: red team report

Artifact: `patch-13-1-r1.diff` (sha256 `904e6edad4b3ad79…`), applied on base `bd122f2` in a private worktree.
Quality bar: `quality-bar-13-1.md`. Ledger rows R1-1 … R1-6 are not reported again.

## Gates re-run on the patched copy

| Gate | Result |
| --- | --- |
| `uv run pytest tests/external -q` | 1829 passed, 4 skipped |
| `uv run ruff check .` | All checks passed |
| `uv run python scripts/check_imports.py` (Q7) | `check_imports OK` |
| `uv run python scripts/gen_schemas.py --check` | OK |
| `uv run python scripts/check_status_vocab.py` | OK |
| `ruff format --check` on the 3 changed files | already formatted |

Real `script_exec` (not a hand-built dict) was run under host `freecadcmd` (private temp cfg files), with the worktree `src` first on `sys.path`. Probe output confirmed `module: D:\Work\Personal\Sources\fcb-redteam-13-1\src\freecad_buddy\contracts\envelope.py`, so the installed addon did not shadow it.

## Reproduced

| Id | Severity | Q | Location | Finding |
| --- | --- | --- | --- | --- |
| RT-1 | low (spec wording; lead decision) | Q4 | `quality-bar-13-1.md` Q4; `tool-contracts.md:30`; `envelope.py:83-86` | Short `value_repr` and short `stdout` still appear twice |
| RT-2 | low | Q2 | `envelope.py:83-85` | Unicode line separators pass the line-break guard |
| RT-3 | low | Q6 | `mcp_server.py:106-109`; `replay_result_sizes.py:8` | Regeneration silently stops when producer and proxy versions differ |
| RT-4 | low | Q2 | `tests/external/test_envelope_summary.py` | A byte-length mutant survives every test |
| RT-5 | low | outside the bar | `tests/external/test_envelope_summary.py:23` | `target` names the output, not the system under test |

### RT-1: short `value_repr` and `stdout` are not held once

Q4 says "A `script_exec`-shaped result holds `value_repr` and `stdout` once (no copy in `text`)". T-13 "Done when" (`tool-contracts.md:30`) and CAP-8 success say "a `script_exec` result holds its `value_repr` once". Neither row is limited to long values. The T-13 table row "`str` with length ≤ 80 and no newline → `key: value` (as today)" requires the copy for short values. The code follows the table. Read literally, Q4 fails for any short result.

Reproduction: real `script_exec` under `freecadcmd` (`probe_script_exec.py`):

```
'result = 42' -> 'doc: fcb-doc:vXD3h21ZMutd920kZhenwg\nfingerprint_after: None\nstdout: \nvalue_repr: 42'
'result = doc.Name' -> "doc: fcb-doc:…\nfingerprint_after: None\nstdout: \nvalue_repr: 'rt'"
"import sys; sys.stdout.write('done')" -> 'doc: fcb-doc:…\nfingerprint_after: None\nstdout: done\nvalue_repr: None'
"print('x'*10)" -> 'doc: fcb-doc:…\nfingerprint_after: None\nstdout: <11 chars>\nvalue_repr: None'
```

Severity: low. The behaviour matches the most specific contract rule, and the CAP-8 intent is limited to "a long string field". Fix: reword Q4 and T-13 "Done when" to "a long `value_repr` (over 80 characters or with a line break)". Do not change the code. If the lead reads Q4 literally, this finding becomes high.

### RT-2: Unicode line separators pass the guard

The docstring promises "one `key: value` line per top-level key". The guard checks only `"\n"` and `"\r"`. `str.splitlines()` also splits on `\x0b`, `\x0c`, `\x1c`–`\x1e`, `\x85`, `\u2028` and `\u2029`. A short `stdout` written with `sys.stdout.write` can hold one of these. `value_repr` is safe, because `repr` escapes them (probe: `value_repr: 'a\\u2028b'`).

```
$ uv run python -c "from freecad_buddy.contracts import summary_text; t = summary_text({'a': 'x\u2028y', 'b': 'p\x85q', 'c': 'z'}); print(len(t.splitlines()), 'lines for 3 keys:', t.splitlines())"
5 lines for 3 keys: ['a: x', 'y', 'b: p', 'q', 'c: z']
```

This is the same class of defect as R1-1 (bare `\r`). T-13 says only "newline", so the contract is not broken. Fix if wanted: `len(value.splitlines()) > 1 or value.endswith(("\n", "\r"))`, or `value != value.splitlines()[0]` when the value is not empty.

### RT-3: regeneration stops when producer and proxy versions differ

`mcp_server.py:106` decides "generated" with `body.get("text") == summary_text(content)`. The `text` is computed where the envelope is built. In the GUI path that is the FreeCAD-side addon (`gui_external/entry.py:64`, `registry.dispatch` over RPC). The comparison runs in the proxy. `bootstrap._mcp_proxy_command` documents a dev install where FreeCAD runs a `build_addon.py` copy, while the proxy runs the repo `.venv` python with the editable `src`. After a change to `src` without a rebuild, the two `summary_text` versions differ. Before this Story, string rendering never changed, so the check stayed stable. Now any envelope with a long string fails the check. The proxy then keeps the producer's text, and its floats are not rounded.

Reproduction (base-commit `summary_text` as producer, patched `_to_call_result` as proxy, `skew.py`):

```
old FreeCAD-side text, new proxy -> 'stdout: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' ... '\nvolume_band: 0.123456789' len 233
```

Expected after a correct regeneration: `stdout: <200 chars>\nvolume_band: 0.12`. The same mechanism affects `scripts/automation/replay_result_sizes.py`. Its docstring (line 8) says that every envelope goes "through `mcp_server._to_call_result`, so the numbers measure the code that ships". A recorded pre-13-1 `script_exec` envelope keeps its old full-copy text in the replay, so the replay does not show the T-13 reduction. This matters if Story 13-20 measures Q8 by replay. In a consistent install (release wheel, or a repo junction) the versions match and this does not happen.

### RT-4: byte-length mutant survives

No new test value holds a non-ASCII character. A mutant that uses `len(value.encode())` for both the limit and `N` passes every test in `test_envelope_summary.py`. Q2 defines N as `len(value)`.

```
$ uv run python mutants.py
utf8-byte-length killed by: NO TEST (survives)
non-ASCII value in any new test: False
```

Fix: add one test with an 80-code-point non-ASCII value (for example `"é" * 80` renders inline) and one with 41 four-byte characters plus a newline (it renders `<42 chars>`).

### RT-5: `target` holds the output

CLAUDE.md §9 says "the system under test is named `target`". The new tests assign the output to it: `test_envelope_summary.py:23` `target = summary_text({"name": value})`. The same Story uses `result = _to_call_result(envelope)` in `test_mcp_surface.py:1148`. Style only.

## Not reproduced

- `summary_text` callers other than the envelope builder: `documents.py:124`, `exports.py:547`, `queries.py:35`, `verify.py:89`, and `script_exec.py:67` (via `mirror_text`, `envelope.py:96-98`, a pure alias). Each one uses the generic text only when no bespoke `summary` is given. No caller parses the text. No defect.
- Q5 bespoke summaries: the diff does not touch any caller. All `text` checks in the UAT scenarios (`tests/uat/scenarios/*.json`, 130 checks) and in `tests/infc` target bespoke summaries or plain-text tools. None reads a generated line that this Story now elides.
- Only `query_tree_summary` sets `structured_output=False` (`tool_catalog.py:1237`), so no tool loses a value to elision. For structured tools, `structuredContent` still carries the full value.
- Skills: no skill tells the agent to read `stdout` or `value_repr` from `text`. The one mention (`skills/freecad-fundamentals/references/tree-codes.md:73`) concerns a bespoke tree summary.
- `str` subclasses and `str`-mixin enums: same rendering as before for short values. Values arrive as plain `str` after the JSON round trip over RPC.
- Q6 regeneration in a consistent install: rounding never changes a string, and `test_Should_regenerate_text_with_char_count_When_rounded_content_holds_a_long_string` fails if either the elision or the regeneration is removed.
- Test double in the `script_exec`-shaped test: the hand-built key set `{doc, stdout, value_repr, fingerprint_after}` matches the real `script_exec.py:57-62` (confirmed by the live probe). The double skips nothing that `summary_text` reads.
- Neighbouring behaviour (dict and list shape signal, non-`str` scalars, the pre-existing `test_summary_text_*` tests) is still covered and passes.
- Comment at `envelope.py:39` cites the contract section instead of a measurement. R1-4 already covers it.

## Verdict

**PASS.** No reproduced high and no product medium. RT-1 needs a lead decision on Q4 and T-13 wording. If the lead reads Q4 literally ("no copy in `text`" for every value), RT-1 is high and the verdict is FAIL. The recommended resolution is to narrow the wording to long values, which matches the T-13 table and the CAP-8 intent.
