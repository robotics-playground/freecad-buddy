#!/bin/bash
# shot.sh <tabx> <out.png>
S=/c/Users/thuan/AppData/Local/Temp/claude/3d3814eab912640f/50958ed8-8fcb-4d26-a32d-c7025b2780ae/scratchpad/verifier-13-18
$S/cua.sh click "{\"pid\":890,\"window_id\":41943133,\"x\":$1,\"y\":884,\"delivery_mode\":\"foreground\"}" > /dev/null
$S/cua.sh list_windows '{"pid":890}' | grep title
tok() { $S/cua.sh get_window_state '{"pid":890,"window_id":41943133,"include_screenshot":false}' > $S/ws.json; python -c "
import json,sys;d=json.load(open(r'$(cygpath -w $S/ws.json)'))
print([e['element_token'] for e in d['elements'] if e.get('role')==sys.argv[1] and e.get('label')==sys.argv[2]][-1])" "$1" "$2"; }
I=$(tok "menu item" Isometric); $S/cua.sh click "{\"pid\":890,\"element_token\":\"$I\"}" > /dev/null
F=$(tok "push button" "Fit All"); $S/cua.sh click "{\"pid\":890,\"element_token\":\"$F\"}" > /dev/null
sleep 1
$S/cua.sh get_window_state "{\"pid\":890,\"window_id\":41943133,\"screenshot_out_file\":\"/repo/tests/uat/run/13-18-r1/evidence/$2\"}" > /dev/null
echo captured $2
