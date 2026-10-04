"""TC-11-02: debug_exec appears only with the exact flag value (H1 inline x4)."""
import asyncio

from tc11lib import *  # noqa: F401,F403
from tc11lib import EVIDENCE, Log, Mcp, baseline, closing, h1, sc

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-02"
WARN = "SECURITY: debug_exec ENABLED by operator flag"


async def run_value(log, value):
    err = (EVIDENCE / f"{TAG}-h1-{value}.stderr.log").as_posix()
    async with h1(log, f"ALLOW_EXEC={value}", err, extra={"FREECAD_BUDDY_ALLOW_EXEC": value,
                  "FREECAD_BUDDY_AUDIT_LOG": (EVIDENCE / f"{TAG}-audit.jsonl").as_posix()},
                  drop=("FREECAD_BUDDY_AUTO_APPROVE",)) as hm:
        names = sorted(t.name for t in (await hm.session.list_tools()).tools)
        caps = sc(await hm.call("query_capabilities", {}))
    log.write({"value": value, "tools": names})
    stderr = open(err, encoding="utf-8", errors="replace").read()
    return names, caps, stderr


async def main():
    log = Log(TAG)
    log.note("Operator acceptance: exec enablement limited to separate H1 headless processes, authorized by the run brief (defensive test of own bridge).")
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            res = {}
            for value in ("1", "true", "yes", "0"):
                res[value] = await run_value(log, value)
                n, c, e = res[value]
                log.note(f"value={value}: tools={len(n)} debug_exec={'debug_exec' in n} exec_enabled={c.get('exec_enabled')} warn={WARN in e}")
            n1, c1, e1 = res["1"]
            log.check("Then =1 lists 45 tools (TC literal)", len(n1) == 45, len(n1))
            log.check("Then =1 debug_exec present", "debug_exec" in n1, len(n1))
            for v in ("true", "yes", "0"):
                n, _, _ = res[v]
                log.check(f"Then {v}: tools/list length 44 (TC literal)", len(n) == 44, len(n))
                log.check(f"Then {v}: debug_exec absent", "debug_exec" not in n, len(n))
            log.check("Then exec_enabled true on =1 only",
                      c1.get("exec_enabled") is True and all(res[v][1].get("exec_enabled") is False for v in ("true", "yes", "0")),
                      {v: res[v][1].get("exec_enabled") for v in res})
            log.check("Then =1 stderr has the SECURITY warning", WARN in e1, "")
            log.check("Then warning absent for true/yes/0", all(WARN not in res[v][2] for v in ("true", "yes", "0")), "")
            log.check("Then (extra) =1 surface = clean surface + debug_exec only",
                      sorted(set(n1) - set(res["0"][0])) == ["debug_exec"], sorted(set(n1) ^ set(res["0"][0])))
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
