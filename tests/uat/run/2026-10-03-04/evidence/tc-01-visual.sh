# usage: bash tc-01-visual.sh <doc-handle> <png-name> [fitall]
# The golden box-10-20-30.FCStd opens with Box Visibility=false in the GUI (no GuiDocument.xml in the
# fixture), so the visual first shows it through FreeCAD's own menu View > Visibility > Show All
# Objects (cua-driver invoke_menu), then frames it with MCP view_fit_viewport (default per plan §3
# rule 5) or the Fit All toolbar button when "fitall" is passed, then captures the window.
cd /d/Work/Personal/Sources/freecad-buddy
E=tests/uat/run/2026-10-03-04/evidence
PID=$(python -c "import json;print(json.load(open('$E/fc.json'))['pid'])" 2>/dev/null || uv run python -c "import json;print(json.load(open('$E/fc.json'))['pid'])")
WIN=$(uv run python -c "import json;print(json.load(open('$E/fc.json'))['window_id'])")
echo "show-all: $(echo "{\"pid\":$PID,\"window_id\":$WIN,\"path\":[\"View\",\"Visibility\",\"Show All Objects\"]}" | cua-driver invoke_menu 2>&1 | tr -d '\n ')"
sleep 1
# invoke_menu can leave the View menu and its submenu popped up; close them with Escape
for k in 1 2 3; do
  for w in $(echo "{\"pid\":$PID}" | cua-driver list_windows 2>&1 | uv run python -c "import json,sys;print(' '.join(str(x['window_id']) for x in json.load(sys.stdin)['windows'] if x['window_id']!=$WIN))"); do
    echo "{\"pid\":$PID,\"window_id\":$w,\"key\":\"escape\"}" | cua-driver press_key > /dev/null 2>&1; sleep 0.5
  done
done
echo "windows after popup close: $(echo "{\"pid\":$PID}" | cua-driver list_windows 2>&1 | grep -c '"window_id"') entries (main listed twice: legacy+new)"
if [ "$3" = "fitall" ]; then
  echo "fitall: $(uv run python $E/gui.py fitall)"
else
  uv run python _automation/uat/fcb.py view_fit_viewport "{\"doc\":\"$1\"}" > "$E/${2%.png}-fit.json" 2>&1
  echo "view_fit_viewport: $(grep -m1 '"status"' "$E/${2%.png}-fit.json") $(grep -E '"(fits|ratio|checked)"' "$E/${2%.png}-fit.json" | tr -d '\n ')"
fi
sleep 1
uv run python $E/gui.py shot "$2"
