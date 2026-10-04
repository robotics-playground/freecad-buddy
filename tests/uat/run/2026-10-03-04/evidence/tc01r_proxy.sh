# usage: tc01r_proxy.sh stop|start <logfile>  -- stop: TerminateProcess the :8765 listener and its .venv launcher (FreeCAD untouched)
# start: run the addon's own proxy command detached, wait for :8765 LISTENING
R=D:/Work/Personal/Sources/freecad-buddy; E=$R/tests/uat/run/2026-10-03-04/evidence
case "$1" in
 stop) powershell -NoProfile -ExecutionPolicy Bypass -File "$E/tc-01-proxy-stop.ps1" ;;
 start) cd $R; nohup .venv/Scripts/pythonw.exe -m freecad_buddy.hosts.main serve --mode rpc --transport http > "$E/$2" 2>&1 &
   disown; for i in $(seq 1 30); do netstat -ano | grep -q "127.0.0.1:8765 .*LISTENING" && break; sleep 1; done
   echo "restarted by hand: .venv/Scripts/pythonw.exe -m freecad_buddy.hosts.main serve --mode rpc --transport http"; netstat -ano | grep "127.0.0.1:8765 .*LISTENING" || echo "NO :8765 LISTENER" ;;
esac
