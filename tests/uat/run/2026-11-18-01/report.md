# UAT Run 2026-11-18-01 — SMOKE run on FreeCAD 1.1.4 in the fcb-desktop container

Status: SMOKE RUN (decision 45), not a full gate run. 111 scenarios ran: 72 runner scenarios (R0 and its review), 15 TC-01 scenarios (P1) and 24 smoke scenarios (S1, S2). Result: 101 PASS, 10 FAIL, 0 BLOCKED, 0 NOT RUN. The 10 FAILs are 9 test-case defects and 1 harness limit. No product defect was found. G3 headless replay UNCHANGED (14 of 14 cases). G3 GUI replay on one control and one planted/reverted pair UNCHANGED.

**Gate 1 is NOT measured.** Decision 45 (`_bmad-output/implementation-artifacts/epic-10-decisions.md`) reduced this run to a smoke run: 144 of the 255 TC-01..TC-14 scenarios did not run, and TC-99 (Gate 2) did not run. This report does not claim Gate 1 green. Story 10.8 AC1 (`epics.md:1450-1452`, full suite) is not met as written. Also, 8 Critical scenarios that ran are FAIL (all test-case defects), so Gate 1 would be red even on the scenarios that ran.

Spec: `_bmad-output/implementation-artifacts/spec-10-8-d-uat-gate-1-run.md`. Lead log: `_bmad-output/implementation-artifacts/lead-log-2026-11-18-uat-gate-1-container.md`. Run context, and the smoke list with the reason for each scenario: `RUN-CONTEXT.md`.

Environment (decision 31): FreeCAD 1.1.4 Linux AppImage on X11 with Mesa software OpenGL in the container. This run does not measure Windows GUI behaviour. Container captures are compared only with captures from the same image.

Terms used in this report:

