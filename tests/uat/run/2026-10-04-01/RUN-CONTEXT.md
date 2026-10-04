# UAT run 2026-10-04-01 — Story 10.1 targeted re-run

Purpose: verify Story 10.1 (commit `70de526`) in the real FreeCAD GUI. Scope is the scenarios
that UAT run `2026-10-03-04` failed for findings F-01, F-02, F-03, F-12, F-20, F-25, F-30, plus
TC-02-01 (save-as label) as a regression check.

## Environment

| Item | Value |
| --- | --- |
| `PROJECT_ROOT` | `D:/Work/Personal/Sources/freecad-buddy` |
| `RUN_DIR` | `D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-04-01` |
| FreeCAD | 1.1.4 GUI, `C:/Program Files/FreeCAD 1.1/bin/freecad.exe`, pid `13352`, window_id `4135230` |
| Addon | junction `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy` → repo `src/freecad_buddy` |
| Bridge | RPC listener `127.0.0.1:54018`; MCP proxy pid `38548` (child `39356`) on `http://127.0.0.1:8765/mcp` |
| `FCB_PYTHON` | `C:/Users/thuan/micromamba/envs/fcb/python.exe` (FreeCAD 1.1.3 + `mcp`, H1 legs only) |
| Logs | `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log`, `mcp-proxy.log` |

Code-under-test proof: `document_create {path: <RUN_DIR>/evidence/no-such-dir/canary.FCStd}`
returned an `INVALID_INPUT` traceback through `documents.py` `_check_save_target`, a function
that exists only in `70de526`. No folder was created.

## How to call and observe

- MCP tools: `uv run python _automation/uat/fcb.py <tool> '<json>'`, or `--batch <file.json>`
  for several calls in one session. The session `mcp__freecad-buddy__*` tools are not connected.
- Paths in MCP arguments: absolute Windows form with forward slashes (`D:/Work/...`). Never pass
  a Git Bash path such as `/d/Work/...`: FreeCAD resolves it to `C:\d\Work\...`.
- Screenshot: `printf '{"pid":13352,"window_id":4135230,"screenshot_out_file":"%s"}' "<abs>.png" | cua-driver get_window_state`, then `Read` the PNG and judge it.
- GUI actions: `cua-driver` with JSON on stdin (see the GUI harness standard). The desktop is
  free; foreground delivery is allowed.
- Close every document: `uv run python _automation/uat/close_all.py`.

## Rules

- Read `tests/uat/test-plan.md` §3 and §6 and
  `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md` before acting.
- Do not edit source, test cases, or any earlier run folder. Write evidence only to
  `RUN_DIR/evidence/`, named `tc-NN-MM-<what>.<ext>`.
- Do not run `freecadcmd` (it rewrites `user.cfg` while the GUI runs). `FCB_PYTHON` is allowed
  for a scenario that names an H1 leg.
- Do not exit or relaunch FreeCAD, except where a scenario requires a restart; then report the
  new pid and window_id.
- Every visual Then needs a real window screenshot that you `Read` yourself.
- An assertion you did not execute is NOT RUN, never PASS.
- On PASS: run the scenario cleanup and leave no document open. On FAIL or PARTIAL: leave the
  state in place and say what is open.

## Expected behaviour after Story 10.1 (judge against this where a test case is out of date)

- **F-01:** `query_tree_summary` with `types`, `name_pattern` or `renderable_only` returns a Pad
  nested in a Body; the failing Body node is dropped. A node failing `visible_only` or
  `exclude_types` drops its subtree.
- **F-02 (Story 10.1 AC2):** `document_save` or `document_create` with a new path sets the label
  to the file stem, as GUI Save As does. The result reports `label` and `path`. TC-02-13 still
  expects the original label after reopen; that expectation is a known test-case defect (fixed
  in Story 10.7). Report the product result against AC2 and mark the test-case defect.
- **F-03:** a missing folder, a directory, or a read-only target returns `INVALID_INPUT` naming
  the path. No folder is created, nothing is written, and `FileName` and `Label` are unchanged.
- **F-12:** a malformed `expect_fingerprint` (no serializer, non-string digest, bad entries, or a
  string that is not 64 lowercase hex) returns `INVALID_INPUT`, and the undo does not run.
- **F-20:** the string form keeps `matches_pre_op: false` on a byte difference. The text states
  the byte comparison and recommends the record form. It never says "did NOT restore".
- **F-25:** a handle to a document closed in the GUI returns `INVALID_INPUT` "unknown or stale
  document handle" on first use, with no `document_list` before it.
- **F-30 (AD-25):** each host writes temp files to `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/`.
  The start sweep removes only `FCB_TMP_` entries: dead hosts' session folders and prefixed
  entries outside every session folder. A non-prefixed entry and a live host's session folder
  survive. TC-99-07's documented deviation predates this; report the product result against this
  rule and say whether the TC text matches.
