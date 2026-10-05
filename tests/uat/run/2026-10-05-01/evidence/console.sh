# usage: console.sh <pid> <window_id> '<python line>' <crop png out>
# Types the line into the FreeCAD Python console (UIA text write), presses Return with a foreground pixel
# press on the console (background Return is dropped), then saves a crop of the console as evidence.
P=$1; W=$2; CODE=$3; OUT=$4
S="C:/Users/thuan/AppData/Local/Temp/claude/D--Work-Personal-Sources-freecad-buddy/c5df8eea-9ec5-41e2-ac28-240b6fc099fd/scratchpad"
cd /d/Work/Personal/Sources/freecad-buddy
echo "{\"pid\":$P,\"window_id\":$W,\"include_screenshot\":false}" | cua-driver get_window_state > "$S/cst.json"
read TOK X Y FY FH < <(uv run python -c "
import json;d=json.load(open(r'$S/cst.json'))
win=[e['element_index'] for e in d['elements'] if e.get('role')=='Window' and e.get('label')=='Python Console']
e=[e for e in d['elements'] if win and e.get('parent_index')==win[0] and e.get('role')=='Edit'][0]
f=e['frame']; print(e['element_token'], f['x']+f['w']//2, f['y']+f['h']-12, f['y'], f['h'])")
[ -z "$TOK" ] && { echo "console edit not found"; exit 1; }
uv run python -c "import json,sys;print(json.dumps({'pid':$P,'element_token':sys.argv[1],'text':sys.argv[2]}))" "$TOK" "$CODE" | cua-driver type_text > /dev/null
echo "{\"pid\":$P,\"window_id\":$W,\"x\":$X,\"y\":$Y,\"key\":\"return\",\"delivery_mode\":\"foreground\"}" | cua-driver press_key > /dev/null
sleep 1
# The first foreground press can be spent activating the window; a second Return on an empty prompt is harmless.
echo "{\"pid\":$P,\"window_id\":$W,\"x\":$X,\"y\":$Y,\"key\":\"return\",\"delivery_mode\":\"foreground\"}" | cua-driver press_key > /dev/null
sleep 2
printf '{"pid":%s,"window_id":%s,"screenshot_out_file":"%s"}' $P $W "$S/cfull.png" | cua-driver get_window_state > /dev/null
uv run --with pillow python -c "
from PIL import Image; im=Image.open(r'$S/cfull.png'); im.crop((0,$FY-20,im.size[0],$FY+$FH)).save(r'$OUT')"
echo "crop -> $OUT"
