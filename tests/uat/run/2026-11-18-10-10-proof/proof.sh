#!/bin/bash
# Runs each rewritten command kind once against the fcb-desktop container and saves the output as
# <kind>.txt in this folder. Needs: container up, PROJECT_ROOT/RUN_DIR/FCB_* exported as in test-plan §6.
# Usage: bash proof.sh   (FreeCAD is started and stopped by this script)
# The K2-*.txt records (menu leaf presses) and K-proxy-restart.txt were made by hand with the commands
# written at the top of each file; this script does not rewrite them.
set -u
export MSYS_NO_PATHCONV=1
here="$(cd "$(dirname "$0")" && pwd)"
X="docker exec -u cua fcb-desktop"
run() { # run <kind> <description> <command...>   (command run through bash -c, output appended)
  local kind="$1" desc="$2"; shift 2
  { echo "## $desc"; echo "\$ $*"; bash -c "$*" 2>&1; echo "exit=$?"; echo; } >> "$here/$kind.txt"
}
: > "$here/K1.txt"; : > "$here/K1b.txt"; : > "$here/K3.txt"; : > "$here/K4.txt"; : > "$here/K5.txt"
: > "$here/K6.txt"; : > "$here/K7.txt"; : > "$here/K8.txt"; : > "$here/K9.txt"; : > "$here/K10.txt"

$X fcb-freecad stop >/dev/null 2>&1
$X sh -c "pkill -f 'serve --mode rpc'" >/dev/null 2>&1
sleep 3
run K4 "no FreeCAD process (TC-01-01 Given)" "$X pgrep -af '^/opt/freecad/usr/bin/freecad'"
run K10 "start FreeCAD with a variable and a file (TC-01-13, TC-16, TC-12 file open)" \
  "docker exec -u cua -e FREECAD_BUDDY_AUDIT_LOG=\$RUN_DIR_C/audit-proof.jsonl fcb-desktop fcb-freecad start /repo/benchmarks/g0/golden-models/box-10-20-30.FCStd"
