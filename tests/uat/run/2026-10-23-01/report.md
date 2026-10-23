# UAT run 2026-10-23-01: replay of run 2026-10-03-04 through the scripted runner

Story 10.7b part V (AC9). The scripted runner (`tests/uat/runner/run.py`) ran 45 scenario files on
FreeCAD 1.1.4. `tests/uat/runner/compare.py` compared each runner verdict with the verdict of UAT
run `2026-10-03-04` and wrote `replay.md`. The agent then read every capture of the run (D4).

## Build and launches

| Field | Value |
| --- | --- |
| Code | `3ca2add` plus the uncommitted part V changes (`git_dirty: true`): scenario files, runner D3 retry; `src/freecad_buddy` unchanged |
| FreeCAD | 1.1.4 (`results.json` `run.freecad_version`), started by the runner with a temporary `-u` profile and `-M tests/uat/probe` |
| Addon | `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy`, `freecad_buddy` linked to `src\freecad_buddy` |
| Launch groups | default (36 scenarios), `FREECAD_BUDDY_AUTO_APPROVE=0` (8: TC-05 x4, TC-08 x4), `FREECAD_BUDDY_SCRIPT_EXEC=0` (1: TC-11-17); no group error |
| Sample seed | `1461316941`, `drawn` |
| Duration | 14:16:42 to 14:23:05 (+07:00), 6 min 23 s |

Runner runs made for this replay:

1. A scratch run of the same 45 files, outside the repository, before this one. Verdicts: 21 PASS,
   1 FAIL, 23 ESCALATE, the same verdict per scenario as this run. One Show All delivery was refused
   once and delivered on the second attempt (TC-02-04, `attempts: 2`, D3).
2. This run, `tests/uat/run/2026-10-23-01`. No scenario file changed between the two runs. No Show
   All delivery was refused (`attempts: 1` on every menu step).

After each run: no `freecad.exe` ran, nothing listened on `127.0.0.1:8765`, and the developer
`user.cfg` SHA-256 was `902837a3…4b32` before and after both runs.

## Runner result

45 scenarios: 21 PASS, 1 FAIL, 23 ESCALATE. Exit code 1 (the FAIL).

- Every ESCALATE has one reason only: its `agent_check`. No step raised, no probe/MCP disagreement,
  no missing capture.
- The FAIL is TC-11-17: `pixel view: expected "a 3D view", observed null`. See Calibration and
  `bugs.md` B1.

## Replay comparison

`replay.md` has one row for each of the 251 scenario ids of TC-01..TC-14 at `bece7ac` and the 4 ids
added in Story 10.7 (255 rows). No row is `unexplained`; `compare.py` exit 0.

| Row | Count | Meaning |
| --- | --- | --- |
| same | 32 | runner verdict matches the 2026-10-03-04 verdict under the verdict map |
| differs | 12 | old `FAIL`, runner `PASS` or `ESCALATE` (`agent_check` only); each has a class |
| not covered | 174 | a deterministic Then needs something the runner schema cannot state; one closed-set reason each |
| not encoded | 30 | runner-expressible, outside the D2 subset; left to Story 10.8 |
| new | 7 | TC-01-15, TC-11-17, TC-11-18, TC-11-19 (added in 10.7), and TC-06-10, TC-06-11, TC-13-17 (old `BLOCKED` or `SKIP`, not compared) |
| removed | 0 | no old id is missing from the current test cases |

The 12 differences:

| Class | Scenarios |
| --- | --- |
| `product fixed (F-04, 10.2)` | TC-03-05 (also F-05, F-06) |
| `product fixed (F-05, 10.2)` | TC-03-06 |
| `product fixed (F-09, 10.3)` | TC-05-03 |
| `product fixed (F-11, 10.3)` | TC-05-08 (also F-10) |
| `product fixed (F-12, 10.1)` | TC-05-14 |
| `product fixed (F-14, 10.4)` | TC-06-03 |
| `product fixed (F-17, 10.2)` | TC-07-03 |
| `test case changed (10.7 edit)` | TC-02-13, TC-02-17, TC-05-15, TC-08-14, TC-13-06 |

TC-05-15: 10.7 changed the When from the Pad Length edit to a fillet radius edit, so the F-13 path
(fixed by Story 10.3 D6) is not exercised.

Ids the runner did not run, by reason (174 `not covered` and 6 `new`): `file check` 55, `H1 host`
35, `GUI action` 34, `raw RPC or second client` 21, `comparison op` 18, `process kill or relaunch` 8,
`log or audit read` 7, `timing bound` 2.

