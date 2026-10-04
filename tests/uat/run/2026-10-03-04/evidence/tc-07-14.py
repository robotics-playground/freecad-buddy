import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
D = lib.EV + "/tc-07-14 exports"; U = D + "/boîte-立方体.step"; L = D + "/" + "a" * 200 + ".step"
async def main():
    os.makedirs(D, exist_ok=True)
    async with lib.Session("tc-07-14") as s:
        s.check("given: dir exists", os.path.isdir(D))
        H, OBJ = await s.open(lib.GOLD + "/box-10-20-30.FCStd"); print(H, OBJ)
        e = await s.call("export_step", {"doc": H, "path": U, "objects": [OBJ]})
        s.check("unicode export OK", e["status"] == "OK", [e["status"], e.get("detail")])
        s.check("file exists at exact path", os.path.exists(U), os.listdir(D))
        s.check("path echoed unmodified", lib.sc(e).get("path") == U, [lib.sc(e).get("path"), U])
        v = await s.call("verify_export_step", {"doc": H, "export_id": lib.sc(e).get("export_id")})
        s.check("verify OK with subject.path == unicode path", v["status"] == "OK" and lib.sc(v).get("subject", {}).get("path") == U, [v["status"], lib.sc(v).get("subject"), v.get("detail")])
        el = await s.call("export_step", {"doc": H, "path": L, "objects": [OBJ]})
        ok_written = el["status"] == "OK" and os.path.exists(L)
        ok_refused = el["status"] in ("INVALID_INPUT", "RECOMPUTE_ERROR") and not os.path.exists(L)
        print("long path len", len(L), el["status"], el.get("detail"))
        vl = None
        if el["status"] == "OK":
            vl = await s.call("verify_export_step", {"doc": H, "export_id": lib.sc(el).get("export_id")})
        s.check("long name written cleanly or refused cleanly", ok_written or ok_refused, [el["status"], os.path.exists(L), (el.get("detail") or {}).get("message"), vl and vl["status"], lib.sc(el).get("bytes"), os.path.getsize(L) if os.path.exists(L) else None])
        s.check("bytes == stat size for unicode path", os.path.getsize(U) == lib.sc(e).get("bytes"), [os.path.getsize(U), lib.sc(e).get("bytes")])
        open("tc-07-14-handle.txt", "w").write(H)
asyncio.run(main())
