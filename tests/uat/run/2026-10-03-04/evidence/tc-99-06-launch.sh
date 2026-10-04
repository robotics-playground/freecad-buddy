# usage: tc-99-06-launch.sh A|B  -> launches FreeCAD through cua-driver launch_app with the dir-X .cmd wrapper
cd /d/Work/Personal/Sources/freecad-buddy
E=tests/uat/run/2026-10-03-04/evidence
LOG="$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"
BEFORE=$(wc -l < "$LOG")
cat $E/tc-99-06-launch-$1.json | cua-driver launch_app > /dev/null 2>&1
for i in $(seq 1 45); do netstat -ano | grep -q "127.0.0.1:8765 .*LISTENING" && break; sleep 2; done
sleep 3
P=$(powershell -NoProfile -c "(Get-Process freecad -EA SilentlyContinue).Id")
W=$(echo "{\"pid\":$P}" | cua-driver list_windows 2>&1 | grep -m1 window_id | tr -dc 0-9)
echo "tag=tc-99-06-dir$1 pid=$P window_id=$W bridge_wait=$((i*2))s"
netstat -ano | grep "127.0.0.1:8765 .*LISTENING" || echo "NO :8765 LISTENER"
echo "--- new addon.log lines ---"
tail -n +$((BEFORE+1)) "$LOG"
