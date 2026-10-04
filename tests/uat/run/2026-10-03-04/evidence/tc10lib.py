"""TC-10 helpers: GUI MCP over :8765, direct RPC to the in-FreeCAD listener, H1 stdio host,
GUI window capture via gui.py, and the incremental results file. Run with `uv run python`."""
from __future__ import annotations

import contextlib
import glob
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

E = Path(__file__).resolve().parent
REPO = E.parents[4]
GOLD = REPO / "benchmarks" / "g0" / "golden-models"
BOX = str(GOLD / "box-10-20-30.FCStd").replace("\\", "/")
CYL = str(GOLD / "cylinder-r5-h20.FCStd").replace("\\", "/")
APPDIR = os.path.expandvars(r"%APPDATA%/FreeCAD/v1-1/freecad-buddy")
ADDON_LOG = f"{APPDIR}/addon.log"
sys.path.insert(0, str(E))


class Log:
    def __init__(self, name: str):
        self.path = E / name
        self.f = open(self.path, "a", encoding="utf-8")

    def write(self, rec: dict) -> None:
        rec = {"t": round(time.time(), 3), **rec}
        self.f.write(json.dumps(rec, ensure_ascii=False, default=repr) + "\n")
        self.f.flush()


def _parse(r) -> dict:
    text = "".join(b.text for b in r.content if hasattr(b, "text"))
    try:
        env = json.loads(text)
    except json.JSONDecodeError:
        env = {"_raw": text}
    return env if isinstance(env, dict) else {"_value": env}


class Gui:
    """MCP over the H2 proxy at :8765."""

    def __init__(self, session, log, tag):
        self.s, self.log, self.tag = session, log, tag

    async def call(self, tool, args):
        t0 = time.time()
        env = _parse(await self.s.call_tool(tool, args))
        self.log.write({"host": "H2", "tag": self.tag, "tool": tool, "args": args,
                        "start": round(t0, 3), "seconds": round(time.time() - t0, 3), "envelope": env})
        return env


@contextlib.asynccontextmanager
async def gui(log, tag):
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            yield Gui(s, log, tag)


# ---------------------------------------------------------------- direct RPC to the listener

def fc_ids() -> tuple[int, int]:
    d = json.loads((E / "fc.json").read_text())
    return int(d["pid"]), int(d["window_id"])


def discovery() -> dict:
    pid, _ = fc_ids()
    return json.load(open(f"{APPDIR}/rpc-{pid}.json"))


