"""TC-11-05: the RPC listener binds loopback only."""
import asyncio
import os
import subprocess

from tc11lib import *  # noqa: F401,F403
from tc11lib import EVIDENCE, Log, Mcp, baseline, closing, mask
from tc11rpc import LAN_IP, Rpc, discovery, lan_connect, netstat_port, proxy_start, proxy_stop

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-05"


async def session(fn):
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


async def main():
    log = Log(TAG)
    rec = discovery()
    port = rec["port"]
    lines0 = netstat_port(port)
    log.check("Given listener LISTENING on discovery port", bool(lines0), lines0)
    ip = subprocess.run(["ipconfig"], capture_output=True, text=True).stdout
    log.check("Given LAN IPv4 known", LAN_IP in ip, LAN_IP)

    async def given(s):
        m = Mcp(s, log)
        return await baseline(m, log, TAG)
    doc = await session(given)

    # When
    log.note(f"listener port from discovery rpc-{rec['pid']}.json: {port}; token {mask(rec['token'])}")
    lines = netstat_port(port)
    log.write({"netstat": lines})
    log.check("Then netstat local address is 127.0.0.1:<port>", bool(lines) and all(ln.split()[1] == f"127.0.0.1:{port}" for ln in lines), lines)
    log.check("Then discovery host is 127.0.0.1", rec.get("host") == "127.0.0.1", rec.get("host"))
    lan = lan_connect(port)
    log.write({"lan_connect": lan})
    log.check("Then LAN-IP connect refused or times out with no handshake",
              not lan["connected"] or "reply" not in lan or not lan.get("reply"), lan)
    log.note("stop proxy (AD-26 single client holds the listener) -> " + proxy_stop().replace("\n", " | "))
    try:
        c = Rpc(log, TAG, "loopback", timeout=15)
        hello = c.hello()
        c.close()
        res = (hello or {}).get("result") or {}
        log.check("Then loopback connect completes rpc_hello, contract_version \"1\"", res.get("contract_version") == "1",
                  {"keys": sorted(res), "contract_version": res.get("contract_version")})
    except OSError as exc:
        log.check("Then loopback connect completes rpc_hello, contract_version \"1\"", False, repr(exc))
    log.check("Then exactly one LISTENING line for the port", len(netstat_port(port)) == 1, netstat_port(port))
    started = proxy_start(TAG)
    log.note(f"proxy restart by hand (addon command, .venv pythonw): {started}")

    async def close_visual(s):
        await closing(Mcp(s, log), log, doc, TAG)
    await session(close_visual)
    log.save()


asyncio.run(main())
