"""TC-11-03: every debug_exec call is audit-logged with a params digest (H1 inline, ALLOW_EXEC=1)."""
import asyncio
import json
import os
import re
import subprocess

from tc11lib import *  # noqa: F401,F403
from tc11lib import BOX, EVIDENCE, Log, Mcp, baseline, closing, h1, sc, short

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-03"
AUDIT = (EVIDENCE / f"{TAG}-audit.jsonl").as_posix()
CODE = "result = len(doc.Objects)\nprint('tc-11-03 exec ran')\n"


async def main():
    log = Log(TAG)
    log.note("Given FREECAD_BUDDY_ALLOW_EXEC=1 is set for the H1 child process of this scenario only; the shell and the GUI keep it unset.")
    log.note(f"Given audit-log path for this scenario: FREECAD_BUDDY_AUDIT_LOG={AUDIT}")
    if os.path.exists(AUDIT):
        os.remove(AUDIT)
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            async with h1(log, "h1-exec", (EVIDENCE / f"{TAG}-h1.stderr.log").as_posix(),
                          extra={"FREECAD_BUDDY_ALLOW_EXEC": "1", "FREECAD_BUDDY_AUDIT_LOG": AUDIT},
                          drop=("FREECAD_BUDDY_AUTO_APPROVE",)) as hm:
                env_seen = await hm.call("query_capabilities", {})
                log.check("Given H1 child sees ALLOW_EXEC=1 (exec_enabled true)", sc(env_seen).get("exec_enabled") is True,
                          sc(env_seen).get("exec_enabled"))
                h1doc = sc(await hm.call("document_open", {"path": BOX})).get("doc")
                ran = await hm.call("debug_exec", {"doc": h1doc, "code": CODE})
                log.note(f"debug_exec -> {short(ran)} value_repr={sc(ran).get('value_repr')} stdout={sc(ran).get('stdout')!r}")
            # When: read the lines exactly as the TC does
            reader = subprocess.run(["python", "-c", "import json;[print(json.loads(l)['event'], json.loads(l)['tool'], "
                                     f"json.loads(l).get('params_digest')) for l in open(r'{AUDIT}')]"],
                                    capture_output=True, text=True)
            log.note("TC reader output:\n" + reader.stdout)
            raw = open(AUDIT, encoding="utf-8").read()
            lines = [json.loads(x) for x in raw.splitlines() if x.strip()]
            ex = [x for x in lines if x.get("tool") == "debug_exec"]
            log.check("Then grep -c '\"tool\": \"debug_exec\"' == 2", raw.count('"tool": "debug_exec"') == 2, raw.count('"tool": "debug_exec"'))
            log.check("Then both lines event exec", len(ex) == 2 and all(x.get("event") == "exec" for x in ex), [x.get("event") for x in ex])
            hexok = all(isinstance(x.get("params_digest"), str) and re.fullmatch(r"[0-9a-f]{64}", x["params_digest"]) for x in ex)
            log.check("Then both carry 64-hex params_digest", len(ex) == 2 and hexok, [x.get("params_digest") for x in ex])
            log.check("Then before/after digests equal", len(ex) == 2 and ex[0]["params_digest"] == ex[1]["params_digest"], "")
            log.check("Then code field equals submitted code", len(ex) == 2 and all(x.get("code") == CODE for x in ex),
                      [x.get("code") for x in ex])
            log.check("Then after line has non-null verify_verdict", len(ex) == 2 and ex[1].get("verify_verdict") is not None,
                      ex[1].get("verify_verdict") if len(ex) == 2 else None)
            log.check("Then every line schema fcb.audit-record/1", all(x.get("schema") == "fcb.audit-record/1" for x in ex), "")
            log.note(f"all audit lines in file: {[(x.get('event'), x.get('tool')) for x in lines]}")
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
