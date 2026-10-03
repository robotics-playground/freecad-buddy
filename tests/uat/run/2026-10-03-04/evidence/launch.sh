# usage: launch.sh <tag>  -> prints pid, window_id, bridge wait, new addon.log lines
cd /d/Work/Personal/Sources/freecad-buddy
LOG="$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"
BEFORE=$(wc -l < "$LOG")
cat _automation/uat/launch.json | cua-driver launch_app > /dev/null 2>&1
for i in $(seq 1 45); do netstat -ano | grep -q "127.0.0.1:8765 .*LISTENING" && break; sleep 2; done
sleep 3
P=$(powershell -NoProfile -c "(Get-Process freecad -EA SilentlyContinue).Id")
W=$(echo "{\"pid\":$P}" | cua-driver list_windows 2>&1 | grep -m1 window_id | tr -dc 0-9)
echo "tag=$1 pid=$P window_id=$W bridge_wait=$((i*2))s"
netstat -ano | grep "127.0.0.1:8765 .*LISTENING" || echo "NO :8765 LISTENER"
echo "--- new addon.log lines ---"
tail -n +$((BEFORE+1)) "$LOG"
