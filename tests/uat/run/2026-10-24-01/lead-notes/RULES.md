# Rules for every re-run phase agent (run 2026-10-24-01)

Repo `D:\Work\Personal\Sources\freecad-buddy`, branch `fix/uat-gate-1-failures`. Run folder
`tests/uat/run/2026-10-24-01/` (read its `RUN-CONTEXT.md`). Previous run for reference and helper
scripts: `tests/uat/run/2026-10-23-02/` (report.md, evidence/*.py, *.ps1, *.sh).
Lead notes: `C:\Users\thuan\AppData\Local\Temp\claude\D--Work-Personal-Sources-freecad-buddy\1d05bc05-6255-4b66-ad49-2004ccbeed34\scratchpad\rerun\`.

## Never

- Never run git commit, reset, checkout, stash, switch, restore, clean, rebase, push.
- Never edit `src/`, `tests/uat/runner/`, `tests/uat/scenarios/`, `tests/uat/testcases/`,
  `scripts/`, `benchmarks/`, `.knowledge-base/`. A wrong test case is a finding, not an edit.
- Never open `benchmarks/*/heldout`.
- Never move, rename, truncate or delete any file outside the run folder and your own temp dirs.
  Read `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log` by byte offset only.
- Never end a FreeCAD you did not start. Never touch the two probe windows at the bottom-left of
  the screen (`FreezeProbe-GDI` and a WezTerm window printing the time): they are the lead's
  display-freeze probe.
- No Co-Authored-By, no idioms.

## Always

- FreeCAD GUI: non-elevated, `-u <temp>\user.cfg -s <temp>\system.cfg`. FreeCADCmd: the same two
  options. A python that imports FreeCAD in-process: `FREECAD_USER_HOME` set to a temp dir.
  Developer `%APPDATA%\FreeCAD\v1-1\user.cfg` SHA-256 must stay
  `4c415695ea8006ae1515001702c2bdf31674508d9a7705c7c73c9ce987d56b75`: hash it at phase start, at
  phase end, and after every launch; a change is a finding you report at once.
- Harness standard: `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md`
  (read it, incl. §2 Launch, Profile). Load the `cua-driver` skill before GUI work.
- One FreeCAD at a time. Before a launch: no `freecad.exe` running, `:8765` free. Log each launch
  in `evidence/launch-log.tsv` (phase, start, pid, profile, env, end).
- Isolation: one scenario at a time from its own Given; never run another scenario during a wait.
- Run `scripts/automation/uat_watchdog.py` between test cases and before File > Exit.
- Visual: every agent-driven scenario ends with a fit and a cua-driver capture that YOU read and
  describe. No MCP field, status or render is visual evidence. After any foreground cua-driver
  action, move the real pointer outside the FreeCAD window (move_cursor scope "desktop") and wait
  1 s before a capture. Before judging any capture, check the display is live: two captures a
  few seconds apart must differ somewhere (title, clock, tree), or the window must visibly
  reflect your last action. If the display is stale, wait up to 5 min, then mark the visual Then
  BLOCKED (display stale) and say so; never judge a stale capture.
- Grade every Then as written (owner rule D-lead-1): a Then not met literally is FAIL with a cause
  class (product defect / test-case defect / harness limit / agent execution fault), even when the
  product behaves as designed. A failed check is a finding with request, output and `file:line`,
  never a retry to get a PASS. An agent execution fault (your own mistake) is reported as such and
  the scenario is re-run once from its Given, and both runs are kept.
- Decisions: decide from `docs/intent.md` and `_bmad-output/specs/spec-freecad-buddy/SPEC.md`
  (with `ARCHITECTURE-SPINE.md`); cite the line.
- Owner acceptance recorded 2026-10-24 00:03 for TC-11-02/08/09/17 (exec-on, auto-approve-on,
  agent restarts, exec-off restart; temporary profiles only) still holds.
- H1 (headless stdio host) scenarios: use `FCB_ENV` as set up by phase R0 (see
  `scratchpad\rerun\h1-env.txt`). Export it before any sweep or H1 call.

## Output

- Evidence files in `tests/uat/run/2026-10-24-01/evidence/` named `tc-xx-yy-<what>.<ext>`.
- Verdict rows appended to `scratchpad\rerun\<phase>.txt`, one per scenario, exactly:
  `TC-xx-yy | <Priority> | <PASS|FAIL (cause)|BLOCKED (reason)> | <evidence files> | <note with file:line>`
  plus `FINDINGS:` and `LAUNCHES:` lines.
- Final message: short table of verdicts, findings, launches, user.cfg hash start/end, anything
  not done. No FreeCAD of yours left running, `:8765` free.
