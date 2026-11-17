# UAT Run 2026-10-23-02 — Gate run TC-01..TC-14, TC-99 and G3 replay on FreeCAD 1.1.4

Status: STOPPED EARLY by a display freeze. Gate 1 RED: Critical 126/174 = 72.4 %, High 54/67 = 80.6 % (33 FAIL, 33 BLOCKED of 255). Gate 2 not run: all 5 TC-99 scenarios BLOCKED. G3 headless replay UNCHANGED against `g3r-2026-10-08-1.1.3`; G3 GUI replay not run (BLOCKED). P11 (TC-13), P12 (TC-14, TC-99) and the G3 GUI replay did not run. Story 10.8 stays open. Spec: `_bmad-output/implementation-artifacts/spec-10-8-d-uat-gate-1-run.md`.

Terms used in this report:

- **Gate 1**: pass rule of the test plan (`tests/uat/test-plan.md:342-441`). Critical scenarios must all PASS (100 %); High scenarios need >= 95 % PASS.
- **Gate 2**: TC-99 conformance check. Each TC-99 scenario documents a known gap against an architecture decision (`AD-n`, in `ARCHITECTURE-SPINE.md`); the run checks that the gap still shows as documented.
- **G3 replay**: replay of the corrupted-plan suite (`benchmarks/g3/fault-injection/`): 10 planted defects must be DETECTED, their 10 reverted builds and 4 controls must pass clean.
- **Runner**: the scripted UAT runner `tests/uat/runner/run.py`. It runs the 72 scenario files in `tests/uat/scenarios/` with no LLM. A scenario it cannot fully grade is ESCALATE; the agent then reads its capture (test-plan §9).
- **Agent-driven scenario**: a scenario with no scenario file. An agent runs it through MCP and `cua-driver` (the desktop automation tool) and reads the window capture.
- **H1**: the headless stdio host (`freecad-buddy serve --transport stdio --mode inline`), with FreeCAD running inline in a worker process. **H2/GUI**: the FreeCAD GUI with the addon; MCP over HTTP on `:8765` through the proxy the addon spawns.
- **Display freeze**: from 2026-10-24 about 08:15, GPU-drawn windows (FreeCAD, WezTerm) stopped repainting on screen and in captures until a physical mouse move. See Execution notes.

Evidence legend for the tables: `cap/TC-xx-yy` = `runner/captures/TC-xx-yy.png`; `ev/<name>` and a bare file name = `evidence/<name>`; `runner/<name>` = runner output. Line numbers in notes are at commit `3025e7c`.

## Build banner

| Field | Value |
| --- | --- |
| Code under test | `3025e7c` (`test(uat): drop the stale fingerprint premise from TC-08-07`). Runner records `git_dirty: true`: untracked spec file and this run folder only. No edit to `src/`, the runner or the test cases during the run |
| FreeCAD GUI | **1.1.4**, `C:\Program Files\FreeCAD 1.1\bin\freecad.exe` (`runner/results.json` `freecad_version`, window title, `query_capabilities.freecad_version`) |
| Addon install | Junction `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy` → `src\freecad_buddy` (`results.json` `addon.linked: true`) |
| Tool surface | `tools/list` = 46 with `script_exec` (TC-01-03) |
| `query_capabilities` | 9 keys; `element_map_available: true`, render `gui_constructed`, `exec_enabled: true` (TC-01-04) |
| RPC contract | `"1"` (TC-01-06) |
| Operator posture | Preferences default: `script_exec` ON, mutation auto-approve ON. Launches with `FREECAD_BUDDY_AUTO_APPROVE=0` or `FREECAD_BUDDY_SCRIPT_EXEC=0` are marked in the launch table. Owner accepted this posture for the run on 2026-10-24 00:03 (decision D-lead-3) |
| H1 leg | Stand-in venv `scratchpad\h1env` on FreeCAD 1.1.4's Python 3.11.14; `freecad-buddy 0.1.1` (non-editable copy of `3025e7c`, `diff -r` identical to `src/freecad_buddy`), `mcp 1.30.0`. The `fcb` micromamba env of `tests/uat/APPENDIX-B-environment-setup.md` step 3 does not exist on this machine (`evidence/h1-setup.txt`) |
| Runner | `uv run python tests/uat/runner/run.py tests/uat/scenarios --out tests/uat/run/2026-10-23-02/runner`, no `--seed`. Seed **1748575703** (drawn). Ran 16:59:57-17:06:27 on 2026-10-23 (`results.json` `started` 16:59:59), **exit 1**: 72 scenarios, 5 PASS, 1 FAIL, 66 ESCALATE, 0 run errors. Three launch groups: default (56 files, pid 29916), `FREECAD_BUDDY_AUTO_APPROVE=0` (15 files, pid 25344), `FREECAD_BUDDY_SCRIPT_EXEC=0` (TC-11-17, pid 18020) |
| Developer `user.cfg` SHA-256 before | `ccf87cfe7650daa8d9f533b0e10c5dc7ae1db0c7a3aa68df3a44a04c0973832b` (`RUN-CONTEXT.md`). See Teardown for the state after |
| Audit logs | One per launch, `evidence/<tag>-audit.jsonl`; runner `runner/audit-group-{0,1,2}.jsonl` |

## Harness gate

- Preflight (`RUN-CONTEXT.md`): no `freecad.exe`, nothing on `:8765`, tree clean except the spec file.
- `cua-driver` daemon: found elevated (pid 23404); restarted non-elevated (pid 5516) before the agent launches (P0 finding F3).
- FreeCAD launches: `Start-Process` from the agent shell (Medium integrity, not elevated), `freecad.exe -u %TEMP%\fcb-uat-<phase>-<tag>\user.cfg`, inherited `FREECAD_BUDDY_*` removed. `launch_app` was not used, because it cannot set the profile or the environment (P2 finding F-P2-4).
- Control: `cua-driver` drives the live window (UIA clicks by element token, `invoke_menu`, NaviCube clicks, foreground pixel clicks where UIA has no element).
- Observation: `get_window_state` writes the real window pixels. The executing agent read every closing capture; the lead read the disputed ones.
- Watchdog `scripts/automation/uat_watchdog.py` between test cases: every run exit 0 (`evidence/p*-watchdog-*.txt`). One P6 run came after FreeCAD exit (agent order fault): `freecad-window` FAIL as expected, temp hygiene OK.
- Phase end checks (`evidence/p*-endcheck.txt`): 0 FreeCAD, `:8765` free, `user.cfg` hash equal to the run baseline, after every phase P0-P10.

## Execution notes

The run went phase by phase, one FreeCAD and one desktop at a time (`RUN-CONTEXT.md`). Times are local (+07:00).

| Phase | When | Scope | Outcome |
| --- | --- | --- | --- |
| P0 | 2026-10-23 16:59-19:04 | Runner run of the 72 scenario files; §9 agent review of the 71-capture review set (66 ESCALATE, 1 FAIL, first of TC-04 and TC-14, 1 no-pixel-check, 1 random sample) on agent launches f1-f7 | 72 rows graded. Runner FAIL TC-08-04 regraded PASS (D-lead-2, scenario-file defect) |
| P1 | 2026-10-23 19:10-19:34 | TC-01, 15 agent-driven | 12 PASS, 3 FAIL |
| P2 | 2026-10-23 19:40-20:05 | TC-02 (8) and TC-03 (6) agent-driven | 1 FAIL (TC-02-08) |
| P3 | 2026-10-23 20:08-20:28 | TC-04, 14 agent-driven | 3 FAIL (test-case) |
| P4 | 2026-10-23 20:36-20:50 | TC-05, 14 agent-driven, `AUTO_APPROVE=0` | 2 FAIL (test-case) |
| P5 | 2026-10-23 20:55-21:41 | TC-06 (8) and TC-08 (10) agent-driven, plus H1 legs | 6 FAIL |
| P6 | 2026-10-23 21:46-22:05 | TC-07, 18 agent-driven | 0 FAIL |
| P7 | 2026-10-23 22:10-22:36 | TC-09, 18 agent-driven, 11 H1 starts | 5 FAIL |
| P8 | 2026-10-23 22:50-23:56 | TC-10, 14 agent-driven, H1 legs | 3 FAIL |
| P9 | 2026-10-24 00:00-08:03 | TC-11, 17 agent-driven, H1 legs. Launch C stayed open 00:44-08:03 under an Explorer window (Human interventions) | 3 FAIL, 1 BLOCKED |
| P10 | 2026-10-24 08:08-10:44 | TC-12, 14 agent-driven (TC-12-07 came from the runner) | 3 PASS, 7 FAIL, 5 BLOCKED; display freeze from 08:15 |
| P13 headless | 2026-10-24 08:44:36-08:44:55 | G3 headless scorer (no display needed) | UNCHANGED |
| P11 | not run | TC-13, 16 agent-driven | BLOCKED (display freeze) |
| P12 | not run | TC-14 (11 agent-driven) and TC-99 (5) | BLOCKED (display freeze) |
| P13 GUI | not run | G3 GUI replay (`tests/uat/run/2026-10-03-04/evidence/g3_gui_replay.py`) | BLOCKED (display freeze) |

Display freeze (lead log `_bmad-output/implementation-artifacts/lead-log-2026-10-24-uat-fixes.md` §2, P10 findings F-P10-4 and F-P10-17):

- Symptom: after some minutes with no physical mouse or keyboard input, GPU-drawn windows (WezTerm, FreeCAD) stop updating on the monitor and in screen captures. The taskbar clock keeps updating. A physical mouse move ends it. `cua-driver` `move_cursor` (desktop scope) does not end it.
- Seen 2026-10-24 about 08:15 (FreeCAD found minimized 08:15:49, unknown cause) to 09:18:12, and 10:03:54 to about 12:20. Launches after 10:04 showed black blocks until 10:44. Evidence: `evidence/lead-desktop-0910.png`, `evidence/lead-freeze-test-*.png`, `evidence/p10-recovery-watch.txt`, `evidence/p10-freeze2-diag.txt`.
- Checked without a cause found: power plan (display never turns off, no screen saver), event logs (nothing display or power related), GPU driver state, DWM overlay setting. An idle test without `cua-driver` activity (12:30-12:33) did not freeze.
- Hypothesis, not proven: the freeze needs both `cua-driver` activity and no physical input; the two full-screen `Cua.AgentCursorOverlay` windows are the main suspect. A probe experiment was running at report time.
- Effect: P10 visual checks after 08:15 were re-run on a painting display where possible (TC-12-05, -09, -10 at 09:50-09:57) or graded BLOCKED. P11, P12 and the G3 GUI replay did not start.

Other notes:

