# Story 10-10: red team report

Diff `031d8e8...5ee4824` on `story/10-10-uat-testcases-in-container`. Red team: redteam-10-10 (opus, high).
Evidence folder: `tests/uat/run/2026-11-18-10-10-redteam/` (each `RT-*.txt` has the command line first).
FreeCAD 1.1.4 in `fcb-desktop`, started with `fcb-freecad start` (pids 18809, 19896, 20130), stopped at the
end; container left up. Mutants ran in a scratch worktree at `5ee4824`, now removed. No test case, script
or product file was edited. Host `user.cfg` SHA-256 still starts `b89a97711941619bb0b`.

## Verdict

**FAIL.** 4 reproduced medium findings: one always-pass check, one never-pass verify call, one wrong
coordinate rule, one test double that hides the exit status. 1 more medium is in a line from before this
Story (10-9).

## Reproduced

| Id | Severity | Q | Where | Finding | Reproduction (decisive line) |
| --- | --- | --- | --- | --- | --- |
| RT-1 | medium | Q2 (Given verify), Q3 rule K3 | `TC-10-concurrency-timeout-and-quarantine.md:185`, `:260`, `:558`, `:595` | Always-pass check. The K3 rule turned `netstat -ano \| grep ":<port>" \| grep ESTABLISHED` into `ss -ltnp \| grep ":<port>" \| grep ESTABLISHED`. `-l` lists only listening sockets, and `ss` prints `ESTAB`, never `ESTABLISHED`. So the guard "the MCP proxy is stopped so the raw client is the only session" passes while the proxy holds the session. `TC-10:148` and test-plan §6 "Established pair" use the right form, `ss -tnp` and `ESTAB`. | `RT-tc10-established.txt`. Proxy pid 20214 holds the listener session. As written: `docker exec -u cua fcb-desktop ss -ltnp \| grep ":41917" \| grep ESTABLISHED` prints nothing, exit 1. `ss -tnp \| grep ":41917"` prints `ESTAB ... 127.0.0.1:47198 127.0.0.1:41917 users:(("python",pid=20214,fd=9))`. |
| RT-2 | medium | Q2, Q4 | `TC-12-gui-workflows.md:97`, `:273` (Then verify of TC-12-04), `TC-13-gui-mcp-parity.md:226`, `:359`, `test-plan.md:347-348` ("Tree row toggle") | Never-pass call. The new selection, active-document and camera reads are written `script_exec { code: ... }` with no `doc`. `doc` is a required property of `script_exec`, so each read returns a validation error. `TC-12:362` passes `doc:<handle>`, so the form is not consistent. Fix: add `doc: <handle>`. | `RT-script-exec-no-doc.txt`: `mcp script_exec { code: "import FreeCADGui as G; result = G.ActiveDocument.Document.Label" }` returns `Input validation error: 'doc' is a required property`. |
| RT-3 | medium (only rows low in the window are hit) | Q4 | `test-plan.md:345` ("Tree row toggle": "take the row's centre in window pixels (the `frame` of an element is in screen pixels: subtract the window origin)"), `TC-12-gui-workflows.md:599` (workbench list item) | Wrong coordinate rule. Pixel `click` coordinates are screenshot pixels. The `cua-driver` skill says: "window-local screenshot pixels (same space as the PNG)". The screenshot is capped at 1568 px, and the maximized window is 1600 x 949, so the screenshot is 1568 x 930, a scale of 0.98. "frame minus origin" gives unscaled window pixels, and the click lands 2% further down and to the right. For a row centre below about window y 450, the error is more than half a row (18 px), so the click selects the next row. The case sites that the verifier ran had rows near the top, so they passed. Fix: read the row centre off the PNG, or multiply frame-minus-origin by `screenshot_width / window width`. | `RT-tree-row-scale.txt`: 40-box document. Row `B16` frame `{x:24,y:509,w:222,h:18}`. Frame-minus-origin `(135,467)` gives `"value_repr":"['B17']"`. The same row in screenshot pixels `(132,457)` gives `['B16']`. Screenshot `rt-scale-after.png`. |
| RT-4 | medium (test double) | Q5 | `tests/external/test_fcb_cua_wrapper.py:23-27` (fake `docker`) | The fake `docker` always exits 0, and no test checks that a non-zero status gets through the wrapper. The real path does pass it through (`no_such_tool` gives exit 1). A mutant that swallows it still passes all 19 tests. A tester who checks `$?` after a refused call would then see 0. Fix: let the fake exit with a code from the environment, and assert that the wrapper returns it, for the tool path and for the management-word path. | `RT-exit-status-mutant.txt`: real wrapper `exit=1`. Mutant (`\|\| true` after the `docker exec` line) `exit=0`. `pytest test_fcb_cua_wrapper.py` against the mutant: `19 passed`. |

