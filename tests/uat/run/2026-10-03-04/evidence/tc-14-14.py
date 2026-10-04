from tc14lib import *
from tc08h1 import h1

ERR = f"{EV}/tc-14-14-h1.stderr.log"
AUDIT = EVIDENCE / "tc-14-14-audit.jsonl"
BUSY = "import time\nt=time.time()\nwhile time.time()-t<45:\n    pass\nresult='busy body finished'\n"


def lines():
    return AUDIT.read_text(encoding="utf-8").splitlines() if AUDIT.exists() else []


async def body(m, log):
    async with h1(log, "tc-14-14", ERR, extra={"FREECAD_BUDDY_ALLOW_EXEC": "1",
                                               "FREECAD_BUDDY_AUDIT_LOG": str(AUDIT)}) as hh:
        o = await hh.call("document_open", {"path": BOX})
        d = sc(o).get("doc")
        t0 = time.time()
        busy = await hh.call("debug_exec", {"doc": d, "code": BUSY})
        log.note(f"busy debug_exec after {time.time()-t0:.1f}s -> {busy.get('status')} {(busy.get('detail') or {}).get('message')}")
        chk = await hh.call("debug_exec", {"doc": d, "code": "result=1"})
        cmsg = (chk.get("detail") or {}).get("message", "")
        log.check("Given following mutating call returns the document-suspect message", cmsg.startswith("document-suspect"), cmsg)
        shot("tc-14-14-before.png")
        n0 = len(lines())
        log.note(f"audit tail position (wc -l) = {n0}")
        r = await hh.call("view_fit_viewport", {"doc": d})
        rmsg = (r.get("detail") or {}).get("message", "")
        log.note(f"fit on suspect -> {r.get('status')} {rmsg}")
        log.check("Then refused with the suspect message", r.get("status") == "INVALID_INPUT" and "suspect" in rmsg, rmsg)
        log.check("Then literal 'the document is now suspect: ...' present", "the document is now suspect:" in rmsg, rmsg)
        new = lines()[n0:]
        vf = [json.loads(x) for x in new if '"view_fit_viewport"' in x]
        log.write({"audit_new_lines": [json.loads(x) for x in new]})
        log.check("Then no new view_fit_viewport audit record past tail", not vf, vf)
        log.note("host: H1 inline (freecad_buddy.hosts.main serve --transport stdio --mode inline, adapters/mcp_server.py)")
        shot("tc-14-14-after.png")
        q = await hh.call("query_tree_summary", {"doc": d})
        log.note(f"cleanup read {q.get('status')} at {time.time()-t0:.1f}s")
        await hh.call("document_close", {"doc": d})


go("tc-14-14", body)
