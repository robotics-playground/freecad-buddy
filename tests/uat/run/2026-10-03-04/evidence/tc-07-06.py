import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
STL = lib.EV + "/tc-07-06-same.stl"; TMF = lib.EV + "/tc-07-06-same.3mf"
async def main():
    for p in (STL, TMF):
        if os.path.exists(p): os.remove(p)
    async with lib.Session("tc-07-06") as s:
        s.check("given: no stale targets", not os.path.exists(STL) and not os.path.exists(TMF))
        H, OBJ = await s.open(lib.GOLD + "/sphere-r10.FCStd"); print(H, OBJ)
        a = await s.call("export_stl", {"doc": H, "path": STL, "objects": [OBJ], "linear": 0.1, "angular": 0.5})
        b = await s.call("export_3mf", {"doc": H, "path": TMF, "objects": [OBJ], "linear": 0.1, "angular": 0.5})
        s.check("both OK", a["status"] == "OK" and b["status"] == "OK", [a["status"], b["status"], a.get("detail"), b.get("detail")])
        fa, fb = lib.sc(a).get("facets"), lib.sc(b).get("facets")
        s.check("identical facet count", fa is not None and fa == fb, [fa, fb])
        s.check("both verified false", lib.sc(a).get("verified") is False and lib.sc(b).get("verified") is False)
        sa, sb = os.path.getsize(STL), os.path.getsize(TMF)
        s.check("both files non-empty", sa > 0 and sb > 0, [sa, sb, lib.sc(a).get("bytes"), lib.sc(b).get("bytes")])
        va = await s.call("verify_export_stl", {"doc": H, "export_id": lib.sc(a)["export_id"]})
        vb = await s.call("verify_export_3mf", {"doc": H, "export_id": lib.sc(b)["export_id"]})
        s.check("paired verifiers OK", va["status"] == "OK" and vb["status"] == "OK", [va["status"], vb["status"], va.get("detail"), vb.get("detail")])
        ca, cb = lib.checks(va).get("self_read.facet_count", {}), lib.checks(vb).get("self_read.facet_count", {})
        s.check("self_read.facet_count measured==expected passed in both", all(c.get("measured") == c.get("expected") and c.get("passed") is True for c in (ca, cb)) and ca != {}, [ca, cb])
        z = await s.call("export_stl", {"doc": H, "path": lib.EV + "/tc-07-06-zero.stl", "objects": [OBJ], "linear": 0.1, "angular": 0})
        msg = (z.get("detail") or {}).get("message", "")
        s.check("angular 0 -> INVALID_INPUT 'deflection out of range:'", z.get("status") == "INVALID_INPUT" and msg.startswith("deflection out of range:") and not os.path.exists(lib.EV + "/tc-07-06-zero.stl"), [z.get("status"), msg, z.get("_raw")])
        import trimesh
        n1, n2 = len(trimesh.load(STL).faces), len(trimesh.load(TMF).faces)
        s.check("trimesh outside: equal face counts", n1 == n2, [n1, n2, fa])
        open("tc-07-06-handle.txt", "w").write(H)
asyncio.run(main())