- Every agent-driven scenario closed with a fit (MCP `view_fit_viewport`, or FreeCAD's own Fit All where the MCP fit returns `nothing_to_frame`) and a `cua-driver` window capture that the agent read.
- A failed check was recorded as a finding with request, output and `file:line`; no retry for a PASS. Agent faults that sent a wrong request were re-sent once with the correct request and the faulty attempt kept as `*-fault1*` (P9 B12, TC-12-06, TC-10-01 clock fault, TC-11-11, TC-11-12).
- No file under `benchmarks/*/heldout` was opened. `benchmarks/` SHA-256 unchanged over P6.


## TC-01 — Session Lifecycle & Transport

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-01-01 | Critical | **PASS** | tc-01-01-after.png, tc-01-01-addon.log, tc-01-01-recovery-dialog.png | Listener and spawn lines in log. :8765 owned by pid 29316, parent 24036 (spawn-line pid), parent FreeCAD 8380. Proxy command uses .venv; no serve by hand. Capture: one whole grey box iso, all inside view, no dialog. Launch by p1_launch.ps1 (runner Start-Process method). |
| TC-01-02 | Critical | **FAIL** | tc-01-02-sweep-stdout.txt, tc-01-02-e2e_report.json, before/after.png | Sweep as written exits 2 (no fcb env). With P0 H1 interpreter exits 1, 4/9: every tree_summary check NO_STATUS. stderr no faults; GUI query_capabilities OK; window unchanged. Cause F1 sweep script. |
| TC-01-03 | Critical | **PASS** | tc-01-03-tools_list.json, after.png | 46 tools, script_exec present, no export_self_read_*; family counts exact, 13 read-only names, additionalProperties false on all 46. Capture one whole box. |
| TC-01-04 | Critical | **PASS** | tc-01-04-rpc.jsonl, tc-01-04-capabilities.json, after.png, after2.png | 9 keys exact, 1.1.4 matches title and rpc-27956.json; element_map_available true, render gui_constructed, exec_enabled true. Proxy stopped: raw rpc_hello capabilities {gui true, qt_loop true, exec_enabled true} = query_capabilities. Proxy restarted by hand with operator-settings values; 46 tools. after2: one whole iso box. |
| TC-01-05 | High | **PASS** | tc-01-05-budgets.txt, after.png | 4 budgets, 30/60/120/180 s sets, mutating flags match. Capture one whole box. |
| TC-01-06 | Critical | **PASS** | tc-01-06-rpc.jsonl, before/after.png | {"code": -32004, "message": "contract version unsupported", "data": {"supported": ["1"]}}, no capabilities, second read "". Listener up. Captures identical. |
| TC-01-07 | Critical | **PASS** | tc-01-07-rpc.jsonl, tc-01-07-addonlog-lines.txt, before/after.png | wrong and omitted token with contract 99: -32000 "auth failed", not -32004; addon.log 2 "token mismatch; closing". Captures identical. |
| TC-01-08 | Critical | **PASS** | tc-01-08-rpc.jsonl, tc-01-08-addonlog-lines.txt, before/after.png | tool call first frame: -32002 "handshake required" id 3, socket closes; "not json": -32002 id null; log line "first frame was not rpc_hello; closing". Captures identical. |
| TC-01-09 | High | **PASS** | tc-01-09-discovery.json (token redacted), tc-01-09-rpc.jsonl, after.png | keys exact, pid 27956 live, 127.0.0.1:61484 LISTENING by it, contract_version "1", 1.1.4; token authenticates. Capture by discovery pid: one whole box. |
| TC-01-10 | High | **PASS** | tc-01-10-before.png | File > Exit closed FreeCAD in 2 s; rpc-27576.json gone; proxy gone; :8765 no LISTEN; 58 other rpc files unchanged. Before: box top view, no dialog. |
| TC-01-11 | High | **PASS** | tc-01-11-rpc.jsonl, before/after.png | dead pid 28980: ConnectionRefusedError 2.05 s, no reply; stale file stays; live bridge OK. Captures identical. |
| TC-01-12 | High | **PASS** | tc-01-12-checks.txt, before/after.png, tc-01-12-proxy.*.log | Only proxy child 29316 stopped; FreeCAD 8380 alive, :8765 free. Proxy restarted by hand (AUTO_APPROVE=1 SCRIPT_EXEC=1, run audit log). rpc-8380.json byte-identical (port 59884, same token). New LISTENING pid 30256, /healthz freecad_pid 8380; query_capabilities 1.1.4; old handle answers "OK: 1 objects, 1 shown."; document_list lists box-10-20-30; fit OK. Captures: same window, same tree label, one whole iso box, no dialog. |
| TC-01-13 | Medium | **FAIL** | tc-01-13-checks.txt, -addon.log, -cli.txt, -startpage.png, -after.png | cause: test-case defect. Visual Then `TC-01...md:520-521` asks for a 3D view and Fit All, but the scenario opens no document (Start page). FREECAD_BUDDY_NO_AUTO_MCP=no: listener 127.0.0.1:62818, rpc-6456.json; log "FREECAD_BUDDY_NO_AUTO_MCP set; not auto-starting the MCP proxy"; no LISTEN on :8765. CLI stderr: "--mode rpc requires --transport http." exit 2; "transport 'http' is not available yet; use --transport stdio." exit 2. startpage.png: Start page, no 3D view, Fit All disabled; after.png (GUI New Document + Fit All): tree Unnamed, empty 3D view, no dialog. Defect: scenario asks for a 3D view but opens no document. |
| TC-01-14 | High | **PASS** | tc-01-14-checks.txt, -kill.txt, -mcp-proxy.log, -rpc.jsonl, before/after.png | kill_app refused (foreign_process_termination_denied); Stop-Process 28980. TCP connect 62907 refused 2.03 s; MCP call httpx.ConnectError; proxy exit 0.5 s after kill, 1 line; :8765 free in 5 s; rpc-28980.json stays. Relaunch 22308: rpc-22308.json, /healthz 200 freecad_pid 22308, proxy 6060 != 17320, new token, no "MCP proxy not started". Killed token to new listener: -32000 "auth failed". Captures: before box top view; after one whole iso box, no recovery prompt. |
| TC-01-15 | Critical | **FAIL** | tc-01-15-checks.txt, -healthz.txt, -addon.log, -before/-probed/-startpage/-after.png | cause: test-case defect. Visual Then `TC-01...md:630` asks for a 3D view; no document is open. /healthz 200 application/json {"service":"freecad-buddy-mcp-proxy","freecad_pid":22308,"session_id":"f30d4e2fe98e68a0"}, no token. before = probed (whole box). http.server holding 8765 (pid 28228): relaunch 29308 logged exactly 1 ERROR "MCP proxy not started: port 8765 is still held by another program, or by an MCP proxy from an older freecad-buddy build after 10.0 s. ..."; no spawn; listener up 127.0.0.1:61358. Captures: Start page, then GUI New Document empty 3D view, no dialog, no Not Responding. Same defect as TC-01-13. |

## TC-02 — Document Ingestion & Handles

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-02-01 | Critical | **PASS** | cap/TC-02-01, ev/tc-02-01-after.png, tc-02-01-mcp.jsonl | (escalate) runner: Start tab with welcome panel, no doc. Reopen + GUI Fit All (MCP fit SPEC_FAILED nothing_to_frame): one view "tc-02-01-uat-roundtrip", one tree entry, empty view, no 2nd view, no dialog. doc != name; saved file 1752 B, exists after close. |
| TC-02-02 | Critical | **PASS** | cap/TC-02-02 | (escalate) one whole 10x20x30 box, Box in tree, no dialog. Properties JSON-safe; Shape/ShapeMaterial are strings "<Solid object at ...>" (stringified value, allowed by the Then). |
| TC-02-03 | Critical | **PASS** | cap/TC-02-03 | (escalate) whole cylinder, title "* tc-02-03-uat-saveas". New file 3725 B in a fresh folder; golden 1923 B = git blob, mtime 2026-07-21; reopen handle differs. |
| TC-02-04 | Critical | **PASS** | cap/TC-02-04, ev/tc-02-04-active-b | (escalate) sphere only, one tab, no orphan box view. After UIA click on sphere tree item, query_tree_summary on A -> "- [FEATURE] Box". Handles differ. |
| TC-02-05 | Critical | **PASS** | tc-02-05-checks.txt, -mcp.jsonl, -given-mcp.jsonl, -before/-hidden/-after.png | Body>Sketch+Pad 60x40x10. Tree Thens met (depth 1 "Body (+2)", depth 3 11 shown, focus "path: Body", expand "(+1 more)", PAD==PartDesign::Pad, 1 match, AND-stack 0, schema rejects visible_only/unknown_filter); v->- marker. Hide by tree context menu Toggle Visibility (Space press delivery_failed). hidden.png: sketch outline only. before/after same whole plate, after differs by selection highlight and property panel. |
| TC-02-06 | Critical | **PASS** | ev/tc-02-06-at4, tc-02-06-after | (escalate) before (Fit All, top) 20x10 pad; after restore same pad iso, Pad row no error mark, no dialog. |
| TC-02-07 | High | **PASS** | tc-02-07-checks.txt, -mcp.jsonl, -after.png | in_list [Body], out_list [Sketch], 11 edges, not truncated, Pad->Sketch. after.png whole plate; tree Body > Origin, Pad > Sketch; no dialog. |
| TC-02-08 | High | **FAIL** | tc-02-08-checks.txt, -mcp.jsonl, -after.png, -after-guifit.png, -after-axiscross.png | Placement Thens PASS (units, local!=global in moved Body, Body global==local, composition Pad (30,20,10) Datum (30,20,25), "object has no placement: NoPlacementSheet"). view_fit_viewport OK fitted, framing fits 0.95, but after.png shows plate cut by top and right view borders (lead read it). F-P2-1. GUI Fit All fallback: whole rotated plate on datum plane, away from world axis cross. |
| TC-02-09 | Critical | **PASS** | tc-02-09-checks.txt, -mcp.jsonl, -verify.txt, -after.png | File > Exit, relaunch with file argument via p2_launch.ps1 -OpenFile (not launch_app: cannot set profile/env). Title box40-hole-r5; 1 doc, transient false, same handle, vol 15214.6. after.png block with round hole, whole, no dialog. |
| TC-02-10 | High | **PASS** | tc-02-10-checks.txt, -mcp.jsonl, -after.png | Windows menu switch; title moved to two-box-compound; A re-read equal JSON; B TwoBoxCompound vol 2000 solids 2 com null. after.png two separate cubes whole, both docs in tree. |
| TC-02-11 | High | **PASS** | tc-02-11-checks.txt, -mcp.jsonl, -schema.json, -before/-after.png | depth 0/-1 "less than the minimum of 1"; max_nodes "Additional properties are not allowed"; schema props doc/focus/expand/depth/filters, additionalProperties false. before/after 0 px. |
| TC-02-12 | High | **PASS** | ev/tc-02-12-at3, at7 | (escalate) GUI Fit All before/after the 3 refusals: 0 px diff, Fusion, no dialog. total_edges 2. |
| TC-02-13 | Medium | **PASS** | ev/tc-02-13-unicode, cap/TC-02-13 | (escalate) before save: title/tab/tree draw CJK runs and wrench as real glyphs, spaces kept, tree entry elided by widget; final: tc-02-13-uat-unicode, no dialog. Target folder fresh. |
| TC-02-14 | Medium | **PASS** | tc-02-14-checks.txt, -mcp.jsonl, -after.png | "[LINK] BoxLink -> LinkTarget" leaf, depth 1 "(+3)", focus "path: OuterPart > InnerPart". after.png two equal cubes whole; tree OuterPart > InnerPart > LinkTarget, BoxLink. |
| TC-02-15 | Critical | **PASS** | ev/tc-02-15-at2, at18, p0-addonlog.txt | (escalate) Fit All baseline vs after 12 refusals: 0 px diff, one box, one tab, no dialog. No crash lines in addon.log. query_tree_summary refusal is text "INVALID_INPUT: unknown or stale document handle: fcb-doc:not-a-real-handle" (no schema field on the wire, as documented). |
| TC-02-16 | Critical | **PASS** | ev/tc-02-16-at3, at9 | (escalate) after double close: Start tab only, no orphan view. Reopen+Show All+Fit All: one whole sphere, one tab. No traceback; sphere-r10 1882 B unchanged; new handle. |
| TC-02-17 | Critical | **PASS** | ev/tc-02-17-at2, tc-02-17-after | (escalate) baseline vs after all refusals incl. not-fcstd.txt and corrupt.FCStd: 0 px diff, no dialog. Corrupt zip and non-FCStd share tail "Invalid project file <path>: ios_base::failbit set: iostream stream error"; missing file says "does not exist!". |
| TC-02-18 | Critical | **PASS** | tc-02-18-checks.txt, -given.txt, -mcp.jsonl, -after.png | IsReadOnly attribute. INVALID_INPUT "save target is not writable", "save folder does not exist", "save path is a directory, not a file"; hashes unchanged; writable save OK. after.png whole cylinder, title tc-02-18-writable. |

## TC-03 — Sketch Authoring

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-03-01 | Critical | **PASS** | tc-03-01-checks.txt, -mcp.jsonl, -after-PlateProfileXY/-RibProfileXZ/-EndProfileYZ.png | 3 creates OK, post_verify passed, dof 0, empty, YZ rotation 120 deg about (0.58,0.58,0.58), ZX schema reject. GUI Fit All (nothing_to_frame). Edit captures nav cube TOP/FRONT/RIGHT, "Empty sketch", 3 sketches. |
| TC-03-02 | Critical | **PASS** | ev/tc-03-02-at8, after-tree | (escalate) MCP fit nothing_to_frame -> GUI Fit All; edit mode: one axis cross, "Empty sketch", no solid; PlateProfile under PlateBody. |
| TC-03-03 | High | **PASS** | ev/tc-03-03-edit-iso | (escalate) edit mode iso: axis cross on the top-face corner at plate thickness; no 2nd sketch. |
| TC-03-04 | Critical | **PASS** | tc-03-04-checks.txt, -mcp.jsonl, -after.png, -after2.png | OK dof 0, 4 geometry/11 constraints, PlateWidth/PlateDepth driving. after2.png (camera moved): closed green rectangle, labels "PlateWidth = 60 mm"/"PlateDepth = 40 mm", Fully constrained. |
| TC-03-05 | Critical | **PASS** | ev/tc-03-05-at11 | (escalate) edit: green line from origin, circle R2.5, quarter arc, isolated point; Fully constrained; no 5th shape. |
| TC-03-06 | Critical | **PASS** | ev/tc-03-06-edit-wide-fitall | (escalate) wide window, edit, Fit All: 5 lines, 3 circles (two touching), 2 points mirrored about V, 45 deg line; labels 60/50/40/70/20/15/10/5 mm, 2.5, 45 deg; about 20 labels + 8 glyphs (overlap, approximate); all green, nothing clipped. |
| TC-03-07 | Critical | **PASS** | ev/tc-03-07-at8, cap/TC-03-07, ev/tc-03-07-edit-fitall | (escalate) before 10x40 tab; after 25x40 slab, no gap; edit: green rectangle, TabWidth = 25 mm. |
| TC-03-08 | High | **PASS** | ev/tc-03-08-at5, at8, tc-03-08w-at14 | (escalate) diagonal solid green before, dashed blue construction between, solid green after; 5 lines. |
| TC-03-09 | Critical | **PASS** | tc-03-09-checks.txt, -mcp.jsonl, -before/-after.png, -snapdirs-*.txt | SPEC_FAILED rolled_back true verified, "verify_sketch failed on LooseProfile (dof=4): sketch.fully_constrained"; digests equal; tmp empty. Images axis cross only, Empty sketch, 0 px. |
| TC-03-10 | High | **PASS** | ev/tc-03-10w-at6, w-at18 | (escalate) same closed green 60x40 rectangle before/after, labels drawn, 4 lines. |
| TC-03-11 | High | **PASS** | ev/tc-03-11w-at7, w-at17 | (escalate) before: parenthesised reference labels overlap 60/40 labels; after: gone, rectangle not shifted. Limit: name SpareWidth not legible under the overlap; identified by parentheses. |
| TC-03-12 | Critical | **PASS** | ev/tc-03-12w-at5, w-at10 | (escalate) same rectangle, green, no extra glyph, no Redundant notice. |
| TC-03-13 | Critical | **PASS** | ev/tc-03-13-at9, cap/TC-03-13, ev/tc-03-13-at15 | (escalate) before plate without projection; edit: magenta external curve on the 60 mm bottom edge. counts.PASS 2; BossProfile out_list [PlatePad]. |
| TC-03-14 | High | **PASS** | ev/tc-03-14w-at11 | (escalate) rectangle on H and V axes, point-on-object marks at 2 pinned corners, all green. |
| TC-03-15 | High | **PASS** | tc-03-15-checks.txt, -given-mcp.jsonl, -mcp.jsonl, -before/-after/-final.png | 0: INVALID_INPUT "constraint 2 Radius value must be positive, got 0.0"; -5 SPEC_FAILED rolled back; 1e9 OK dof 0. before/after two equal green circles, BossRadius R2.5, HoleSpacing 40, 0 px. final.png not judged per TC. -5 explanation "ValueError: Invalid constraint index: 4" (F-P2-5). |
| TC-03-16 | Critical | **PASS** | ev/tc-03-16w-at5, w-at9 | (escalate) rectangle stays 60x40, green, one width label 60. |
| TC-03-17 | Critical | **PASS** | tc-03-17-checks.txt, -given-mcp.jsonl, -mcp.jsonl, -before/-after/-after-3d.png | "unknown object: NoSuchSketch", "geo_id 99 is outside the sketch (0..3)", "object is not a sketch: PlatePad"; no mutation. Edit pair 0 px green rectangle. after-3d whole plate (Tasks panel over a corner). |
| TC-03-18 | Critical | **PASS** | ev/tc-03-18w-at5, w-at13 | (escalate) no circle; HoleSpacing 40 over same span; rib 45 -> 30 deg. |
| TC-03-19 | Critical | **PASS** | tc-03-19-checks.txt, -given-mcp.jsonl, -mcp.jsonl, -before/-after.png | remove geo 1 OK; stale INVALID_INPUT "constraints[0].first geo_id 1 is outside the sketch (0..0, or -1/-2 axes)"; mixed batch geo_id 88 refused; PlateProfile unchanged, dof 0. Images rectangle identical; ScrapProfile 1 line instead of 2. |
| TC-03-20 | Critical | **PASS** | ev/tc-03-20-at12, cap/TC-03-20, ev/tc-03-20-at17 | (escalate) 5 mm plate whole, circle on top; edit: R4 circle + external curve on a real edge. Only finding: REPOINTED, owner BossProfile, prop AttachmentSupport. |
| TC-03-21 | High | **PASS** | ev/tc-03-21-at7, at14 | (escalate) before vs after 4 rejects: 0 px diff, sketch only, no dialog. |

## TC-04 — Feature Modelling

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-04-01 | Critical | **PASS** | cap/TC-04-01 | (first of TC-04) one whole 10x20x30 box; empty PlateBody (Bracket doc) draws nothing; no 2nd solid. |
| TC-04-02 | Critical | **PASS** | cap/TC-04-02 | not in the review set; scripted pixel check: sample Block.BlockPad geometry true, extent fraction 0.94, touches_edge false. |
| TC-04-03 | Critical | **PASS** | ev/tc-04-03-axiscross | (escalate) axis cross on (Std_AxisCross by script_exec, because invoke_menu View > Toggle axis cross was refused): origin and the z=0 outline at mid-height of the 20x30x10 block. |
| TC-04-04 | High | **PASS** | tc-04-04-mcp.jsonl, -checks.txt, -after.png | RevPad 6000 z -10..0 Reversed; TwoPad 8400 Length2 4; TaperPad 6447.65 TaperAngle 5; taper 120 refused "taper_angle must be in (-90.0, 90.0) degrees". Capture three whole boxes; RevPad hangs below sketch plane, TwoPad tallest with seam, TaperPad sides lean out. |
| TC-04-05 | Critical | **PASS** | tc-04-05-* | Slot 11800, through 11300, face_count 15, ThroughAll; pad ThroughAll refused. Capture plate with blind square recess at (10,10) and through opening at (40,15) showing background. Tasks panel hides part of back edge. |
| TC-04-06 | Critical | **PASS** | tc-04-06-* | 1570.8, faces 3, ReferenceAxis V_Axis, out_list ShaftProfile; Edge1/400 deg/second_angle refusals. Capture one closed upright cylinder, h:w ratio matches h=2d iso. |
| TC-04-07 | Critical | **PASS** | tc-04-07-*, -after-zoom.png | 11915.64 DrillPoint Angled, Dimension, faces 8; refusals verbatim; ThroughAll 11881.21 on 2nd scratch plate. Capture round bore at (10,20); zoom wall and floor, no opening. |
| TC-04-08 | High | **PASS** | cap/TC-04-08, ev/tc-04-08-hole-zoom | (escalate) zoom down the hole axis: counterbore wall, flat step, narrower bore -> two diameters. |
| TC-04-09 | Critical | **PASS** | cap/TC-04-09, ev/tc-04-09-top, ev/tc-04-09-oracle-checks.txt | (escalate) all four plate corners rounded, OtherBody separate. Oracle (re-run, launch f7): Edge1/2/5/8 5 mm along Z; Edge3 60 mm, Edge7 40 mm horizontal. |
| TC-04-10 | Critical | **PASS** | tc-04-10-*, -zoom-two/-angle/-equal2.png, -top.png | Oracle edges Edge1/3/17; EqualChamfer 11994.38; faces 7/8/9; refusals verbatim; verify solid_count 1. Top view three straight corner cuts different legs 20x20, 28x14, 15x26 px. |
| TC-04-11 | Critical | **PASS** | cap/TC-04-11 | (escalate) plate exactly 2 holes along its long axis; disc exactly 6 evenly spaced. |
| TC-04-12 | Critical | **PASS** | cap/TC-04-12, ev/tc-04-12-top | (no pixel check) top view: PlaneMirror = two separated 20x30 blocks either side of x=0; DatumMirror pair either side of the yellow MirrorPlane; FaceMirror one doubled block. |
| TC-04-13 | Critical | **PASS** | tc-04-13-*, -front.png, -front-corner.png | 4 datums; RaisedPlane z 15 FlatFace Face6, out_list PlatePad; kind curve reject; point+TwoPointLine refused. Capture yellow plane over plate, axis line on (0,0) edge, CS at corner; front view plane ~10 mm above top; point marker at origin. |
| TC-04-14 | Critical | **PASS** | ev/tc-04-14-at7, at8, cap/TC-04-14 | (escalate) same 20x30 footprint 10 mm, then visibly taller (25 mm), one solid; runner capture 12 mm midplane. |
| TC-04-15 | High | **PASS** | tc-04-15-*, -front.png | BasePad 12000, Face1 z 20; RiserPad z 0..25 14000 UpToFace [Pad, Face1]; UpToInfinity refused pre-transaction. Front view T shape, riser flush with slab. |
| TC-04-16 | Critical | **FAIL** | tc-04-16-mcp.jsonl, -checks.txt, -before/-after.png | cause: test-case defect. Then `:686` accepts only equal digests or `rolled_back_via_snapshot`; product proves `rolled_back_verified` by mass properties (`transaction.py:345-370`). Fillet r20 Edge3: RECOMPUTE_ERROR "recompute left 1 object(s) invalid: TooBigFillet: BRep_API: command not done", rolled_back true, rolled_back_verified, no TooBigFillet, 12000, no snapshot, verify_recompute OK. Fingerprint Then not met literally (digests differ). Captures same sharp plate, pixel-identical. |
| TC-04-17 | Critical | **PASS** | tc-04-17-* | Edge3 20 mm seam. DropFillet and MixedFillet refused "cannot be shown to survive the dress-up ... FreeCAD drops the rest without reporting it"; no snapshot; volume unchanged. Conditional "dressed N of M" NOT RUN as Then directs. Captures same cylinder sharp rims, identical. |
| TC-04-18 | High | **PASS** | ev/tc-04-18-at11, cap/TC-04-18 | (escalate) one hole before and after the refused patterns (at11 vs at17 0 px). |
| TC-04-19 | High | **PASS** | tc-04-19-*, -after-shift.png | "length must be positive, got 0.0"/"got -10.0" (TC prefixes), "up_to='Length' is length-driven; 'length' is required". No snapshot, tree unchanged, Tip null. Captures flat outline identical; camera shift under Tasks panel: no material. |
| TC-04-20 | Medium | **PASS** | cap/TC-04-20 | (escalate) small round on the left vertical edge, small bevel on the front vertical edge, about 1 mm. |
| TC-04-21 | Critical | **FAIL** | tc-04-21-* | cause: test-case defect. Then `:910` quotes a message no longer in source; observed `BlockPad.Length is a App::PropertyLength and takes a {value, unit} quantity or a number, got [25]`. Thickness/Shape/deg refusals verbatim; "ShaftRev.Base is read-only"; batch refused, Length 10 mm; volume 6000. Step 4 [25] refused pre-transaction with "BlockPad.Length is a App::PropertyLength and takes a {value, unit} quantity or a number, got [25]" - quoted string not in source. Captures same 10 mm box. 2026-10-03-04 Shape FAIL fixed. |
| TC-04-22 | Critical | **PASS** | tc-04-22-* | 5 messages verbatim; tree unchanged; no snapshot. Captures one plate identical. |
| TC-04-23 | Critical | **FAIL** | tc-04-23-* | cause: test-case defect. Then `:1000` fingerprint wording as TC-04-16. Fixture DoF 2; Pad SPEC_FAILED rolled_back, "verify_sketch failed on LooseProfile (dof=2): ...", no LoosePad, Tip null; digests differ (rolled_back_verified). Captures outline only, 0 px. |
| TC-04-24 | Critical | **PASS** | tc-04-24-*, -after-end.png, -tree-zoom.png | Radius 20: RECOMPUTE_ERROR, "recompute left 1 object(s) invalid: EdgeFillet: BRep_API: command not done", rolled_back, Radius 1.0 mm, verify_recompute OK. End view ~1 mm round, no 20 mm round; tree EdgeFillet green tip, no red overlay. |

## TC-05 — Mutation Protocol, Rollback Proof & TNP Guard

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-05-01 | Critical | **PASS** | tc-05-01-mcp.jsonl, -after.png | OK, detail null, digests b083c6..!=c4fe85.., passed true, rolled_back false, proven null, fcb.mutation/2, no transaction_id, text "Mutation committed; fingerprint c4fe85329675.", Pad 12000.0. PNG whole shaded prism ~1.5:1, no dialog. query_mass_properties Body INVALID_INPUT "object has no queryable shape: Body" (F-P4-3). |
| TC-05-02 | Critical | **PASS** | tc-05-02-mcp.jsonl, -after.png | spy 1 entry FCB_TMP_snap_4sc10os6\tc_05_02.FCStd, 3rd value False; snapshot check [], no snapshot_path, .FCBak []. PNG whole prism. |
| TC-05-03 | Critical | **PASS** | ev/tc-05-03-at4, cap/TC-05-03 | (escalate) same flat 20x20 sketch before/after, no solid, no error marker, no dialog. |
| TC-05-04 | High | **PASS** | tc-05-04-mcp.jsonl, -after.png | touched ['Fillet','Body'], no Sketch; tree diff {Fillet}; preview diff.touched ['Body','Fillet'] - same set, other order (Then :22 "the preview predicted the same set"; lead: set equality per the Then's own wording). is_valid true. PNG prism with left vertical edge rounded, others sharp. |
| TC-05-05 | Critical | **PASS** | tc-05-05-mcp.jsonl, -before/-after.png | isError + envelope, RECOMPUTE_ERROR, mutation.recompute_error, rolled_back_verified (Then allows massprops), no snapshot_path, changed []. Pad 12000, no Fillet. before/after same sharp prism; 711 px diff only status-bar counter. |
| TC-05-06 | Critical | **FAIL** | tc-05-06-mcp.jsonl, -before/-after.png | cause: test-case defect. Reproducer 1 (`:234`) has no `length`: `length must be a {value, unit} quantity, got None`; the conditional at `:246` does not hold. Fixture Pad, Fillet r2, Sketch001 on Fillet Face5, Pocket 900. Reproducer 1 (pattern 200) refused at preview INVALID_INPUT "length must be a {value, unit} quantity, got None" (F-P4-2); apply with preview_id null schema refusal. Reproducer 2 (Radius 400) rolled_back_verified. No escalation; no rolled_back true with proven null. before/after 0 px. |
| TC-05-07 | Critical | **PASS** | tc-05-07-mcp.jsonl, -before/-after.png | rolled_back false, proven null, SPEC_FAILED, snapshot_path FCB_TMP_snap_pv656jfb\tc_05_07.FCStd exists; text unproven form; explanation ends "pre-mutation fingerprint c4fe85...". After: swapped sphere, tree only Sphere. Snapshot not removed by agent (F-P4-5). |
| TC-05-08 | Critical | **PASS** | ev/tc-05-08-at13, cap/TC-05-08 | (escalate) same sharp 20x20x30 prism before/after, not blank, no dialog. |
| TC-05-09 | Critical | **PASS** | tc-05-09-mcp.jsonl, -after.png | 3 failure paths (SPEC_FAILED verified; RECOMPUTE_ERROR verified; preview refused "unknown object in base: NoSuchPad"); after each GoodFillet OK, snapshots [], undo "buddy: feature_fillet GoodFillet". PNG prism one narrow rounded edge. |
| TC-05-10 | Critical | **PASS** | tc-05-10-mcp.jsonl, -before/-after.png | SPEC_FAILED "RuntimeError: injected commit failure", rolled_back true, no snapshot_path, fp_after null, fp_before 64-hex+exportBinary; closing pad OK. before/after flat sketch outline, 20 px overlay edge. Text "Mutation rolled back (None): ..." (F-P4-4). |
| TC-05-11 | Critical | **PASS** | tc-05-11-mcp.jsonl, -after.png | rolled_back false, SPEC_FAILED, snapshot_path FCB_TMP_snap_tvtdo67h exists, fp_after null, Pad 12000, unproven text. PNG whole prism. |
| TC-05-12 | Critical | **PASS** | tc-05-12-mcp.jsonl, -before/-after.png | SPEC_FAILED "RuntimeError: injected setup failure", fp_before c4fe85..+exportBinary, tnp UNSUPPORTED, fp_after null, rolled_back false/null, touched [], no snapshot_path; Pad 12000; undo undone "buddy: feature_pad Pad". before/after same prism, 20 px overlay edge. Text "...could not be proven: None." (F-P4-4). |
| TC-05-13 | High | **PASS** | tc-05-13-mcp.jsonl, -checks.txt, -after.png, -tabs.png | copy SHA = golden 94969a..; handles differ; probe digests equal d1011f.., 64-hex; serializer exportBinary, keys {digest, serializer}; pad moved digest. Fit on handle-a INVALID_INPUT "the live viewport is showing 'tc_05_13_box_copy'..."; tab clicked, fit OK. PNG one box three edge lengths whole. Copy deleted (in run folder? check). |
| TC-05-14 | High | **PASS** | ev/tc-05-14-at12, cap/TC-05-14 | (escalate) prism unchanged (at12 vs at16 0 px). Two-build Thens N/A on a single-build run (record N/A). |
| TC-05-15 | Critical | **PASS** | ev/tc-05-15-at13, cap/TC-05-15 | (escalate) same left corner rounded, strip wider (2 -> 3 mm), no other edge. tnp_audit CLEAN, counts PASS 2, findings []; Fillet out_list [Pad]. |
| TC-05-16 | Critical | **PASS** | tc-05-16-mcp.jsonl, -before/-after.png | Doc A preview INVALID_INPUT "dress-up base Pad is not the Tip of Body Body; the Tip is Fillet. ..."; no Chamfer. Doc B SPEC_FAILED FLAGGED REPOINTED owner BossProfile layer 1, rolled_back_verified, 12000; preview FLAGGED. before/after 0 px thin plate with circle. |
| TC-05-17 | Critical | **FAIL (test-case defect)** | tc-05-17-mcp.jsonl, -before/-after/-after2.png | RECOMPUTE_ERROR, recompute_clean false, FLAGGED, BROKEN layer 0, rolled_back true, Fillet OK met. Then TC-05...md:677 "a BROKEN entry's owner is Fillet" not met: only BROKEN owner "Pad". F-P4-1. Captures same prism rounded edge; after2 0 px. |
| TC-05-18 | Critical | **PASS (degraded; build-gated Thens not exercised)** | tc-05-18-mcp.jsonl, -scan-checks.txt, -before/-after.png | element_map_available true; degraded form SPEC_FAILED UNSUPPORTED findings [] counts {} element_map_version "15.70200.5"; scan 206 tnp blocks 0 CLEAN+null version. 0 px. |

## TC-06 — Render and GUI Visual Fidelity

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-06-01 | Critical | **FAIL (harness limit)** | tc-06-01-checks.txt, -after2.png, -mcp.png, -zoom-*.png | Window and render one flat 60x40x5 plate iso, same 1.50 ratio; tone band passed. AA Then (TC-06 file:119) reads developer user.cfg AntiAliasing 4 (on), but live temp -u profile has no key (GetInt -1): render edge 3 colours hard stair, window also 3 colours. Render and window agree. (06-12 later pre-seeded AA=4 in its temp profile.) |
| TC-06-02 | Critical | **PASS** | tc-06-02-checks.txt, -<cam>.png, -<cam>-viewport.png, -after.png | Asymmetric L-block; 7 renders match window views (dividers front 0.625, right 0.60, back 0.375, notch mirrored); 'oblique' schema refused. Views set by NaviCube (Standard Views drop-down does not open under cua-driver). |
| TC-06-03 | Critical | **PASS** | cap/TC-06-03, runner/tc-06-03-*.png | (escalate) window: 2 solids (PadA, BoxB), no datum/origin/sketch line; default render same 2 solids; include-a = PadA only; exclude-a = BoxB only; include-body = PadA block, not blank. |
| TC-06-04 | High | **PASS** | ev/tc-06-04-at4/at6/at12, runner/tc-06-04-*.png | (escalate) window BoxA stays grey before, after the red call and at the end (0 px diffs); red render BoxA red; t80 translucent; t0 and t100 differ, t0 BoxA own colour. |
| TC-06-05 | High | **PASS** | cap/TC-06-05, runner/tc-06-05-*.png | (escalate) window no orange face; unfocused render same two boxes and camera; focused tighter; highlight BoxA orange, BoxB grey. |
| TC-06-06 | Critical | **PASS** | tc-06-06-checks.txt, -hidden.png, -after.png, -default-*.png | Hidden via tree context menu; hidden window and render one cube; after cube + tall bar. |
| TC-06-07 | High | **PASS** | cap/TC-06-07, runner/tc-06-07-*.png | (escalate) window three-quarter view, 3 faces, Z up; custom render = iso render (0 px diff). |
| TC-06-08 | High | **PASS** | tc-06-08-checks.txt, -default.png, -after.png | 1920x1920, 640x480, 1920, 800x1920; 4096 schema refused; width 0 INVALID_INPUT. Window and render same plate. |
| TC-06-09 | Critical | **FAIL (test-case defect)** | tc-06-09-checks.txt, -after.png, -iso.png, -unstyled-after.png | Volume, com, tree, dirty false, Touched [] unchanged; style not persisted; window grey box = render. Temp Then (TC-06 file:474) "at most" the 3 linked files: folder holds 21 (17 earlier same-session renders + 3 links + unstyled re-render), all match returned links, no orphan. |
| TC-06-10 | Critical | **PASS** | tc-06-10-checks.txt, -after.png, -recomputed.png | ['Touched']; dirty render OK dirty_document true text "...Document dirty (pending/broken recompute)."; after recompute false, volume 5000. Window and render one box 20:10:25. |
| TC-06-11 | Critical | **PASS** | tc-06-11-checks.txt, -before.png, -after.png | H1 render none; render OK available false reason "offscreen probe render failed: No module named 'pivy'", no link, no images, scene []. GUI before/after identical. |
| TC-06-12 | Medium | **PASS** | tc-06-12-checks.txt, -zoom-*.png | Select-String 4 (8 samples); render edge 17 colours, window 14: blended. SetInt 0 -> 3-colour stair; restored 4. Temp profile pre-seeded AntiAliasing=4. |

## TC-07 — Verification & Export Pairing

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-07-01 | Critical | **PASS** | cap/TC-07-01 | (escalate) whole 1:2:3 box; checks ids exactly the 5 named, all passed. |
| TC-07-02 | High | **PASS** | cap/TC-07-02 | (escalate) cylinder about 2:1; measure ids exactly shape.volume, shape.bbox, shape.solid_count, shape.valid, shape.watertight. |
| TC-07-03 | Critical | **PASS** | ev/tc-07-03-edit-framed | (escalate) edit mode: one green horizontal segment from the origin, horizontal glyph, 10 mm label, Fully constrained; grade_under checks.0 sketch.fully_constrained passed false. |
| TC-07-04 | Critical | **PASS** | tc-07-04-after.png, -after-top.png, -checks.txt | verify_recompute OK, 1 check recompute.clean, failing_objects [], "Recompute clean: no errors.", volume 15214.6, 1.1.4/element_map 15. after: iso box with round opening, tree BoxHole no error; top (camera only): background through hole. |
| TC-07-05 | Critical | **PASS** | tc-07-05-after.png | both OK, verified false, 2 ids, bytes = stat (6886/6854), AP242 grep 1/AUTOMOTIVE 0, AP214 AUTOMOTIVE 1; schema measured; AP203 schema rejection "'AP203' is not one of ['AP214', 'AP242']"; re-import 6000.0. Capture closed box ~1:2:3. |
| TC-07-06 | Critical | **PASS** | tc-07-06-after.png | facets 976=976, sizes 48884/9898, verifies OK, self_read 976/976, angular 0 INVALID_INPUT "deflection out of range: ...", trimesh 976. Capture closed faceted round body. |
| TC-07-07 | Critical | **PASS** | tc-07-07-after.png, -after-top.png | OK, 4 ids, schema AP242, tol {"rel":0.001}, 15214.6, valid, topology 7/15/1, subject match, no FCB_TMP_ doc, re-import 15214.6. Box with opening; top view through. |
| TC-07-08 | Critical | **PASS** | tc-07-08-after.png, -after-back.png | 5 trimesh_stl + 4 stl2 ids, self_read 12/12 8/8, agreement trimesh_stl/stdlib_stl true, tess {0.1,0.5}, volume_band abs 146.67 = (2/3)*0.1*2200 = 146.666 (test-plan rule 9: band 0.01); truncated -> SPEC_FAILED; outside trimesh 6000.0. after: box 3 faces whole; back (NaviCube): other 3 whole. |
| TC-07-09 | Critical | **PASS** | tc-07-09-source.png, -after.png, -after-bottom.png | 4 lib3mf + 5 trimesh_3mf ids, unit 1 source_is_mm, manifold 1/0, metadata, self_read 100/100 52/52, agreement lib3mf, band 52.36, measured 1555.55 within, abs; outside lib3mf unit 1, watertight. source/after same size (45.84 vs 45.79 mm), faceted cylinder ~2:1 top closed; bottom closed. |
| TC-07-10 | High | **PASS** | tc-07-10-coarse.png, -after.png | facets 218 < 10174; bands 418.88 / 8.38 (ratio 49.99 of 2-decimal fields; Then "about"); fine not 4.19; abs only; coarse 3942.88 < 4188.79 passed; floor 1e-05 INVALID_INPUT "deflection out of range:". coarse.png flat plates angular; after.png smooth sphere. |
| TC-07-11 | High | **PASS** | tc-07-11-before.png, -after.png | 3x INVALID_INPUT "export supports a single object; got multiple"; "unknown object: NoSuchObject"; "document has no objects to export". before/after same box; only preselection highlight differs. |
| TC-07-12 | Medium | **PASS** | tc-07-12-after.png | omitted objects OK volume 6000.0; H2 INVALID_INPUT exact; no compound file; objects [] same payload; re-import 6000.0. Capture one box. |
| TC-07-13 | High | **PASS** | tc-07-13-after.png, -after-top.png | genus grade OK 15214.6; STL verify OK euler 0; compound OK solid_count 2 volume 2000; com null key present; compound expect_watertight SPEC_FAILED; trimesh "0 True". Mesh box with faceted opening; top through. |
| TC-07-14 | Medium | **PASS** | tc-07-14-after.png | Unicode export OK "tc-07-14 exports/boîte-立方体.step", path echoed, verify subject.path equal, bytes 6886; 298-char path RECOMPUTE_ERROR "Writing of STEP failed", no file; re-import 6000.0. Capture closed box; badge 1 from failed write. |
| TC-07-15 | Medium | **PASS** | tc-07-15-after.png | 3 writes OK; bytes = stat each; 3 ids; stale coarse id after fine SPEC_FAILED self_read.facet_count 10106 vs 304; trimesh 3992.01 inside band. Capture closed coarse faceted sphere. |
| TC-07-16 | Critical | **PASS** | tc-07-16-after.png | 4x INVALID_INPUT + no-such-dir RECOMPUTE_ERROR, no fail-* file, no stub, no dir, no export_id; recovery export OK; re-import 6000.0. Capture closed box; badge 1. |
| TC-07-17 | Critical | **PASS** | tc-07-17-before.png, -after.png | 3x INVALID_INPUT "unknown or stale export_id: fcb-export:bogus"; empty id "missing required 'export_id'"; H2 "export_id ... does not belong to document ..."; trimesh 6000.0. before/after same box. |
| TC-07-18 | Critical | **PASS** | tc-07-18-after.png | 6 crossed INVALID_INPUT "export_id <id> is not a step|stl|3mf export", structured_content {}; own ids OK; sizes unchanged; trimesh 6000.0. Capture whole box. |
| TC-07-19 | Critical | **PASS** | tc-07-19-after.png | crossed INVALID_INPUT exact, {}; correct pairing OK; symmetric refusal; verify_recompute OK; re-import 6000.0. Capture rectangular body sharp edges. |
| TC-07-20 | Critical | **PASS** | tc-07-20-open-shell.png, -pre-showall.png | wrong-volume SPEC_FAILED expect_volume 7200 vs 6000; open-shell SPEC_FAILED watertight false solid_count 0; bare checks OK; clean-control OK; trimesh 7200.0 and False. Capture thin flat open strip. |
| TC-07-21 | Critical | **PASS** | tc-07-21-after.png | 3 writes verified false, "export written -> <path>.", write schema fcb.result-envelope/1, verify fcb.validation-report/1 OK; STL cut to 0 B -> SPEC_FAILED; closed status set; re-import 6000.0. Capture closed box. |

## TC-08 — Preview, the Confirm-Token Gate & Verified Undo

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-08-01 | Critical | **FAIL (test-case defect)** | tc-08-01-checks.txt, -before/-after.png | diff.schema "fcb.geometry-diff/2"; Then TC-08 file:63 wants "/1"; contracts/diff.py:77 Literal["fcb.geometry-diff/2"]. Other Thens pass (volume 0->12000, solids +1, faces +6, touched/new Pad, validity OK, TNP CLEAN, token + ISO expiry). Window flat 20x20 sketch before/after 0 px. |
| TC-08-02 | Critical | **FAIL (product defect)** | tc-08-02-checks.txt, -statusbar-*.png, -notification-popup.png | Preview after 32000; live volume/bbox/com unchanged; document_list unchanged; TempDoc []. Failing fillet-500 preview OK validity RECOMPUTE_ERROR. Visual "IDENTICAL by eye" not met: pad identical but status-bar notification badge blank->'1' (711 px); notification "Fillet: BRep_API: command not done (2 times)". Throwaway-copy recompute posts an error into the human's GUI. |
| TC-08-03 | Critical | **PASS** | ev/tc-08-03-at9, cap/TC-08-03 | (escalate) before (GUI Fit All) flat sketch; after 20x20x30 solid. |
| TC-08-04 | High | **PASS** | cap/TC-08-04, ev/tc-08-04-at11/at14 | runner FAIL caused by scenario-file encoding defect `tc-08-04.json:487` (`"\bFillet\b"` is a JSON backspace); test-case Then `TC-08...md:169` met by the observed explanation. Finding F-1. (fail) before vs after preview 0 px; sharp-edged pad, no round, no error colour. See Part 4. |
| TC-08-05 | Medium | **PASS** | tc-08-05-checks.txt, -h1.jsonl | off -> available false reason "off"; auto -> true; H1 -> available false "offscreen probe render failed: No module named 'pivy'", OK; 'sometimes' schema refusal. Window pad unchanged 0 px. |
| TC-08-06 | Critical | **PASS** | tc-08-06-checks.txt, -toolbar-*.png | string/object forms matches_pre_op true; fp c4fe..->b083..; undone 'buddy: feature_pad Pad'; "restored the pre-op state"; null expectation phrase; restored_objects no Pad; 42 schema refusal. Window flat sketch before/after; only Redo button turned green. |
| TC-08-07 | Critical | **PASS** | ev/tc-08-07-at10/at12, cap/TC-08-07 | (escalate) refused replay leaves the window identical (0 px); tree Body, Probe (then Probe2 in runner capture), no duplicated body, no dialog. |
| TC-08-08 | Critical | **PASS** | ev/tc-08-08-at8/at11, cap/TC-08-08 | (escalate) refused pocket: same flat square, only status-bar text differs; after: 30 mm solid. |
| TC-08-09 | Critical | **PASS** | ev/tc-08-09-at8/at11/at24 | (escalate) refused 60 mm call: flat sketch unchanged; after: 30 mm tall against 20 base, not 60. |
| TC-08-10 | Critical | **PASS** | ev/tc-08-10-at16/at20, cap/TC-08-10 | (escalate) TC0810B title and tab stay active, flat sketch, no pad; TC0810A not activated. |
| TC-08-11 | Critical | **PASS** | ev/tc-08-11-at8, at14 | (escalate) after the stale call (GUI Fit All): rectangle 40x20, no solid; runner after: 40x20x30 pad. |
| TC-08-12 | High | **FAIL (agent execution fault)** | tc-08-12-checks.txt, -notifications.png | TTL 900.108 s; spent +1 s "already authorized"; post-deadline "has expired; re-run preview_dry_run"; Probe3 OK; one Probe. Images not identical apart from Probe: badge 0->2 and extra Tasks title-bar button, caused by TC-08-21 run in the same GUI during the 900 s wait ("Box: Length of box too small" + traceback from agent's failed script_exec). Expired call added no body, no dialog. Re-run needed. |
| TC-08-13 | Critical | **FAIL** | ev/tc-08-13-at8/at9, cap/TC-08-13 | cause: test-case defect. Then quotes `confirm.elicitation_action must be 'accept', got 'decline'`; over MCP the schema refuses first: `Input validation error: 'decline' is not one of ['accept']`. (escalate) refused call 0 px; after single 30 mm solid. Note: decline refused by the MCP schema "Input validation error: 'decline' is not one of ['accept']"; the listener text "elicitation_action must be accept" is not reachable over MCP (raw RPC not used, harness rule 6). Corrected call OK. |
| TC-08-14 | Critical | **PASS** | ev/tc-08-14-at8/at20, cap/TC-08-14 | (escalate) all variants: 0 px; flat sketch, no solid, no dialog. |
| TC-08-15 | Critical | **PASS** | ev/tc-08-15-at9/at13, cap/TC-08-15 | (escalate) refusals 0 px, flat sketch; after: solid. |
| TC-08-16 | Critical | **PASS** | ev/tc-08-16-at9/at13, cap/TC-08-16 | (escalate) declines 0 px, flat sketch; after: solid. |
| TC-08-17 | Critical | **PASS** | tc-08-17-checks.txt, -tools-schema.json | 19/19 refused with exact gate message (agent's first feature_pattern call lacked 'direction' -> schema error on agent input; re-issued valid). confirm:null schema refusal; tree unchanged; save/export_stl OK no confirm; exactly 19 tools have confirm; samples OK; visibility-only write OK changed [] audit display_state. Window filleted pad before/after 0 px. |
| TC-08-18 | Critical | **PASS** | tc-08-18-checks.txt, -approve.jsonl, -*-h1.stderr.log | H1: unset OK; forged token "carries an invalid signature"; =1 OK; =0 and =true gate message; SECURITY line only unset and =1; audit one approval line mode auto_approve source FREECAD_BUDDY_AUTO_APPROVE. GUI golden box 0 px. |
| TC-08-19 | High | **PASS** | tc-08-19-checks.txt | "not a previewable mutation tool: '<name>' (previewable: <19 sorted>)"; schema refusals; TempDoc []; no save file. Window 0 px. |
| TC-08-20 | High | **PASS** | tc-08-20-checks.txt | "operation.args must not carry 'doc'; the preview supplies it"; TempDoc []; no Pad; token on B "issued for a different document". Window A active flat sketch 0 px. |
| TC-08-21 | Critical | **PASS** | tc-08-21-checks.txt, -txn-edit.png | "nothing to undo on UndoProbe: the undo stack is empty"; first undo 'buddy: create body Body'; UndoMode 0 "undo is unavailable on UndoOff: the document reports UndoMode 0"; open transaction via double-click Pad task dialog -> "TxnProbe has an open transaction; ..."; broken undo RECOMPUTE_ERROR Box. GUI Fit All fallback (empty doc). Window no Body before/after. |

## TC-09 — Error Contract & Fault Injection

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-09-01 | Critical | **FAIL (harness defect: stale sweep script)** | tc-09-01-edge_report.json, -sweep-as-written.txt, -checks.txt, -probe-h1.jsonl, -before/-after.png | As written exit 2 ("fcb env python not found"). On h1 interpreter via p7_sweep.py: all_passed False, total 13 (not 14), 6/7, exit 1, fault_shape checks NO_STATUS. Pass: retired_max_nodes_rejected=SCHEMA_ERROR, no crash signature, 5 INFO INVALID_INPUT, 0 Traceback. Captures whole box 0 px. |
| TC-09-02 | Critical | **FAIL (harness defect: same stale sweep)** | tc-09-02-when.txt, -checks.txt, -before/-after.png | Observed statuses [INVALID_INPUT, NO_STATUS, OK, SCHEMA_ERROR]; NO_STATUS outside the seven. Other Thens pass: status.py:11-19 7 members, check_status_vocab exit 0, OOM_KILLED declared only, WORKER_CRASHED entry.py:69-77/:104-110, rpc_client.py:72; _invoke :138-157 final except :156. Captures identical. |
| TC-09-03 | Critical | **PASS** | ev/tc-09-03-at4/at10 | (escalate) 0 px, one box, no dialog. |
| TC-09-04 | Critical | **PASS** | tc-09-04-checks.txt, -mcp.jsonl, png | 4 wrong-type calls isError no envelope ("'1' is not of type 'integer'" etc.); no output file. Captures same box 0 px. |
| TC-09-05 | Critical | **PASS** | tc-09-05-tool_surface.json (46), -checks.txt | surface command []; 5 calls "Additional properties are not allowed ('<key>' was unexpected)"; document_list names H. 0 px. |
| TC-09-06 | High | **PASS** | ev/tc-09-06-at6/at12 | (escalate) 0 px, no new segment, no dialog. |
| TC-09-07 | High | **PASS** | tc-09-07-checks.txt, -addonlog.txt, png | depth 0/-1, max_edges 0/-1, occurrences 0/1 "less than the minimum"; depth 2147483647 "OK: 1 objects, 1 shown."; depth 1 one line; max_edges 1 OK 0 edges (truncation not exercised: fixture has no edges); no traceback. box40 with hole 0 px; Tasks panel covers far corner. |
| TC-09-08 | High | **PASS** | tc-09-08-checks.txt, -n.step | absent/[] checks OK same 5 fact ids; null rejected; absent depth OK; absent ap FILE_SCHEMA AP242 (F-18 of 2026-10-03-04 fixed). Captures identical. |
| TC-09-09 | Medium | **FAIL (test-case defect)** | tc-09-09-checks.txt, -addonlog.txt, -before/-after.png | Visual Then "golden model still shown" not met: When's document_create of 4096-'a' doc makes new active empty view (289184 px diff). Tree TC0909Scratch, box-10-20-30, aaa... String Thens pass (label 4096, path INVALID_INPUT, "unknown object: ccc...", traceback 4000/4000, query_capabilities OK). |
| TC-09-10 | Medium | **PASS** | tc-09-10-checks.txt | 10-deep fn INVALID_INPUT "unknown assertion fn: {'a': ...}" (F-22 fixed); "'expect_volume' is not of type 'object'"; "expect_volume.tol.rel must be a non-negative number"; verify_shape OK; no RecursionError. Captures identical. |
| TC-09-11 | High | **PASS** | tc-09-11-checks.txt | max_nodes 0/50 rejected "'max_nodes' was unexpected"; props ['doc','focus','expand','depth','filters']; plain "OK: 1 objects, 1 shown."; depth 1 one line; edge report retired_max_nodes_rejected ok. 0 px. |
| TC-09-12 | Critical | **PASS** | ev/tc-09-12-at4/at14 | (escalate) 0 px, golden model still shown. Tree refusal text "INVALID_INPUT: unknown or stale document handle: fcb-doc:does-not-exist" (text only on the wire). |
| TC-09-13 | Critical | **PASS** | tc-09-13-checks.txt | 4 reads + export INVALID_INPUT "unknown object: NoSuchObject", no step file; "box" INVALID_INPUT; empty "missing required 'object' name" (F-23 fixed). 0 px. |
| TC-09-14 | Critical | **PASS** | tc-09-14-checks.txt, -addonlog.txt | "unknown object: NoSuchSketch", "object is not a sketch: Body", "unknown object in feature: NoSuchFeature"; verify_recompute OK; "11 objects" before/after; 4 INFO 0 tracebacks. Same block; 5837 px only status-bar "Preselected:" text. |
| TC-09-15 | Critical | **FAIL (human intervention: physical mouse)** | tc-09-15-checks.txt, -h1.jsonl, -grep.txt, -after.png, -after-recapture2.png | String Thens pass: H1 and H2 isError, structuredContent null, "{'handle': 'fcb-doc:x'} is not of type 'string'"; no "unknown or stale"; guard text mcp_server.py:259, rpc_listener.py:418; 46 tools. Visual Then not met: right face green preselection ("Preselected: box_10_20_30.Box.Face2"), 118848 px; physical mouse moved over 3D view from ~22:24. Same geometry, no dialog. Re-run needed. |
| TC-09-16 | Critical | **PASS** | tc-09-16-checks.txt | "document_open failed for '<path>': File ... does not exist!"; "document_open requires a 'path'"; AGENTS.md "Invalid project file ...: ios_base::failbit..."; no doc, no handle; open_bad_path ok. Golden box 0 px. |
| TC-09-17 | Critical | **PASS** | ev/tc-09-17-after-tree | (escalate) Pad row red error overlay, last valid 20x20x10 block shown; MCP fit OK. checks.0/1 recompute.object passed false; src/freecad_buddy/usecases/verify.py:22 `_RECOMPUTE_ERROR_STATES = frozenset({"Invalid", "Error", "Touched"})`. |
| TC-09-18 | Critical | **PASS** | ev/tc-09-18-after-tree | (escalate) Pad row error overlay, Sketch gone (Body holds Origin, Pad), last valid block shown. Pad check at checks.1. |
| TC-09-19 | High | **PASS** | tc-09-19-checks.txt, -server.stderr.log, -audit.jsonl | H1 audit log = directory: create/close/query_capabilities OK, 46 tools; 4x "ERROR freecad_buddy.mcp_server: audit write failed" (mcp_server.py:306); writable path 4 records, 2nd of pair verify_verdict. Identical. |
| TC-09-20 | Critical | **PASS** | tc-09-20-then.txt, snap_1..3, -append.jsonl | prefix True x3; head diff empty; 585<1170<1859; 6 JSON lines fcb.audit-record/1; 3 with verify_verdict; audit_log.py:48 open "a". Identical. |
| TC-09-21 | High | **PASS** | tc-09-21-checks.txt, -h1.jsonl, -edge.stderr.log | H1 query_object NoSuchObject traceback 1899 chars, ValidationError, no unexpected key; export_stl Q:/no_such_dir RECOMPUTE_ERROR OSError unexpected=true; rpc_dispatch.py:29, :88-91; 5 INVALID_INPUT 0 Traceback. Identical. |
| TC-09-22 | Critical | **FAIL (harness defect: stale sweep scripts)** | tc-09-22-checks.txt, -when.txt, -e2e_report.json, -server.stderr.log | "both report files all_passed True": e2e False (9, 4 passed, tree_summary NO_STATUS), edge False (6/13). Pass: no crash signature, 0 tracebacks. Identical. Given "ls tc-09-22-e2e_report.json" fails before the When (only the When creates it) - test-case defect too. |
| TC-09-23 | Critical | **PASS** | tc-09-23-checks.txt, -mcp.jsonl, -tools-list.json, -before/-after.png | pid 11300 alive all P7, 46 tools start/end; round trip OK; export volume 6000.0; document_list empty; no snap/prev. Before TC0918Broken with error mark; after whole box fitted, no dialog. Replayed P0 TC-09-03/06/12/17/18 steps ungraded (p7-replay-*). |

## TC-10 — Concurrency, Timeout Budget & Document Quarantine

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-10-01 | Critical | **FAIL (harness defect: stale sweep)** | tc-10-01-checks.txt, -six-spans.json, -e2e_report.json, -server.stderr.log, -before/-after.png | all_passed False: run_mcp_e2e.py:57-58 _status reads structuredContent; tree_summary NO_STATUS x5. As written exit 2; via p7_sweep 4/9. Other Thens pass: 6 spans no overlap, all OK, order matches, 0 marshal lines, no traceback. (Agent's first span run had own client clock fault, kept as run1-clockfault-*.) Captures whole iso box 0 px. |
| TC-10-02 | High | **PASS** | tc-10-02-checks.txt, -latency.json, -timeouts.json | median "40 0.009"; TIMEOUT 0; 5 query_screenshot OK max 0.042 s (render unavailable no pivy); no call over timeout_s. Whole box 0 px. |
| TC-10-03 | Critical | **FAIL (test-case defect)** | tc-10-03-checks.txt, -when-discovery.txt, -rpc.jsonl | When glob(...rpc-*.json)[0] picks rpc-10224.json (1 of 60, dead pid), port 64336; B connect refused ConnectionRefusedError 10061. Informational with rpc-11736.json: B -32000 "bridge busy..." 0.219 s then 0 bytes; C "auth failed"; proxy document_list OK; refusal line 1x. Captures 0 px. |
| TC-10-04 | High | **PASS** | tc-10-04-checks.txt, -rpc.jsonl, -proxy-*.txt | A hello carries contract/freecad/capabilities; B -32002 "handshake required" then 0 bytes; C served after B. GUI Fit All (proxy stopped); whole box. Proxy restarted by hand with operator-settings values. |
| TC-10-05 | High | **PASS** | tc-10-05-checks.txt, -h1.jsonl, -server.stderr.log | preview_dry_run OK in 100.13 s (FeaturePython recompute sleeps 100 s, p8_slow.py); document_list OK same session; no "timed out"/"connection reset"; no FCB_TMP_prev_. 0 px. |
| TC-10-06 | High | **PASS** | tc-10-06-checks.txt, -rpc.jsonl | Session B reads A's cylinder handle, lists and closes it; list omits it. GUI Fit All; whole box, cylinder gone. |
| TC-10-07 | Critical | **FAIL (test-case defect)** | tc-10-07-checks.txt, -h1.jsonl, -audit.jsonl, -chain-run.txt | Two Thens read detail.data.quarantined from query_tree_summary (text only, mcp_server.py:111-115). Observed "TIMEOUT: not dispatched: the session is quarantined..." 0.008 s and "WORKER_CRASHED: ...past twice its 30 s budget...restart the headless host" at 65 s; query_object probe {"quarantined": true}. Other Thens pass: TIMEOUT 30.023 s marshal_timeout maybe_still_running, worker CPU 31.6->35.1, worker 29652 alive, OK at 85 s, audit TIMEOUT line. After capture 0 px. |
| TC-10-08 | Critical | **PASS** | tc-10-08-checks.txt, -greps.txt | D mutation INVALID_INPUT "document-suspect: a prior call timed out..."; no D marker; stderr +0 bytes; audit 1 INVALID_INPUT script_exec; E OK marker; greps entry.py 0, rpc_listener.py:422. 0 px. |
| TC-10-09 | Critical | **PASS** | tc-10-09-checks.txt | failing read INVALID_INPUT; mutation still refused; passing query_tree_summary OK then mutation OK; READ_ONLY_PROFILE lists query_tree_summary. After (tc-10-09-D.FCStd in GUI): 10x20x30 box + one QuarantineCleared cube. |
| TC-10-10 | Critical | **PASS** | tc-10-10-checks.txt, -audit-before-retry.jsonl, -greps.txt | "do not blind-retry"; audit 1 before + 1 after on F; LateBox once; fingerprint 554070c8 != d10f0d82; retry grep 1 hit mcp_server.py:199. Manual retry returns TIMEOUT (dispatched, closed set; mutation overruns 30 s by design) - lead accepts as terminal envelope (Then :29 "normal terminal envelope, proving retry is a client action"). After box + one LateBox, not doubled. |
| TC-10-11 | High | **PASS (human intervention noted)** | tc-10-11-checks.txt | verify_recompute TIMEOUT 120.005 s, "no mutation was attempted..." and "the body may still be running and ", not "now suspect", marshal_timeout; mutation TIMEOUT {"quarantined": true} "not dispatched:"; 140 s OK, AcceptedAfterRead once. After: G whole and framed, right face green preselection from human pointer pass 23:36:42-23:37:41 (after H1 ended 23:36:05), 115200 px. Then :35 criteria (paints, no Not Responding, no modal, G whole and framed, unchanged BY the H1 read timeout) met. |
| TC-10-12 | Critical | **PASS** | tc-10-12-checks.txt, -kill.jsonl, -mcp-proxy-after-kill.log | Stop-Process 16284 5 s into sleep(25): WORKER_CRASHED "listener connection dropped" 5.312 s; :8765 free at +1.12 s; proxy log dropped-connection, "exits and frees port 8765" 1. Restart 30808 no recovery dialog; 46 tools; healthz 30808. Whole box 0 px. rpc-16284.json not deleted (rule). |
| TC-10-13 | Critical | **PASS** | tc-10-13-checks.txt | 1 line "frame read failed... connection closed mid-frame", no traceback; fresh hello contract "1"; document_list OK; no document-suspect; menu query answers. GUI Fit All, whole box. |
| TC-10-14 | High | **PASS** | tc-10-14-checks.txt | over-cap ConnectionResetError (allowed); cap line 1x; non-UTF-8 0 bytes; third client OK; working set +11.5 MB; mutating script_exec not refused. Whole box. |

## TC-11 — Security Posture & Artifact Hygiene

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-11-01 | Critical | **PASS** | ev/tc-11-01-before/after.png, tc-11-01-h1.jsonl, tc-11-01-h1.stderr.log, tc-11-01-proxy-tools.json, tc-11-01-audit.jsonl | (escalate) before vs after the H1 session 0 px, one box, no dialog. H1 tools/list 46 with script_exec; proxy 46, same list; SECURITY script_exec ENABLED in H1 stderr and GUI addon.log; exec_enabled true both hosts; H1 value_repr '0'; H1 audit 2 exec lines, 2nd verify_verdict OK; grep of src for ALLOW_EXEC/AllowExec/debug_exec empty; Given operator settings FREECAD_BUDDY_SCRIPT_EXEC='1' (preference). |
| TC-11-02 | Critical | **PASS** | tc-11-02-before/after.png, -{a..f}.jsonl/.stderr.log, -checks.txt | a,b,c,e: 45 tools, no script_exec, exec_enabled false, no SECURITY line; d,f: 46, true, SECURITY line. Acceptance Given met (operator 2026-10-24 00:03). Captures same box, 0 px. |
| TC-11-03 | Critical | **PASS** | tc-11-03-audit.jsonl, -h1.jsonl, -checks.txt, before/after.png | 2 exec lines same 64-hex digest, code "result = doc.Name", line 1 no verify_verdict, line 2 OK, fingerprint_before null, fcb.audit-record/1. 0 px. |
| TC-11-04 | Critical | **PASS** | tc-11-04-h1.jsonl, -tool_surface.json, -checks.txt | grep only tool_catalog.py:1071 audit_event="exec"; 30 mutating specs in families; previews script_exec/no_such_tool "not a previewable mutation tool: ..."; closed-schema True on tool_surface.json written from H1 tools/list (TC names file with no producer); undeclared key "Additional properties are not allowed". 0 px. |
| TC-11-05 | Critical | **PASS** | tc-11-05-checks.txt, -rpc.jsonl, before/after.png, after-noshowall.png | 127.0.0.1:49942 one LISTENING; record host 127.0.0.1; LAN 192.168.50.13 ConnectionRefusedError; loopback hello "1". After: GUI Fit All (proxy stopped), box ~1.5% larger, same single box whole framed. (agent's first after capture skipped Show All, kept.) Proxy restarted by hand. |
| TC-11-06 | Critical | **PASS** | tc-11-06-checks.txt, before/after.png | 127.0.0.1:8765 only; LAN POST curl exit 7; loopback 307; --host "unrecognized arguments: --host 0.0.0.0" exit 2; entry.py:44-45 literals; auth grep empty. 0 px. |
| TC-11-07 | High | **PASS** | tc-11-07-checks.txt, -rpc.jsonl, before/after.png | rpc-17944.json attrib A; icacls SYSTEM, Administrators, TAN-PC\thuan; token len 43; wrong token {"code":-32000,"message":"auth failed"} then 0 bytes; file gone after File > Exit. 0 px. |
| TC-11-08 | Critical | **PASS** | tc-11-08-*.jsonl/.stderr.log, -approve.jsonl, -checks.txt | unset: warning exact, feature_body_create OK, 1 approval line mode auto_approve source FREECAD_BUDDY_AUTO_APPROVE; =0 and =true refused exact confirm message. Acceptance Given met. 0 px. |
| TC-11-09 | High | **PASS** | tc-11-09-checks.txt, -s09-stdout.txt, -rpc.jsonl, before/after.png | old and new tokens differ; OLD token auth failed then 0 bytes; OLD + version 999 auth failed; NEW token "1"; rpc-17944.json gone. After restart 35504 reopened box 0 px. |
| TC-11-10 | Critical | **PASS** | tc-11-10-mcp.jsonl, -h1.jsonl, -checks.txt, before/after.png | list [box_10_20_30] before/after; preview OK; export_step + verify OK; fingerprint d1011f78 equal; session folder empty; H1 same. Tree no FCB_TMP_ item; 0 px. |
| TC-11-11 | Critical | **FAIL (test-case defect)** | tc-11-11-h1.jsonl, -checks.txt, before/after.png | Then TC-11 file :527 "each preview's detail.message names the real cause": succeeding and failing previews are status OK, detail null (contracts/envelope.py:52 "required non-null unless status == OK"). Other Thens met: FCB_TMP_prev_ count 0; failing preview diff.validity.status RECOMPUTE_ERROR; raising preview INVALID_INPUT "unknown object in profile: NoSuchSketch"; document_list only tc11_11. Captures same box; 57320 px only title bar focus shade. |
| TC-11-12 | Critical | **PASS** | tc-11-12-h1.jsonl, -checks.txt, tc-11-12-workdir/ | commit count 0 no snapshot_path; rollback rolled_back_verified count 0; commit-raises SPEC_FAILED "RuntimeError: tc-11-12 forced commit failure" count 0; unproven text "Mutation failed and its rollback could not be proven: ...", FCB_TMP_snap_ltz_sul3 kept; unhashable SPEC_FAILED FCB_TMP_snap_rkdnklfg kept; under tc-11-12-workdir/tmp/FCB_TMP_session_32184_*. (first attempt discarded: agent's wrong fillet base, -fault1 files.) 0 px. |
| TC-11-13 | Critical | **PASS** | tc-11-13-checks.txt, before/after.png | keep-a.txt removed, keep-b.txt and folder kept, exit 0; FCB_TMP_snap_tc1113 removed. 0 px. |
| TC-11-14 | Critical | **FAIL (test-case defect)** | tc-11-14-h1.jsonl, -listing{1,2,3}.txt, -checks.txt | Then TC-11 file :695 "third listing adds only the requested path": adds tc11-export.stl AND box-copy.20261024-001919.FCBak (document_save backup, which Then :696 allows). Other Thens met (sweep changed nothing, no FCB_TMP_, no audit log; save changed only box-copy.FCStd mtime). 0 px. |
| TC-11-15 | Critical | **FAIL (test-case defect)** | tc-11-15-append.jsonl, -checks.txt, before/after.png | :734 grep also prints "Binary file ...__pycache__/documents.cpython-311/312/314.pyc ... matches" (pyc 2026-10-07/13); :735 grep returns audit_log.py:9 "this sink never truncates, rotates, or reads it." Met: 8 -> 17 lines, first 8 identical, sha256 equal; open "a" line 48; concurrent 17 -> 51, 0 unparsable. After differs only in status-bar preselection text (6186 px, human). |
| TC-11-16 | High | **PASS** | tc-11-16-checks.txt, -e2e-report.json, -audit.jsonl, -render.png, before/after.png | token absent from report, 4 PNGs, audit, addon.log, mcp-proxy.log; capabilities no token; hello keys capabilities/contract_version/freecad_version. 0 px. |
| TC-11-17 | Critical | **PASS** | cap/TC-11-17, ev/tc-11-17-before/after.png, tc-11-17-h1.*, tc-11-17-audit.jsonl, tc-11-17-audit-count.txt | (escalate) runner capture and f5 re-run: box only, no Leak, 0 px before/after. f5 addon.log FREECAD_BUDDY_SCRIPT_EXEC='0' (env), no SECURITY script_exec line. Proxy exec_enabled false, refusal "unknown method: script_exec", tree Box only, GUI audit lines 5 -> 5. H1: 45 tools, INVALID_INPUT with the exact "script_exec is off: ..." message, 2 exec lines with the code (2nd INVALID_INPUT), tree "OK: 0 objects". |
| TC-11-18 | Critical | **BLOCKED (harness limit: H1 venv has no pivy)** | tc-11-18-checks.txt, -listing-before/after.txt, -render.png, -h1.jsonl, before/after.png | Then :883 "H1 ... holding the H1 render": H1 render "offscreen probe render failed: No module named 'pivy'" (substitute venv, include-system-site-packages=false; fcb env missing). Other Thens met: temp_dir under workdir\tmp, render FCB_TMP_shot_czymfi9a.png in GUI session folder, no snap/prev, mint paths FCB_TMP_snap_4rq2z4d8, FCB_TMP_prev_rm0ob77k; %TEMP% 54=54; minted dirs removed; listings identical. After same box, title differs. |
| TC-11-19 | Critical | **PASS** | tc-11-19-checks.txt, -listing-before/after.txt, -q4-*.txt, -h1.stderr.log, before/after.png | "session-start sweep removed 2"; 999996 and orphan gone; live/non-prefixed/OS-temp kept; H1 "removed 1"; one grep line per host. Given met by H1 product sweep. Explorer covered FreeCAD 00:45-08:02 (human; unpainted captures kept). After same box; 19919 px only menu bar focus. |

## TC-12 — GUI Workflows Observed Through the Bridge

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-12-01 | Critical | **BLOCKED (display frozen)** | none | Not run: needs pixel sketch drawing on a painted view; display frozen 08:15-09:18 and ~10:04-end. |
| TC-12-02 | Critical | **PASS** | tc-12-02-*.png/txt, -checks.txt | Title "Unnamed - FreeCAD 1.1.4", one tree root without child, empty 3D view; fit nothing_to_frame -> GUI Fit All. |
| TC-12-03 | Critical | **BLOCKED (display frozen)** | tc-12-03-checks.txt, -verify.txt, -after.png | Non-visual Thens PASS (verify_state satisfied, volume 6000.0, verify_shape OK, label box-10-20-30, transient false); launch via p10_launch -OpenFile not launch_app. After capture is the frozen frame. |
| TC-12-04 | Critical | **FAIL (test-case defect)** | tc-12-04-*, -checks.txt | Then :250 token click on TreeItem does not select (selected:false); same file :691 says so on 1.1.4. :254 4188.79 vs 4188.7902 met under test-plan rule 9. Visual :257 not met (no highlighted row). (harness finding: click action "select" does select a TreeItem.) |
| TC-12-05 | Critical | **FAIL (harness limit)** | tc-12-05-checks.txt, -before/after.png (re-run 09:50 on painting display; frozen attempt tc-12-05-frozen-*) | When View > Visibility > "Toggle Visibility" refused menu_path_unavailable segment 2 (item present in desktop capture). With deviation (select + Space) other Thens and visual PASS: before two cubes, after only ObjectA, ObjectB row greyed. |
| TC-12-06 | Critical | **FAIL (test-case defect + harness limit)** | tc-12-06-checks.txt, -popup.png, -edit.png, -edit-desktop.png, -after.png, -fault1-* | :350 verify_state "unknown" multi_match (5 "buddy:" entries); dropdown is a separate popup not in main-window capture (popup capture shows "buddy: feature_fillet Fillet" first); :353 document_undo removes the pad before the closing capture (undid "buddy: feature_pad Pad", correct). Agent fault1: pixel click on Undo arrow ran Undo; scenario restarted from Given. |
| TC-12-07 | High | **PASS** | ev/tc-12-07-given, tc-12-07-props-iso, tc-12-07-after, cap/TC-12-07 | (escalate) clean: Recompute button grey. Dirty (script_exec Length=8, no recompute): old 5 mm pad drawn, button enabled (UIA enabled True), touched overlay on Pad, dirty_document true. After Edit > Recompute: no marks, button grey, 8 mm solid; verify_recompute OK, recompute touched 0, volume 1600.0. |
| TC-12-08 | High | **FAIL (test-case defect)** | tc-12-08-checks.txt, -after.png, -bracket.FCStd | :467 query_mass_properties "Cube001" INVALID_INPUT "unknown object: Cube001": Name Box001, Label Cube001; queries.py:188-198 by Name. Save via toolbar button (File > Save refused). Save/title/handle Thens PASS; visual PASS (title without "*", Cube and Cube001, one cube whole). |
| TC-12-09 | High | **PASS** | tc-12-09-checks.txt, -dialog.png, -after.png (re-run 09:55; frozen kept) | Preferences window listed; script_exec 'scheduled'; read during dialog OK 0.157 s; Cancel by token; capabilities OK; :8765 listening. Captures: painted Preferences dialog with OK/Cancel/Apply; after main window no dialog. |
| TC-12-10 | Medium | **FAIL (harness limit)** | tc-12-10-checks.txt, -verify-sketcher.txt, -after.png (re-run 09:57) | :569 verify_state "unknown", combo still "Part Design": UIA click on "Sketcher" ListItem does not switch workbench (painting and frozen display). Given needed script_exec activateWorkbench. Handle Thens PASS. Visual not met: Show All refused, 3D view empty. |
| TC-12-11 | Medium | **FAIL (harness limit)** | tc-12-11-frozen-checks.txt, -frozen-* | :613 after token scroll (route global_input) tree2 UIA snapshot same 15 rows (run during freeze; UIA rows not pixel-based). Depth/filter/max_nodes/budget Thens PASS (61 objects; depth 1: 1 shown; depth 3: 61; filters 26 matches). Visual not judged (frozen). |
| TC-12-12 | Medium | **BLOCKED (harness limit + display frozen)** | tc-12-12-checks.txt | Given cannot be verified: Start page example cards have no UIA name; capture frozen. |
| TC-12-13 | Critical | **BLOCKED (display frozen)** | tc-12-13-frozen-checks.txt, -frozen-* | Non-visual Thens PASS (3 stale reads + stale close INVALID_INPUT; same pid; list B only; B volume 1570.8; TreeItems B only). PNG half of :716 and visual :724 not judged (frozen). |
| TC-12-14 | Critical | **FAIL (test-case defect or product gap)** | tc-12-14-checks.txt, -post-state.txt, tc-12-c-addon.log | When quit routes failed (File > Exit refused segment 1; background alt+f4 no effect); quit by title-bar Close (deviation). Exit, port, proxy gone, rpc deleted, ConnectError, restart, healthz PASS. :779 addon.log has no teardown line (only "client reset the connection"); bootstrap.py:510-531 stop_bridge logs nothing. Visual not judged (frozen). |
| TC-12-15 | Critical | **BLOCKED (display frozen)** | tc-12-15-checks.txt, -kill.json, -mcp-proxy.log, -proxy-log-line.txt | Non-visual Thens PASS (WORKER_CRASHED 1.75 s; FreeCAD gone; ConnectError; proxy 31980 gone ~2 s "has exited; the MCP proxy exits"; restart own proxy healthz 35252; sweep "removed 0"). Visual not judged. rpc-33684.json left (rule). |

## TC-13 — GUI and MCP Parity

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-13-01 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-02 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-03 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-04 | Critical | **PASS** | cap/TC-13-04, ev/tc-13-04-render.png | (escalate) window flat 40x40x10 plate with centred hole; render (re-run copy, see finding F2) same silhouette, hole, camera, no extra body. |
| TC-13-05 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-06 | Critical | **PASS** | cap/TC-13-06, ev/tc-13-06-render.png, tc-13-06-tone-checks.txt | (escalate) same outline, hole, faces, Z up; no Body/Sketch/Origin in render; rendered_objects [BoxHole]; tone band: every face at least 65/255 from white background, every channel in [20, 235]. |
| TC-13-07 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-08 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-09 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-10 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-11 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-12 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-13 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-14 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-15 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-16 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-17 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-13-18 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |

## TC-14 — Viewport Framing & Auto-Fit

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-14-01 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-02 | Critical | **PASS** | cap/TC-14-02 | (first of TC-14) one whole box framed. |
| TC-14-03 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-04 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-05 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-06 | Critical | **PASS** | cap/TC-14-06, ev/tc-14-06-at13/at16 | (escalate) title "* DocB", DocB tab active; 0 px across the refusal. |
| TC-14-07 | Critical | **PASS** | cap/TC-14-07 | (sample) one whole box framed. |
| TC-14-08 | High | **PASS** | ev/tc-14-08-at3/at7, cap/TC-14-08 | (escalate) same box after both rejects (at3 vs at7 0 px); runner capture differs only in status-bar counter. |
| TC-14-09 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-10 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-11 | Critical | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-12 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-13 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-14 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-15 | High | **BLOCKED (display frozen)** | lead-desktop-0910.png, p10-recovery-watch.txt | Not run: from ~08:15 2026-10-24 GPU-drawn windows on this machine do not repaint (P10 F-P10-4); a visual Then cannot be judged. |
| TC-14-16 | Critical | **PASS** | cap/TC-14-16, tc-14-16-mcp.jsonl | (escalate) list_windows title "* box-10-20-30 - FreeCAD 1.1.4" before and after the fit. |

## TC-99 — Architecture-Decision Conformance Gaps (EXPECTED-FAIL)

All five scenarios are Critical. None ran: P12 stopped on the display freeze.

| Scenario | AD | Verdict | Observed |
| --- | --- | --- | --- |
| TC-99-01 | AD-3 | **BLOCKED (display frozen)** | Not run: display frozen (see TC-13). Evidence: `lead-desktop-0910.png`. |
| TC-99-02 | AD-3 | **BLOCKED (display frozen)** | Not run: display frozen (see TC-13). Evidence: `lead-desktop-0910.png`. |
| TC-99-04 | AD-25 | **BLOCKED (display frozen)** | Not run: display frozen (see TC-13). Evidence: `lead-desktop-0910.png`. |
| TC-99-05 | AD-25 | **BLOCKED (display frozen)** | Not run: display frozen (see TC-13). Evidence: `lead-desktop-0910.png`. |
| TC-99-06 | AD-25 | **BLOCKED (display frozen)** | Not run: display frozen (see TC-13). Evidence: `lead-desktop-0910.png`. |

## Gate 1 summary

255 scenarios in TC-01..TC-14 (TC-99 is not in Gate 1). Counts are taken from the tables above. A verdict word with a cause in brackets counts as that word: `FAIL (test-case defect)` is a FAIL, `PASS (degraded; ...)` is a PASS.

| TC | Scenarios | PASS | PARTIAL | FAIL | BLOCKED | SKIP |
| --- | --- | --- | --- | --- | --- | --- |
| TC-01 | 15 | 12 | 0 | 3 | 0 | 0 |
| TC-02 | 18 | 17 | 0 | 1 | 0 | 0 |
| TC-03 | 21 | 21 | 0 | 0 | 0 | 0 |
| TC-04 | 24 | 21 | 0 | 3 | 0 | 0 |
| TC-05 | 18 | 16 | 0 | 2 | 0 | 0 |
| TC-06 | 12 | 10 | 0 | 2 | 0 | 0 |
| TC-07 | 21 | 21 | 0 | 0 | 0 | 0 |
| TC-08 | 21 | 17 | 0 | 4 | 0 | 0 |
| TC-09 | 23 | 18 | 0 | 5 | 0 | 0 |
| TC-10 | 14 | 11 | 0 | 3 | 0 | 0 |
| TC-11 | 19 | 15 | 0 | 3 | 1 | 0 |
| TC-12 | 15 | 3 | 0 | 7 | 5 | 0 |
| TC-13 | 18 | 2 | 0 | 0 | 16 | 0 |
| TC-14 | 16 | 5 | 0 | 0 | 11 | 0 |
| **Total** | **255** | **189** | **0** | **33** | **33** | **0** |

| Priority | Scenarios | PASS | PARTIAL | FAIL | BLOCKED | SKIP | Pass rate | Threshold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Critical | 174 | 126 | 0 | 26 | 22 | 0 | 126/174 = 72.4 % | 100 % |
| High | 67 | 54 | 0 | 3 | 10 | 0 | 54/67 = 80.6 % | >= 95 % |
| Medium | 14 | 9 | 0 | 4 | 1 | 0 | 9/14 = 64.3 % | none |

**Gate 1 verdict: RED.** Critical 126/174 = 72.4 % (needs 100 %). High 54/67 = 80.6 % (needs >= 95 %). 33 FAIL and 33 BLOCKED. Story 10.8 stays open (spec D2).

The lead log counts 260 scenarios (TC-99 included): Critical 179 = 126 PASS, 26 FAIL, 27 BLOCKED. The 5 extra Critical scenarios are the TC-99 rows, all BLOCKED. Gate 1 uses the 174 Critical scenarios of TC-01..TC-14.

Cause of the 33 FAILs (from the Note column and the Findings below): 3 suspected product defects (TC-02-08, TC-08-02, and TC-12-14, whose verdict reads "test-case defect or product gap"); 5 harness defects from stale sweep scripts (TC-01-02, TC-09-01, TC-09-02, TC-09-22, TC-10-01); 4 harness limits (TC-06-01, TC-12-05, TC-12-10, TC-12-11); 1 test-case defect plus harness limit (TC-12-06); 18 test-case defects (TC-01-13, TC-01-15, TC-04-16, TC-04-21, TC-04-23, TC-05-06, TC-05-17, TC-06-09, TC-08-01, TC-08-13, TC-09-09, TC-10-03, TC-10-07, TC-11-11, TC-11-14, TC-11-15, TC-12-04, TC-12-08); 2 to re-run without a fix (TC-08-12 agent execution fault, TC-09-15 physical mouse). Rule D-lead-1 (owner, 2026-10-23): a Then whose literal check is not met is FAIL with cause "test-case defect", even when the product behaves as designed.

BLOCKED: 32 scenarios by the display freeze (TC-12-01, TC-12-03, TC-12-12 (also a harness limit), TC-12-13, TC-12-15; 16 of TC-13; 11 of TC-14); TC-11-18 because the H1 stand-in venv has no `pivy`. Plus the 5 TC-99 rows outside Gate 1.

## Gate 2 — TC-99 conformance (expected-fail)

**Not run.** All 5 TC-99 scenarios are BLOCKED: P12 did not start because of the display freeze. No comparison with the documented deviations was made, so no scenario is EXPECTED-FAIL, FAILS-DIFFERENTLY or promoted. The last Gate 2 result is the one of run 2026-10-03-04, which had 8 TC-99 scenarios; the suite now holds 5.

## G3 replay (corrupted-plan suite)

### Headless (spec D1, second form): UNCHANGED

- Command: `benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x --check --frames-check benchmarks/g3/fault-injection/frames-reference.json`, on the H1 stand-in venv with FreeCAD 1.1.4, 2026-10-24 08:44:36-08:44:55, exit 0.
- Result: planted 10/10 DETECTED; reverted 10/10 PASS_CLEAN; controls 4/4 PASS_CLEAN; flagged 0. Sensitivity 1.000, false alarm 0.000. `frames-check: OK vs benchmarks\g3\fault-injection\frames-reference.json`. `validators.yaml not written` (`--check`).
- Reference `g3r-2026-10-08-1.1.3`: sensitivity 1.0, false alarm 0.0, same outcome per case. **Verdict: UNCHANGED.**
- First attempt 08:44:15-08:44:16 failed before scoring: `ModuleNotFoundError: No module named 'yaml'` (`score_g3_replay.py:46`); the stand-in venv lacked `pyyaml`. Kept as `evidence/g3-headless/*-fault1.txt`. `pyyaml==6.0.3` was added (`pyyaml-install.txt`), then the run above.
- Evidence: `evidence/g3-headless/` (`stderr.txt`, `cases.jsonl`, `G3.E.3.1.1.x.json`, `g3-headless-summary.txt`, `start.txt`, `exit.txt`).

| Case | Planted | Reverted | Outcome |
| --- | --- | --- | --- |
| blind-hole-made-through | DETECTED | PASS_CLEAN | DETECTED |
| datum-origin-swapped | DETECTED | PASS_CLEAN | DETECTED |
| extra-unrequested-pocket | DETECTED | PASS_CLEAN | DETECTED |
| hole-on-wrong-face | DETECTED | PASS_CLEAN | DETECTED |
| mirrored-hole-pattern | DETECTED | PASS_CLEAN | DETECTED |
| missing-bolt-holes | DETECTED | PASS_CLEAN | DETECTED |
| pocket-before-pad | DETECTED | PASS_CLEAN | DETECTED |
| radius-for-diameter | DETECTED | PASS_CLEAN | DETECTED |
| wrong-hole-diameter | DETECTED | PASS_CLEAN | DETECTED |
| wrong-plate-thickness | DETECTED | PASS_CLEAN | DETECTED |
| control-equivalent-step-order | — | — | PASS_CLEAN |
| control-faithful-mounting-plate | — | — | PASS_CLEAN |
| control-named-datum-honoured | — | — | PASS_CLEAN |
| control-tolerance-edge-hole | — | — | PASS_CLEAN |

### GUI (spec D1, first form): not run

The GUI replay with `tests/uat/run/2026-10-03-04/evidence/g3_gui_replay.py` on FreeCAD 1.1.4 did not run: BLOCKED by the display freeze. Spec D1 asks for both forms, so the G3 part of Story 10.8 AC1 is not met by this run.

## Visual check

- Every agent-driven scenario that has a verdict other than BLOCKED closes with a fit and a `cua-driver` window capture that the executing agent read and described in the Note column. No MCP field, status or MCP render stands as visual evidence.
- The runner's review set (71 captures: 66 ESCALATE, 1 FAIL, 2 first-of-test-case, 1 no-pixel-check, 1 random sample, seed 1748575703) was read by the agent per test-plan §9. Where an `agent_check` names a before-capture or a between-step Given, the agent re-ran the scenario's steps by MCP to that step and captured there (`ev/tc-xx-yy-atN` files).
- The lead read the capture behind the one product FAIL graded on a picture: TC-02-08 `tc-02-08-after.png` (plate cut by the top and right view borders).
- A scenario whose visual Then could not be judged is never PASS: it is BLOCKED (display frozen) or FAIL with the reason in the Note. The frozen-frame captures from P10 are kept as `*-frozen-*` and graded as not judged.
- Captures with a human pointer effect (preselection highlight) are named in the Note (TC-09-15, TC-10-11, TC-11-15).

## Findings

Each finding: what was sent, what came back, and where in the source, as recorded in the phase notes. The bug list with state is `bugs.md` (ids `B-nn` for FAIL causes, `N-nn` for findings with no verdict change).

### Suspected product defects

| # | Scenario(s) | Request → observed | Source | State |
| --- | --- | --- | --- | --- |
| B-02 | TC-02-08 (FAIL) | Body placed at (30,20,10), rotated 30 deg about Z. `view_fit_viewport` → `OK fitted`, framing `fits 0.95`; window shows the plate cut by the top and right borders. Fit uses the container-local box (0,0,0)-(60,40,10), not the global box (10,20,10)-(81.96,84.64,20). AD-30 class (false "fits") | `usecases/framing.py:91` `model_bounds`, `:95-102` `_object_bounds`; `view_fit.py:162-168` | fix on branch (uncommitted; lead check pending) |
| B-03 | TC-08-02 (FAIL) | Failing `preview_dry_run` (fillet r500) on the throwaway copy posts a GUI notification "Fillet: BRep_API: command not done (2 times)"; status-bar badge blank → 1 (711 px). The preview's recompute reaches the human's GUI (AD-31) | `evidence/tc-08-02-notification-popup.png`, `tc-08-02-statusbar-*.png` | fix on branch (uncommitted; lead check pending) |
| B-04 | TC-12-14 (FAIL) | Clean quit writes no teardown line to `addon.log`; only "client reset the connection" | `hosts/gui_addon/bootstrap.py:510-531` `stop_bridge` logs nothing | fix on branch (uncommitted; lead check pending) |
| N-02 | TC-10-03, TC-11 (no verdict) | 61 `rpc-*.json` discovery files in `%APPDATA%\FreeCAD\v1-1\freecad-buddy`, all but the live one from killed FreeCADs, each with a dead token; nothing removes them. AD-25 binds every file writer ("unbounded artifact growth") | P9 B8; lead log §5 W5 | open |
| N-03 | H1 sweeps (fix work) | H1 stdio front deadlocks with pip numpy 2.4.6: `verify_export_stl` hangs in `import trimesh`; a thread blocked on `sys.stdin.buffer.readline()` then `import numpy`. Conda numpy 1.26.4 does not hang | `adapters/export_oracle.py:187` via `rpc_proxy.py:49`; repro `scratchpad/fix/w3/repro_numpy_stdin.py` (lead log §5 W3) | open |
| N-04 | TC-05-06 (fix work) | `feature_pattern` with 200 occurrences: recompute ran more than 10 min and 5 GB with no limit; 20 occurrences commit | lead log §5 W4 | open |
| N-08 | TC-01-10 (no verdict) | `document_save {doc, path}` then `document_save {doc}`: both `saved true`; title stays `* tc-01-10-box - FreeCAD 1.1.4`. GUI Save clears the `*` | `usecases/documents.py:341` saveAs, `:533` save (likely: App-level save does not clear the Gui::Document modified flag; not verified) | open |
| N-09 | TC-04-06/10/15/17, TC-05-15 (no verdict) | Consumed profile sketch stays shown after `feature_pad`/`pocket`/`revolve`; FreeCAD's own Pad hides it | `usecases/features.py:516-532`; `tc-04-10-top.png` | open |
| N-10 | TC-04-13 (no verdict) | `feature_datum` result: `feature_state.body ""`, `is_tip false`, `shape_summary` volume 4e+101, area 8e+100 (infinite datum) | `usecases/features.py:329-335` reads `_Body`, `:296` | open |
| N-11 | TC-05-10/12/18, TC-11-12 (no verdict) | Summary text prints `None`: "Mutation rolled back (None): ...", "...could not be proven: None."; a committed but unhashable mutation says "Mutation failed and its rollback could not be proven: <path>." though the commit landed | `usecases/transaction.py:491-497` `summarize_mutation` | open |
| N-12 | TC-07-20 (no verdict) | Failed check detail `\|7200.0 - 6000.0\| = 1200.0 <= 6 mm^3`: fixed `<=` text in a failed-check message | `usecases/assertions.py:861`, `:892`, `:917`, `:954`; `usecases/exports.py:360` | open |
| N-13 | TC-08-12/21 (no verdict) | A failing `script_exec` posts its full traceback as a GUI notification | P5 observation (a); `tc-08-12-notifications.png` | open |
| N-14 | TC-06-06 (no verdict) | `query_tree_summary` says "2 objects, 2 shown" while one line carries the `-` hidden marker | P5 observation (b) | open |
| N-15 | TC-06, TC-10, TC-11 (no verdict) | GUI session render folder survives File > Exit (next start sweep removes it); H1 worker leaves an empty `FCB_TMP_session_<pid>_<token>` after a clean stdin close | P5 observations (c)(d), F-P8-6, P9 B9 | open |
| N-16 | TC-11-18 (no verdict) | MCP-created document `tc11-18` is active (title `* tc11-18`) but has no MDI tab and no tree entry | `tc-11-18-after.png`; P9 B10 | open |
| N-17 | TC-03-15 (no verdict) | Radius -5 explanation `ValueError: Invalid constraint index: 4` does not name the negative value (same in 2026-10-03-04) | F-P2-5 | open |
| N-18 | TC-04 (no verdict) | `query_mass_properties` `com` null for Compound-shaped PartDesign results | `usecases/queries.py:591-596` | open |
| N-19 | TC-12 (no verdict) | `query_mass_properties` bbox `xmax` 10.0 before Show All, 9.98 after (display or tessellation dependent) | F-P10-3 | open |
| N-20 | TC-06-03 (no verdict) | MCP render face tones inverted against the window; no Then compares tone | P0 F6; `runner/tc-06-03-default.png` | open |

### Disputed grades (lead judgement recorded)

- TC-08-04 PASS over a runner FAIL (D-lead-2): the scenario file `tc-08-04.json:487` holds `"\bFillet\b"`, a JSON backspace (U+0008), so the regex can never match. The test-case Then (`TC-08-preview-confirm-and-undo.md:169`, a non-empty explanation naming the failing check) is met: "recompute left 1 object(s) invalid: Fillet: BRep_API: command not done". Visual Then `:175` met, 0 of 1535072 px differ.
- TC-05-04 PASS: preview `diff.touched ['Body','Fillet']` vs commit `['Fillet','Body']`; the Then says "the preview predicted the same set", graded as set equality.
- TC-10-10 PASS: the manual retry returns `TIMEOUT` (dispatched; the mutation overruns 30 s by design); accepted as the "normal terminal envelope" of Then `:29`.
- TC-10-11 PASS with human intervention noted: the after-capture preselection comes from a human pointer pass 23:36:42-23:37:41, after the H1 read ended at 23:36:05.
- TC-11-05 PASS: Then heading "identical"; its verify list (same single box, whole and framed, no new object, no dialog) is met; box about 1.5 % larger from the Then's own GUI Fit All fallback.
- TC-11-14 FAIL (test-case): the added `.FCBak` is FreeCAD's own save backup inside an explicit `document_save`, not a bridge orphan under AD-25 (lead decision, lead log §5 W5).
- TC-05-17 and TC-06-09 FAIL (test-case) after a cause check: Layer-0 TNP sweep reports only objects failing `isValid()`, on 1.1.4 only `Pad` (`tnp_guard.py:380-406`, verification-design.md:94, :232); renders stay until the session-start sweep because a link may still be read (AD-25).
- TC-12-14 FAIL: verdict reads "test-case defect or product gap"; fix work treats the missing teardown line as a product gap (B-04).

### Test-case defects

Recorded per scenario in the tables (FAIL with cause "test-case defect", rule D-lead-1). Line numbers refer to `tests/uat/testcases/TC-xx-*.md` at `3025e7c`.

| Scenario(s) | Defect | Cite |
| --- | --- | --- |
| TC-01-13, TC-01-15 | Visual Then asks for a 3D view and Fit All; the scenario opens no document (Start page) | `TC-01:520-521`, `:630` |
| TC-04-16, TC-04-23 | Then accepts only equal digests or `rolled_back_via_snapshot`; product proves `rolled_back_verified` by mass properties (AD-5) | `TC-04:686`, `:1000`; `transaction.py:345-370` |
| TC-04-21 | Quoted message no longer in source; observed `BlockPad.Length is a App::PropertyLength and takes a {value, unit} quantity or a number, got [25]`; `:908` cites `features.py:1764`, now `:1767` | `TC-04:910`; `features.py:1782-1789` |
| TC-05-06 | Reproducer 1 has no `length`: `length must be a {value, unit} quantity, got None`; conditional Then does not hold | `TC-05:234`, `:246`; `features.py:1396` → `:121` |
| TC-05-17 | Then expects BROKEN owner `Fillet`; only `Pad` is invalid on 1.1.4 | `TC-05:677`; `tnp_guard.py:380-406` |
| TC-06-09 | "At most" the 3 linked files; session folder keeps all same-session renders (21, all linked) | `TC-06:474` |
| TC-08-01 | Then wants `fcb.geometry-diff/1`; contract is `/2` | `TC-08:63`; `contracts/diff.py:77` |
| TC-08-13 | Then quotes the listener message; over MCP the input schema refuses `decline` first | `mcp-tools-design.md:554` |
| TC-09-09 | Visual Then "golden model still shown" contradicts the When's `document_create` (new active empty view) | `TC-09:385`, `:404` |
| TC-09-22 | Given lists `tc-09-22-e2e_report.json` before the When creates it | `TC-09:861` |
| TC-10-03 | When takes `glob(...rpc-*.json)[0]`: picks a stale file (1 live of 60) | `TC-10:153` |
| TC-10-07 | Two Thens read `detail.data.quarantined` from `query_tree_summary`, a text-only tool | `TC-10:324-325`; `mcp_server.py:111-115` |
| TC-11-11 | Then reads `detail.message` on an `OK` preview; `detail` is null on `OK` | `TC-11:527`; `contracts/envelope.py:52` |
| TC-11-14 | Third listing must add only the export; FreeCAD's save adds a `.FCBak` that `:696` allows | `TC-11:695-696` |
| TC-11-15 | `grep` also prints `__pycache__/*.pyc` matches; pattern matches the docstring `audit_log.py:9` | `TC-11:734`, `:735` |
| TC-12-04 | Token click on a TreeItem does not select (`:691` says so on 1.1.4); `4188.7902` vs rule 9 rounding | `TC-12:237`, `:250`, `:254`, `:691` |
| TC-12-06 | `verify_state` selector `"buddy:"` matches 5 entries; popup not in the main-window capture; undo runs before the closing capture | `TC-12:350`, `:353` |
| TC-12-08 | Queries resolve by Name; object `Cube001` is a Label (Name `Box001`) | `TC-12:467`; `queries.py:188-198` |
| Scenario file TC-08-04 | `"\bFillet\b"` is a JSON backspace (finding F-1, no verdict change) | `tests/uat/scenarios/tc-08-04.json:487` |
| No verdict change | `query_mass_properties Body` → `object has no queryable shape: Body` (When only) | `TC-05:50`; `queries.py:587` |
| No verdict change | Re-import recipe `query_mass_properties Reimport` fails for `Mesh::Feature` | `TC-07:26-27`; `queries.py:584-587` |
| No verdict change | "first tree line": the object name is on the first `- [FEATURE]` line | `TC-07:51` |
| No verdict change | `tool_surface.json` has no producer; key `input_schema` vs MCP `inputSchema` | `TC-11:233` |
| No verdict change | `launch_app` cannot set `-u` profile or env; the Then's launch route cannot be used | `TC-02:368-371` |
| No verdict change | Hide step should name the tree context-menu route (Space press `delivery_failed`) | `TC-02:240` |

### Harness findings

| # | Scenario(s) | Finding | Cite |
| --- | --- | --- | --- |
| B-01 | TC-01-02, TC-09-01, TC-09-02, TC-09-22, TC-10-01 (FAIL) | Sweep scripts read the status only from `structuredContent` and the tree from a second content block; since `57d3adb` `query_tree_summary` sends one text block by design (`mcp-tools-design.md:60`). Every tree check gives `NO_STATUS`. The scripts also hard-code the `fcb` env path: as written exit 2 "fcb env python not found" | `scripts/automation/run_mcp_e2e.py:44`, `:57-58`, `:64-74`; `mcp_server.py:99-100`, `:111-115` |
| B-10 | TC-06-01 (FAIL) | AA Then reads the developer `user.cfg` (AntiAliasing 4); the temporary `-u` profile has no key, so the live window has no anti-aliasing. Later TC-06 launches pre-seeded `AntiAliasing=4` | `TC-06:119` |
| N-06 | all H1 legs | `fcb` micromamba env and micromamba absent; H1 ran on a scratchpad stand-in venv | `evidence/h1-setup.txt` |
| N-07 | TC-11-18 (BLOCKED) | Stand-in venv has no `pivy` (`include-system-site-packages=false`): H1 render "offscreen probe render failed: No module named 'pivy'" | `TC-11:883` |
| — | P0 | `cua-driver` daemon was elevated (pid 23404); restarted non-elevated (pid 5516) | P0 F3 |
| — | P0, P1, TC-12 | `invoke_menu` Show All leaves the View menu and Visibility submenu open as top-level windows not in the main-window capture; after about 25 min on one launch, Show All refused 3/3 `menu_path_unavailable` (`run.py:123`); after about 09:45 on pid 29744, `invoke_menu` stopped resolving leaves (File > Save, Windows, Show All, File > Exit); "Toggle axis cross" and "Toggle Visibility" leaves refused | P0 F5, P1 F2, F-P10-11, F-P10-13 |
| — | TC-02-05, TC-12 | Background `press_key` space and accessibility click do not select a TreeItem; background combo list-item click and token scroll do nothing; foreground delivery works | F-P2-2, F-P10-12, F-P10-16; lead log §5 W6 |
| — | TC-12-06 | Undo arrow has no UIA element; a pixel click on it runs Undo | F-P10-10 |
| — | TC-12-14 | Background `alt+f4` has no effect | F-P10-14 |
| — | TC-06-02 | Standard Views drop-down does not open under `cua-driver`; NaviCube used | F-P5-6 |
| — | TC-06 | Tree context menu only partly in UIA on re-open (8 of 27 items) | F-P5-7 |
| — | TC-02, TC-04 | Transient untitled top-level "FreeCAD" window (1000x550) at capture time, gone about 10 s later; failed STEP write raises badge 1 and a transient window | P3 B5, P6 B5 |
| — | many | Fresh `-u` profile shows the Tasks overlay over the right ~400 px of the 3D view; parts behind it are hidden; MCP fit fills 95 % including that area | F-P2-3, P3 B6 |
| — | TC-07 | `view_fit_viewport` resets the view direction to iso; extra camera-only views taken after the required fit capture | P6 B4 |
| — | TC-13-04, TC-13-06 | Runner has no keep step for the MCP render; the render in the session temp is removed at teardown; agent check used a re-run render (launch f2) | P0 F2 |
| — | P9 | `p8_proxy.ps1` start keeps the caller pipe open; a `Start-Job` proxy died with its job | P9 B11 |
| — | evidence | P0 `tc-05-03-mcp.jsonl` holds full (expired) `fcb-preview` tokens | F-P4-7 |
| — | TC-08-12 | Agent execution fault: TC-08-21 ran in the same GUI during the 900 s TTL wait; badge 0 → 2 | F-P5-5 |

## Human interventions

| When (local) | What | Effect |
| --- | --- | --- |
| 2026-10-23 21:48 | FreeCAD pid 6744 main window found minimized. Owner did not minimize it; desktop event of unknown cause. Restored with `bring_to_front` | None on verdicts (P6 B3) |
| 2026-10-23 22:24-22:28 | Physical mouse over the 3D view; preselection highlight `Face2` kept in the capture | TC-09-15 FAIL, re-run needed (P7 F3). Later captures guarded by a pointer-outside check |
| 2026-10-23 22:53-23:52 | Physical pointer moved often, partly inside the FreeCAD window (23:36:18-23:37:57 across the 3D view) | One capture affected: `tc-10-11-after.png` (TC-10-11 PASS, noted) (F-P8-5) |
| 2026-10-24 00:02-00:36 | Pointer inside the window at 00:02:36, 00:03:12, 00:04:59, 00:15:01 (preselection `Edge7` in `tc-11-15-before.png`), 00:21:20, 00:35:56. An external client (pid 15776, not the agent) sent SYN to `:8765` about 00:33 | TC-11-15 after-capture differs only in status-bar text (P9 B13) |
| 2026-10-24 00:03 | Owner accepted for this run: `script_exec` ON, mutation auto-approve ON, agent FreeCAD restarts, restart with `script_exec` OFF (temporary test profiles only) | Givens of TC-11-02, -08, -09, -17 met (D-lead-3) |
| 2026-10-24 00:45:15-08:02:22 | A maximized Explorer window (`D:\...\into-the-multiverse-asmoday`) covered FreeCAD launch C. Cause unknown. Agent ran `bring_to_front` after it was gone | Unpainted captures kept; TC-11-19 PASS (P9 B13) |
| 2026-10-24 08:15:49 | FreeCAD pid 30140 found minimized; owner did not minimize it; cause unknown. `bring_to_front` 08:16:06. Display freeze began about the same time | F-P10-4 |
| 2026-10-24 09:18:12 and about 12:20 | Display freeze ended each time by a physical mouse move (owner: "it was stuck, moving mouse fixed it") | P10 re-captures 09:50-09:57; P11/P12/G3 GUI not started |
| 2026-10-24 12:46 | The lead closed the owner's own FreeCAD (pid 21664, graceful close, owner approved) because it held `:8765` during fix work | Rewrote developer `user.cfg` (Teardown) |

Agent input, not human: foreground clicks where UIA has no element (TC-12, NaviCube views) and background Escape for open menus.


## FreeCAD launches

Every FreeCAD launch made for the gate, from `evidence/launch-log.tsv` (88 rows), plus the G3 headless scorer run. Times are 2026 local time (+07:00), `MM-DD hh:mm:ss`. Paths: `evidence\` = this run's `evidence/`, `%TEMP%` = `C:\Users\thuan\AppData\Local\Temp`. H1 rows are headless stdio hosts; their FreeCAD runs inline in the worker process.

| # | Phase | Start | PID | Profile | Env | End |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | P0 runner group 0 | 10-23 16:59:59 (runner start; first audit line 17:00:06) | 29916 | runner temporary %TEMP%\fcb-uat-run-*\user.cfg | FREECAD_BUDDY_AUDIT_LOG=runner/audit-group-0.jsonl; launch map default | after last audit line 10-23 17:04:39 |
| 2 | P0 runner group 1 | before first audit line 10-23 17:04:48 | 25344 | runner temporary %TEMP%\fcb-uat-run-*\user.cfg | FREECAD_BUDDY_AUDIT_LOG=runner/audit-group-1.jsonl FREECAD_BUDDY_AUTO_APPROVE=0 | after last audit line 10-23 17:06:09 |
| 3 | P0 runner group 2 | before first audit line 10-23 17:06:18 | 18020 | runner temporary %TEMP%\fcb-uat-run-*\user.cfg | FREECAD_BUDDY_AUDIT_LOG=runner/audit-group-2.jsonl FREECAD_BUDDY_SCRIPT_EXEC=0 | 10-23 17:06:27 (runner end, :8765 free) |
| 4 | P0 | 10-23 17:08:07 | 26672 | %TEMP%\fcb-uat-p0-f1\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\f1-audit.jsonl | 10-23 17:32:20 |
| 5 | P0 | 10-23 17:32:21 | 23968 | %TEMP%\fcb-uat-p0-f2\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\f2-audit.jsonl | 10-23 17:38:52 |
| 6 | P0 | 10-23 17:38:52 | 1420 | %TEMP%\fcb-uat-p0-f3\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\f3-audit.jsonl FREECAD_BUDDY_AUTO_APPROVE=0 | 10-23 17:51:24 |
| 7 | P0 | 10-23 17:51:25 | 1876 | %TEMP%\fcb-uat-p0-f4\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\f4-audit.jsonl | 10-23 17:59:05 |
| 8 | P0 | 10-23 17:59:06 | 21704 | %TEMP%\fcb-uat-p0-f5\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\f5-audit.jsonl FREECAD_BUDDY_SCRIPT_EXEC=0 | 10-23 18:03:47 |
| 9 | P0 | 10-23 18:03:47 | 21652 | %TEMP%\fcb-uat-p0-f6\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\f6-audit.jsonl | 10-23 19:03:28 |
| 10 | P0 | 10-23 19:04:25 | 1136 | %TEMP%\fcb-uat-p0-f7\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\f7-audit.jsonl | 10-23 19:04:43 |
| 11 | P1 | 10-23 19:10:55 | 8380 | %TEMP%\fcb-uat-p1-tc-01-01\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-01-01-audit.jsonl | 10-23 19:18:10 |
| 12 | P1 | 10-23 19:18:22 | 27576 | %TEMP%\fcb-uat-p1-tc-01-10\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-01-10-audit.jsonl | 10-23 19:20:05 |
| 13 | P1 | 10-23 19:20:23 | 6456 | %TEMP%\fcb-uat-p1-tc-01-13\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-01-13-audit.jsonl FREECAD_BUDDY_NO_AUTO_MCP=no | 10-23 19:22:01 |
| 14 | P1 | 10-23 19:22:09 | 28980 | %TEMP%\fcb-uat-p1-tc-01-14\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-01-14-audit.jsonl | 10-23 19:23:16 |
| 15 | P1 | 10-23 19:23:16 | 22308 | %TEMP%\fcb-uat-p1-tc-01-14r\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-01-14r-audit.jsonl | 10-23 19:24:59 |
| 16 | P1 | 10-23 19:25:11 | 29308 | %TEMP%\fcb-uat-p1-tc-01-15b\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-01-15b-audit.jsonl | 10-23 19:26:19 |
| 17 | P1 | 10-23 19:26:37 | 27956 | %TEMP%\fcb-uat-p1-tc-01-socket\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-01-socket-audit.jsonl | 10-23 19:29:26 |
| 18 | P1 | 10-23 19:30:43 | 29952 | %TEMP%\fcb-uat-p1-tc-01-socket2\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-01-socket2-audit.jsonl | 10-23 19:34:47 |
| 19 | P2 | 10-23 19:40:20 | 23152 | %TEMP%\fcb-uat-p2-tc-02-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-02-a-audit.jsonl | 10-23 19:56:10 |
| 20 | P2 | 10-23 19:56:15 | 29208 | %TEMP%\fcb-uat-p2-tc-02-09\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-02-09-audit.jsonl (file argument: <repo>\benchmarks\g0\golden-models\box40-hole-r5.FCStd) | 10-23 20:05:31 |
| 21 | P3 | 10-23 20:08:48 | 29440 | %TEMP%\fcb-uat-p3-tc-04-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-04-a-audit.jsonl | 10-23 20:28:51 |
| 22 | P4 | 10-23 20:36:40 | 24108 | %TEMP%\fcb-uat-p4-tc-05-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-05-a-audit.jsonl FREECAD_BUDDY_AUTO_APPROVE=0 | 10-23 20:49:29 |
| 23 | P4 | 10-23 20:49:52 | 28744 | %TEMP%\fcb-uat-p4-tc-05-wd\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-05-wd-audit.jsonl FREECAD_BUDDY_AUTO_APPROVE=0 | 10-23 20:50:16 |
| 24 | P5 | 10-23 20:55:30 | 21204 | %TEMP%\fcb-uat-p5-tc-06-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-06-a-audit.jsonl | 10-23 21:01:47 |
| 25 | P5 | 10-23 21:01:57 | 23332 | %TEMP%\fcb-uat-p5-tc-06-b\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-06-b-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-23 21:19:22 |
| 26 | P5 H1 | 10-23 21:18:18 | 24224 (H1 worker; host = p0_h1.py stdio child) | H1 venv scratchpad\h1env, inline FreeCAD with its default user data (user.cfg SHA-256 unchanged after); cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-06-11-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-06-11] | 10-23 21:18:21 |
| 27 | P5 | 10-23 21:19:27 | 30488 | %TEMP%\fcb-uat-p5-tc-08-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-08-a-audit.jsonl FREECAD_BUDDY_AUTO_APPROVE=0 | 10-23 21:41:44 |
| 28 | P5 H1 | 10-23 21:25:35 | H1 worker (p0_h1.py stdio child; pid not recorded) | H1 venv scratchpad\h1env, inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-08-05-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-08-05] | 10-23 21:25:37 |
| 29 | P5 H1 | 10-23 21:29:37 | H1 worker (p0_h1.py stdio child) | H1 venv scratchpad\h1env, inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-08-18-approve.jsonl (FREECAD_BUDDY_AUTO_APPROVE unset) (all other FREECAD_BUDDY_* removed) [TC-08-18 unset] | 10-23 21:29:39 |
| 30 | P5 H1 | 10-23 21:29:39 | H1 worker (p0_h1.py stdio child) | H1 venv scratchpad\h1env, inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-08-18-eq1-audit.jsonl FREECAD_BUDDY_AUTO_APPROVE=1 (all other FREECAD_BUDDY_* removed) [TC-08-18 eq1] | 10-23 21:29:41 |
| 31 | P5 H1 | 10-23 21:29:41 | H1 worker (p0_h1.py stdio child) | H1 venv scratchpad\h1env, inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-08-18-eq0-audit.jsonl FREECAD_BUDDY_AUTO_APPROVE=0 (all other FREECAD_BUDDY_* removed) [TC-08-18 eq0] | 10-23 21:29:43 |
| 32 | P5 H1 | 10-23 21:29:43 | H1 worker (p0_h1.py stdio child) | H1 venv scratchpad\h1env, inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-08-18-true-audit.jsonl FREECAD_BUDDY_AUTO_APPROVE=true (all other FREECAD_BUDDY_* removed) [TC-08-18 true] | 10-23 21:29:45 |
| 33 | P6 | 10-23 21:46:23 | 6744 | %TEMP%\fcb-uat-p6-tc-07-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-07-a-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-23 22:05:08 |
| 34 | P7 | 10-23 22:10:15 | 11300 | %TEMP%\fcb-uat-p7-tc-09-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-09-a-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-23 22:36:16 |
| 35 | P7 H1 | 10-23 22:14:25 | H1 worker; host = stdio child of p7_sweep.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\p7-sweep-tc-09-01\audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-01 edge sweep] | 10-23 22:14:27 |
| 36 | P7 H1 | 10-23 22:15:25 | H1 worker; host = stdio child of p7_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-09-01-probe-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-01 result-shape probe] | 10-23 22:15:27 |
| 37 | P7 H1 | 10-23 22:26:11 | H1 worker; host = stdio child of p7_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-09-15-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-15] | 10-23 22:26:13 |
| 38 | P7 H1 | 10-23 22:29:50 | H1 worker; host = stdio child of p7_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-09-19-unwritable_dir (all other FREECAD_BUDDY_* removed) [TC-09-19 unwritable] | 10-23 22:29:52 |
| 39 | P7 H1 | 10-23 22:29:52 | H1 worker; host = stdio child of p7_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-09-19-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-19 writable] | 10-23 22:29:54 |
| 40 | P7 H1 | 10-23 22:30:59 | H1 worker; host = stdio child of p7_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-09-20-append.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-20] | 10-23 22:31:01 |
| 41 | P7 H1 | 10-23 22:32:12 | H1 worker; host = stdio child of p7_sweep.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\p7-sweep-tc-09-21\audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-21 edge sweep] | 10-23 22:32:14 |
| 42 | P7 H1 | 10-23 22:32:14 | H1 worker; host = stdio child of p7_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-09-21-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-21 probe; client aborted on the agent's malformed JSON argument, no call sent] | 10-23 22:32:16 |
| 43 | P7 H1 | 10-23 22:32:29 | H1 worker; host = stdio child of p7_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-09-21-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-21 probe] | 10-23 22:32:31 |
| 44 | P7 H1 | 10-23 22:33:43 | H1 worker; host = stdio child of p7_sweep.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\p7-sweep-tc-09-22-e2e\audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-22 e2e sweep] | 10-23 22:33:45 |
| 45 | P7 H1 | 10-23 22:33:45 | H1 worker; host = stdio child of p7_sweep.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\p7-sweep-tc-09-22-edge\audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-09-22 edge sweep] | 10-23 22:33:47 |
| 46 | P8 | 10-23 22:50:01 | 11736 | %TEMP%\fcb-uat-p8-tc-10-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-10-a-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-23 23:52:52 |
| 47 | P8 H1 | 10-23 22:50:58 | H1 worker; host = stdio child of p7_sweep.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\p8-sweep-tc-10-01\audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-10-01 e2e sweep] | 10-23 22:51:00 |
| 48 | P8 H1 | 10-23 22:51:07 | H1 worker; host = stdio child of p8_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-10-01-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-10-01 six reads; discarded: the agent's client clock fault, files run1-clockfault-*] | 10-23 22:51:08 |
| 49 | P8 H1 | 10-23 22:51:32 | H1 worker; host = stdio child of p8_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-10-01-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-10-01 six reads] | 10-23 22:51:33 |
| 50 | P8 H1 | 10-23 22:53:04 | H1 worker; host = stdio child of p7_sweep.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\p8-sweep-tc-10-02\audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-10-02 e2e sweep] | 10-23 22:53:06 |
| 51 | P8 H1 | 10-23 22:53:06 | H1 worker; host = stdio child of p8_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-10-02-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-10-02 latency] | 10-23 22:53:08 |
| 52 | P8 H1 | 10-23 22:56:02 | 25472 (H1 worker; front 32780, launcher 23344; host = stdio child of p8_h1.py) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-10-05-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-10-05] | 10-23 22:57:44 |
| 53 | P8 H1 | 10-23 23:21:35 | 29652 (H1 worker; launcher 34160, front 32212, front launcher 27440; host = stdio child of p8_h1.py chain) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence (default workdir evidence\freecad-buddy-workdir) | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-10-07-audit.jsonl (all other FREECAD_BUDDY_* removed); stderr tc-10-07-server.stderr.log [TC-10-07..TC-10-11, one session] | 10-23 23:36:05 |
| 54 | P8 | 10-23 23:53:05 | 16284 | %TEMP%\fcb-uat-p8-tc-10-12\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-10-12-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-23 23:54:06 (ended by Stop-Process -Force, TC-10-12 kill) |
| 55 | P8 | 10-23 23:54:22 | 30808 | %TEMP%\fcb-uat-p8-tc-10-12r\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-10-12r-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-23 23:55:23 |
| 56 | P9 | 10-24 00:00:23 | 17944 | %TEMP%\fcb-uat-p9-tc-11-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-11-a-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-24 00:38:25 |
| 57 | P9 H1 | 10-24 00:01:24 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_SCRIPT_EXEC=0 (all other FREECAD_BUDDY_* removed) [TC-11-02 run a] | 10-24 00:01:25 |
| 58 | P9 H1 | 10-24 00:01:25 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_SCRIPT_EXEC=true (all other FREECAD_BUDDY_* removed) [TC-11-02 run b] | 10-24 00:01:27 |
| 59 | P9 H1 | 10-24 00:01:27 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_UNATTENDED=1 (all other FREECAD_BUDDY_* removed) [TC-11-02 run c] | 10-24 00:01:28 |
| 60 | P9 H1 | 10-24 00:01:29 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_UNATTENDED=1 FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1 (all other FREECAD_BUDDY_* removed) [TC-11-02 run d] | 10-24 00:01:30 |
| 61 | P9 H1 | 10-24 00:01:31 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_UNATTENDED=1 FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=true (all other FREECAD_BUDDY_* removed) [TC-11-02 run e] | 10-24 00:01:32 |
| 62 | P9 H1 | 10-24 00:01:33 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_UNATTENDED=yes (all other FREECAD_BUDDY_* removed) [TC-11-02 run f] | 10-24 00:01:34 |
| 63 | P9 H1 | 10-24 00:02:46 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-11-03-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-11-03] | 10-24 00:02:48 |
| 64 | P9 H1 | 10-24 00:05:23 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-11-04-h1-audit.jsonl (all other FREECAD_BUDDY_* removed) [TC-11-04] | 10-24 00:05:24 |
| 65 | P9 H1 | 10-24 00:06:46 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-11-08-approve.jsonl (all other FREECAD_BUDDY_* removed) [TC-11-08 unset] | 10-24 00:06:52 |
| 66 | P9 H1 | 10-24 00:06:52 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-11-08-eq0-audit.jsonl FREECAD_BUDDY_AUTO_APPROVE=0 (all other FREECAD_BUDDY_* removed) [TC-11-08 eq0] | 10-24 00:06:53 |
| 67 | P9 H1 | 10-24 00:06:54 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-11-08-true-audit.jsonl FREECAD_BUDDY_AUTO_APPROVE=true (all other FREECAD_BUDDY_* removed) [TC-11-08 true] | 10-24 00:06:55 |
| 68 | P9 H1 | 10-24 00:08:27 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence\<TAB>c-11-11-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=evidence\<TAB>c-11-11-workdir (all other FREECAD_BUDDY_* removed) [TC-11-11] -- AGENT FAULT: both paths held a TAB character (the agent's call), host ran with unusable paths; logs kept as tc-11-11-h1-fault1.* | 10-24 00:08:31 |
| 69 | P9 H1 | 10-24 00:09:50 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-11-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=evidence/tc-11-11-workdir (all other FREECAD_BUDDY_* removed) [TC-11-11] | 10-24 00:09:52 |
| 70 | P9 H1 | 10-24 00:12:03 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-12-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=evidence/tc-11-12-workdir (all other FREECAD_BUDDY_* removed) [TC-11-12 first attempt, discarded: the agent's two r=50 fillets named base Pad, not the tip Fillet, and were refused before the bracket; logs tc-11-12-h1-fault1.*, workdir tc-11-12-workdir-fault1] | 10-24 00:12:05 |
| 71 | P9 H1 | 10-24 00:12:33 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-12-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=evidence/tc-11-12-workdir (all other FREECAD_BUDDY_* removed) [TC-11-12] | 10-24 00:12:35 |
| 72 | P9 H1 | 10-24 00:15:56 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-15-append.jsonl (all other FREECAD_BUDDY_* removed) [TC-11-15 batches 1 and 2] | 10-24 00:15:58 |
| 73 | P9 H1 | 10-24 00:16:28 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-15-append.jsonl (all other FREECAD_BUDDY_* removed) [TC-11-15 concurrent writer 2] | 10-24 00:16:30 |
| 74 | P9 H1 | 10-24 00:16:28 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-15-append.jsonl (all other FREECAD_BUDDY_* removed) [TC-11-15 concurrent writer 1] | 10-24 00:16:30 |
| 75 | P9 H1 | 10-24 00:18:19 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-10-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=evidence/tc-11-10-workdir (all other FREECAD_BUDDY_* removed) [TC-11-10 H1 leg, first attempt discarded: the agent's export_step call lacked objects on a multi-object document; logs tc-11-10-h1-fault1.*] | 10-24 00:18:21 |
| 76 | P9 H1 | 10-24 00:18:35 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-10-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=evidence/tc-11-10-workdir (all other FREECAD_BUDDY_* removed) [TC-11-10 H1 leg] | 10-24 00:18:36 |
| 77 | P9 H1 | 10-24 00:20:22 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-14-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=evidence/tc-11-14-workdir (all other FREECAD_BUDDY_* removed) [TC-11-14] | 10-24 00:20:24 |
| 78 | P9 | 10-24 00:38:35 | 35504 | %TEMP%\fcb-uat-p9-tc-11-b\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-11-b-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-24 00:44:09 |
| 79 | P9 H1 | 10-24 00:41:18 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-18-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=evidence/tc-11-18-workdir (all other FREECAD_BUDDY_* removed) [TC-11-18 H1 leg] | 10-24 00:41:19 |
| 80 | P9 H1 | 10-24 00:44:22 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-19-q4-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=%APPDATA%/FreeCAD/v1-1/freecad-buddy/workdir (all other FREECAD_BUDDY_* removed) [TC-11-19 Given via product sweep (Q4 option b): tools/list only] | 10-24 00:44:23 |
| 81 | P9 | 10-24 00:44:44 | 36140 | %TEMP%\fcb-uat-p9-tc-11-c\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-11-c-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-24 08:03:42 |
| 82 | P9 H1 | 10-24 00:46:18 | H1 worker; host = stdio child of p9_h1.py (pid not recorded) | H1 venv scratchpad\h1env (h1-setup.txt), inline FreeCAD with its default user data; cwd evidence | FREECAD_BUDDY_AUDIT_LOG=evidence/tc-11-19-h1-audit.jsonl FREECAD_BUDDY_WORKDIR=evidence/tc-11-19-workdir (all other FREECAD_BUDDY_* removed) [TC-11-19 H1 sweep] | 10-24 00:46:20 |
| 83 | P10 | 10-24 08:08:07 | 30140 | %TEMP%\fcb-uat-p10-tc-12-a\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-12-a-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-24 08:32:03 |
| 84 | P10 | 10-24 08:32:07 | 8208 | %TEMP%\fcb-uat-p10-tc-12-b\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-12-b-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-24 09:04:05 |
| 85 | P10 | 10-24 09:05:40 | 29744 | %TEMP%\fcb-uat-p10-tc-12-c\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-12-c-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-24 10:38:19 |
| 86 | P10 | 10-24 10:38:45 | 29312 | %TEMP%\fcb-uat-p10-tc-12-d\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-12-d-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-24 10:39:28 |
| 87 | P10 | 10-24 10:39:33 | 33684 | %TEMP%\fcb-uat-p10-tc-12-e\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-12-e-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) (file argument: <repo>\benchmarks\g0\golden-models\box-10-20-30.FCStd) | 10-24 10:41:21 (Stop-Process -Force, TC-12-15) |
| 88 | P10 | 10-24 10:41:58 | 35252 | %TEMP%\fcb-uat-p10-tc-12-f\user.cfg | FREECAD_BUDDY_AUDIT_LOG=evidence\tc-12-f-audit.jsonl (profile pre-seeded: Preferences/View AntiAliasing=4) | 10-24 10:44:04 |
| 89 | P13 G3 headless (from lead note `p13.txt`; not in `launch-log.tsv`) | 10-24 08:44:36 | in-process FreeCAD 1.1.4 under `score_g3_replay.py` | H1 venv `scratchpad\h1env` + pyyaml 6.0.3 | `--leg 1.1.x --check --frames-check frames-reference.json`; first attempt 08:44:15-08:44:16 exit 1 (`stderr-fault1.txt`) | 10-24 08:44:55 exit 0 |

## Teardown

State at report time, 2026-10-24 13:31 (+07:00):

- FreeCAD: no `freecad.exe` or `FreeCADCmd` process. No FreeCAD started for the run is left. The last run launch (pid 35252) exited 10:44:04; the P10 end check at 10:44:14 found 0 FreeCAD and `:8765` free.
- `:8765`: no listener.
- Discovery files: the run left `rpc-*.json` of its killed or crashed FreeCADs in `%APPDATA%\FreeCAD\v1-1\freecad-buddy` (for example `rpc-16284.json` from TC-10-12 and `rpc-33684.json` from TC-12-15, not deleted by rule). 61 files in total at 13:31, the oldest from 2026-08-01 (finding N-02).
- Developer `user.cfg` (`%APPDATA%\FreeCAD\v1-1\user.cfg`): **not equal to the run baseline.** The baseline `ccf87cfe7650daa8d9f533b0e10c5dc7ae1db0c7a3aa68df3a44a04c0973832b` held through the whole run: every phase end check P0-P10 matched it, the last at 10:44:14. After the run it changed twice, neither time by a run FreeCAD (lead log §4):
  - 12:46:33: the owner's own FreeCAD (pid 21664, started without `-u`) wrote it when the lead closed that FreeCAD gracefully, with the owner's approval. New SHA-256 `39d770956016d8d51e7c931c183add34499cc597704cb270c1ff5fbec553fa73` (67547 B).
  - 12:52:29: a fix-work agent (W1b) ran `freecadcmd.exe` with no `-u`; FreeCADCmd saves its parameters on exit and rewrote the file: 67547 → 67483 B, SHA-256 `4c415695ea8006ae1515001702c2bdf31674508d9a7705c7c73c9ce987d56b75`. `system.cfg` was also rewritten (12:52:29, 12:56:02, 13:03:58). No copy of the 12:46 file exists, so that change cannot be shown or undone.
  - At 13:31 the hash is `4c415695…` (last write 13:05:05, same content). Rule for all agents since 12:52: every FreeCADCmd call uses `-u <temp>\user.cfg -s <temp>\system.cfg`.
  - Spec AC "developer `user.cfg` SHA-256 is unchanged" therefore does not hold at report time, by causes outside the run.
- `addon.log` (`%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log`): the developer log was moved aside during P1 so the run could slice its own lines. The pieces are: scratchpad `addon.log.dev-backup-before-p1` (258,549 B, lines from 2026-10-04 16:09:12 to 19:04:28, as recorded in the lead note `TODO-end.txt`), `evidence/p1-addon-L1-L2.log` (3,771 B, 19:10:56..19:19:55), `evidence/p1-addon-L4-L5.log` (5,136 B, 19:20:24..19:24:57), and the current file from 19:25:13 (250,385 B at 13:31, fix-work launches have appended to it). Owner choice: merge at run end. **Merge pending** at report time.
- `mcp-proxy.log`: the proxy rewrites it at each start (normal behaviour). Backup `mcp-proxy.log.dev-backup-before-p1` (358 B) in the scratchpad; no restore needed.
- Recovery data: the P0 `BracketPlate` recovery folder (P0 launch f6 ended by `Stop-Process -Force`) was moved to scratchpad `p1-recovery-aside` (test data, kept).
- Golden files unchanged (P4 check); `benchmarks/` hash unchanged (P6 check).
- `git`: nothing staged or committed by the run. The run added only `tests/uat/run/2026-10-23-02/`. Other working-tree changes on the branch are fix work (see After the run).

## After the run

- Fix work runs on the branch `fix/uat-gate-1-failures` (created from `main` at `3025e7c`), uncommitted at report time; each commit needs the owner's approval. Plan, decisions, incidents and results: `_bmad-output/implementation-artifacts/lead-log-2026-10-24-uat-fixes.md`.
- Fixes exist on the branch for the FAILs: product (TC-02-08 in `usecases/framing.py`; TC-08-02 in `usecases/preview.py`; TC-12-14 in `hosts/gui_addon/bootstrap.py`), harness (sweep scripts `scripts/automation/run_mcp_e2e.py`, `run_mcp_edge_cases.py`), and test-case text (TC-01, TC-03..TC-06, TC-08..TC-12, `tests/uat/scenarios/tc-08-13.json`). TC-08-12 and TC-09-15 need a re-run only. `bugs.md` gives the state per entry.
- These fixes do not change this report. Per spec D2, the fixed scenarios, the BLOCKED ones (P11 TC-13, P12 TC-14 and TC-99, the G3 GUI replay, TC-11-18, TC-12 BLOCKED) and the two re-run-only scenarios must run again into a **new run folder**. Gate 1 counts that re-run, not this folder.
- Open items with no fix on the branch are in `_bmad-output/implementation-artifacts/deferred-work.md`.
