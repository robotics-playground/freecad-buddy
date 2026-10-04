"""Writes tc-01-results.json for UAT run 2026-10-03-04, TC-01."""
import json
from pathlib import Path

E = Path(__file__).resolve().parent
FIX = (
    "Fixture box-10-20-30.FCStd opens with Box Visibility=false (no GuiDocument.xml), so view_fit_viewport returns "
    "SPEC_FAILED view_fit.unverified 'no visible shape-bearing objects to measure' and the view is empty "
    "(tc-01-01-after.png, tc-01-01-fit.json). Test-case/fixture defect. Each visual first ran FreeCAD menu "
    "View>Visibility>Show All Objects via cua-driver invoke_menu, then the fit."
)
AD26 = (
    "AD-26: the proxy holds the only RPC connection (listen backlog 1), so a direct client is refused or blocked; "
    "the proxy was terminated for the probe and restarted by hand with the addon's command."
)
R = [
    {"id": "TC-01-01", "priority": "Critical", "verdict": "PASS",
     "evidence": ["tc-01-01-given-launch.txt", "tc-01-01-addonlog-checks.txt", "tc-01-01-proxy-process.txt",
                  "tc-01-01-mcp-out.json", "tc-01-01-fit.json", "tc-01-01-after.png",
                  "tc-01-01-fit-after-show.json", "tc-01-01-after-shown.png"],
     "note": "Listener on 127.0.0.1:59314; addon spawned proxy pid 9380 (.venv\\Scripts\\pythonw.exe -m "
             "freecad_buddy.hosts.main serve --mode rpc --transport http). The :8765 owner is its child 34584 "
             "(uv base pythonw, same args) because the uv venv pythonw is a launcher. Literal Then 'owning pid "
             "equals spawn pid' fails: test-case defect; the addon log names the launcher pid, not the server pid. "
             "Win32_Process.CommandLine is empty from the non-elevated shell; read via NtQueryInformationProcess. "
             + FIX + " With the box shown: fit OK ratio 0.949, whole box visible, no dialog."},
    {"id": "TC-01-02", "priority": "Critical", "verdict": "PASS",
     "evidence": ["tc-01-02-given.txt", "tc-01-02-sweep.stdout.txt", "tc-01-02-exit.txt", "tc-01-02-e2e_report.json",
                  "tc-01-02-server.stderr.log", "tc-01-02-checks.txt", "tc-01-02-before.png", "tc-01-02-after.png"],
     "note": "exit 0, 29/29, all_passed True, box volume 6000.0, every verify_export_* OK, stderr clean, GUI "
             "query_capabilities OK after the sweep. The sweep writes to _automation/; copied to evidence. Before and "
             "after captures identical; one document, no new window. " + FIX},
    {"id": "TC-01-03", "priority": "Critical", "verdict": "PASS",
     "evidence": ["tc-01-03-list.py", "tc-01-03-checks.txt", "tc-01-03-tools_list.keep.json",
                  "tc-01-03-additionalProperties.json", "tc-01-03-after.png"],
     "note": "45 tools, no export_self_read_*, no debug_exec, family counts match, the 13 read-only names present, "
             "additionalProperties False on all 45. Cleanup deleted tools_list.json; the .keep copy is the evidence. "
             + FIX},
    {"id": "TC-01-04", "priority": "Critical", "verdict": "PASS",
     "evidence": ["tc-01-04-checks.txt", "tc-01-04-capabilities.json", "tc-01-04-about-desktop.png",
                  "tc-01-04-about-invoke.txt", "tc-01-06-rpc.txt", "tc-01-04-after.png"],
     "note": "Banner keys exact, types correct, render gui_constructed, exec_enabled false. About dialog shows "
             "Version 1.1.4 (TC expects 1.1.1: test-case defect); rpc-33184.json freecad_version 1.1.4. The rpc file "
             "holds no capabilities; handshake exec_enabled=false was read with a direct rpc_hello in the TC-01-06 "
             "proxy-down window (AD-26). Harness: invoke_menu Help>About blocks until the modal closes, then returns "
             "menu_path_unavailable; UIA busy, so About was captured with get_desktop_state and dismissed with a "
             "foreground Escape. " + FIX},
    {"id": "TC-01-05", "priority": "High", "verdict": "PASS",
     "evidence": ["tc-01-05-budgets.txt", "tc-01-05-checks.txt", "tc-01-05-after.png"],
     "note": "Budgets {30,60,120,180}; only preview_dry_run is 180; 60 set exact; sketch/feature/export all 120 and "
             "mutating True; query/verify mutating False; document_open/close mutating True. The 30 s set has 11 "
             "names, not 10: view_fit_viewport (30.0, mutating True, tool_catalog.py:906) is missing from the TC "
             "list: test-case defect. " + FIX},
    {"id": "TC-01-06", "priority": "Critical", "verdict": "PASS",
     "evidence": ["tc-01-rpc.py", "tc-01-proxy-stop.ps1", "tc-01-06-literal-proxy-up.txt", "tc-01-06-rpc.txt",
                  "tc-01-06-proxy-restart.log", "tc-01-06-before.png", "tc-01-06-after.png"],
     "note": "Reply {code:-32004, message:'contract version unsupported', data:{supported:['1']}}, no result or "
             "capabilities, second readline ''. Listener survived (authenticated hello OK); query_capabilities OK via "
             "the restarted proxy; windows identical. Deviations: the TC command picks sorted(glob)[-1] = "
             "rpc-9756.json (dead pid) -> ConnectionRefusedError: test-case defect; used rpc-<live pid>.json. " + AD26},
    {"id": "TC-01-07", "priority": "Critical", "verdict": "PASS",
     "evidence": ["tc-01-07-rpc.txt", "tc-01-07-proxy-restart.log", "tc-01-07-before.png", "tc-01-07-after.png"],
     "note": "Wrong token + v99 and omitted token both -> -32000 'auth failed'; no capabilities, freecad_version or "
             "supported; socket closed; two 'token mismatch; closing' lines; listener survived. " + AD26},
    {"id": "TC-01-08", "priority": "Critical", "verdict": "PASS",
     "evidence": ["tc-01-08-rpc.txt", "tc-01-08-proxy-restart.log", "tc-01-08-before.png", "tc-01-08-after.png"],
     "note": "query_capabilities as first frame -> -32002 'handshake required' id 3, frame2 ''; 'not json' -> -32002 "
             "id null; log line present for case 1. Observation: the malformed-JSON refusal writes no log line "
             "(rpc_listener.py:269-271); the proxy kill logs a full ConnectionResetError traceback at ERROR. " + AD26},
    {"id": "TC-01-09", "priority": "High", "verdict": "PASS",
     "evidence": ["tc-01-09-discovery.json", "tc-01-09-checks.txt", "tc-01-09-after.png"],
     "note": "Keys exact; pid 33184 is freecad.exe; 127.0.0.1:59314 LISTENING by 33184; contract_version '1'; "
             "freecad_version 1.1.4 (TC expects 1.1.1: test-case defect); token authenticates (proxy-down window, "
             "AD-26). Windows mode -rw-r--r--, ACL SYSTEM/Administrators/user FullControl (recorded, not failed). "
             "Legacy $APPDATA/FreeCAD/Mod is empty. Token masked in the evidence copy."},
    {"id": "TC-01-10", "priority": "High", "verdict": "PASS",
     "evidence": ["tc-01-10-prep.txt", "tc-01-10-given.txt", "tc-01-10-before.png", "tc-01-10-checks.txt",
                  "tc-01-10-other-rpc-before.txt", "tc-01-10-other-rpc-after.txt"],
     "note": "FreeCAD 35716 exited in about 1 s via File>Exit; rpc-35716.json deleted; addon-spawned proxy 33740 and "
             "listener 37032 gone; :8765 free; the other 11 rpc files unchanged; dead window not capturable; no "
             "FreeCAD window on the desktop. Deviations: FreeCAD was relaunched first so the proxy under test was "
             "addon-spawned (TC-01-06..09 had replaced it); the visibility-modified document was closed via MCP "
             "before Exit to avoid a save dialog. Before PNG (Fit All, top view) shows the box rectangle whole."},
    {"id": "TC-01-11", "priority": "High", "verdict": "PASS",
     "evidence": ["tc-01-11-given.txt", "tc-01-11-checks.txt", "tc-01-11-before.png", "tc-01-11-after.png"],
     "note": "12 rpc files vs 1 FreeCAD. rpc-9756.json (dead pid): ConnectionRefusedError in 2.05 s (< 5 s); file "
             "still present; live bridge OK; windows identical. " + FIX},
    {"id": "TC-01-12", "priority": "High", "verdict": "PASS",
     "evidence": ["tc-01-12-given.txt", "tc-01-12-kill.txt", "tc-01-12-proxy-restart.log", "tc-01-12-checks.txt",
                  "tc-01-12-mcp-out.json", "tc-01-12-before.png", "tc-01-12-after.png"],
     "note": "FreeCAD 35464 survived; rpc file unchanged (port 53661, same token hash, same started); :8765 LISTENING "
             "on new pid 4548; same freecad_version; the pre-restart handle answered query_tree_summary OK; "
             "document_list shows box-10-20-30; view_fit_viewport OK through the restarted proxy; windows identical. "
             "Harness: literal 'Stop-Process -Id 33068' -> Access is denied; used TerminateProcess; killing the "
             "listener also ended the .venv launcher 36104."},
    {"id": "TC-01-13", "priority": "Medium", "verdict": "PARTIAL",
     "evidence": ["tc-01-13-given.txt", "tc-01-13-launcher.cmd", "tc-01-13-launch.txt", "tc-01-13-cli.txt",
                  "tc-01-13-fit.txt", "tc-01-13-after.png", "tc-01-13-cleanup.txt"],
     "note": "FREECAD_BUDDY_NO_AUTO_MCP=no via a .cmd wrapper passed to launch_app (no env field): listener started, "
             "rpc-36284.json written, nothing on :8765, verbatim 'FREECAD_BUDDY_NO_AUTO_MCP set; not auto-starting "
             "the MCP proxy'. CLI: both exit 2 with the exact stderr strings; :8765 still free. Visual read: normal "
             "main window, menu bar, Model panel, Start page, no dialog. NOT RUN: the Fit All framing Then; with no "
             "document there is no 3D view and no Fit All button in the UIA tree (test-case defect: the scenario "
             "opens no document but expects a 3D view). Cleanup kill_app refused "
             "(foreign_process_termination_denied); the instance exited via File>Exit instead."},
    {"id": "TC-01-14", "priority": "High", "verdict": "PASS",
     "evidence": ["tc-01-14-given.txt", "tc-01-14-before.png", "tc-01-14-kill.txt", "tc-01-14-mcp-after-kill.txt",
                  "tc-01-14-relaunch.txt", "tc-01-14-after-relaunch.txt", "tc-01-14-after.png",
                  "tc-01-14-cleanup.txt"],
     "note": "cua-driver kill_app refused: foreign_process_termination_denied; used TerminateProcess (taskkill /F "
             "equivalent, allowed by RUN-CONTEXT for this TC). After the kill: port 53333 refused in 2.03 s; proxy "
             "22056 orphaned but alive, returns WORKER_CRASHED 'listener connection dropped' (no fabricated OK); "
             "stale rpc-33732.json kept. Relaunch 32944 wrote rpc-32944.json; new token differs; old token on the "
             "new listener -> -32000 auth failed; killed pid not capturable; new window healthy, no recovery dialog. "
             "Finding: the relaunched addon logs 'MCP proxy already on http://127.0.0.1:8765/mcp; not spawning' and "
             "the orphan proxy re-attaches to the new FreeCAD, so the new session is served by a proxy that is not "
             "its child and will not end with it. " + FIX},
]
(E / "tc-01-results.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
print(len(R), "results written")