sleep 3
PID=$($X pgrep -f '^/opt/freecad/usr/bin/freecad' | head -1)
[ -n "$PID" ] || { echo "proof.sh: FreeCAD did not start" >&2; exit 1; }
ready=no
for i in $(seq 1 60); do
  h=$(curl -fsS --max-time 2 http://127.0.0.1:18765/healthz 2>/dev/null)
  if echo "$h" | grep -q "freecad_pid\":$PID"; then ready=yes; break; fi
  sleep 3
done
[ "$ready" = yes ] || { echo "proof.sh: the proxy never pinned to FreeCAD pid $PID" >&2; exit 1; }
sleep 5
echo "healthz: $h" >> "$here/K10.txt"
run K10 "operator settings line shows the audit log from the environment (env)" "$X grep 'operator settings:' \"\$FCB_USER_DIR/freecad-buddy/addon.log\" | tail -1"

run K1 "list_windows (TC-01 step)" "echo '{\"pid\":$PID}' | \"\$FCB_CUA\" list_windows"
WID=$(echo "{\"pid\":$PID}" | "$FCB_CUA" list_windows | python -c "import json,sys;print(json.load(sys.stdin)['windows'][0]['window_id'])")
run K1 "get_window_state with a screenshot under \$RUN_DIR (the wrapper maps it to /repo)" \
  "echo '{\"pid\":$PID,\"window_id\":$WID,\"screenshot_out_file\":\"\$RUN_DIR/K1-window.png\"}' | \"\$FCB_CUA\" get_window_state | head -c 300; ls -l \"\$RUN_DIR/K1-window.png\""
run K1b "status" "\"\$FCB_CUA\" status | head -3"

run K3 "port owner of :8765 (TC-01-01)" "$X ss -ltnp | grep :8765"
run K3 "port owner, netstat form kept for reference" "$X netstat -tlnp | grep :8765"
PROXY=$($X ss -ltnp | grep ':8765' | sed -E 's/.*pid=([0-9]+).*/\1/')
run K4 "FreeCAD process list (TC-01 Then)" "$X pgrep -af '^/opt/freecad/usr/bin/freecad'"
run K4 "one pid shows its command (TC-01-01 pid check)" "$X ps -p $PID -o pid=,comm="
run K4 "count of FreeCAD processes (TC-01-09)" "$X pgrep -fc '^/opt/freecad/usr/bin/freecad'"
run K4 "a dead pid prints nothing, exit 1" "$X ps -p 999996 -o pid="
run K5 "CPU seconds (TC-10-07)" "$X ps -o cputimes= -p $PID"
run K5 "resident KiB (TC-10-14)" "$X ps -o rss= -p $PID"
run K5 "proxy command line (TC-01-01)" "$X sh -c \"tr '\\0' ' ' < /proc/$PROXY/cmdline\""
run K5 "only one serve process (TC-01-01)" "$X pgrep -af 'hosts.main serve'"
run K6 "grep user.cfg (TC-06 AA preference)" "$X grep -c AntiAliasing \"\$FCB_CONFIG_DIR/user.cfg\""
run K6 "test -e repo file (TC-12-04)" "test -e benchmarks/g0/golden-models/box-10-20-30.FCStd && echo True"
run K6 "stat of a run-folder file (TC-12-08)" "stat -c %y \"\$RUN_DIR/K1-window.png\""
run K6 "find in the session tmp (TC-06)" "$X find \"\$FCB_USER_DIR/freecad-buddy/workdir/tmp\" -name 'FCB_TMP_shot_*.png'"
run K6 "the example file TC-12-15 opens exists in the container" "$X ls -l /opt/freecad/usr/share/examples/ArchDetail.FCStd"
run K7 "ls the user data folder (TC-01-08)" "$X ls \"\$FCB_USER_DIR/freecad-buddy\""
run K7 "grep addon.log (TC-01-01)" "$X grep 'spawned MCP proxy' \"\$FCB_USER_DIR/freecad-buddy/addon.log\""
run K7 "tail addon.log (TC-12-14)" "$X tail -n 3 \"\$FCB_USER_DIR/freecad-buddy/addon.log\""
run K7 "mv addon.log aside, then back (TC-01-01 rotation)" "$X mv \"\$FCB_USER_DIR/freecad-buddy/addon.log\" \"\$FCB_USER_DIR/freecad-buddy/addon.log.prev\" && $X mv \"\$FCB_USER_DIR/freecad-buddy/addon.log.prev\" \"\$FCB_USER_DIR/freecad-buddy/addon.log\"; echo moved"
run K7 "discovery file mode (TC-01-09, TC-11-07)" "$X stat -c '%a %n' \"\$FCB_USER_DIR/freecad-buddy/rpc-$PID.json\""
run K8 "FCB_PYTHON runs a script in the container, RUN_DIR mapped (TC-11-19 sleeper form)" \
  "\"\$FCB_PYTHON\" -c \"import os; open(r'\$RUN_DIR/K8-sleeper.pid','w').write(str(os.getpid())); print('wrote', os.getpid())\"; cat \"\$RUN_DIR/K8-sleeper.pid\""
run K8 "FCB_PYTHON imports the addon and FreeCAD (TC-07 trimesh, lib3mf form)" "\"\$FCB_PYTHON\" -c \"import trimesh, lib3mf, FreeCAD; print('imports ok', FreeCAD.Version()[:3])\""
run K8 "OS temp count in /tmp (TC-11-18)" "$X sh -c \"find /tmp -maxdepth 1 -name 'FCB_TMP_*' | wc -l\""
run K8 "installed addon hash equals dist/addon (TC-16 Given)" \
  "$X sha256sum \"\$FCB_USER_DIR/Mod/FreeCADBuddy/freecad_buddy/__init__.py\"; sha256sum dist/addon/freecad_buddy/__init__.py"
run K9 "relay healthz from the host (TC-01-14)" "curl -s http://127.0.0.1:18765/healthz"
run K9 "in-container loopback healthz (TC-01-15)" "$X curl -s http://127.0.0.1:8765/healthz"
run K9 "container LAN address (TC-11-05)" "$X hostname -I"
LAN=$($X hostname -I | awk '{print $1}')
run K9 "LAN address refused on :8765 (TC-11-06)" "$X curl -s -m 3 http://$LAN:8765/mcp; echo curl_exit=\$?"
run K9 "nc to the listener port on the LAN address is refused (TC-11-05)" "$X nc -zv -w 2 $LAN 8765"
run K9 "relay reaches the MCP endpoint (TC-10 H2 precondition)" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18765/mcp"
run K10 "close_all.py runs in the container (TC-16 Cleanup)" "$X fcb-py /repo/_automation/uat/close_all.py"
run K10 "foreign holder on :8765 (TC-01-15), then removed" \
  "$X sh -c \"pkill -f 'serve --mode rpc' ; sleep 2\"; docker exec -d -u cua fcb-desktop fcb-py -m http.server 8765 --bind 127.0.0.1; sleep 3; $X ss -ltnp | grep :8765; $X pkill -f 'http.server 8765'; sleep 1; $X ss -ltnp | grep :8765 || echo holder-gone"

# TC-11-19 plant and cleanup blocks, copied from the test case with D, L set
SLEEP_PID=$(cat "$RUN_DIR/K8-sleeper.pid")
T="$FCB_USER_DIR/freecad-buddy/workdir/tmp"
run K8 "TC-11-19 plant block" "D=999996; docker exec -u cua -e T=\"$T\" -e D=\$D -e L=$SLEEP_PID fcb-desktop sh -c '
mkdir -p \"\$T/FCB_TMP_session_\${D}_deadbeef/FCB_TMP_snap_x\" && echo x > \"\$T/FCB_TMP_session_\${D}_deadbeef/FCB_TMP_snap_x/Doc.FCStd\"
mkdir -p \"\$T/FCB_TMP_snap_orphan\" && echo x > \"\$T/FCB_TMP_snap_orphan/Doc.FCStd\"
mkdir -p \"\$T/FCB_TMP_session_\${L}_cafebabe\" && echo x > \"\$T/FCB_TMP_session_\${L}_cafebabe/keep.txt\"
mkdir -p \"\$T/not-reserved\" && echo x > \"\$T/not-reserved/keep.txt\"
echo x > \"\$T/keep-me.txt\"
mkdir -p /tmp/FCB_TMP_snap_tc1119'; $X ls -R \"$T\"; $X ls -d /tmp/FCB_TMP_snap_tc1119"
run K8 "TC-11-19 cleanup block" "docker exec -u cua -e T=\"$T\" -e L=$SLEEP_PID fcb-desktop sh -c 'rm -rf \"\$T/FCB_TMP_session_\${L}_cafebabe\" \"\$T/FCB_TMP_session_999996_deadbeef\" \"\$T/FCB_TMP_snap_orphan\" \"\$T/not-reserved\" \"\$T/keep-me.txt\" /tmp/FCB_TMP_snap_tc1119'; $X ls \"$T\"; echo cleaned"
rm -f "$RUN_DIR/K8-sleeper.pid"

# K4/K5 kill forms against a scratch process, then FreeCAD itself (TC-12-15 form)
run K4 "kill and kill -KILL a scratch sleeper" "docker exec -d -u cua fcb-desktop sleep 600; sleep 1; S=\$($X pgrep -f 'sleep 600'); echo sleeper=\$S; $X kill \$S; sleep 1; $X ps -p \$S -o pid= ; echo gone_exit=\$?"
run K4 "kill -KILL FreeCAD (TC-12-15 unclean kill) and read the survivors" \
  "$X kill -KILL $PID; sleep 4; $X pgrep -af '^/opt/freecad/usr/bin/freecad'; echo pgrep_exit=\$?; $X ss -ltnp | grep :8765; echo ss_exit=\$?; curl -s -m 3 http://127.0.0.1:18765/healthz; echo relay_exit=\$?"
$X fcb-freecad stop >/dev/null 2>&1
$X sh -c "pkill -f 'serve --mode rpc'" >/dev/null 2>&1
echo "done"