### Before this Story (not in the diff, for the leader to route)

| Id | Severity | Where | Finding | Reproduction |
| --- | --- | --- | --- | --- |
| RT-5 | medium | `TC-01-session-lifecycle-and-transport.md:83` (from `9019b76c`, Story 10-9) | Never-pass Given. "no stale H1 server holds the golden files": `docker exec -u cua fcb-desktop pgrep -af freecad_buddy.hosts.main` "returns nothing". The same Given block needs the GUI (`:84` `document_open`, `:85` capture). The GUI's own proxy runs `... -m freecad_buddy.hosts.main serve --mode rpc --transport http`, so the pattern always matches it. Use `pgrep -af 'hosts.main serve --transport stdio'`, or exclude `--transport http`. | `RT-tc01-02-given-pgrep.txt`: `20214 /home/cua/.local/share/FreeCAD/v1-1/FreeCADBuddy/venv/bin/python -m freecad_buddy.hosts.main serve --mode rpc --transport http`, exit 0. |

## Ran and held (no finding)

- Fix batches `b5064f1...5ee4824`. I read every changed line. The wmctrl and `set_window_frame` text,
  window-level keys, the rename editor, the `UndoNames` read (V-Q2, known) and the Standard View buttons
  agree with the verifier's records. Pixel routes: see RT-3. `script_exec` reads: see RT-2.
- Schema check of every `echo '<json>' | "$FCB_CUA" <tool>` payload: 605 payloads in the test cases,
  `test-plan.md` and `APPENDIX-B`. Keys, required fields and enum values were checked against
  `"$FCB_CUA" describe <tool>` of the live driver (11 tools). 0 mismatches. Every tool name exists in
  `list-tools`.
- TC-01-15 foreign holder, run as written, holder start to cleanup (`RT-tc01-15-foreign-holder.txt`): ERROR
  count `1`, no `spawned MCP proxy`, `LISTEN` only on the holder pid 19865, RPC listener up. The cleanup
  freed the port, and the restart got a new proxy (`freecad_pid` 20130).
- TC-10:153 discovery read with `python3` in the container: `20130 127.0.0.1 41917`.
- TC-13:519 relative `document_open`: `INVALID_INPUT ... does not exist` (`RT-tc13-519-relative.txt`).
- `fcb_py.sh` live in the container. TC-01-03 When, as written: prints `46`, and the JSON is written to the
  host run folder (`RT-fcb-py-tc01-03.txt`). `test_fcb_cua_wrapper.py` + `test_fcb_py_wrapper.py`:
  30 passed. The 10-9 RT-4 sibling and backslash cases are still in `test_fcb_py_wrapper.py:131-170`.
- `docker exec -u cua -e FCB_USER_DIR` with the test-plan exports gives the container path. Without
  `MSYS_NO_PATHCONV` it gives `C:/Program Files/Git/home/cua/...`, which is why the export is needed
  (`RT-env-passthrough.txt`).
- `"$FCB_CUA" status` exit 0, `Cua Driver daemon is running`. A screenshot to `$RUN_DIR` lands on the host.
- Q7 greps: 37 missing hard breaks in TC-15 only, 1 machine path in TC-16:23, 17 files, 274 headings.
  Q8: `src/`, scenarios, runner, watchdog and probe are unchanged.
- Census blind spot (K9 skips a whole line that holds `docker exec`): no host `curl` to `:8765` outside
  `docker exec` and outside the relay. No host `python -c` reads a container file.

## Tool blind spots shown

- `then-check.py` compares only Then and And-under-Then heads, and `census.sh` counts only host-command
  words. Neither can see RT-1 (a Given check whose meaning changed, written with container commands), RT-2
  or RT-3.
- `then-check.py` makes each `hand` reason from the host kinds in the base clause (`REASONS`). A hand edit
  that also weakens a check therefore gets a reason automatically. Q2 depends on a person reading each
  `hand` pair.

## Not reproduced (low)

- `cua-driver` returns exit 0 for tool errors: `get_window_state` on a dead pid prints `... is stale or no
  longer running`, and a missing `window_id` prints `Missing required integer field`. TC-01:403 and :581
  ("fails to capture") must be judged by the text, not by `$?`. The wording does not say so.
- Bad JSON on stdin (`{pid:`) makes `list_windows` list all windows with no error, so a typo in a payload
  is not reported.
- `fcb_paths.sh` has no left boundary: `/mnt<root>/x` would map to `/mnt/repo/x`. No payload has that form.
- The Start page of this profile still shows the first-run panel (`Done`, `Open First Start Setup`). The
  claim in test-plan §6 GUI routes ("a new container profile shows ...") is still correct. The panel can
  also show on a profile that is not new.
