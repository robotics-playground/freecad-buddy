# Native FreeCAD Part > Check Geometry on one open document, driven with cua-driver.
# Usage: PID=<freecad pid> WIN=<main window_id> bash cg_native.sh <document label> <tag>
# Prints the result row, Solids and Volume read from FreeCAD's own Check Geometry panel,
# and saves evidence/cg-<tag>.png. Aborts on any step it cannot verify.
: "${PID:?set PID}" "${WIN:?set WIN}"
doc=$1; tag=$2; HERE=$(dirname "$0"); WSF="$TEMP/ws.json"; W=$(cygpath -w "$WSF")
WS() { echo "{\"pid\":$PID,\"window_id\":$WIN,\"include_screenshot\":false}" | timeout 60 cua-driver get_window_state > "$WSF" 2>&1; }
DCLICK() { echo "{\"target\":{\"kind\":\"desktop\",\"display_id\":\"primary\"},\"x\":$1,\"y\":$2}" | timeout 30 cua-driver click > /dev/null 2>&1; sleep ${3:-1}; }
TITLE() { echo "{\"pid\":$PID}" | timeout 20 cua-driver list_windows 2>&1 | grep -m1 '"title"' | sed 's/.*"title": "\(.*\)",/\1/'; }
dialog_open() { WS; [ -n "$(python "$HERE/ui.py" "$W" button "Run check")" ]; }

# 1. Close any open task dialog. A Check Geometry task binds to the document active when it opened.
for i in 1 2 3; do dialog_open || break; XY=$(python "$HERE/ui.py" "$W" button "Close"); DCLICK $XY 2; done
dialog_open && { echo "ABORT: task dialog will not close"; exit 1; }

# 2. Activate the document: Ctrl+Tab until the window title names it.
for i in $(seq 1 20); do case "$(TITLE)" in *"$doc - FreeCAD"*) break;; esac
  echo "{\"pid\":$PID,\"keys\":[\"ctrl\",\"tab\"],\"delivery_mode\":\"foreground\"}" | timeout 30 cua-driver hotkey > /dev/null 2>&1; sleep 1; done
case "$(TITLE)" in *"$doc - FreeCAD"*) ;; *) echo "ABORT: cannot activate $doc"; exit 1;; esac

# 3. Select the document's Body row (expand the document row with the Right key if needed).
WS; XY=$(python "$HERE/ui.py" "$W" bodyunder "$doc")
if [ -z "$XY" ]; then
  XY=$(python "$HERE/ui.py" "$W" tree "$doc"); DCLICK $XY
  echo "{\"pid\":$PID,\"key\":\"right\",\"delivery_mode\":\"foreground\"}" | timeout 30 cua-driver press_key > /dev/null 2>&1; sleep 0.5
  WS; XY=$(python "$HERE/ui.py" "$W" bodyunder "$doc")
fi
[ -z "$XY" ] && { echo "ABORT: no Body row under $doc"; exit 1; }
DCLICK $XY

# 4. Part > Check Geometry (Part workbench toolbar button; screen position on a 2560x1440 display),
#    then Run check. A click on the button can land as a hover only, so try up to 3 times.
for i in 1 2 3; do DCLICK 1490 215 3; dialog_open && break; done
dialog_open || { echo "ABORT: Check Geometry did not open"; exit 1; }
XY=$(python "$HERE/ui.py" "$W" button "Run check"); DCLICK $XY 4

# 5. Read FreeCAD's own result and save a desktop screenshot.
WS; python "$HERE/ui.py" "$W" text > "$TEMP/sc.txt"
echo '{}' | timeout 60 cua-driver get_desktop_state > "$TEMP/d.json" 2>&1
python - "$(cygpath -w "$TEMP/d.json")" "$tag" "$(cygpath -w "$TEMP/sc.txt")" "$W" "$(cygpath -w "$HERE")" <<'PY'
import json, base64, sys, re, os
d = json.load(open(sys.argv[1], encoding="utf-8"))
open(os.path.join(sys.argv[5], "cg-%s.png" % sys.argv[2]), "wb").write(base64.b64decode(d["screenshot_png_b64"]))
text = open(sys.argv[3], encoding="utf-8").read(); w = json.load(open(sys.argv[4], encoding="utf-8"))
rows = [e.get("label") for e in w["elements"] if (e.get("label") or "").endswith(".Body")]
inv = [e.get("label") for e in w["elements"] if "invalid shape" in (e.get("label") or "") or "No errors" in (e.get("label") or "")]
last = text.split("Checked object")[-1]; g = lambda k: (re.search(k + r":\s+(\S+)", last) or [None, None])[1]
print(json.dumps({"tag": sys.argv[2], "rows": rows[:2], "solids": g("Solids"), "volume": g("Volume"), "status": inv[:2]}))
PY