Partial coverage: 35 scenario files encode only part of the deterministic Thens of their test case.
Each such row in `replay.md` ends with `Not checked: <Then> (<reason>)`, so a `same` row names what
it did not check. Most are the before-capture Givens (`GUI action`), set or membership Thens encoded
by index (`comparison op`), and the H1, log and file parts of the part R pilots. The TC-06 render
Thens are not in that list: the agent read the render copies (D4), and the rows say so.

After this run, review removed two range checks that stood in for an inequality: `tc-03-13.json`
`counts.PASS` (`approx 50.5 ± 49.5`) and `tc-02-12.json` `total_edges` (`approx 1001 ± 999`). Both
passed in this run and are now in `left_out` as `comparison op`. The committed files are those
two checks short of the files this run executed; no other scenario file changed.

Of the 34 old FAILs, 12 are encoded. The other 22 are `not covered`; no old FAIL is `not encoded`.

## Agent review (D4 calibration read)

The agent read all 45 window captures and the 13 render PNGs the TC-06 scenarios copy into the run
folder. Reason: the runner's `review` reason, or `calibration read` for a scenario outside the
review set. Verdict: the agent's verdict on the visual Thens the capture can settle. Where an
`agent_check` asks for a live action this replay did not take (GUI Fit All, Sketcher edit mode, a
capture before the save or between steps, the MCP render kept), the line says NOT JUDGED or PARTIAL;
that follow-up is left to Story 10.8.

- TC-02-01 (no pixel check): Start page, no document open, no dialog. The pilot ends with the close; the visual Then (reopened document framed) is not reached. NOT JUDGED
- TC-02-02 (first of TC-02): one whole box inside the 3D view, Box in the tree, no dialog. PASS
- TC-02-03 (sample): one whole cylinder, title `tc-02-03-uat-saveas`, no dialog. PASS
- TC-02-04 (calibration read): one whole sphere, `sphere-r10` active, no dialog. PASS
- TC-02-06 (calibration read): one whole pad (20 x 10 x 5), Body in the tree, no dialog. PASS
- TC-02-12 (escalate): top view, Fusion at the top right and cut by the view edges; unframed, the runner has no GUI Fit All. NOT JUDGED
- TC-02-13 (escalate): document `tc-02-13-uat-unicode`, empty view, no dialog. The Unicode Then needs a capture before the save. NOT JUDGED
- TC-02-15 (escalate): top view, box cut by the view edges; unframed (no GUI Fit All). NOT JUDGED
- TC-02-16 (escalate): top view, sphere zoomed past the view; unframed (no GUI Fit All). One window, no orphan view, no dialog. NOT JUDGED
- TC-02-17 (escalate): top view, box cut by the view edges; unframed (no GUI Fit All). No dialog. NOT JUDGED
- TC-03-05 (escalate): sketch MixedProfile: a line, a circle, an arc and a point, all inside the view. Colours and constraint marks need edit mode. NOT JUDGED
- TC-03-06 (escalate): sketch ConstraintBed: lines, touching circles and points, all inside the view. Colours and constraint marks need edit mode. NOT JUDGED
- TC-03-07 (escalate): one whole slab about 25 x 40, no hole, gap or broken face. The edit-mode rectangle is not checked. PARTIAL
- TC-03-13 (escalate): one whole plate. The projected external curve shows only in edit mode. NOT JUDGED
- TC-03-20 (escalate): one whole 5 mm plate with the BossProfile circle on its top face, no torn face. The edit-mode projection is not checked. PARTIAL
- TC-04-02 (first of TC-04): one 20 x 30 x 10 block, footprint wider than its height, no extra solid. PASS
- TC-04-03 (escalate): one 20 x 30 x 10 block with the XY sketch outline drawn at mid-height, so the pad straddles the sketch plane. PASS
- TC-04-09 (escalate): plate with four rounded vertical corners, and the OtherBody block beside it. PASS
- TC-05-03 (no pixel check): the 20 x 20 sketch outline only, no solid: the pad rolled back. PASS
- TC-05-08 (first of TC-05): one whole 20 x 20 x 30 pad, no fillet left behind. PASS
- TC-05-14 (calibration read): one whole 20 x 20 x 30 pad, unchanged. PASS
- TC-05-15 (sample): 20 x 20 x 30 pad with one rounded vertical edge (the 3 mm fillet). PASS
- TC-06-03 (escalate): window: PadA and BoxB. Renders: default both solids; include PadA only; exclude PadA shows BoxB only; include BodyA shows the Tip solid, not blank; no datum. PASS
- TC-06-04 (escalate): window: BoxA and BoxB in their own grey. Renders: BoxA red, BoxB grey; BoxA red and translucent with BoxB behind; transparency 0 shows BoxA, 100 hides it. PASS
- TC-06-05 (escalate): window: two adjacent boxes. Renders: the focused render fills more of the frame with BoxA; highlight draws BoxA orange, BoxB grey. PASS
- TC-06-07 (escalate): window: one whole box. Renders: the custom-quaternion render and the iso render show the same view. PASS
- TC-07-01 (first of TC-07): one whole box, no dialog. PASS
- TC-07-02 (calibration read): one whole cylinder, no dialog. PASS
- TC-07-03 (escalate): one sketch line framed edge to edge, the Group object in the tree; constraint marks and the fully-constrained colour show only in edit mode. NOT JUDGED
- TC-08-03 (first of TC-08): one whole 20 x 20 x 30 pad. PASS
- TC-08-08 (calibration read): one whole 20 x 20 x 30 pad. PASS
- TC-08-13 (calibration read): one whole 20 x 20 x 30 pad. PASS
- TC-08-14 (escalate): the flat 20 x 20 sketch outline, no solid, no dialog. PASS
- TC-09-03 (first of TC-09): one whole box, no dialog. PASS
- TC-09-12 (sample): one whole box, no dialog. PASS
- TC-09-17 (escalate): the last valid block; the Pad tree icon carries the error mark. PASS
- TC-09-18 (escalate): the last valid block; the Pad tree icon carries the error mark and Pad has no Sketch under it. PASS
- TC-11-01 (first of TC-11): one whole box, no dialog. PASS
- TC-11-17 (fail): one whole box inside the 3D view, framed, no dialog; the visual Then is met. The `view: null` finding is not on screen (B1). PASS on the visual Then
- TC-12-07 (escalate): one whole block, Edit menu title highlighted after Edit > Recompute, no dialog. The clean and dirty states between steps are not captured. NOT JUDGED
- TC-13-04 (escalate): a flat 40 x 40 x 10 plate with one centred through-hole. The MCP render is not kept, so parity is not judged. NOT JUDGED
- TC-13-06 (escalate): the same plate; the render is not kept, so render parity is not judged. NOT JUDGED
- TC-14-02 (first of TC-14): one whole box, framed. PASS
- TC-14-07 (calibration read): one whole box, framed. PASS
- TC-14-16 (calibration read): one whole box, framed; title carries `*` (modified). PASS

