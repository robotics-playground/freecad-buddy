# source r3_env.sh: sets PID and WID of the running FreeCAD and defines helpers cc (cua call), wins, menu.
PID=$(powershell -NoProfile -c "(Get-Process freecad -EA SilentlyContinue | Select-Object -First 1).Id" | tr -d '\r\n')
WID=$(cua-driver call list_windows "{\"pid\":$PID}" | python -c "import json,sys; ws=json.load(sys.stdin)['windows']; print(max(ws,key=lambda w:w['bounds']['width']*w['bounds']['height'])['window_id'])")
wins(){ cua-driver call list_windows "{\"pid\":$PID}" | python -c "import json,sys; print([(w['window_id'],w['title']) for w in json.load(sys.stdin)['windows']])"; }
menu(){ cua-driver call invoke_menu "{\"pid\":$PID,\"window_id\":$WID,\"path\":$1}" | tr -d '\n '; echo; }
key(){ echo "{\"pid\":$PID,\"window_id\":$WID,\"key\":\"$1\"${2:+,\"delivery_mode\":\"foreground\"}}" | cua-driver call press_key | tr -d '\n '; echo; }
nextra(){ cua-driver call list_windows "{\"pid\":$PID}" | python -c "import json,sys; print(len([w for w in json.load(sys.stdin)['windows'] if w['window_id']!=$WID]))"; }
closepop(){ sleep 1.5; for i in 1 2 3 4; do n=$(nextra); [ "$n" = "0" ] && break; key escape >/dev/null; sleep 1; done; wins; }
