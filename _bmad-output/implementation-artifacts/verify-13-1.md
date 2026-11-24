# Story 13-1: verification report (rounds r1 and r2)

Verifier: verifier for Story 13-1 (claude-opus-5-5). Date 2026-11-24.

**Verdict on r2 (sha256 `899bd67ed468`): PASS.** r2 supersedes r1. Section "Round r2" holds the
r2 gates and mutants. The live check ran on r1; section "Round r2" says why it holds for r2.

## Round r1

### Artifact tested

- Patch: `_bmad-output/implementation-artifacts/patch-13-1-r1.diff`, sha256 `904e6edad4b3ad793904bb6d5b1072d4689ec6802e49765f6ae4dd8dc73d45ba`.
- Base: `bd122f2`. Copy: `git worktree add --detach D:\Work\Personal\Sources\fcb-verify-13-1 bd122f2`, then `git apply` of the patch. `git diff -- src tests` in the copy equals the patch byte for byte. The main tree equalled r1 at the start.
- `patch-13-1-r2.diff` appeared during the r1 run. It is verified in section "Round r2".

### Gates (in the copy, own `.venv` from `uv sync --extra dev`)

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check` on the 3 changed files | `3 files already formatted` |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `uv run python scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `uv run pytest tests/external -q` | `1829 passed, 4 skipped, 6 warnings in 178.36s`. No flaky failure this run. |

infc suite not run: no infc test reads generated `text` with a long string (builder claim; Q-bar marks infc optional).

### Falsification (mutants in the copy, each restored after; restore checked with `cmp`)

Command per mutant: `uv run pytest tests/external/test_envelope_summary.py tests/external/test_mcp_surface.py -q`. Baseline: 82 passed.

| Mutant | Change at `src/freecad_buddy/contracts/envelope.py` | Red tests |
| --- | --- | --- |
| a | `:42` `INLINE_STRING_LIMIT = 80` → `81` | `test_Should_render_char_count_When_string_has_81_characters` (1 failed) |
| b | `:84` drop `or "\n" in value` | `test_Should_render_char_count_When_short_string_has_a_newline`, `test_Should_hold_long_strings_once_When_content_is_script_exec_shaped` (2 failed) |
| c | `:86` `f"{key}: <{len(value)} chars>"` → `f"{key}: {value}"` | 81-chars, newline, carriage-return, script_exec-shaped (all `test_envelope_summary.py`), and `test_mcp_surface.py::test_Should_regenerate_text_with_char_count_When_rounded_content_holds_a_long_string` (5 failed) |
| d (extra) | `:84` drop `or "\r" in value` | `test_Should_render_char_count_When_short_string_has_a_carriage_return` (1 failed) |
| e (extra) | `:84` `>` → `>=` | `test_Should_render_string_inline_When_it_has_exactly_80_characters` (1 failed) |

Every mutant turned at least one named test red.

### AC map

| Q | Criterion | Evidence |
| --- | --- | --- |
| Q1 | str ≤ 80, no newline → `key: value` | `tests/external/test_envelope_summary.py:18` (exactly 80), `:4` (old scalar test). Mutant e kills `:18`. |
| Q2 | str > 80 or with newline → `key: <N chars>` | `test_envelope_summary.py:29` (81), `:40` (`\n`), `:51` (`\r`). Mutants a, b, c, d. |
| Q3 | dict/list and non-str scalars unchanged | `test_envelope_summary.py:11`, `:87`, `:98` (container holding long strings keeps shape signal). |
| Q4 | script_exec result holds `value_repr`/`stdout` once | Unit: `test_envelope_summary.py:62`. Live: PASS, see below. |
| Q5 | bespoke summaries unchanged | Diff touches only `summary_text`. `test_mcp_surface.py:1169` (hand-written text kept). Full suite green. |
| Q6 | regeneration after rounding still correct | `test_mcp_surface.py:1142` (existing), `:1155` (new, long string). Mutant c kills `:1155`. |
| Q7 | `contracts/` stdlib only | `check_imports OK`. r1 adds no import. |
| Q8 | `text` share ≤5% over a session | NOT RUN, by plan (Story 13-20). One data point below. |

### Live check (Q4, E2E in `fcb-desktop`): PASS