In most captures the Tasks panel (`Start Part`) overlaps the right side of the 3D view and covers a
corner of the part. The part stays inside the view. This is the fresh-profile layout, the same as
in part R, and not a finding.

### Calibration: pixel check against the agent reading

| Count | Value |
| --- | --- |
| Scenarios with a `pixel` block that has `samples` | 32 |
| Pixel check passed, agent judged the visual Then met | 27 |
| Pixel check passed, agent judged the visual Then in part (PARTIAL) | 2: TC-03-07, TC-03-20 |
| Pixel check passed, the capture cannot settle the visual Then (NOT JUDGED) | 2: TC-03-13, TC-12-07 |
| Pixel false alarm (pixel finding, agent sees the visual Then met) | 1: TC-11-17 |
| Pixel miss (pixel check passed, agent sees a failed visual Then) | 0 |

TC-11-17 is not a fault of the pixel measurement. `check_pixel` reported `view` null because the
probe snapshot had no active 3D view; it measured nothing. The window shows the box framed. The
probe reads no active view after the first `query_capabilities` of a launch (the open deferred
product finding: `usecases/shim.py` opens its probe documents without `hidden=True`). See `bugs.md`
B1.

Summary of the agent verdicts on all 45 scenarios: 30 PASS (TC-11-17 counted on its visual Then),
2 PARTIAL (TC-03-07, TC-03-20), 13 NOT JUDGED (TC-02-01, TC-02-12, TC-02-13, TC-02-15, TC-02-16,
TC-02-17, TC-03-05, TC-03-06, TC-03-13, TC-07-03, TC-12-07, TC-13-04, TC-13-06). No agent reading
contradicts a scripted PASS. The 13 scenarios without pixel samples are all in the review set
(`no pixel check` or `escalate`). The 15 PARTIAL and NOT JUDGED scenarios are handed to Story 10.8
in `deferred-work.md`.

## Verdicts this report counts

`results.json` keeps the scripted verdicts. Under test-plan §9 "The window wins", the TC-11-17 visual
Then is met. The `view` finding stays open as the product finding in B1, so TC-11-17 stays FAIL in
this report. No other agent verdict contradicts a scripted verdict. This run is a replay, not a
Gate 1 run.
