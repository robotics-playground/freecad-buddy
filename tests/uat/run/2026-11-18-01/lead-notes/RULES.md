# Phase rules — run 2026-11-18-01 (Story 10-8-d, UAT Gate 1)

Read this file first, then the test case file(s) of your phase, then `tests/uat/test-plan.md` §3 and §6
(container routes: "Menu route", "Pixel points", "Tree row toggle", "GUI routes in the container",
"Process commands"). Write plain English. No idioms.

Run lead: `uatlead-10-8-d`. You are a phase agent (`uat-run-practices.md` §1). The run reports what it
finds: a FAIL is a finding, never a reason to change anything (spec D2).

## Never

- git commit, reset, checkout, stash, switch, restore, clean, rebase, push.
- Edit `src/`, `tests/uat/runner/`, `tests/uat/scenarios/`, `tests/uat/testcases/`, `scripts/`,
  `benchmarks/`, `.knowledge-base/`, `dist/`, or the docker files. A wrong test case is a finding, not an edit.
- Open, list or copy `benchmarks/*/heldout` (decision 43).
- Move, truncate or delete files outside the run folder and your temp dirs. Read `addon.log` by
  byte offset only; never rotate or edit it.
- Run FreeCAD on the Windows host. Every GUI step runs in container `fcb-desktop`.
- Rebuild the image or recreate the container (only the run lead does that).
- Retry a failed check to get a PASS. A failed check is a finding with request, raw output and `file:line`.
- Use host port 8765 (the host bridge port). The container proxy is reached on host `127.0.0.1:18765`.
- Spawn other agents.

## Always

- Host shell (Git Bash) setup before any command:
  ```bash
  export MSYS_NO_PATHCONV=1
  export PROJECT_ROOT=D:/Work/Personal/Sources/freecad-buddy
  export RUN_DIR=$PROJECT_ROOT/tests/uat/run/2026-11-18-01
  export RUN_DIR_C=/repo/tests/uat/run/2026-11-18-01
  export FCB_PYTHON=$PROJECT_ROOT/scripts/automation/fcb_py.sh
  export FCB_CUA=$PROJECT_ROOT/scripts/automation/fcb_cua.sh
  export FCB_USER_DIR=/home/cua/.local/share/FreeCAD/v1-1
  export FCB_CONFIG_DIR=/home/cua/.config/FreeCAD/v1-1
  ```
- Paths in MCP tool arguments and `cua-driver` JSON are container paths: `$PROJECT_ROOT` is `/repo`,
  `$RUN_DIR` is `/repo/tests/uat/run/2026-11-18-01`. Only `/repo/tests/uat/run/` is writable.
- MCP tools: `mcp__freecad-buddy-docker__*` (container proxy). GUI tools: `mcp__cua-driver-docker__*`, or
  `echo '<json>' | "$FCB_CUA" <tool>`. `cua-driver` exits 0 on a tool error: judge a step by its text.
  The tool lists are deferred: load them with ToolSearch (`+freecad-buddy-docker`, `+cua-driver-docker`).
- FreeCAD: start with `docker exec -u cua fcb-desktop fcb-freecad start` (add `-e NAME=value` after
  `-u cua` when a Given sets a variable). Ready when `curl -fsS http://127.0.0.1:18765/healthz` shows a
  number in `freecad_pid`. Take the window id from `list_windows` (pid from `/healthz` or
  `fcb-freecad status`). Stop with `docker exec -u cua fcb-desktop fcb-freecad stop`; done when
  `fcb-freecad status` shows no pid. The first start in this container shows a Welcome panel on the
  Start page: press its `Done` button by token.
- One FreeCAD at a time. Before each launch: `fcb-freecad status` shows no pid. Append one row per
  launch to `$RUN_DIR/evidence/launch-log.tsv`:
  `phase<TAB>start ISO<TAB>freecad pid<TAB>profile (container)<TAB>env (or -)<TAB>end ISO<TAB>how ended`.
- Hash the developer `user.cfg` at phase start and phase end:
  `sha256sum "$APPDATA/FreeCAD/v1-1/user.cfg"`. Run baseline since 21:15: `63fa48cfe55eb515b30113b21e4732da70a1aa0b877c51dab3b8a4e979b9bd2a` (changed by a host FreeCAD the run did not start; decision 8 value was `b89a9771...d85a0`).
- One scenario at a time, each from its own Given. Close open documents when a Given needs none.
- Watchdog between test cases and before you stop FreeCAD at phase end:
  `docker exec -u cua fcb-desktop fcb-py /repo/scripts/automation/uat_watchdog.py --pid <pid> --window <wid> --since "2026-11-18T19:29:00+0700"`.
  A surviving `FCB_TMP_snap_*` (exit 1 naming it) stops your phase: report it to the run lead at once.