Setup:
- `uv run python scripts/build_addon.py --release` in the copy. The built `envelope.py` and the wheel (`freecad_buddy-0.1.1-py3-none-any.whl`, sha256 prefix `b9d477c56403`) both hold `INLINE_STRING_LIMIT = 80`.
- `compose.yaml` mounts `../../..` as `/repo` and uses `../../../dist/addon` as build context, both relative to the compose file. So I ran `docker compose -f tests/close-loop/docker/compose.yaml up -d --build` from the copy. `docker inspect` mounts: `D:\...\fcb-verify-13-1 -> /repo`. The main tree `dist/` was not touched. No override file needed.
- In the container, the addon copy `~/.local/share/FreeCAD/v1-1/Mod/FreeCADBuddy/.../envelope.py` and the proxy venv copy (`FreeCADBuddy/venv/lib/python3.13/site-packages/.../envelope.py`, process `venv/bin/python -m freecad_buddy.hosts.main serve --mode rpc --transport http`) both hold the patch.
- `fcb-freecad start`; `/healthz` → `{"service":"freecad-buddy-mcp-proxy","freecad_pid":632,...}`.

Call: MCP streamable HTTP client (`mcp` SDK) to `http://127.0.0.1:18765/mcp`: `document_create {"label":"Verify131"}`, then `script_exec` with code that prints 5 lines (365 chars) and binds `result` to a 10-item list (repr 250 chars).

Result (`structuredContent`):
```
"text": "doc: fcb-doc:QGMUXh1IUcNfMzl-jtdH6A\nfingerprint_after: None\nstdout: <365 chars>\nvalue_repr: <250 chars>"
```
Occurrence count of a marker string from each value:

| Marker | in `structuredContent` | in `text` | in `content[0]` JSON block |
| --- | --- | --- | --- |
| `value_repr element 00` | 1 | 0 | 1 |
| `stdout line 0 of` | 1 | 0 | 1 |

`text` length / `structuredContent` JSON length = 0.097 for this one call (script_exec only; not the Q8 session measure).

GUI proof: `cua-driver get_window_state` on pid 632, window ` Verify131 - FreeCAD 1.1.4`, 651 elements, tree item `Verify131`, tab `Verify131 : 1`. I read the screenshot: the FreeCAD GUI shows the document the MCP call created. The GUI host served the call.

Evidence: `tests/uat/run/13-1-r1/evidence/`
- `script_exec-response.json` — raw `document_create` and `script_exec` `CallToolResult` JSON.
- `freecad-window.png` — FreeCAD window capture (container software rendering).
- `call_script_exec.py` — the client used.

### Observations (not defects of this Story)

1. `content[0]` is a JSON text block that repeats the whole envelope, so the wire carries each long value twice (`content[0]` and `structuredContent`). T-13 targets the `text` field only, and Claude Code reads `structuredContent` only when it is present, so the agent reads each value once. A client that reads `content` reads it once too. Not a T-13 breach. Relevant to Story 13-20 if it measures wire bytes instead of what the agent reads.
2. r1 renders a value with `\v`, `\f`, `\x1c`–`\x1e`, `\x85`, `\u2028` or `\u2029` inline. T-13 and Q2 name only "newline", so r1 meets the bar as written. r2 closes this.
3. Builder report says "8 new" tests in `test_envelope_summary.py`; the file has 7 new there plus 1 in `test_mcp_surface.py` (8 in total). Wording only.

### Verdict: PASS (for r1, sha256 `904e6edad4b3`)

All gates green, all five mutants killed by named tests, Q1–Q7 mapped to tests, live Q4 check PASS with evidence. Q8 NOT RUN by plan. No product defect found in r1.

### Teardown

- `fcb-freecad stop` → `freecad pids:` empty. `docker compose ... down` → container `fcb-desktop` and network removed. The image `fcb-desktop:local` remains and now carries r1; rebuild before the next run (r2 is in the main tree).
- Before this run an exited `fcb-desktop` container (from the main tree compose) existed. Compose recreated it from the copy and `down` removed it. The next `up` from the main tree creates it again.
- Worktree `fcb-verify-13-1` removed. Scratch files removed except the client script in the scratchpad. Host port 8765 and `freecad-buddy-wt-13-2` not touched.

## Round r2

### Artifact tested

