# usage: fitcap.sh <pid> <window_id> <doc handle> <tag>  -> <tag>-before.png, <tag>-fit-mcp.json, <tag>-after.png
P=$1; W=$2; D=$3; T=$4
E=D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-05-01/evidence
cd /d/Work/Personal/Sources/freecad-buddy
printf '{"pid":%s,"window_id":%s,"screenshot_out_file":"%s"}' $P $W "$E/$T-before.png" | cua-driver get_window_state > /dev/null
LOGTAG=$T uv run python $E/run.py call view_fit_viewport "{\"doc\":\"$D\"}" > $E/$T-fit-mcp.json
sleep 1
printf '{"pid":%s,"window_id":%s,"screenshot_out_file":"%s"}' $P $W "$E/$T-after.png" | cua-driver get_window_state > /dev/null
grep -E '"status"|"code"|fitted|"fits"|ratio|checked' $E/$T-fit-mcp.json
