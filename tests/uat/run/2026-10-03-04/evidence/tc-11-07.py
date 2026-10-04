"""TC-11-07: discovery file 0600 + token (probe part; the quit/not-found Then runs in tc-11-07-quit.sh)."""
import asyncio
import json
import os
import stat
import subprocess

from tc11lib import *  # noqa: F401,F403
from tc11lib import EVIDENCE, Log, Mcp, baseline, closing, mask
from tc11rpc import APPDIR, Rpc, discovery_files, proxy_start, proxy_stop
from tc03lib import ids

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-07"


async def session(fn):
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


async def main():
    log = Log(TAG)
    pid, _ = ids()
    path = f"{APPDIR}/rpc-{pid}.json"
    log.check("Given discovery file for running pid exists", os.path.exists(path), os.path.basename(path))

    async def given(s):
        return await baseline(Mcp(s, log), log, TAG)
    doc = await session(given)

    files = discovery_files()
    live = [f for f in files if f == f"rpc-{pid}.json"]
    log.note(f"ls rpc-*.json: {files}")
    others = []
    for f in files:
        p = int(f[4:-5])
        alive = subprocess.run(["tasklist", "/FI", f"PID eq {p}", "/NH"], capture_output=True, text=True).stdout
        if f != f"rpc-{pid}.json":
            others.append({"file": f, "pid_alive": str(p) in alive, "mtime": os.path.getmtime(f"{APPDIR}/{f}")})
    log.write({"other_discovery_files": others})
    log.check("Then exactly one discovery file for the live listener pid, named rpc-<pid>.json", len(live) == 1, live)
    log.note(f"{len(others)} other rpc-*.json files exist, none for a live pid: {all(not o['pid_alive'] for o in others)}; "
             f"newest mtime {max((o['mtime'] for o in others), default=0):.0f} (pre-date this run)")
    st = os.stat(path)
    attrib = subprocess.run(["attrib", path.replace("/", "\\")], capture_output=True, text=True).stdout.strip()
    acl = subprocess.run(["icacls", path.replace("/", "\\")], capture_output=True, text=True).stdout.strip()
    log.write({"stat_mode": oct(st.st_mode), "attrib": attrib, "icacls": acl})
    log.check("Then not world-readable (Windows: record what chmod did; ACL is owner/SYSTEM/Administrators only)",
              "Everyone" not in acl and "BUILTIN\\Users" not in acl and "Authenticated Users" not in acl,
              {"mode": oct(stat.S_IMODE(st.st_mode)), "readonly_bit": not (st.st_mode & stat.S_IWRITE), "attrib": attrib[:30],
               "acl_principals": [ln.split(":")[0].split()[-1] for ln in acl.splitlines()[:3]]})
    rec = json.load(open(path, encoding="utf-8"))
    log.check("Then record carries non-empty token (masked)", isinstance(rec.get("token"), str) and bool(rec["token"]), mask(rec.get("token")))
    log.check("Then contract_version is \"1\"", rec.get("contract_version") == "1", rec.get("contract_version"))

    log.note("stop proxy -> " + proxy_stop().replace("\n", " | "))
    c = Rpc(log, TAG, "wrong-token", timeout=15)
    reply = c.hello(token="tc11-wrong-token-" + "x" * 20)
    nxt = None
    try:
        nxt = c.recv_frame(timeout=5)
    except OSError as exc:
        nxt = repr(exc)
    c.close()
    err = (reply or {}).get("error") or {}
    log.write({"wrong_token_reply": reply, "next": nxt})
    log.check("Then wrong token refused: error frame message exactly 'auth failed'", err.get("message") == "auth failed", reply)
    log.check("Then refusal discloses nothing (no data.supported, no capabilities, no result)",
              "result" not in (reply or {}) and "supported" not in json.dumps(err.get("data") or {}) and "capabilities" not in json.dumps(reply),
              {"error_keys": sorted(err), "data": err.get("data")})
    log.note(f"proxy restart: {proxy_start(TAG)}")

    async def close_visual(s):
        await closing(Mcp(s, log), log, doc, TAG)
    await session(close_visual)
    log.save()


asyncio.run(main())
