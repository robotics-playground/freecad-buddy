"""Quit FreeCAD cleanly (close docs, File>Exit), stop an orphan hand-started proxy, relaunch clean via launch.sh.

python tc11cycle.py <tag> [quit-only]   -> prints JSON; updates fc.json and launch-log.tsv on relaunch.
"""
import asyncio
import datetime
import json
import os
import re
import subprocess
import sys
import time

from tc03lib import cua, ids
from tc11lib import EVIDENCE, Log, Mcp, close_all
from tc11rpc import APPDIR, proxy_listening, proxy_stop

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

REPO = "D:/Work/Personal/Sources/freecad-buddy"


def alive(pid):
    return str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout


async def close_docs(tag):
    log = Log(f"{tag}-cycle")
    if proxy_listening():
        async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                await close_all(Mcp(s, log), log)
    log.save()


def quit_fc(tag):
    pid, win = ids()
    import threading
    worker = threading.Thread(target=lambda: asyncio.run(close_docs(tag)))
    worker.start()
    worker.join()
    r = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["File", "Exit"]})
    for _ in range(60):
        if not alive(pid):
            break
        time.sleep(1)
    out = {"old_pid": pid, "exit_menu": {"effect": r.get("effect"), "error": r.get("error")}, "exited": not alive(pid),
           "discovery_file_after_quit_exists": os.path.exists(f"{APPDIR}/rpc-{pid}.json")}
    if proxy_listening():
        out["orphan_proxy_stop"] = proxy_stop().replace("\n", " | ")
    out["port_8765_free"] = not proxy_listening()
    return out


def relaunch(tag):
    r = subprocess.run(["C:/Program Files/Git/usr/bin/bash.exe", "-l",f"{EVIDENCE.as_posix()}/launch.sh", tag], capture_output=True, text=True, timeout=300)
    m = re.search(r"pid=(\d+) window_id=(\d+)", r.stdout)
    pid, win = int(m.group(1)), int(m.group(2))
    ns = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    owner = next((ln.split()[-1] for ln in ns.splitlines() if "127.0.0.1:8765" in ln and "LISTENING" in ln), None)
    spawned = None
    if owner:
        q = subprocess.run(["powershell", "-NoProfile", "-c",
                            f"(Get-CimInstance Win32_Process -Filter 'ProcessId={owner}').ParentProcessId"],
                           capture_output=True, text=True).stdout.strip()
        spawned = int(q) if q.isdigit() else None
    fc = {"pid": pid, "window_id": win, "proxy_listener_pid": int(owner) if owner else None,
          "proxy_spawned_pid": spawned, "freecad_version": "1.1.4"}
    (EVIDENCE / "fc.json").write_text(json.dumps(fc), encoding="utf-8")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "status", "--short", "src"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with open(EVIDENCE / "launch-log.tsv", "a", encoding="utf-8") as f:
        f.write(f"{now}\t{pid}\t{head}\t{tag} relaunch (no extra env) via launch.sh; proxy :8765 owner {owner} parent {spawned}; "
                f"git status --short src: [{st}]\n")
    return {"launch_stdout": r.stdout[-1500:], "fc": fc, "head": head, "src_dirty": bool(st)}


if __name__ == "__main__":
    tag = sys.argv[1]
    res = {"quit": quit_fc(tag)}
    if len(sys.argv) < 3:
        res["relaunch"] = relaunch(tag)
    (EVIDENCE / f"{tag}-cycle.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
