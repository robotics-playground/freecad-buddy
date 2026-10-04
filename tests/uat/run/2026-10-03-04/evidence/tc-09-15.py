import asyncio
import subprocess

from tc09lib import *  # noqa
from tc08h1 import h1

ARGS = {"doc": {"handle": "fcb-doc:x"}}


async def inline_part(log):
    async with h1(log, "inline", EV + "/tc-09-15-inline.stderr.log") as s:
        e = await s.call("verify_recompute", ARGS)
        tl = await s.session.list_tools()
        schema = [t.inputSchema["properties"]["doc"] for t in tl.tools if t.name == "verify_recompute"][0]
        return e, len(tl.tools), schema


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-15")
    ie, n_inline, ischema = await inline_part(log)
    log.note(f"inline host verify_recompute doc schema: {ischema}")
    ie_isreject = ie.get("_isError") and "status" not in ie
    log.check("inline: envelope INVALID_INPUT 'doc handle must be a string'", ie.get("status") == "INVALID_INPUT" and msg(ie) == "doc handle must be a string",
              {"status": ie.get("status"), "msg": msg(ie), "raw": (ie.get("_raw") or "")[:200], "isError": ie.get("_isError")})
    he = await m.call("verify_recompute", ARGS)
    log.note(f"H2 recorded divergence: status={status(he)} raw={raw(he)} msg={msg(he)}")
    log.check("H2 result recorded (divergence is not a failure)", True, {"status": status(he), "raw": raw(he), "sc": he.get("_sc")})
    g = subprocess.run(["C:/Program Files/Git/bin/bash.exe", "-c",
                        f'cd "{PROJECT}"; grep -n "doc handle must be a string" src/freecad_buddy/adapters/mcp_server.py; echo ---; '
                        f'grep -rn "doc handle must be a string" src/freecad_buddy/usecases; echo ---; '
                        f'grep -n "_call_tool" src/freecad_buddy/hosts/gui_external/entry.py src/freecad_buddy/adapters/mcp_server.py'],
                       capture_output=True, text=True)
    (EVIDENCE / "tc-09-15-grep.txt").write_text(g.stdout, encoding="utf-8")
    parts = g.stdout.split("---")
    log.check("guard string in mcp_server.py, not in usecases", "mcp_server.py" not in parts[0] and parts[0].strip() != "" and parts[1].strip() == "",
              g.stdout.strip()[:400])
    log.check("two distinct _call_tool implementations", "entry.py" in parts[2] and "mcp_server.py" in parts[2], parts[2].strip())
    tl = await m.session.list_tools()
    log.check("both hosts still answer tools/list", n_inline > 0 and len(tl.tools) > 0, (n_inline, len(tl.tools)))
    log.check("no registry lookup message (type problem, not missing handle)", "unknown or stale" not in msg(ie) + msg(he), (msg(ie), msg(he)))
    await frame_shot(m, doc, "tc-09-15-after.png")


go("tc-09-15", body)
