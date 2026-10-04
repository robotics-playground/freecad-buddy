"""TC-11-09: the session token is regenerated per listener start. Tokens stay in memory; only masks are logged."""
import asyncio
import json
import os
import time

from tc11lib import *  # noqa: F401,F403
from tc11lib import BOX, EVIDENCE, Log, Mcp, baseline, close_all, mask, sc, short, show_all
from tc03lib import fitall, ids, shot
from tc11rpc import APPDIR, Rpc, proxy_start, proxy_stop, read_record
from tc11cycle import quit_fc, relaunch

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-09"


async def session(fn):
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


async def main():
    log = Log(TAG)
    log.note("Operator acceptance of a FreeCAD restart: given by the run brief (relaunch procedure in RUN-CONTEXT).")

    async def given(s):
        m = Mcp(s, log)
        await close_all(m, log)
        o = await m.call("document_open", {"path": BOX})
        log.check("Given document_open box OK", o.get("status") == "OK", short(o))
    await session(given)
    log.note(f"GUI Show All Objects: {show_all()}")
    fa = fitall()
    time.sleep(1)
    log.check("Given framed via GUI Fit All (same path as the after capture)", fa.get("route") == "accessibility", fa)
    log.check("Given baseline captured", shot(f"{TAG}-before.png").get("exists"), f"{TAG}-before.png")

    old_pid, _ = ids()
    old = read_record(old_pid)["token"]
    log.note(f"old token (pid {old_pid}): {mask(old)}")
    q = quit_fc(TAG)
    log.write({"quit": q})
    rl = relaunch(TAG)
    log.write({"relaunch": {k: v for k, v in rl.items() if k != "launch_stdout"}, "launch_stdout": rl["launch_stdout"]})
    new_pid, _ = ids()
    new_rec = read_record(new_pid)
    new = new_rec["token"]
    log.note(f"new token (pid {new_pid}): {mask(new)}")
    log.check("Then second token differs from the first (compared in memory)", isinstance(new, str) and new and new != old,
              {"old": mask(old), "new": mask(new)})

    log.note("stop addon proxy so the listener accepts a raw client -> " + proxy_stop().replace("\n", " | "))
    c = Rpc(log, TAG, "old-token")
    r1 = c.hello(token=old)
    try:
        eof = c.sock.recv(1)
        eof_desc = f"recv returned {len(eof)} bytes"
    except OSError as exc:
        eof, eof_desc = None, repr(exc)
    c.close()
    log.check("Then OLD token refused: error message exactly 'auth failed'", ((r1 or {}).get("error") or {}).get("message") == "auth failed", r1)
    log.check("Then connection closed after refusal: next recv returns zero bytes", eof == b"", eof_desc)
    c = Rpc(log, TAG, "old-token-bad-version")
    r2 = c.hello(token=old, version="99")
    c.close()
    log.check("Then auth before version: OLD token + contract_version 99 -> 'auth failed'",
              ((r2 or {}).get("error") or {}).get("message") == "auth failed", r2)
    c = Rpc(log, TAG, "new-token")
    r3 = c.hello()
    c.close()
    log.check("Then new token accepted: contract_version \"1\"", ((r3 or {}).get("result") or {}).get("contract_version") == "1",
              {"result_keys": sorted((r3 or {}).get("result") or {})})
    log.check("Then stale discovery rpc-<old pid>.json no longer exists", not os.path.exists(f"{APPDIR}/rpc-{old_pid}.json"),
              f"rpc-{old_pid}.json exists={os.path.exists(f'{APPDIR}/rpc-{old_pid}.json')}")
    log.note(f"proxy restart by hand: {proxy_start(TAG)}")

    async def reopen(s):
        m = Mcp(s, log)
        await close_all(m, log)
        o = await m.call("document_open", {"path": BOX})
        log.check("Then (visual) golden model reopened after restart", o.get("status") == "OK", short(o))
        return sc(o).get("doc")
    await session(reopen)
    log.note(f"GUI Show All Objects: {show_all()}")
    fa = fitall()
    time.sleep(1)
    log.check("Then (visual) framed via GUI Fit All (TC prefers GUI path after restart)", fa.get("route") == "accessibility", fa)
    log.check("Then (visual) after captured", shot(f"{TAG}-after.png").get("exists"), f"{TAG}-after.png")
    log.save()


asyncio.run(main())