- Patch: `_bmad-output/implementation-artifacts/patch-13-1-r2.diff`, sha256 `899bd67ed4687b40307f23e2da8594c8357e0e205165271e8592b2aa070aa291`. Diff against `bd122f2`; supersedes r1.
- Fresh copy: `git worktree add --detach D:\Work\Personal\Sources\fcb-verify-13-1-r2 bd122f2`, `git apply` of r2, own `.venv` from `uv sync --extra dev`. `git diff -- src tests` in the copy equals r2 byte for byte, before and after the mutants. The main tree also equals r2.
- Change against r1: `src/freecad_buddy/contracts/envelope.py:47` `_LINE_BREAK = re.compile("[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]")`, used at `:89` `len(value) > INLINE_STRING_LIMIT or _LINE_BREAK.search(value)`. New parametrized line-break test, new non-ASCII length test, test variable `target` renamed `result`.

### Gates

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check` on the 3 changed files | `3 files already formatted` |
| `uv run python scripts/check_imports.py` | `check_imports OK` (new `import re` is stdlib) |
| `uv run python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `uv run python scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `uv run pytest tests/external -q` | `1 failed, 1838 passed, 4 skipped in 149.82s`. The failure is the known unstable `test_managed_venv.py::test_Should_start_an_external_interpreter_When_freecad_set_pythonhome`; alone it gives `1 passed in 0.28s`. |

Extra check: over all code points 0..0x10FFFF, the set of characters that split `"a" + c + "b"` into two lines with `str.splitlines` equals the set `_LINE_BREAK` matches (`True`, difference empty).

### Falsification (r2 copy, each mutant restored; restore checked with `cmp`)

Command per mutant: `uv run pytest tests/external/test_envelope_summary.py tests/external/test_mcp_surface.py -q`. Baseline: 92 passed.

| Mutant | Change | Red tests |
| --- | --- | --- |
| a (×10) | drop one character from `_LINE_BREAK` (`:47`), once for each of `\n \r \v \f \x1c \x1d \x1e \x85 \u2028 \u2029` | each drop turns red `test_Should_render_char_count_When_short_string_has_a_line_break[<that char>]`; dropping `\n` also turns red `..._has_a_newline` and `..._script_exec_shaped` (3 failed) |
| b | `:89` `len(value)` → `len(value.encode())` | `test_Should_count_characters_not_bytes_When_string_is_non_ascii` (1 failed) |
| b' (extra) | `:91` `<{len(value)} chars>` → `<{len(value.encode())} chars>` | `..._has_a_line_break[\x85]`, `[\u2028]`, `[\u2029]`, `test_Should_count_characters_not_bytes_When_string_is_non_ascii` (4 failed) |

The lead's mutant (a) named one character that did not survive the message; dropping each of the ten covers it.

### AC map (r2 line numbers)

| Q | Evidence |
| --- | --- |
| Q1 | `tests/external/test_envelope_summary.py:20` (exactly 80), `:6`, `:68` (80 non-ASCII chars inline) |
| Q2 | `test_envelope_summary.py:31` (81), `:42` (newline), `:53`–`:57` (10 line-break characters), `:68` (81 non-ASCII chars elided) |
| Q3 | `test_envelope_summary.py:13`, `:107`, `:118` |
| Q4 | Unit `test_envelope_summary.py:82`. Live: see below |
| Q5 | `tests/external/test_mcp_surface.py:1169`; diff touches only `summary_text` |
| Q6 | `test_mcp_surface.py:1142`, `:1155` |
| Q7 | `check_imports OK` |
| Q8 | NOT RUN, by plan (Story 13-20) |

### Live check for r2

Not re-run, by the lead's instruction (no container rebuild for r2). The r1 live call used values that elide under both r1 and r2 rules: `stdout` 365 chars with `\n`, `value_repr` 250 chars. r2 changes only which short strings count as holding a line break, so r2 gives the same `text` for that call. This is reasoning from the diff, not a measurement on r2.

### Verdict on r2: PASS

All gates green (one known unstable test, passes alone). Every mutant killed by a named test. Q1–Q7 mapped to tests. No product defect found. The image `fcb-desktop:local` carries r1, not r2: rebuild before the next container run.

### Teardown

Worktree `fcb-verify-13-1-r2` removed. No container started for r2.