- Every agent-driven scenario ends with a fit (test-plan §3 rule 5) and a `cua-driver` capture written
  with `screenshot_out_file` under `$RUN_DIR_C/evidence/`, which you `Read` and describe (what is on
  screen: part present, whole, not clipped, right shape, dialogs). No MCP field, status or
  `query_screenshot` render is visual evidence.
- Grade every Then as written. Not met literally = FAIL with one cause class (`uat-run-practices.md`
  §7): `product defect`, `test-case defect`, `harness limit`, `agent execution fault`. Read the design
  before you blame the product. An agent execution fault (your own mistake) allows one re-run from the
  Given; keep both runs.
- A step that no element, key or pixel route serves is `NOT RUN` (reason). A Then you did not execute
  is never PASS.
- On a FAIL: save the diagnostic state to evidence (document list, tree summary, capture, log tail by
  byte offset) before you go on, and do not run that scenario's Cleanup. Then continue with the next
  scenario from its own Given.
- TC-02-08 runs as written; a FAIL there is a product finding, deferred (decision 34).
- Decisions cite the deciding line in `docs/intent.md`, `_bmad-output/specs/spec-freecad-buddy/SPEC.md`
  or `ARCHITECTURE-SPINE.md` (`file:line` and a short quote).
- A step that needs a human decision (a disputed visual): record it, give your best grade with the
  reason, mark it `HUMAN?`, and continue.
- Write each row to your report file as soon as the scenario ends, so a stop keeps the rows.
- When the session limit is near: finish the current scenario, write its row, and stop with a report
  that names the next scenario.
- At phase end: close every document, run the watchdog, stop FreeCAD, confirm no pid, hash `user.cfg`.
  Leave nothing of yours running.

## Watch items from earlier phases

- R0b-1 F1 (serious): a replay script used the MCP client default URL `http://127.0.0.1:8765/mcp` and
  drove a FreeCAD on the Windows host (the owner's). Every MCP client you write sets
  `http://127.0.0.1:18765/mcp` explicitly; print the URL before the first call. Before any script call,
  check that `curl -fsS http://127.0.0.1:18765/healthz` names the container FreeCAD pid you started.
- Lead grading rule (TC-07-03): a visual Then is graded in the state the scenario defines. Do not add
  a GUI step the test case does not contain (for example Sketcher edit mode) to make a Then pass;
  record the Then as not met and name the missing step (test-case defect).

- R0a-1 F2: after a GUI **Fit All** toolbar press the container 3D view can repaint 15 to 20 s late; a
  capture taken at once shows the old camera (status bar size unchanged). Wait about 20 s, take two
  captures a few seconds apart, and judge only a capture that shows your last action
  (`uat-run-practices.md` §6 live display check).
- R0a-1 F3: the `Show All Objects` leaf press by `element_token` can return `unverifiable` and leave
  objects hidden. Check with `query_tree_summary` (`v` marker). If it did not take effect, use the
  tree-row toggle (test-plan §6 "Tree row toggle") and record which route you used.
- R0a-1 F6: the container has no font for emoji (U+1F527 draws as an empty box). A visual Then on an
  emoji glyph is a `harness limit` FAIL; the label text itself is checked through `document_list`.

## Output

- Evidence: `$RUN_DIR/evidence/tc-xx-yy-<what>.<ext>` (captures `tc-xx-yy-after.png`, `-before.png`).
- Report file: `$RUN_DIR/lead-notes/phase-<id>-report.md`, with:
  - a table `| Scenario | Priority | Verdict | Evidence | Note |`, one row per scenario of your list.
    Verdict is `PASS`, `FAIL (<cause class>)`, `NOT RUN (<reason>)` or `BLOCKED (<reason>)`. The note
    names the Thens checked, the raw value for each failed Then, `file:line`, and what the capture shows.
  - `FINDINGS:` one line each: id, short title, cause class, request, raw output, `file:line`.
  - `LAUNCHES:` one line per FreeCAD launch (also in `launch-log.tsv`).
  - `user.cfg` hash at phase start and end.
  - Watchdog results between test cases.
- Final message to the run lead (at most 15 lines): report file path, counts by verdict, each FAIL /
  NOT RUN / BLOCKED id with its cause class, findings count, launches count, `user.cfg` equal yes/no,
  FreeCAD stopped yes/no, any `HUMAN?` item.