- **Gate 1**: pass rule of the test plan (`tests/uat/test-plan.md:457-561`): every Critical scenario PASS, High at least 95 % PASS, on the full suite.
- **Runner**: the scripted UAT runner `tests/uat/runner/run.py`. It runs the 72 scenario files of `tests/uat/scenarios/` with no LLM. A scenario that it cannot fully grade is ESCALATE, and an agent then reads its capture (test-plan §9 review).
- **Agent-driven scenario**: a scenario with no scenario file. A phase agent runs it through MCP and `cua-driver` (the desktop automation tool) and reads the window capture.
- **Smoke set (a)**: one Critical scenario per fix area that FAILED in run 2026-10-23-02 and was fixed in Epic 10. **Smoke set (b)**: one core Critical scenario per test case (TC) that set (a) does not reach.
- **H1**: the headless stdio host (front process plus worker). **H2**: the FreeCAD GUI with the addon, MCP over HTTP through the proxy that the addon spawns (host relay `127.0.0.1:18765`).
- **Cause classes** (`uat-run-practices.md` §7): `product defect`; `test-case defect` (the test case is wrong, not the product); `harness limit` (the test environment cannot show the Then); `agent execution fault` (the agent's own mistake; one re-run from the Given, both runs kept).
- **G3 replay**: replay of the corrupted-plan suite (`benchmarks/g3/fault-injection/`). The 10 planted defects must be DETECTED, and their 10 reverted builds and the 4 controls must pass clean.

## Counts

| Set | Scenarios | PASS | FAIL | Critical PASS / FAIL | High PASS / FAIL | Medium PASS / FAIL |
| --- | --- | --- | --- | --- | --- | --- |
| Runner set (R0 and review), TC-02..TC-14 | 72 | 64 | 8 | 46 / 6 | 17 / 1 | 1 / 1 |
| P1, TC-01 (agent-driven) | 15 | 15 | 0 | 8 / 0 | 6 / 0 | 1 / 0 |
| Smoke set (a), fixed-failure areas | 17 | 17 | 0 | 17 / 0 | — | — |
| Smoke set (b), core scenario per TC | 7 | 5 | 2 | 5 / 2 | — | — |
| **Total** | **111** | **101** | **10** | **76 / 8** | **23 / 1** | **2 / 1** |
| Not run (decision 45) | 144 of TC-01..TC-14; 5 of TC-99 | — | — | — | — | — |

FAILs by cause class: test-case defect 9 (TC-02-15, TC-02-17, TC-03-03, TC-03-20, TC-07-03, TC-07-05, TC-09-12, TC-13-04, TC-13-10); harness limit 1 (TC-02-13). Product defect 0.

Fix areas of run 2026-10-23-02 that this run confirms: B-01 sweep scripts (TC-01-02, TC-09-01; S0 sweeps 29/29 and 14/14), B-03 preview notification (TC-08-02), B-04 teardown log line (TC-12-14), W4 test-case fixes (TC-04-16, TC-04-21, TC-05-06, TC-05-17, TC-06-09, TC-08-01), B-10 anti-aliasing profile (TC-06-01), W5 (TC-10-03, TC-11-11, TC-11-14), W3 (TC-10-07), W6 (TC-12-04, TC-12-05, TC-12-06), TC-01-13 and TC-01-15 visual Then, Story 10.6c proxy identity (TC-01-14, TC-01-15), TC-08-13 (runner). Not checked again: TC-02-08 framing (decision 34, outside the smoke scope); TC-04-23, TC-09-02, TC-09-22, TC-10-01 (same areas as checked scenarios); TC-11-15.

## Build banner

| Item | Value |
| --- | --- |
| Branch | `story/10-8-d-gate-1-run` |
| Commit | `2db195ceaee52796280ab1cb3c8f47d88f8f0bc4`; at run start only leader files were uncommitted (`evidence/s0-git-status.txt`) |
| Addon wheel SHA-256 | `d40a271bf1a9c8e8f5b84bb6a601ecea858a6bc6ea77ae8afb1f7b26a5e3fe8c` (`evidence/addon-wheel-sha256.txt`) |
| Image id | `sha256:ccccd43b5b3df8ee1eaaf547643570184c90099415298be0b98bd6cc103dddc4`; container recreated at 2026-11-18T19:30+0700 (clean profile) |
| FreeCAD | 1.1.4 Linux AppImage in container `fcb-desktop` (`H1 ok 1.1.4`) |
| Developer `user.cfg` SHA-256 | before: `b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a0` (decision 8). Changed at 21:04:27 by the owner's own host FreeCAD (decision 46, finding R-1) to `63fa48cfe55eb515b30113b21e4732da70a1aa0b877c51dab3b8a4e979b9bd2a`, the accepted baseline. Equal to that baseline at every later phase start and end, and at run end |
| Run start | 2026-11-18T19:29:00+0700 |

## Harness gate (S0)

| Check | Result | Evidence |
| --- | --- | --- |
| H1 host | `H1 ok 1.1.4` | `evidence/s0-h1.txt` |
| `run_mcp_e2e.py` | exit 0, 29/29 | `evidence/s0-e2e.log`, `evidence/e2e_report.json` |
| `run_mcp_edge_cases.py` | exit 0, 14/14 | `evidence/s0-edge.log`, `evidence/edge_report.json` |
| Probe fault set | detected 5/5, false alarms 0/2 | `evidence/s0-probe-faults.log` |
| Pixel fault set | detected 4/4, false alarms 0/2 | `evidence/s0-pixel-faults.log` |
| G3 GUI scripts | git blob ids equal to `tests/uat/g3-gui/` (`a2b43c52...`, `eb67d351...`) | `evidence/g3-gui-script-blob-ids.txt` |

## Runner runs

| Run | Folder | Seed | Result |
| --- | --- | --- | --- |
| R0 | `runner/` | `423616651`, `sample_seed_source: drawn` | 2026-11-18 19:33-19:39 +0700, exit 0. 72 scenarios: 5 PASS, 0 FAIL, 67 ESCALATE, 0 `not_run`. All 3 launch groups started (default 56, `AUTO_APPROVE=0` 15, `SCRIPT_EXEC=0` 1). `git_dirty` true (leader files only). No `runner-rerun-<n>` folder |

## Execution notes

- Phases: S0; R0; the R0 review in six parts (R0a-1 TC-02, R0a-2 TC-03, R0a-3 TC-04, R0b-1 TC-05..TC-07, R0b-2 TC-08, R0b-3 TC-09 and TC-11..TC-14); P1 (TC-01) and P1-R; the smoke phases S1 (11) and S2 (13); G3. Every phase agent ran on model `sonnet`, one at a time. Phase reports: `lead-notes/phase-<id>-report.md`. Lead checks: `lead-notes/lead-grades.md`.
- Scope change: the run started as a full gate run. Decision 45 (about 21:00) reduced it to a smoke run. The first run lead read the change only after P1 (decision 47). R0b-2, R0b-3 and P1, done before the stop, stay in this report.
- Lead regrades: TC-07-03 PASS to FAIL (first lead). TC-03-03 and TC-03-20 PASS to FAIL (second lead), so that one rule holds across the run: a visual Then is graded in the state that the scenario defines, with no added GUI step (`lead-notes/RULES.md` watch items). Those passes rested on an added Sketcher edit-mode step or Isometric press. TC-13-10 is the same class.
- Re-runs from the Given after an agent execution fault (both runs kept): TC-01-10 (P1-R; run 1 checked a hand-started proxy), TC-02-15 (R0a-1), TC-08-01 (S1), TC-10-07 and TC-11-11 (S2, errors in the agent's own client scripts).
- Lead judgements (`lead-grades.md`): TC-10-07 visual Then compared with `tc-09-01-after.png`, because the Given capture was not taken (same window, document and camera, just before the When; byte-identical to the after capture). TC-11-14 swept through H2 only (the When names no host). TC-05-06 CONDITIONAL PASS: both reproducers returned `rolled_back_verified`, and the test case records this as not exercised.
- Fixtures: many Givens state a model with no create steps. Phase agents built them with typed tools or one `script_exec` (S1 F4, S2 F3).
- The `cua-driver-docker` MCP session was dead in S1 and S2. GUI steps used the CLI wrapper `scripts/automation/fcb_cua.sh`.
- The container 3D view can repaint 15-20 s after a GUI Fit All press (R0a-1 F2). Agents waited and took two captures. The Tasks overlay at the right of the 3D view covers part of some models. Each capture is judged on the visible pixels, and the lead rows name what is covered.

## Scenario verdicts

Notes are cut to about 320 characters. The full note is in the phase report named at the end of each note. Set: `runner` = R0 scenario file; `P1` = TC-01 phase; `smoke-a`, `smoke-b` = smoke sets.

### TC-01

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-01-01 | Critical | P1 | PASS | evidence/tc-01-01-after.png | FreeCAD 1.1.4 (live version). Listener on 127.0.0.1:43209; "spawned MCP proxy (pid 13061) -> http://127.0.0.1:8765/mcp"; LISTEN pid 13061 equals spawn pid; cmdline venv/bin/python -m freecad_buddy.hosts.main serve --mode rpc --transport http, only serve process; query_capabilities OK; 0 "failed to spawn". Show All ... (`phase-P1-report.md`) |
| TC-01-02 | Critical | P1 | PASS | evidence/tc-01-02-{before,after}.png, tc-01-02-e2e_report.json, tc-01-02-server.stderr.log | Sweep exit 0 (29/29 checks); all_passed True; query_mass_properties:box-10-20-30 volume=6000.0; all 10 verify_export_step/stl entries OK; stderr grep for access violation/segfault/swig director empty; query_capabilities OK after sweep. The sweep script writes its files to _automation/ (script behaviour); I copied them ... (`phase-P1-report.md`) |
| TC-01-03 | Critical | P1 | PASS | evidence/tc-01-03-after.png | Client URL printed: http://127.0.0.1:18765/mcp (container proxy via relay). Count 46 (script_exec on, default posture; recorded for later test cases). No export_self_read_* names; script_exec one line; family counts document_ 7, query_ 8, verify_ 6, export_ 3, sketch_ 8, feature_ 11, preview_ 1, view_ 1, script_ 1; 13 ... (`phase-P1-report.md`) |
| TC-01-04 | Critical | P1 | PASS | evidence/tc-01-04-after.png, tc-01-04-rpc_hello.txt | Banner keys exactly the nine named; freecad_version 1.1.4 = title "* box-10-20-30 - FreeCAD 1.1.4" = rpc-12978.json "freecad_version": "1.1.4"; element_map_available true; serializer exportBinary; render gui_constructed; exec_enabled true; sketcher_available and partdesign_available true. Env FREECAD_BUDDY_SCRIPT_EXEC ... (`phase-P1-report.md`) |
| TC-01-05 | High | P1 | PASS | evidence/tc-01-05-after.png, tc-01-05-budgets.txt | Host dist/addon __init__.py sha256 equals installed (ca78f505...4369163). 45 rows (tool_specs leaves out script_exec): budgets 30.0 x11, 60.0 x4, 120.0 x29, 180.0 x1; only preview_dry_run at 180; 30 s set is the 11 named; 60 s set is document_open, query_screenshot, verify_shape, verify_sketch; all ... (`phase-P1-report.md`) |
| TC-01-06 | Critical | P1 | PASS | evidence/tc-01-06-{before,after}.png, tc-01-06-reply.txt | Reply frame: {"jsonrpc": "2.0", "id": 1, "error": {"code": -32004, "message": "contract version unsupported", "data": {"supported": ["1"]}}}; no result, no capabilities, no freecad_version; second readline '' (socket closed); query_capabilities OK after. Both captures read: identical (same md5), one box solid, whole, ... (`phase-P1-report.md`) |
| TC-01-07 | Critical | P1 | PASS | evidence/tc-01-07-{before,after}.png, tc-01-07-replies.txt | Both attempts (wrong token + version 99; token omitted + version 99) returned {"jsonrpc": "2.0", "id": 7, "error": {"code": -32000, "message": "auth failed"}}: auth before version, no capabilities/freecad_version/supported. addon.log holds exactly 2 lines "freecad_buddy.rpc_listener: token mismatch; closing" ... (`phase-P1-report.md`) |
| TC-01-08 | Critical | P1 | PASS | evidence/tc-01-08-{before,after}.png, tc-01-08-replies.txt | Attempt 1 frame1 {"jsonrpc": "2.0", "id": 3, "error": {"code": -32002, "message": "handshake required"}}, frame2 ''; no result or structured_content. Attempt 2 (not json) frame1 {"jsonrpc": "2.0", "id": null, "error": {"code": -32002, "message": "handshake required"}}, frame2 ''. addon.log has 1 line "first frame was ... (`phase-P1-report.md`) |
| TC-01-09 | High | P1 | PASS | evidence/tc-01-09-after.png, tc-01-09-discovery.json | Path $FCB_USER_DIR/freecad-buddy/rpc-12978.json; ls $FCB_USER_DIR/../Mod exit 2 (No such file or directory). Keys exactly schema, pid, host, port, token, contract_version, freecad_version, started. pid 12978 equals list_windows pid; ps shows "12978 freecad". host 127.0.0.1 port 43209, ss LISTEN owned by freecad pid ... (`phase-P1-report.md`) |
| TC-01-10 | High | P1 | PASS | evidence/tc-01-10-before.png, tc-01-10-after.png (not created: capture of dead pid refused) | Final verdict from the P1-R re-run (fresh addon-spawned proxy, all 7 Thens met, phase-P1-R-report.md); run 1 was an agent execution fault (hand-started proxy). Before: GUI Fit All toolbar button pressed (route accessibility), capture read: box whole, status bar 66.37 mm x 37.42 mm. document_list showed no transient doc; I closed the document through MCP before the quit so no save dialog could appear. Quit by pressing the Exit leaf. pgrep after quit: nothing, exit 1. ... (`phase-P1-report.md`) |
| TC-01-11 | High | P1 | PASS | evidence/tc-01-11-{before,after}.png, tc-01-11-attach.txt | Given: 5 rpc-*.json (15171 live plus 2077, 3584, 4468, 5328) vs 1 FreeCAD process. Picked rpc-2077.json (port 40709). `ps -p 2077` prints nothing, exit 1. Script printed "refused: ConnectionRefusedError [Errno 111] Connection refused" and "elapsed 0.06", no reply line. File rpc-2077.json still present. ... (`phase-P1-report.md`) |
| TC-01-12 | High | P1 | PASS | evidence/tc-01-12-{before,after}.png | Old proxy pid 15272 killed (only it); :8765 free (ss exit 1); restarted by hand pid 15551 with FREECAD_BUDDY_AUTO_APPROVE=1 and FREECAD_BUDDY_SCRIPT_EXEC=1 (values of the last operator settings line); ps shows "15171 freecad"; rpc-15171.json sha256 unchanged (same port and token); ss LISTEN on 15551; ... (`phase-P1-report.md`) |
| TC-01-13 | Medium | P1 | PASS | evidence/tc-01-13-after.png, tc-01-13-cli1.err, tc-01-13-cli2.err | Launch with FREECAD_BUDDY_NO_AUTO_MCP=no (pid 15726). addon.log: "freecad-buddy RPC listener started on 127.0.0.1:34483" and "FREECAD_BUDDY_NO_AUTO_MCP set; not auto-starting the MCP proxy"; rpc-15726.json exists; :8765 not bound (ss exit 1) before and after the CLI commands. CLI 1 stderr "--mode rpc requires ... (`phase-P1-report.md`) |
| TC-01-14 | High | P1 | PASS | evidence/tc-01-14-{before,after}.png, tc-01-14-connect.txt, tc-01-14-old-discovery.json, tc-01-14-new-discovery.json | Pre-kill: FreeCAD pid 16092, RPC port 37837, proxy pid 16176 (addon-spawned, from the LISTEN row). Given step added by me: FreeCAD starts on the Start page where Fit All is disabled, so I opened the golden model through MCP, Show All, then pressed the Fit All toolbar button (route accessibility). Before capture read: ... (`phase-P1-report.md`) |
| TC-01-15 | Critical | P1 | PASS | evidence/tc-01-15-{before,probed,after}.png, tc-01-15-healthz.txt, tc-01-15-addon.log.txt | Part 1 (pid 16458): `curl -s -i http://127.0.0.1:8765/healthz` in container: "HTTP/1.1 200 OK", content-type application/json, body {"service":"freecad-buddy-mcp-proxy","freecad_pid":16458,"session_id":"e91cf8db6a28c056"}; token (rpc-16458.json) occurs 0 times in the response; no path or env value. Before and probed ... (`phase-P1-report.md`) |

### TC-02

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-02-01 | Critical | runner | PASS | evidence/r0a1-TC-02-01-after.png | doc != name: `fcb-doc:jqmVt5HXuCJCwAA4uy9yXQ` vs `uat_roundtrip`. Save file 1756 bytes (ls -l), still present after close. Bare save INVALID_INPUT as written, list transient true/false as written, close then 0 docs. view_fit_viewport on the empty reopened doc returned SPEC_FAILED view_fit.nothing_to_frame, so fit was ... (`phase-R0a-1-report.md`) |
| TC-02-02 | Critical | runner | PASS | runner/captures/TC-02-02.png | agent_check JSON-safe properties: query_object OK, name Box, type Part::Feature, error null, 8 properties, all values JSON strings or scalars. Two are strings holding a pointer text: `Shape` = `<Solid object at 0x55cf9d8b3060>`, `ShapeMaterial` = `<Material at 0x55cf9dc9eff0>`. The Then allows "a stringified value", ... (`phase-R0a-1-report.md`) |
| TC-02-03 | Critical | runner | PASS | runner/captures/TC-02-03.png | Re-run by MCP. Target absent before save (ls). Save wrote 3728 bytes (ls -l). Golden file size and mtime before and after: `1923 1784644677` both. Reopen handle `fcb-doc:iwHhJkfHmtYfeso5Fs2i8Q` differs from first `fcb-doc:1CCrjBrhpD-qiSC5fgq47Q`. Save-as handle equal to open handle. Volume 1570.8 from R0 step (within ... (`phase-R0a-1-report.md`) |
| TC-02-04 | Critical | runner | PASS | runner/captures/TC-02-04.png, evidence/r0a1-TC-02-04-rows.png | GUI action: pixel click (72,175) on the sphere-r10 tree row, foreground; `script_exec` `App.ActiveDocument.Name` returned `'sphere_r10'`, so B active. Then query A tree: `- [FEATURE] Box`; query B tree: `- [FEATURE] Sphere`; Sphere in A and Box in B both INVALID_INPUT `unknown object: Sphere` / `unknown object: Box`; ... (`phase-R0a-1-report.md`) |
| TC-02-06 | Critical | runner | PASS | evidence/r0a1-TC-02-06-before.png, -after.png, runner/captures/TC-02-06.png | agent_check before capture taken in a re-run by MCP (same build steps as scenario file): healthy volume 1000.0. Typed break returned RECOMPUTE_ERROR `Pad: Cannot create a pad with a total length of zero.`, rolled_back true. script_exec break then recompute: RECOMPUTE_ERROR errors `Pad: ['Touched','Invalid']`. Restore ... (`phase-R0a-1-report.md`) |
| TC-02-09 | Critical | smoke-b | PASS | evidence/tc-02-09-after.png, tc-02-09-gui.png | Given: document_list 0 open. FreeCAD restarted with the file (pid 18277). Then: verify_state satisfied (TreeItem box40-hole-r5); list_windows title " box40-hole-r5 - FreeCAD 1.1.4" after pressing Next (doc tab sat behind Start); document_list "1 open document(s): box40-hole-r5.", doc fcb-doc:9NqYRj14jCeE-W36k3P3hQ, ... (`phase-S1-report.md`) |
| TC-02-12 | High | runner | PASS | evidence/r0a1-TC-02-12-before.png, -after.png | Given total_edges: 2 (`Fusion->Box`, `Fusion->Cylinder`). Fit All by toolbar token, route accessibility. max_edges 1: `edges` length 1 = `Fusion->Box` (equals edges[0]), returned_edges 1, truncated true, total_edges 2. max_edges 0, -5, 1.5 refused by the MCP schema layer: `Input validation error: 0 is less than the ... (`phase-R0a-1-report.md`) |
| TC-02-13 | Medium | runner | FAIL (harness limit) | evidence/r0a1-TC-02-13-unicode.png, runner/captures/TC-02-13.png | Failed Then (visual): "🔧 emoji drawn as real glyphs ... not `?` marks, empty boxes". Raw: the picture shows an empty box where U+1F527 is. Cause check: `docker exec -u cua fcb-desktop sh -c 'fc-list ":charset=1f527"'` printed nothing, so the container has no font with that glyph. The bridge label is intact: ... (`phase-R0a-1-report.md`) |
| TC-02-15 | Critical | runner | FAIL (test-case defect) | evidence/r0a1-TC-02-15-run3-before.png, -run3-after.png (also run1 and run2 files kept) | Failed Then: "each response carries `schema` `fcb.result-envelope/1` and `detail.code` `INVALID_INPUT`". Raw (second client, mcp python client on :18765, request `query_tree_summary {doc:"fcb-doc:not-a-real-handle"}`): isError true, structuredContent null, content `['INVALID_INPUT: unknown or stale document handle: ... (`phase-R0a-1-report.md`) |
| TC-02-16 | Critical | runner | PASS | evidence/r0a1-TC-02-16-after-d.png (after.png, -b, -c are earlier captures of the same run taken before the view repainted) | First close OK `closed: true`, name `sphere_r10`. Second close INVALID_INPUT `unknown or stale document handle: fcb-doc:dGCdTWPR4tCZ0T0prO1tZg` (the exact handle). query_tree_summary on released handle: `INVALID_INPUT: unknown or stale document handle: fcb-doc:dGCdTWPR4tCZ0T0prO1tZg`. list `0 open document(s).`. ... (`phase-R0a-1-report.md`) |
| TC-02-17 | Critical | runner | FAIL (test-case defect) | evidence/r0a1-TC-02-17-before.png, -after.png | Failed Then: "both tails read `Invalid project file <path>: ios_base::failbit set: iostream stream error`". Raw (raw mcp client, `document_open {path: ".../tc-02-17-not-fcstd.txt"}`): INVALID_INPUT `document_open failed for '/repo/.../tc-02-17-not-fcstd.txt': Invalid project file /repo/.../tc-02-17-not-fcstd.txt: ... (`phase-R0a-1-report.md`) |

### TC-03

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-03-02 | Critical | runner | PASS | evidence/r0a2-TC-03-02-after.png | Re-run by replay of scenario steps by MCP. view_fit_viewport returned SPEC_FAILED (no shape-bearing object), so fit was GUI Fit All toolbar token (the agent_check allows it). Steps 0-7 all expect checks met on re-run (create, body, sketch OK rolled_back false, tree child regex, Tip None, verify dof 0, Orphan ... (`phase-R0a-2-report.md`) |
| TC-03-03 | High | runner | FAIL (test-case defect) | evidence/r0a2-TC-03-03-after.png, -iso.png | Lead regrade PASS to FAIL: the visual Then on elevation is not visible in the top-down edit view the scenario defines; the pass rested on an added Isometric press (lead-grades.md). Re-run by replay: all 25 expect checks OK on re-run (face Plane z 5, placement z {5,mm}, both-refusal message exact, curved `Face1 on Cylinder is not a planar face`, geometric refusal, fit OK). Note: the top-down edit view alone cannot show elevation, the isometric press in edit mode did. Task panel hides the right ... (`phase-R0a-2-report.md`) |
| TC-03-04 | Critical | smoke-b | PASS | evidence/tc-03-04-after.png | Given built by me (test case gives no create step): document_create tc-03-04, sketch_create PlateProfile XY; query_sketch_info geometry=[]. sketch_add_geometry status OK, rolled_back false, post_verify fully_constrained true and passed true, sketch_state readable true dof 0 fully_constrained true. verify_sketch OK dof ... (`phase-S1-report.md`) |
| TC-03-05 | Critical | runner | PASS | evidence/r0a2-TC-03-05-after.png | Re-run by replay: 28 expect checks OK (types LineSegment, Circle, ArcOfCircle, Point; geo_ids [0..3]; dof 0; constraint_count 13; redundant []; ellipse, too-long, too-short, bare-radius refused by schema text). Visual: the Tasks panel overlays the right part of the view, so the arc is partly hidden by the panel, not ... (`phase-R0a-2-report.md`) |
| TC-03-06 | Critical | runner | PASS | evidence/r0a2-TC-03-06-after.png (clipped, before GUI fit), -after-fit.png (graded) | Re-run by replay: all expect checks OK (8 calls OK, ids, 29 constraints, 3 schema refusals, count still 29). Glyph and label count: about 25 marks visible (dimension labels 60, 2.5, 5, 45, 20 x3, 40 x3, 50, 70, 30, 15, 10 and glyphs =, //, perpendicular, tangent-radius pairs); the labels in the lower middle overlap ... (`phase-R0a-2-report.md`) |
| TC-03-07 | Critical | runner | PASS | evidence/r0a2-TC-03-07-before.png, -after.png, -edit.png | Re-run by replay: all expect checks OK (datum, recompute, volume 5000 band, verify_shape OK, value+sense INVALID_INPUT, read-only refusal). The before capture was taken by me in the re-run (agent_check GUI action Given). Edit view also shows the grey reference label `TabDepthRef 40 mm` overlapping the 40 mm driving ... (`phase-R0a-2-report.md`) |
| TC-03-08 | High | runner | PASS | evidence/r0a2-TC-03-08-before.png, -mid.png, -after.png | Re-run by replay with captures at three points. All expect checks OK on the full step list (flags false/true/false, dof 0 after each toggle, `[4, 4]` refused `is listed twice; a double toggle is a no-op`, `[99]` refused `is outside the sketch (0..4)`, fit OK). Intermediate state looked different (dashed blue) as the ... (`phase-R0a-2-report.md`) |
| TC-03-10 | High | runner | PASS | evidence/r0a2-TC-03-10-before.png, -after.png | Re-run by replay, no expect check FAILED (remove geo 3: SPEC_FAILED, rolled back; info reads 4 geometry and 11 constraints; side sketch cascade OK; `[7]` refused; `[]` refused by schema `[] should be non-empty`). Before capture taken in my re-run before the removal. (`phase-R0a-2-report.md`) |
| TC-03-11 | High | runner | PASS | evidence/r0a2-TC-03-11-before.png, -after.png | Re-run by replay: all expect checks OK (id branch 12 -> 12 constraints; name branch `SpareWidth` -> 11; dof 0 after each; id 0 refused `0 is less than the minimum of 1`; unknown name INVALID_INPUT; `{id: 3}` refused by anyOf schema). The `SpareWidth` text is unreadable in the before image because the reference labels ... (`phase-R0a-2-report.md`) |
| TC-03-12 | Critical | runner | PASS | evidence/r0a2-TC-03-12-before.png, -after.png | Re-run by replay: all expect checks OK (redundant Horizontal -> RECOMPUTE_ERROR, rolled back, 11 constraints, verify OK, recompute OK). Watchdog after TC-03-11: exit 0. A status bar badge `1` (probably FreeCAD's notification count for the recompute error) appeared in the after capture; it is not a dialog. (`phase-R0a-2-report.md`) |
| TC-03-13 | Critical | runner | PASS | evidence/r0a2-TC-03-13-before.png, -after.png | Re-run by replay, all expect checks OK. agent_check items: tnp_audit raw `{"status":"CLEAN","element_map_version":"15.70200.5","counts":{"PASS":2},"findings":[]}` so counts.PASS >= 1 met; whole-document `query_dependencies {doc}` raw edges include `{"from":"BossProfile","to":"PlatePad"}` (13 edges, not truncated); ... (`phase-R0a-2-report.md`) |
| TC-03-14 | High | runner | PASS | evidence/r0a2-TC-03-14-after.png | Re-run by replay: all expect checks OK (axes call OK, dof 0, redundant [], ids 11 and 12, AxisFirst OK dof 0, `-9` refused INVALID_INPUT). Fit was the GUI Fit All in edit mode (MCP fit step skipped). (`phase-R0a-2-report.md`) |
| TC-03-16 | Critical | runner | PASS | evidence/r0a2-TC-03-16-before.png, -after.png | Re-run by replay. Conflict call RECOMPUTE_ERROR, explanation raw `recompute left 1 object(s) invalid: PlateProfile: Over-constrained sketch (`phase-R0a-2-report.md`) |
| TC-03-18 | Critical | runner | PASS | evidence/r0a2-TC-03-18-before.png, -after.png | Re-run by replay: all expect checks OK. Raw: deg datum on Distance INVALID_INPUT `Distance value unit must be one of ['mm'], got 'deg'` (names the unit); bare radius `Input validation error: 2.5 is not of type 'object'`; missing value `'value' is a required property`; deg radius `'deg' is not one of ['mm']`; extra key ... (`phase-R0a-2-report.md`) |
| TC-03-20 | Critical | runner | FAIL (test-case defect) | evidence/r0a2-TC-03-20-before.png, -after.png, -iso.png | Lead regrade PASS to FAIL: "as thin as before" is not visible in the top-down edit view; the pass rested on an added Isometric press (lead-grades.md). Re-run by replay, all expect checks OK. agent_check items: REPOINTED at findings.0 raw `{"owner":"BossProfile","prop":"AttachmentSupport",...,"verdict":"REPOINTED"}`, explanation `TNP audit flagged 1 reference(s): BossProfile.AttachmentSupport REPOINTED`, move call SPEC_FAILED; plate volume after rollback `12000.0`; ... (`phase-R0a-2-report.md`) |
| TC-03-21 | High | runner | PASS | evidence/r0a2-TC-03-21-before.png, -after.png, runner/captures/TC-03-21.png | Re-run by replay. All four calls refused at the schema layer as text (`Additional properties are not allowed ('visible'|'color'|'weight'|'hint' was unexpected)`), no status or mutation block. info geometry (4) and constraints (11) after the calls equal the Given reads (compared directly; my helper cannot resolve `$` ... (`phase-R0a-2-report.md`) |

### TC-04

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-04-01 | Critical | runner | PASS | runner/captures/TC-04-01.png | Scripted checks cover the non-visual Thens (no findings). Visual Then judged on the capture. (`phase-R0a-3-report.md`) |
| TC-04-02 | Critical | runner | PASS | runner/captures/TC-04-02.png | Pixel check box fraction 0.94 not touching edge. Tasks panel overlays a corner. (`phase-R0a-3-report.md`) |
| TC-04-03 | Critical | runner | PASS | evidence/r0a3-TC-04-03-axis.png, runner/captures/TC-04-03.png | agent_check axis cross: toggled by token (View > Toggle Axis Cross), origin at mid-height. Toggled off after. (`phase-R0a-3-report.md`) |
| TC-04-08 | High | runner | PASS (HUMAN?) | runner/captures/TC-04-08.png, evidence/r0a3-TC-04-08-hole-zoom.png | agent_check counterbore shape: two concentric rims in the zoom, low resolution. (`phase-R0a-3-report.md`) |
| TC-04-09 | Critical | runner | PASS | runner/captures/TC-04-09.png | agent_check comparison op: script_exec on PlatePad edges gives 5.0 mm, Z length 5.0 for edges 1,2,5,8 only. OtherBody ignored for the visual Then. (`phase-R0a-3-report.md`) |
| TC-04-11 | Critical | runner | PASS | runner/captures/TC-04-11.png | agent_check hole count: 2 on plate, 6 on disc. (`phase-R0a-3-report.md`) |
| TC-04-12 | Critical | runner | PASS | runner/captures/TC-04-12.png | All visual Thens met; scripted checks stand for the rest. (`phase-R0a-3-report.md`) |
| TC-04-14 | Critical | runner | PASS | evidence/r0a3-TC-04-14-before.png, -after.png (unfit, not used), -after-fit.png | Re-run by script replay from the Given: edit committed OK. The first after capture was before a fit; the verdict rests on after-fit. (`phase-R0a-3-report.md`) |
| TC-04-16 | Critical | smoke-a | PASS | evidence/tc-04-16-before.png, tc-04-16-after.png | Given built by me with typed tools (body PlateBody, sketch PlateSketch 60x40, pad PlatePad 5 mm): volume 12000.0; snapshot list [] ; topology oracle Edge3 = 60.0 mm at z 0 (bottom edge). Then: feature_fillet 20 mm on Edge3 returned status RECOMPUTE_ERROR, mutation.rolled_back true, rollback_proven ... (`phase-S1-report.md`) |
| TC-04-18 | High | runner | PASS | evidence/r0a3-TC-04-18-before.png, runner/captures/TC-04-18.png | Hole count one in both. (`phase-R0a-3-report.md`) |
| TC-04-20 | Medium | runner | PASS | runner/captures/TC-04-20.png, evidence/r0a3-TC-04-20-fillet-zoom.png, -chamfer-zoom.png | Round and bevel on different edges. (`phase-R0a-3-report.md`) |
| TC-04-21 | Critical | smoke-a | PASS | evidence/tc-04-21-before.png, tc-04-21-after.png | Given built by me (body BlockBody, sketch BlockSketch 20x30, pad BlockPad 10 mm): volume 6000.0; snapshot list []. Step 1 INVALID_INPUT "BlockPad has no property named 'Thickness'"; step 2 INVALID_INPUT "BlockPad.Shape is a Part::PropertyPartShape, which feature_set_parameters cannot write"; step 3 INVALID_INPUT ... (`phase-S1-report.md`) |

### TC-05

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-05-03 | Critical | runner | PASS | evidence/r0b1-tc-05-03-before.png, -after.png, -after-b.png, runner/captures/TC-05-03.png | agent_check Given before capture: taken after `view_fit_viewport` OK, flat rhombus outline x 305..1521, y 152..853 (the Tasks panel hides a short stretch of the upper-right edge, the outline continues on both sides). After capture (20 s, then a second 4 s later): identical picture, no solid. Scripted Thens from R0 ... (`phase-R0b-1-report.md`) |
| TC-05-06 | Critical | smoke-a | PASS (CONDITIONAL: escalation not exercised) | evidence/tc-05-06-before.png, tc-05-06-after.png | Launch 19434 with FREECAD_BUDDY_AUTO_APPROVE=0 (operator settings line `FREECAD_BUDDY_AUTO_APPROVE='0' (env)`; 0 "auto-approve ENABLED" lines after it). Order change: run after TC-07-05 to group launches. Given built by me with one script_exec (no typed-tool recipe in the test case): Body, Sketch 60x40, Pad 30, Fillet ... (`phase-S1-report.md`) |
| TC-05-08 | Critical | runner | PASS | evidence/r0b1-tc-05-08-before.png, -after.png, -after-b.png, r0b1-tc-05-08-snap-after-snapshot.png, runner/captures/TC-05-08.png | agent_check before capture: whole prism, same as after. I ran the scenario twice (second run only to capture the window right after the snapshot-restore failure, before the WITH-undo repeat). All captures: same prism, same size (x 670..1157, y 152..853), sharp edges, one tab TC0508, no dialog. Scripted Thens (R0 and ... (`phase-R0b-1-report.md`) |
| TC-05-14 | High | runner | PASS | evidence/r0b1-tc-05-14-before.png, -after.png, -after-b.png, runner/captures/TC-05-14.png | agent_check items: second build Given = N/A (single FreeCAD 1.1.4 build, serializer exportBinary); CONDITIONAL two-build Then = N/A; before capture read, identical to after. Scripted Thens from R0 data: tagless record refused INVALID_INPUT `expect_fingerprint record: cannot compare fingerprints: serializer tag ... (`phase-R0b-1-report.md`) |
| TC-05-15 | Critical | runner | PASS | evidence/r0b1-tc-05-15-before.png, -after.png, -after-b.png, runner/captures/TC-05-15.png | agent_check items: `query_dependencies {object: "Fillet"}` -> `in_list ["Body"]`, `out_list ["Pad"]` (Fillet depends on Pad; read on the committed state). tnp_audit of the radius change: status CLEAN, `findings` [] (so every listed finding is RE_BASELINED, none listed), `counts {"PASS": 2}` (>= 1), ... (`phase-R0b-1-report.md`) |
| TC-05-17 | Critical | smoke-a | PASS | evidence/tc-05-17-before.png, tc-05-17-after.png | Same launch 19434 (auto-approve off). element_map_available true (query_capabilities). Given built by me with one script_exec: Body, Sketch 60x40, Pad 30 mm, Fillet 2 mm on Edge1; volume 71974.25. preview_dry_run then sketch_remove_geometry Sketch geo 0 with confirm: status RECOMPUTE_ERROR, post_verify.recompute_clean ... (`phase-S1-report.md`) |

### TC-06

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-06-01 | Critical | smoke-a | PASS | evidence/tc-06-01-pre.png, -viewport.png, -after.png, -mcp.png, -aa-zoom-viewport.png, -aa-zoom-mcp.png | Run in launch 18277 (auto-approve on) before TC-05-06/05-17 (order changed to group launches; each scenario still ran from its own Given). Given: live AntiAliasing value_repr before my write = -1 (key unset on the clean `fcb-freecad start` profile); scratch document wrote 4 and was closed; box-10-20-30 opened (Box, ... (`phase-S1-report.md`) |
| TC-06-03 | Critical | runner | PASS | evidence/r0b1-tc-06-03-after.png, -after-b.png, runner/tc-06-03-default.png, -include-a.png, -exclude-a.png, -include-body.png, runner/captures/TC-06-03.png | Window (20 s after fit, two captures): two solids, BodyA's 20x20x10 block behind and BoxB (20x10x15) in front on the right, no datum plane, origin marker or sketch line; the Tasks panel overlays only empty space. R0 renders read: default = the same two solids in the same arrangement, no datum plane; include-a = one ... (`phase-R0b-1-report.md`) |
| TC-06-04 | High | runner | PASS | evidence/r0b1-tc-06-04-before.png, -after.png, -after-b.png, runner/tc-06-04-red.png, -red-t80.png, -t0.png, -t100.png | Before and after window captures identical: small BoxA in front is grey, big BoxB behind is grey, nothing red. R0 renders: red.png front view, centre square red, surround grey (BoxB keeps grey). red-t80.png: same square now dull pink-grey (BoxB grey shows through; BoxB outline lies outside BoxA, so only the colour mix ... (`phase-R0b-1-report.md`) |
| TC-06-05 | High | runner | PASS | evidence/r0b1-tc-06-05-after.png, -after-b.png, runner/tc-06-05-unfocused.png, -focused.png, -highlight.png, runner/captures/TC-06-05.png | Window: two adjoining grey boxes (BoxA left, longer BoxB right), all faces grey, no orange; the unfocused render shows the same pair in the same iso view. focused.png: a magnified corner of BoxA only, cut by the frame (fills far more than unfocused). highlight.png: BoxA front face bright orange, its top darker ... (`phase-R0b-1-report.md`) |
| TC-06-07 | High | runner | PASS | evidence/r0b1-tc-06-07-after.png, -after-b.png, runner/tc-06-07-custom.png, -iso.png, runner/captures/TC-06-07.png | Window (Isometric fit): three faces visible (top, narrow left, wide right), Z up, the vertical middle edge nearest the viewer, whole and not clipped. custom.png and iso.png are the same picture (same silhouette, faces and shades). Missing orientation INVALID_INPUT `camera 'custom' requires custom_orientation (a ... (`phase-R0b-1-report.md`) |
| TC-06-09 | Critical | smoke-a | PASS | evidence/tc-06-09-after.png, tc-06-09-render-iso-unstyled.png, tc-06-09-render-top-green.png | Given: box-10-20-30 opened, Show All leaf unverifiable but tree `v Box`, verify_recompute OK no failing object. Before/after: volume 6000.0 both and bbox/com identical; query_tree_summary depth 2 identical (`v [FEATURE] Box`); Touched list `[]`. Three renders (iso, top with green 50 % style, front focus face 2) all ... (`phase-S1-report.md`) |

### TC-07

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-07-01 | Critical | runner | PASS | evidence/r0b1-tc-07-01-after.png, -after-b.png, runner/captures/TC-07-01.png | agent_check ids: R0 data and my re-run `checks` ids in order `assert.expect_volume`, `assert.expect_bbox`, `shape.solid_count`, `shape.valid`, `shape.watertight`, all passed, volume measured 6000.0, verdict OK; `expect_genus` INVALID_INPUT `unknown assertion fn: 'expect_genus'`. Window: one whole closed box, narrow ... (`phase-R0b-1-report.md`) |
| TC-07-02 | High | runner | PASS | evidence/r0b1-tc-07-02-after.png, -after-b.png, runner/captures/TC-07-02.png | agent_check ids: exactly `shape.volume`, `shape.bbox`, `shape.solid_count`, `shape.valid`, `shape.watertight`, no `expected` key, all passed true, volume 1570.8 (analytic 1570.7963). Repeat with `expect_volume` 1.0: SPEC_FAILED. Window: one cylinder, round top face and round lower edge, about twice as tall as wide ... (`phase-R0b-1-report.md`) |
| TC-07-03 | Critical | runner | FAIL (test-case defect) | evidence/r0b1-tc-07-03-after.png, -after-b.png, -edit.png, -editfit.png, -editfit-b.png, runner/captures/TC-07-03.png | Lead regrade PASS to FAIL: the visual Then needs Sketcher edit mode, which the scenario does not contain (lead-grades.md). agent_check `failed check ids include sketch.fully_constrained`: first grade SPEC_FAILED, check id `sketch.fully_constrained`, dof 4, message `dof=4, conflicting=0, malformed=0, evaluate_bad=False, degenerate=0`. Second grade OK dof 0; duplicate Horizontal RECOMPUTE_ERROR, `rolled_back` true, `recompute_clean` false; ... (`phase-R0b-1-report.md`) |
| TC-07-05 | Critical | smoke-b | FAIL (test-case defect) | evidence/tc-07-05-after.png | One Then not met literally: "the envelope text equals `STEP export written -> <path>.`". Raw `text` of the AP242 export: "STEP export written -> /repo/tests/uat/run/2026-11-18-01/evidence/tc-07-05-ap242.step.\n\nWarning: the model does not fully fit the live viewport, so the human is seeing only part of it. Call ... (`phase-S1-report.md`) |

### TC-08

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-08-01 | Critical | smoke-a | PASS | evidence/tc-08-01-before.png, tc-08-01-after.png (run 2); tc-08-01-run1-before.png, tc-08-01-run1-after.png (run 1) | Launch 19434 (auto-approve off). Given built by me with one script_exec: Body, Sketch 20x20 with 11 constraints; verify_sketch OK dof 0 fully_constrained true. Run 1 fault (agent execution fault): I fitted with view_fit_viewport and then also pressed the GUI Fit All before the before-capture, so the after capture (MCP ... (`phase-S1-report.md`) |
| TC-08-02 | Critical | smoke-a | PASS | evidence/tc-08-02-before.png, tc-08-02-after.png | Same launch 19434 (auto-approve off). Given built by me with one script_exec: Body, Sketch 20x20 (verify_sketch OK dof 0), Pad 30 mm; Pad volume 12000.0; TempDoc check `[]` before; document_list one doc (tc-08-02, transient true). preview_dry_run feature_set_parameters Pad Length 80 mm: status OK, diff.deltas.volume ... (`phase-S1-report.md`) |
| TC-08-03 | Critical | runner | PASS | evidence/r0b2-tc-08-03-before.png, -after.png | Fit and before capture done (GUI action item met). Before = flat sketch; after = 20x20x30 box. Scripted Thens: R0 findings empty. (`phase-R0b-2-report.md`) |
| TC-08-04 | High | runner | PASS | evidence/r0b2-tc-08-04-before.png, -after.png | Before capture taken; fillet preview `validity.is_valid` false, `diff.new` [] in re-run; images identical. (`phase-R0b-2-report.md`) |
| TC-08-07 | Critical | runner | PASS | evidence/r0b2-tc-08-07-before.png, -after.png | Replay returned `confirm.preview_id has already authorized a mutation; re-run preview_dry_run`; tree one `Probe`. Wording note above. (`phase-R0b-2-report.md`) |
| TC-08-08 | Critical | runner | PASS | evidence/r0b2-tc-08-08-before.png, -refused.png, -after.png | Refusal text `confirm.preview_id was issued for 'feature_pad', not 'feature_pocket'`. (`phase-R0b-2-report.md`) |
| TC-08-09 | Critical | runner | PASS | evidence/r0b2-tc-08-09-before.png, -refused.png, -after.png | Refusal text `confirm.preview_id was issued for different arguments` (60 mm call and Pad1 call). (`phase-R0b-2-report.md`) |
| TC-08-10 | Critical | runner | PASS | evidence/r0b2-tc-08-10-before.png, -after.png | Refusal `confirm.preview_id was issued for a different document`; B and A trees without Pad; own-document apply OK. Window title/tab stays TC0810B. (`phase-R0b-2-report.md`) |
| TC-08-11 | Critical | runner | PASS | evidence/r0b2-tc-08-11-before.png, -refused.png, -after.png | Stale call: `the document has changed since the preview was taken; re-run preview_dry_run`; planted: `cannot read the state of fcb-doc:... to authorize the mutation: planted: state unreadable`. Ordering note above. (`phase-R0b-2-report.md`) |
| TC-08-13 | Critical | runner | PASS | evidence/r0b2-tc-08-13-before.png, -refused.png, -after.png | See review line. (`phase-R0b-2-report.md`) |
| TC-08-14 | Critical | runner | PASS | evidence/r0b2-tc-08-14-before.png, -after.png | Messages: `is not a preview token`; `is malformed` x3; `is not decodable`; `carries an invalid signature` x3 (outside-alphabet, tampered, truncated); `12345` gives `Input validation error: 12345 is not of type 'string'`; tree has no Pad. (`phase-R0b-2-report.md`) |
| TC-08-15 | Critical | runner | PASS | evidence/r0b2-tc-08-15-before.png, -refused.png, -after.png | All three refusals are schema refusals (`Additional properties are not allowed ('autoApprove' ...)`, `'yes' is not of type 'object'`); token survived (`survived` OK); no Pad in tree before it. (`phase-R0b-2-report.md`) |
| TC-08-16 | Critical | runner | PASS | evidence/r0b2-tc-08-16-before.png, -refused.png, -after.png | `'decline'`, `'cancel'`, `None` each `Input validation error: ... is not one of ['accept']`; token survived; no Pad before apply. (`phase-R0b-2-report.md`) |

### TC-09

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-09-01 | Critical | smoke-a | PASS | evidence/tc-09-01-before.png, tc-09-01-after.png, tc-09-01-edge_report.json, tc-09-01-edge.stderr.log, tc-09-01-sweep.log | Same launch 20220. Given: pgrep count of H1 processes 0; box-10-20-30 open (handle fcb-doc:30pq9eKzVmQV187Sm7jmmw), Show All leaf unverifiable, fit OK. Sweep `uv run python scripts/automation/run_mcp_edge_cases.py` (spawns H1 in the container via docker exec, run/log line 4 of run_mcp_e2e.py) exit 0 in 16 s. ... (`phase-S2-report.md`) |
| TC-09-03 | Critical | runner | PASS | evidence/r0b3-tc-09-03-before.png, -after.png, runner/captures/TC-09-03.png | GUI Given: Show All by leaf token (tree `v [FEATURE] Box`), `view_fit_viewport` OK ratio 0.95, before capture taken. Four omissions refused by the schema layer, isError, no envelope: `export_step` `'path' is a required property`; `verify_shape` `'doc' is a required property`; `verify_export_stl` `'export_id' is a ... (`phase-R0b-3-report.md`) |
| TC-09-06 | High | runner | PASS | evidence/r0b3-tc-09-06-before.png, -after.png, runner/captures/TC-09-06.png | Given: sketch geo count 4 (`query_sketch_info`, 4 geo, 11 constraints), fit OK 0.95, before capture. Empty geometry: `Input validation error: [] should be non-empty`. 1-element start: `[0] is too short`. 4-element start: `[0, 0, 0, 0] is too long` (distinct messages, no envelope). `export_step {objects: []}` returns ... (`phase-R0b-3-report.md`) |
| TC-09-12 | Critical | runner | FAIL (test-case defect) | evidence/r0b3-tc-09-12-after.png, runner/captures/TC-09-12.png | Failed Then: "each `detail.message` contains `fcb-doc:does-not-exist` ... `detail.code` equals `INVALID_INPUT`". Raw: `query_tree_summary {doc:"fcb-doc:does-not-exist"}` returns isError with the text only `INVALID_INPUT: unknown or stale document handle: fcb-doc:does-not-exist` (no envelope, no detail, no ... (`phase-R0b-3-report.md`) |
| TC-09-17 | Critical | runner | PASS | runner/captures/TC-09-17.png, evidence/r0b3-TC-09-17-treecrop.png | R0 steps: verify_recompute status RECOMPUTE_ERROR, verdict RECOMPUTE_ERROR, checks[0] id recompute.object passed false detail.code recompute.error (`Body: Touched`), checks[1] `Pad: Linked shape object is empty`, text `Recompute: 2 error(s): Body, Pad.`; second grading identical failing_objects [Body, Pad]; clean box ... (`phase-R0b-3-report.md`) |
| TC-09-18 | Critical | runner | PASS | runner/captures/TC-09-18.png, evidence/r0b3-TC-09-18-treecrop.png | R0 steps: failing_objects [Body, Pad] contains Pad; check measured `No object linked` equals the `getStatusString` the script printed (`freecad_status` stdout `No object linked`); detail.message `Pad: No object linked`; detail.objects [Pad]; checks length 2 equals failing_objects length 2; measured non-empty. ... (`phase-R0b-3-report.md`) |

### TC-10

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-10-03 | Critical | smoke-a | PASS | evidence/tc-10-03-before.png, tc-10-03-after.png, tc-10-03-clients.txt, tc-10-03-clients.py | Launch 20220. Given: rpc-20220.json present (also stale rpc-2077/3584/4468/5328.json), proxy pid 20311 ESTAB to listener port 41855. Show All leaf unverifiable, view_fit_viewport OK ratio 0.95. B (valid token, my script run inside the container to the listener): connect 0.001 s, first frame after 0.201 s ... (`phase-S2-report.md`) |
| TC-10-07 | Critical | smoke-a | PASS | evidence/tc-10-07-after.png, tc-10-07-client.out, tc-10-07-audit.jsonl, tc-10-07-server.stderr.log, tc-10-07-h1client.py | Lead judgement: visual compared with tc-09-01-after.png (Given capture not taken; same pre-When state). Same launch 20220. H1 client is my script `tc-10-07-h1client.py` (stdio child H1 host started in the container with `fcb_py.sh`, audit log in evidence). Runs 1 and 2 (agent execution fault: a quoting error in my script at the worker-pid read, before the script_exec call; outputs kept as tc-10-07-run1-clientfault.out ... (`phase-S2-report.md`) |

### TC-11

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-11-01 | Critical | runner | PASS | evidence/r0b3-tc-11-01-before.png, -after.png, -h1.stderr.log, -audit.jsonl, r0b3-h1client.py, r0b3-proxyclient.py | Given: `env|grep -E 'FREECAD_BUDDY_(SCRIPT_EXEC|UNATTENDED)'` in the container: empty (exit 1). addon.log line 256 `FREECAD_BUDDY_SCRIPT_EXEC='1' (preference)`, line 259 `SECURITY: script_exec ENABLED: ...` (this launch, UTC 14:24:01). H1 (stdio client in container, own child host, explicit audit path): tools/list 46, ... (`phase-R0b-3-report.md`) |
| TC-11-11 | Critical | smoke-a | PASS | evidence/tc-11-11-before.png, tc-11-11-after.png, tc-11-11-client.out, tc-11-11-h1client.py, tc-11-11-audit.jsonl, tc-11-11-server.stderr.log, tc-11-11-workdir/ | Same launch 20220. H1 client is my script (stdio child H1 in the container, `FREECAD_BUDDY_WORKDIR=/repo/tests/uat/run/2026-11-18-01/evidence/tc-11-11-workdir`). Earlier attempts (agent execution faults in my fixture or script: wrong sketch attribute, under-constrained sketch that gave validity SPEC_FAILED on the ... (`phase-S2-report.md`) |
| TC-11-14 | Critical | smoke-a | PASS | evidence/tc-11-14-before.png, tc-11-14-after.png, tc-11-14-list1.txt, tc-11-14-list2.txt, tc-11-14-list3.txt, tc-11-14-userdocs/ | Lead judgement: the When names no host; H2 sweep accepted. Same launch 20220. User document folder = `evidence/tc-11-14-userdocs` with a copy of box-10-20-30.FCStd (mtime 22:31:22.2). Opened by the proxy (H2 leg), Show All leaf unverifiable, fit OK ratio 0.95. Read-only sweep over the proxy: query_tree_summary, query_object, query_mass_properties (volume 6000), ... (`phase-S2-report.md`) |
| TC-11-17 | Critical | runner | PASS | evidence/r0b3-tc-11-17-before.png, -after.png, -h1.stderr.log, -audit.jsonl | Group 2 start `docker exec -u cua -e FREECAD_BUDDY_SCRIPT_EXEC=0 fcb-desktop fcb-freecad start` (pid 12565). The operator acceptance of the restart is this run's launch group 2 (recorded in launch-log.tsv). addon.log from byte 41797: `operator settings: ... FREECAD_BUDDY_SCRIPT_EXEC='0' (env) ...`; no `SECURITY: ... (`phase-R0b-3-report.md`) |

### TC-12

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-12-04 | Critical | smoke-a | PASS | evidence/tc-12-04-tree.png, tc-12-04-tree2.png, tc-12-04-after.png, tc-12-04-after-b.png | Same launch 20220. Given: document_open box (fcb-doc:F0Nyr8iGSMJps1Th4SBdfA) and sphere (fcb-doc:qj2ClF1Srnk0TdWd_ADqqg); document_list 2 entries. Volumes: Box 6000, Sphere 4188.79. Show All Objects leaf pressed in each document with its tab in front (the Windows > Next leaf cycles Start, box, sphere; first press ... (`phase-S2-report.md`) |
| TC-12-05 | Critical | smoke-a | PASS | evidence/tc-12-05-before.png, tc-12-05-after.png | Same launch 20220. Given built by me (test case gives no create step): document_create tc1205 + one script_exec adding Part::Box ObjA (20 mm cube) and Part::Cylinder ObjB (r8, h30, at x=50); volumes 8000.0 and 6031.86; tree `v [BOX] ObjA`, `v [CYLINDER] ObjB`. view_fit_viewport OK ratio 0.95; pre-toggle tree lines ... (`phase-S2-report.md`) |
| TC-12-06 | Critical | smoke-a | PASS | evidence/tc-12-06-before-mutation.png, tc-12-06-pre-dropdown.png, tc-12-06-after.png, tc-12-06-after-b.png | Same launch 20220. Given built by me with one script_exec (no create steps in the test case): Body, Sketch 60x40 fully constrained, Pad 20 mm (volume 48000.0, State Up-to-date); vertical edges by outside oracle (Shape.Edges bbox): Edge1 (0,0), Edge2 (60,0), Edge5 (60,40), Edge8 (0,40); `<edge>` = Edge1. UndoNames ... (`phase-S2-report.md`) |
| TC-12-07 | High | runner | PASS | evidence/r0b3-tc-12-07-clean.png, -props.png, -after.png, runner/captures/TC-12-07.png | Re-run by MCP from the Given (volume 1000.0, `verify_recompute` OK). Clean-state GUI Given: snapshot lists `push button = "Recompute"` with no token, picture shows the button greyed. `script_exec` `value_repr` `['Touched']`. `query_screenshot` `dirty_document` true, text `Rendered 2 objects. Document dirty ... (`phase-R0b-3-report.md`) |
| TC-12-14 | Critical | smoke-a | PASS | evidence/tc-12-14-before.png, tc-12-14-after.png, tc-12-14-state-before.txt, tc-12-14-state-after.txt | Launch 20220 ended, launch 23013 started. Given: document_list 0 documents; pgrep pid 20220; `ss -ltnp` row `127.0.0.1:8765 ... python,pid=20311` (proxy child pid 20311); discovery file rpc-20220.json listed (also stale rpc-2077/3584/4468/5328.json); addon.log size 12028 bytes before the quit. Before capture read: ... (`phase-S2-report.md`) |

### TC-13

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-13-01 | Critical | smoke-b | PASS | evidence/tc-13-01-tree.png, tc-13-01-after.png | Same launch 20220. box40-hole-r5 opened (fcb-doc:s4r-C1EU0wxx9TsoraiskQ). MCP query_tree_summary depth 2: `OK: 1 objects, 1 shown.` and `- [FEATURE] BoxHole` (hidden before Show All; file has no GuiDocument.xml). Name BoxHole, not Cut. document_list: one entry, label box40-hole-r5. Snapshot `tree item` elements (role ... (`phase-S2-report.md`) |
| TC-13-04 | Critical | runner | FAIL (test-case defect) | evidence/r0b3-tc-13-04-viewport.png, -viewport2.png, -mcp.png, runner/captures/TC-13-04.png | Failed Thens (visual): "the proportion is confirmed ... a flat square plate, 40 by 40 by 10 mm, four times wider than it is tall" and "confirm the silhouette, hole position, and camera match" (window vs `tc-13-04-mcp.png`). Raw: the window after Show All and the `Fit All` toolbar button (token `Fit All` push button, ... (`phase-R0b-3-report.md`) |
| TC-13-06 | Critical | runner | PASS | evidence/r0b3-tc-13-06-menu.png, -viewport.png, -mcp.png, runner/captures/TC-13-06.png | Show All by leaf token; `Isometric` push button by token, then `getCameraOrientation().Q` `(0.4247, 0.1759, 0.3399, 0.8205)` (iso). `Fit All` toolbar button by token, 20 s wait, then render and window capture. `scene.rendered_objects` `["BoxHole"]`, `resource_link` set (copied to evidence). Volume after render 15214.6 ... (`phase-R0b-3-report.md`) |
| TC-13-10 | Critical | smoke-b | FAIL (test-case defect) | evidence/tc-13-10-before.png, tc-13-10-after-pad.png, tc-13-10-viewport.png, tc-13-10-diagnostic.txt | Same launch 20220. Given built with typed tools: document_create TC13Pad, feature_body_create Body, sketch_create Sketch (XY, in Body), sketch_add_geometry 4 lines with 11 constraints (RectWidth 30 mm, RectDepth 20 mm): dof 0, fully_constrained true. Tree items before the pad: TC13Pad, Body. Before: GUI Fit All ... (`phase-S2-report.md`) |

### TC-14

| Scenario | Priority | Set | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- | --- |
| TC-14-02 | Critical | runner | PASS | runner/captures/TC-14-02.png | Scripted checks stand for status, fitted, document, camera_recorded, text, detail. My own fit call: status OK, `fitted` true, `document` `box_10_20_30`, `camera_recorded` true, text `fitted the live viewport to 'box_10_20_30'`, `detail` null. Visual Then met on the runner capture (see review line). (`phase-R0b-3-report.md`) |
| TC-14-03 | Critical | smoke-b | PASS | evidence/tc-14-03-before.png, tc-14-03-after.png, tc-14-03-after-b.png | Same launch 20220. box-10-20-30 opened, Show All leaf unverifiable. Camera: the default view gave `framing: does not fit, computed` with no ratio; I pressed the View > Zoom > Zoom Out leaf 3 times by token (the default view was already zoomed in, so no Zoom In press was needed) and the next read gave `does not fit, ... (`phase-S2-report.md`) |
| TC-14-05 | Critical | smoke-b | PASS | evidence/tc-14-05-before.png, tc-14-05-after.png, tc-14-05-after-b.png, tc-14-05-render.png | Same launch 20220. The TC-14-04 bar was rebuilt with typed tools (document_create tc14bar, feature_body_create BarBody, sketch_create BarSketch, sketch_add_geometry 40x40 with 11 constraints, feature_pad BarPad 800 mm): BarPad volume 1280000, bbox 40x40x800. Camera state: `framing: does not fit, computed` (the new ... (`phase-S2-report.md`) |
| TC-14-06 | Critical | runner | PASS | evidence/r0b3-tc-14-06-before.png, -after.png, runner/captures/TC-14-06.png | Given: DocA fit returned OK while DocA was focused; DocB built (40 mm bar) and fitted OK; `document_list` 2 documents; `list_windows` title `* DocB - FreeCAD 1.1.4`; `ratio_before` 0.95 (`framing: fits, ratio 0.95, computed`). `view_fit_viewport {doc: DocA}` returned INVALID_INPUT, `detail.message` `the live viewport ... (`phase-R0b-3-report.md`) |
| TC-14-07 | Critical | runner | PASS | runner/captures/TC-14-07.png | graded by the scripted pixel check (test-plan §9), outside the review set (`phase-R0-report.md`) |
| TC-14-08 | High | runner | PASS | evidence/r0b3-tc-14-08-after.png, runner/captures/TC-14-08.png | Given framing ratio 0.95 (`framing: fits, ratio 0.95, computed`). `factor: 0.5`: `Input validation error: Additional properties are not allowed ('factor' was unexpected)`. `confirm: true`: `Input validation error: Additional properties are not allowed ('confirm' was unexpected)`. Ratio after: 0.95 (cached). Capture ... (`phase-R0b-3-report.md`) |
| TC-14-16 | Critical | runner | PASS | evidence/r0b3-tc-14-16-after.png, runner/captures/TC-14-16.png | `verify_shape` structured_content before and after identical (volume 6000, bbox [10,20,30], 1 solid, valid, watertight, verdict OK). `query_mass_properties` volume 6000 after. Window title `* box-10-20-30 - FreeCAD 1.1.4` before and after the fit (list_windows). `verify_recompute` OK, failing_objects []. (`phase-R0b-3-report.md`) |

## Gate 1 summary (smoke run: not a Gate 1 measure)

Gate 1 is not computed: the suite did not run in full (decision 45). The table shows how much of each TC ran.

| TC | Scenarios in suite | Ran | PASS | FAIL | Not run |
| --- | --- | --- | --- | --- | --- |
| TC-01 | 15 | 15 | 15 | 0 | 0 |
| TC-02 | 18 | 11 | 8 | 3 | 7 |
| TC-03 | 21 | 16 | 14 | 2 | 5 |
| TC-04 | 24 | 12 | 12 | 0 | 12 |
| TC-05 | 18 | 6 | 6 | 0 | 12 |
| TC-06 | 12 | 6 | 6 | 0 | 6 |
| TC-07 | 21 | 4 | 2 | 2 | 17 |
| TC-08 | 21 | 13 | 13 | 0 | 8 |
| TC-09 | 23 | 6 | 5 | 1 | 17 |
| TC-10 | 14 | 2 | 2 | 0 | 12 |
| TC-11 | 19 | 4 | 4 | 0 | 15 |
| TC-12 | 15 | 5 | 5 | 0 | 10 |
| TC-13 | 18 | 4 | 2 | 2 | 14 |
| TC-14 | 16 | 7 | 7 | 0 | 9 |
| **Total** | **255** | **111** | **101** | **10** | **144** |

By priority, on the 111 scenarios that ran: Critical 76 PASS of 84 (8 FAIL); High 23 PASS of 24 (1 FAIL); Medium 2 PASS of 3 (1 FAIL).

## Gate 2 — TC-99 conformance

Not run (decision 45). No fix area of the smoke list needs a TC-99 scenario.

## G3 replay (corrupted-plan suite)

### Headless: UNCHANGED

Command (spec Code Map), from a container temp copy with every `*heldout*` path left out (`find -path '*heldout*'` count 0; temp copy removed after the run): `fcb-py benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x --run g3r-2026-11-18-01-1.1.4 --check --frames-check benchmarks/g3/fault-injection/frames-reference.json`. Exit 0.

| Item | Result | Reference `g3r-2026-10-08-1.1.3` |
| --- | --- | --- |
| Planted | 10 of 10 DETECTED | 10 of 10 |
| Controls and reverted builds | 14 of 14 PASS_CLEAN (4 controls, 10 reverted), flagged 0 | 14 of 14 |
| Sensitivity / false alarm | 1.000 / 0.000 | 1.0 / 0.0 |
| Anchor frames | `frames-check: OK` | equal |
| `validators.yaml` | not written (`--check`) | — |

Evidence: `evidence/g3-headless.log`, `evidence/g3-headless/` (`G3.E.3.1.1.x.json`, `cases.jsonl`, `audit.jsonl`, `server.stderr.log`).

### GUI (smoke: one control and one planted/reverted pair): UNCHANGED

`uv run --extra dev python g3_gui_replay.py control-faithful wrong-hole-diameter` from `evidence/g3-gui/`, against container FreeCAD pid 24818 through `http://127.0.0.1:18765/mcp`. Exit 0, no `gui_error`.

| Case | Build | Status | Classification | Volume (mm^3) | 2026-10-03-04 row |
| --- | --- | --- | --- | --- | --- |
| `g3-fault-plan-control-faithful-mounting-plate` | control | OK | — | 28229.8 | OK, 28229.80 |
| `g3-fault-plan-wrong-hole-diameter` | planted | INVALID_INPUT (failed checks `assert.expect_volume`, `assert.hole_diameter`, 4 x `assert.distance_between`) | DETECTED | 27593.63 | INVALID_INPUT, DETECTED, 27593.63 |
| `g3-fault-plan-wrong-hole-diameter` | reverted | OK | — | 28229.8 | OK, 28229.80 |

Captures read by the lead (`evidence/g3-gui/`): control and reverted show the same plate from the top with four equal round through-holes near the corners, whole, no dialog. The planted capture shows the same plate with four larger holes, each drawn with a second ring, so the planted hole diameter is visible. Watchdog after the replay: exit 0 (`evidence/g3-gui/watchdog.txt`).

## Visual check

Every agent-driven scenario ends with a fit and a `cua-driver` capture that its phase agent read and described (phase reports). The lead re-read every FAIL capture, every capture on which a disputed visual PASS rests, and at least one capture per TC per phase (`lead-notes/lead-grades.md`: 46 rows).

## Findings

The finding list with ids is `bugs.md`. Summary:

| Id | Scenario(s) | Cause class | Finding |
| --- | --- | --- | --- |
| B-11 | TC-02-15, TC-09-12 | test-case defect | Then reads `schema` and `detail.code` from `query_tree_summary`, a text-only tool (`mcp-tools-design.md` §1.3) |
| B-12 | TC-02-17 | test-case defect | Expected MSVC iostream text; Linux FreeCAD gives `basic_ios::clear: iostream error` |
| B-13 | TC-03-03, TC-03-20 | test-case defect | Visual Then on thickness or elevation in a top-down Sketcher edit view; no camera step |
| B-14 | TC-07-03 | test-case defect | Visual Then needs Sketcher edit mode; the scenario has no edit-mode step |
| B-15 | TC-07-05 | test-case defect | `text` "equals" the export line; the framing warning (`contracts/envelope.py:111`) is appended when the model does not fit |
| B-16 | TC-13-04 | test-case defect | Window camera (top) and render camera (iso) cannot match; no window camera step |
| B-17 | TC-13-10 | test-case defect | "viewport solid reads as that thickness" in a top view; no camera step |
| B-18 | TC-02-13 | harness limit | Container has no emoji font; U+1F527 draws as an empty box |
| R-1 | TC-05-03 (R0b-1) | agent execution fault | One phase replay script used host `:8765` and drove the owner's host FreeCAD once (decision 46) |

Observations with no verdict change (from the phase reports): Tasks overlay covers part of the 3D view (R0a-2 F2, R0a-3 O1); GUI Fit All repaint delay (R0a-1 F2); `Show All Objects` leaf returns `unverifiable` (R0a-1 F3); Givens with no create steps (S1 F4, S2 F3); Cleanup lines that would delete run evidence (S1 F6, S2 F4); render face tones differ from the window (N-20, TC-06-01, TC-14-05); `view_fit_viewport` on a document with only a sketch in edit mode returns `nothing_to_frame` (S1 F5); `view_fit_viewport` audited as three `mutation` lines (R0b-3 F4); TC-08-07 and TC-08-11 wording (R0b-2 F1, F2); `fcb_py.sh` warns about the host `FREECAD_BUDDY_WORKDIR` (P1 F1).

## Human interventions

None during the run phases. The owner used a FreeCAD on the Windows host from 20:15 to 20:55 and at 21:04 (their own work, decision 46); the host `user.cfg` change came from that session, and the run accepted the new baseline.

## FreeCAD launches

Runner R0: 3 launch groups with temporary `-u`/`-s` profiles (`runner/results.json`). Agent and lead launches, all in container `fcb-desktop` (`evidence/launch-log.tsv`):

| Phase | Start (+07:00) | pid | Env | End |
| --- | --- | --- | --- | --- |
| R0a-1 | 20:10:35 | 5328 | - | 20:20:48 `fcb-freecad stop` |
| R0a-2 | 20:23:33 | 6141 | - | 20:44:11 stop |
| R0a-3 | 20:47:25 | 7818 | - | 20:51:47 stop |
| R0b-1 | 20:54:00 | 8310 | `AUTO_APPROVE=0` | 21:01:20 stop |
| R0b-1 | 21:01:40 | 9076 | - | 21:10:17 stop |
| R0b-2 | 21:14:16 | 10006 | `AUTO_APPROVE=0` | 21:21:33 stop |
| R0b-3 | 21:23:39 | 11748 | - | 21:33:29 stop |
| R0b-3 | 21:33:35 | 12565 | `SCRIPT_EXEC=0` | 21:35:45 stop |
| P1 | 21:37:39 | 12978 | - | 21:47:20 File > Exit |
| P1 | 21:47:32 | 15171 | - | 21:49:35 stop |
| P1 | 21:49:43 | 15726 | `NO_AUTO_MCP=no` | 21:50:55 stop |
| P1 | 21:51:17 | 16092 | - | 21:52:30 `kill -KILL` (TC-01-14) |
| P1 | 21:52:58 | 16458 | - | 21:54:50 File > Exit |
| P1 | 21:54:58 | 16921 | port 8765 held by `http.server` | 21:57:30 stop |
| P1-R | 21:58:23 | 17331 | - | 22:00:46 File > Exit |
| S1 | 22:06:05 | 18102 | - | 22:06:31 stop |
| S1 | 22:06:32 | 18277 | - | 22:14:54 stop |
| S1 | 22:14:58 | 19434 | `AUTO_APPROVE=0` | 22:21:28 stop |
| S2 | 22:24:57 | 20220 | - | 22:42:36 File > Exit (TC-12-14) |
| S2 | 22:43:11 | 23013 | - | 22:43:31 stop |
| G3 | 22:46:22 | 24818 | - | 22:47:50 stop |

## Teardown

- Container FreeCAD: `fcb-freecad status` shows no pid; no `:8765` listener in the container (`ss -ltn`).
- No `FCB_TMP_snap_*` left: watchdog exit 0 at the end of every phase and after G3 (temp-hygiene 0 snapshot dirs).
- Developer `user.cfg` SHA-256 at run end: `63fa48cfe55eb515b30113b21e4732da70a1aa0b877c51dab3b8a4e979b9bd2a`, equal to the accepted baseline (decision 46).
- No phase agent alive. `/tmp/g3r` removed from the container.
- Commit: not done by the run lead; the leader commits after owner approval.
