"""TC-10-11 on H1: a read-only call that overruns its budget (verify_recompute, budget 120 s, on a
fixture whose recompute sleeps 130 s), then a mutation on the same handle."""
import asyncio
import json
import time

from tc10lib import E, Log, h1

log = Log("tc-10-11.jsonl")
ADD = ("b=doc.addObject('Part::Box','AcceptedAfterRead')\nb.Length=5\nb.Width=5\nb.Height=5\n"
       "b.Placement.Base=FreeCAD.Vector(15,0,0)\ndoc.recompute()\nresult='accepted'\n")


async def main():
    out = {}
    async with h1(log, "11", str(E / "tc-10-11-server.stderr.log"),
                  extra={"FREECAD_BUDDY_ALLOW_EXEC": "1", "FREECAD_BUDDY_AUDIT_LOG": str(E / "tc-10-11-audit.jsonl")}) as s:
        H = (await s.call("document_open", {"path": str(E / "tc-10-slow-130.FCStd")}))["structured_content"]["doc"]
        t0 = time.time()
        v = await s.call("verify_recompute", {"doc": H})
        d = v.get("detail") or {}
        msg = d.get("message") or ""
        out["read_only_call"] = {"tool": "verify_recompute", "seconds": round(time.time() - t0, 2), "status": v.get("status"),
                                 "message": msg, "marshal_timeout": (d.get("data") or {}).get("marshal_timeout"),
                                 "contains_no_mutation_text": "no mutation was attempted, so the document is not marked suspect" in msg,
                                 "contains_may_still_run": "the body may still be running and " in msg,
                                 "contains_now_suspect": "the document is now suspect" in msg}
        m = await s.call("debug_exec", {"doc": H, "code": ADD})
        out["mutation"] = {"status": m.get("status"), "message": (m.get("detail") or {}).get("message"),
                           "refused_document_suspect": "document-suspect" in ((m.get("detail") or {}).get("message") or "")}
        fit = await s.call("view_fit_viewport", {"doc": H})
        out["h1_view_fit_viewport"] = {"status": fit.get("status"), "message": (fit.get("detail") or {}).get("message")}
        sv = await s.call("document_save", {"doc": H, "path": str(E / "tc-10-11-H.FCStd")})
        out["save_for_gui_visual"] = sv.get("status")
        await s.call("document_close", {"doc": H})
    (E / "tc-10-11-checks.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


asyncio.run(main())
