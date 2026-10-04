import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = lib.EV + "/tc-07-15-over.stl"
async def main():
    if os.path.exists(P): os.remove(P)
    async with lib.Session("tc-07-15") as s:
        s.check("given: no stale target", not os.path.exists(P))
        H, OBJ = await s.open(lib.GOLD + "/box-10-20-30.FCStd")
        w1 = await s.call("export_stl", {"doc": H, "path": P, "objects": [OBJ], "linear": 0.5}); sz1 = os.path.getsize(P)
        w2 = await s.call("export_stl", {"doc": H, "path": P, "objects": [OBJ], "linear": 0.01}); sz2 = os.path.getsize(P)
        vstale = await s.call("verify_export_stl", {"doc": H, "export_id": lib.sc(w1).get("export_id")})
        w3 = await s.call("export_stl", {"doc": H, "path": P, "objects": [OBJ], "linear": 0.5}); sz3 = os.path.getsize(P)
        B = [lib.sc(w).get("bytes") for w in (w1, w2, w3)]; Fc = [lib.sc(w).get("facets") for w in (w1, w2, w3)]
        print("bytes", B, "stat", [sz1, sz2, sz3], "facets", Fc)
        s.check("all three OK", all(w["status"] == "OK" for w in (w1, w2, w3)), [w["status"] for w in (w1, w2, w3)])
        s.check("overwrite replaces (after fine == B2, not B1+B2)", sz2 == B[1] and sz2 != B[0] + B[1], [sz2, B])
        s.check("bytes == stat after each write", [sz1, sz2, sz3] == B, [[sz1, sz2, sz3], B])
        s.check("third write bytes == B1 and facets == coarse facets", B[2] == B[0] and Fc[2] == Fc[0], [B, Fc])
        ids = [lib.sc(w).get("export_id") for w in (w1, w2, w3)]
        s.check("three distinct export_ids", len(set(ids)) == 3, ids)
        sr = lib.checks(vstale).get("self_read.facet_count", {})
        s.check("stale coarse id after fine write -> SPEC_FAILED on self_read.facet_count", vstale.get("status") == "SPEC_FAILED" and sr.get("passed") is False, [vstale.get("status"), (vstale.get("detail") or {}).get("message"), sr])
        import trimesh
        m = trimesh.load(P)
        s.check("outside trimesh: True, 1 body, volume near 6000", m.is_watertight and len(m.split()) == 1 and abs(m.volume - 6000) < 1, [m.is_watertight, len(m.split()), m.volume])
        open("tc-07-15-handle.txt", "w").write(H)
asyncio.run(main())
