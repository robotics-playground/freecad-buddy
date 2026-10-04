"""TC-11 direct-RPC helpers: reuse tc10lib's raw NDJSON client and proxy stop/start (AD-26 single client)."""
import json
import os
import socket
import subprocess

import time
from pathlib import Path

from tc10lib import APPDIR, Rpc, discovery, proxy_listening, proxy_stop  # noqa: F401

E = Path(__file__).resolve().parent
REPO = E.parents[4]


def proxy_start(tag):
    """Restart the proxy by hand with the addon's own command (.venv pythonw, detached), as TC-01/TC-10 did."""
    logf = open(E / f"{tag}-proxy-restart.log", "w")
    subprocess.Popen([str(REPO / ".venv" / "Scripts" / "pythonw.exe"), "-m", "freecad_buddy.hosts.main", "serve",
                      "--mode", "rpc", "--transport", "http"], cwd=str(REPO), stdout=logf, stderr=logf,
                     creationflags=0x00000008 | 0x00000200)
    for _ in range(60):
        if proxy_listening():
            return "proxy listening"
        time.sleep(1)
    return "proxy NOT listening after 60 s"

LAN_IP = "192.168.50.13"


def netstat_port(port):
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    return [ln.strip() for ln in out.splitlines() if f":{port} " in ln and "LISTENING" in ln]


def lan_connect(port, host=LAN_IP, timeout=3.0):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
    except OSError as exc:
        return {"connected": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        s.settimeout(timeout)
        s.sendall(b'{"jsonrpc":"2.0","id":1,"method":"rpc_hello","params":{}}\n')
        data = s.recv(4096)
        return {"connected": True, "reply": data.decode(errors="replace")[:200]}
    except OSError as exc:
        return {"connected": True, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        s.close()


def discovery_files():
    return sorted(f for f in os.listdir(APPDIR) if f.startswith("rpc-") and f.endswith(".json"))


def read_record(pid):
    return json.load(open(f"{APPDIR}/rpc-{pid}.json", encoding="utf-8"))
