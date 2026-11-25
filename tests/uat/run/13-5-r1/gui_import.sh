#!/bin/bash
# usage: gui_import.sh <doc label> <container file path>
# Creates an empty document through MCP, then imports the file through FreeCAD's File > Import dialog.
set -u
cd "$(dirname "$0")"
C=./cua.sh
W='"pid":506,"window_id":37748829'
uv run --project /d/Work/Personal/Sources/fcb-verify-13-5 python mcp1.py document_create "{\"label\":\"$1\"}" | head -c 200; echo
$C get_window_state "{$W,\"include_screenshot\":false}" > gi1.json
IMP=$(python tok.py gi1.json "menu item" "Import…")
$C click "{\"pid\":506,\"element_token\":\"$IMP\"}" | grep -E '"effect"'
sleep 2
DLG=$($C list_windows '{"pid":506}' | python -c "import json,sys;print([w['window_id'] for w in json.load(sys.stdin)['windows'] if w['title']=='Import file'][0])")
$C get_window_state "{\"pid\":506,\"window_id\":$DLG,\"include_screenshot\":false}" > gi2.json
NAME=$(python tok.py gi2.json "text" "File name:")
$C type_text "{\"pid\":506,\"element_token\":\"$NAME\",\"text\":\"$2\"}" | grep -E '"effect"'
$C get_window_state "{\"pid\":506,\"window_id\":$DLG,\"include_screenshot\":false}" > gi3.json
OPEN=$(python tok.py gi3.json "push button" "Open")
$C click "{\"pid\":506,\"element_token\":\"$OPEN\"}" | grep -E '"effect"'
sleep 4
$C list_windows '{"pid":506}' | grep -E '"title"'
