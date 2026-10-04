# usage: tc01r_launch.sh <tag> [launch_app json file] [record]  (record = do not launch, only record the running FreeCAD)  -> launch via cua-driver launch_app, wait :8765 (max 30 s), write fc.json + launch-log.tsv
R=D:/Work/Personal/Sources/freecad-buddy; E=$R/tests/uat/run/2026-10-03-04/evidence; cd $R
LOG="$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"; BEFORE=$( [ -f "$LOG" ] && wc -l < "$LOG" || echo 0)
T=$(date +%Y-%m-%dT%H:%M:%S); J=$(cat "${2:-$R/_automation/uat/launch.json}")
[ "$3" = record ] || echo "$J" | cua-driver launch_app > /dev/null 2>&1
for i in $(seq 1 15); do netstat -ano | grep -q "127.0.0.1:8765 .*LISTENING" && break; sleep 2; done; sleep 3
P=$(powershell -NoProfile -c "(Get-Process freecad -EA SilentlyContinue).Id")
W=$(echo "{\"pid\":$P}" | cua-driver list_windows 2>&1 | grep -m1 '"window_id"' | tr -dc 0-9)
L=$(netstat -ano | grep "127.0.0.1:8765 .*LISTENING" | awk '{print $5}'); PP=""
[ -n "$L" ] && PP=$(powershell -NoProfile -c "(Get-CimInstance Win32_Process -Filter 'ProcessId=$L').ParentProcessId")
echo "{\"pid\": $P, \"window_id\": $W, \"proxy_listener_pid\": ${L:-null}, \"proxy_spawned_pid\": ${PP:-null}, \"freecad_version\": \"1.1.4\"}" > $E/fc.json
printf "%s\t%s\t%s\t%s launch via cua-driver launch_app %s; proxy :8765 owner %s parent %s; git status --short src: [%s]\n" "$T" "$P" "$(git rev-parse --short HEAD)" "$1" "$J" "${L:-none}" "${PP:-none}" "$(git status --short src)" >> $E/launch-log.tsv
echo "tag=$1 pid=$P window_id=$W :8765 owner=${L:-none} parent=${PP:-none}"; cat $E/fc.json
echo "--- new addon.log lines ---"; tail -n +$((BEFORE+1)) "$LOG"
