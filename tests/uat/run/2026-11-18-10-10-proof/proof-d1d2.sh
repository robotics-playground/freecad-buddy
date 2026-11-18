#!/bin/bash
# Fix round 1 proof: D1 (Toggle Visibility) and D2 (Recompute) as the test cases now write them.
# Needs the container up, FreeCAD running with box-10-20-30.FCStd open, and the test-plan §6
# variables exported (FCB_CUA, RUN_DIR). Writes D1-toggle-visibility.txt and D2-recompute.txt here.
set -u
export MSYS_NO_PATHCONV=1
here="$(cd "$(dirname "$0")" && pwd)"
X="docker exec -u cua fcb-desktop"
M="$X fcb-py /repo/tests/uat/run/2026-11-18-10-10-proof/mcpcall.py"
PID=$($X pgrep -f '^/opt/freecad/usr/bin/freecad' | head -1)
WID=$(echo "{\"pid\":$PID}" | "$FCB_CUA" list_windows | python -c "import json,sys;print(json.load(sys.stdin)['windows'][0]['window_id'])")
DOC=$($M document_list '{}' | python -c "import json,sys;print(json.load(sys.stdin)['structured_content']['documents'][0]['doc'])")
say() { echo "\$ $*"; }
tree() { $M query_tree_summary "{\"doc\":\"$DOC\"}" | tail -1; }
sel() { $M script_exec "{\"doc\":\"$DOC\",\"code\":\"import FreeCADGui as G; result = [o.Name for o in G.Selection.getSelection()]\"}" | grep -o 'value_repr[^,]*' | head -1; }
state() { $M script_exec "{\"doc\":\"$DOC\",\"code\":\"o = doc.getObject('Box'); result = list(o.State)\"}" | grep -o 'value_repr":"[^"]*"' | head -1; }
clr() { $M script_exec "{\"doc\":\"$DOC\",\"code\":\"import FreeCADGui as G; G.Selection.clearSelection(); result = 1\"}" > /dev/null; }
touch() { $M script_exec "{\"doc\":\"$DOC\",\"code\":\"doc.getObject('Box').touch(); result = 1\"}" > /dev/null; }
press() { # press <label>: fresh snapshot, then click the menu leaf by token
  echo "{\"pid\":$PID,\"window_id\":$WID,\"include_screenshot\":false}" | "$FCB_CUA" get_window_state > "$here/.snap.json"
  token=$(python -c "import json,sys;d=json.load(open(sys.argv[1]));print([e['element_token'] for e in d['elements'] if e.get('label')==sys.argv[2] and e.get('role')=='menu item'][0])" "$(cygpath -m "$here/.snap.json")" "$1")
  echo "{\"pid\":$PID,\"element_token\":\"$token\"}" | "$FCB_CUA" click > /dev/null
}

{
  echo "# D1 Toggle Visibility: foreground pixel click on the tree row, then window-level press_key space"
  echo "# Box row centre from the screenshot of get_window_state (window-local pixels)"
  press "Show All Objects"; sleep 2
  echo "visibility before: $(tree)   selection: $(sel)"
  clr; echo "selection cleared: $(sel)"
  say "background pixel click: selection stays empty"
  echo "{\"pid\":$PID,\"window_id\":$WID,\"x\":80,\"y\":175}" | "$FCB_CUA" click > /dev/null; sleep 1; echo "selection: $(sel)"
  clr
  say 'echo {"pid":..,"window_id":..,"x":80,"y":175,"delivery_mode":"foreground"} | "$FCB_CUA" click'
  echo "{\"pid\":$PID,\"window_id\":$WID,\"x\":80,\"y\":175,\"delivery_mode\":\"foreground\"}" | "$FCB_CUA" click > /dev/null; sleep 1
  echo "selection: $(sel)"
  say 'echo {"pid":..,"window_id":..,"key":"space","delivery_mode":"foreground"} | "$FCB_CUA" press_key'
  echo "{\"pid\":$PID,\"window_id\":$WID,\"key\":\"space\",\"delivery_mode\":\"foreground\"}" | "$FCB_CUA" press_key > /dev/null; sleep 1.5
  echo "visibility after space: $(tree)   (the marker v = shown, - = hidden)"
  echo "{\"pid\":$PID,\"window_id\":$WID,\"key\":\"space\",\"delivery_mode\":\"foreground\"}" | "$FCB_CUA" press_key > /dev/null; sleep 1.5
  echo "visibility after second space: $(tree)"
  say "old route: press_key space with the tree item element_token"
  echo "{\"pid\":$PID,\"window_id\":$WID,\"include_screenshot\":false}" | "$FCB_CUA" get_window_state > "$here/.snap.json"
  token=$(python -c "import json,sys;d=json.load(open(sys.argv[1]));print([e['element_token'] for e in d['elements'] if e.get('role')=='tree item' and e.get('label')=='Box'][-1])" "$(cygpath -m "$here/.snap.json")")
  echo "{\"pid\":$PID,\"element_token\":\"$token\",\"key\":\"space\"}" | "$FCB_CUA" press_key 2>&1 | head -2
  echo "visibility after the old route: $(tree)"
} > "$here/D1-toggle-visibility.txt" 2>&1

{
  echo "# D2 Recompute: F5 hotkey, the Recompute leaf; ctrl+r does nothing"
  touch; echo "State after touch: $(state)"
  say 'echo {"pid":..,"window_id":..,"keys":["f5"]} | "$FCB_CUA" hotkey'
  echo "{\"pid\":$PID,\"window_id\":$WID,\"keys\":[\"f5\"]}" | "$FCB_CUA" hotkey > /dev/null; sleep 2; echo "State after F5: $(state)"
  touch; echo "State after touch: $(state)"
  echo "{\"pid\":$PID,\"window_id\":$WID,\"keys\":[\"ctrl\",\"r\"]}" | "$FCB_CUA" hotkey > /dev/null; sleep 2; echo "State after ctrl+r: $(state)"
  say "press the Recompute leaf by element_token"
  press "Recompute"; sleep 2; echo "State after the leaf: $(state)"
} > "$here/D2-recompute.txt" 2>&1
rm -f "$here/.snap.json"
