import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = lib.EV + "/tc-07-12-default.step"; PC = lib.EV + "/tc-07-12-default-compound.step"
async def main():
    for p in (P, PC):
        if os.path.exists(p): os.remove(p)
    async with lib.Session("tc-07-12") as s:
        s.check("given: no stale target", not os.path.exists(P))
        o = await s.call("document_open", {"path": lib.GOLD + "/box-10-20-30.FCStd"}); H = lib.sc(o)["doc"]
        s.check("given: open OK", o["status"] == "OK")
        e1 = await s.call("export_step", {"doc": H, "path": P})
        s.check("omitted objects -> OK", e1["status"] == "OK", [e1["status"], e1.get("detail")])
        v = await s.call("verify_export_step", {"doc": H, "export_id": lib.sc(e1).get("export_id")})
        mv = lib.checks(v).get("export_step.volume", {}).get("measured")
        s.check("verify OK, volume within 0.1% of 6000", v["status"] == "OK" and isinstance(mv, (int, float)) and abs(mv - 6000) <= 6, [v["status"], mv])
        o2 = await s.call("document_open", {"path": lib.GOLD + "/two-box-compound.FCStd"}); H2 = lib.sc(o2)["doc"]
        t2 = await s.call("query_tree_summary", {"doc": H2}); print("compound tree", lib.sc(t2).get("tree"))
        e2 = await s.call("export_step", {"doc": H2, "path": PC})
        m2 = (e2.get("detail") or {}).get("message")
        s.check("multi-object doc -> INVALID_INPUT 'document has multiple objects; specify ...'", e2.get("status") == "INVALID_INPUT" and m2 == "document has multiple objects; specify 'objects' with the one to export", [e2.get("status"), m2, json.dumps(lib.sc(e2))])
        s.check("ambiguous case wrote nothing", not os.path.exists(PC), os.path.exists(PC))
        e3 = await s.call("export_step", {"doc": H, "path": P, "objects": []})
        s.check("objects [] same OK result as omitted", e3["status"] == "OK" and lib.sc(e3).get("bytes") == lib.sc(e1).get("bytes") and lib.sc(e3).get("path") == lib.sc(e1).get("path"), [e3["status"], e3.get("detail"), lib.sc(e3).get("bytes"), lib.sc(e1).get("bytes")])
        open("tc-07-12-handle.txt", "w").write(f"{H} {H2}")
asyncio.run(main())