class Rpc:
    """One raw NDJSON connection to the listener; logs every frame (token redacted)."""

    def __init__(self, log, tag, name="A", timeout=10.0):
        self.rec = discovery()
        self.log, self.tag, self.name = log, tag, name
        self.sock = socket.create_connection((self.rec["host"], self.rec["port"]), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""
        self.n = 0
        self.log.write({"tag": tag, "client": name, "event": "connect", "port": self.rec["port"]})

    def send_raw(self, data: bytes, note=""):
        self.sock.sendall(data)
        self.log.write({"tag": self.tag, "client": self.name, "event": "send_raw", "bytes": len(data), "note": note})

    def send(self, method, params=None):
        self.n += 1
        frame = {"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}
        shown = json.loads(json.dumps(frame))
        if "token" in shown["params"]:
            shown["params"]["token"] = "<discovery token>"
        self.sock.sendall((json.dumps(frame) + "\n").encode())
        self.log.write({"tag": self.tag, "client": self.name, "event": "send", "frame": shown})

    def recv_frame(self, timeout=None):
        if timeout is not None:
            self.sock.settimeout(timeout)
        t0 = time.time()
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                self.log.write({"tag": self.tag, "client": self.name, "event": "eof",
                                "partial": self.buf.decode(errors="replace")[:200]})
                return None
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        obj = json.loads(line)
        self.log.write({"tag": self.tag, "client": self.name, "event": "recv",
                        "seconds": round(time.time() - t0, 3), "frame": obj})
        return obj

    def hello(self, token=None, version=None):
        self.send("rpc_hello", {"token": token if token is not None else self.rec["token"],
                                "contract_version": version or self.rec["contract_version"]})
        return self.recv_frame()

    def call(self, method, params=None, timeout=None):
        self.send(method, params)
        fr = self.recv_frame(timeout)
        return (fr or {}).get("result", fr)

    def close(self):
        try:
            self.sock.close()
        finally:
            self.log.write({"tag": self.tag, "client": self.name, "event": "close"})


# ---------------------------------------------------------------- proxy stop / start

def proxy_stop() -> str:
    out = subprocess.run(["powershell", "-NoProfile", "-File", str(E / "tc-01-proxy-stop.ps1")],
                         capture_output=True, text=True)
    return out.stdout + out.stderr


def proxy_start(tag: str) -> str:
    """Restart the proxy by hand with the addon's own command (as TC-01 did)."""
    py = REPO / ".venv" / "Scripts" / "pythonw.exe"
    logf = open(E / f"tc-10-{tag}-proxy-restart.log", "w")
    subprocess.Popen([str(py), "-m", "freecad_buddy.hosts.main", "serve", "--mode", "rpc", "--transport", "http"],
                     cwd=str(REPO), stdout=logf, stderr=logf,
                     creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    for _ in range(60):
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
        if "127.0.0.1:8765" in r and "LISTENING" in r.split("127.0.0.1:8765", 1)[1].split("\n", 1)[0]:
            return "proxy listening"
        time.sleep(1)
    return "proxy NOT listening after 60 s"


def proxy_listening() -> bool:
    r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    return any("127.0.0.1:8765" in ln and "LISTENING" in ln for ln in r.splitlines())


# ---------------------------------------------------------------- GUI capture

def gui_py(*args) -> str:
    out = subprocess.run(["uv", "run", "python", str(E / "gui.py"), *args], capture_output=True, text=True,
                         cwd=str(REPO), timeout=120)
    return (out.stdout + out.stderr).strip()


def cua(tool: str, payload: dict) -> dict:
    out = subprocess.run(["cua-driver", tool], input=json.dumps(payload), capture_output=True, text=True, timeout=60)
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"_raw": out.stdout[:500], "_err": out.stderr[:500]}


def show_all() -> dict:
    pid, win = fc_ids()
    return cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Visibility", "Show All Objects"]})


def addon_log_lines() -> int:
    with open(ADDON_LOG, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def addon_log_since(n: int) -> list[str]:
    with open(ADDON_LOG, encoding="utf-8", errors="replace") as f:
        return f.readlines()[n:]


# ---------------------------------------------------------------- H1 headless host

FCB = os.path.expandvars(r"%USERPROFILE%\micromamba\envs\fcb")


def h1_env(extra=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = ";".join([rf"{FCB}\Library\bin", rf"{FCB}\Library\lib", str(REPO / "src"), str(E), str(E / "tc10_site")])
    env["PATH"] = rf"{FCB}\Library\bin;{FCB}\Library\lib;" + env["PATH"]
    env["PYTHONUTF8"] = "1"
    env.update(extra or {})
    return env


class H1:
    def __init__(self, session, log, tag):
        self.s, self.log, self.tag = session, log, tag

    async def call(self, tool, args):
        t0 = time.time()
        r = await self.s.call_tool(tool, args)
        t1 = time.time()
        env = _parse(r)
        self.log.write({"host": "H1", "tag": self.tag, "tool": tool, "args": args, "start": round(t0, 3),
                        "end": round(t1, 3), "seconds": round(t1 - t0, 3), "isError": bool(r.isError),
                        "envelope": env})
        return env


@contextlib.asynccontextmanager
async def h1(log, tag, errlog_path, extra=None):
    from mcp import StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=rf"{FCB}\python.exe",
                                   args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio",
                                         "--mode", "inline"], env=h1_env(extra))
    with open(errlog_path, "w", encoding="utf-8") as err:
        async with stdio_client(params, errlog=err) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                yield H1(s, log, tag)


# ---------------------------------------------------------------- results

RESULTS = E / "tc-10-results.json"


def result(id_, priority, verdict, evidence, note):
    data = json.loads(RESULTS.read_text()) if RESULTS.exists() else []
    data = [r for r in data if r["id"] != id_]
    data.append({"id": id_, "priority": priority, "verdict": verdict, "evidence": evidence, "note": note})
    data.sort(key=lambda r: r["id"])
    RESULTS.write_text(json.dumps(data, indent=1, ensure_ascii=False))
