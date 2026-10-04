"""Supplementary: the stale-id pairing signal on a curved part, where coarse and fine tessellations differ."""
import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = lib.EV + "/tc-07-15-over-sphere.stl"
async def main():
    if os.path.exists(P): os.remove(P)
    async with lib.Session("tc-07-15") as s:
        H, OBJ = await s.open(lib.GOLD + "/sphere-r10.FCStd")
        w1 = await s.call("export_stl", {"doc": H, "path": P, "objects": [OBJ], "linear": 0.5}); sz1 = os.path.getsize(P)
        w2 = await s.call("export_stl", {"doc": H, "path": P, "objects": [OBJ], "linear": 0.01}); sz2 = os.path.getsize(P)
        print("sphere bytes", lib.sc(w1).get("bytes"), lib.sc(w2).get("bytes"), "stat", sz1, sz2, "facets", lib.sc(w1).get("facets"), lib.sc(w2).get("facets"))
        s.check("supplementary sphere: overwrite replaces (stat == B2, != B1+B2)", sz2 == lib.sc(w2).get("bytes") and sz2 != lib.sc(w1).get("bytes") + lib.sc(w2).get("bytes"), [sz1, sz2])
        v = await s.call("verify_export_stl", {"doc": H, "export_id": lib.sc(w1).get("export_id")})
        sr = lib.checks(v).get("self_read.facet_count", {})
        s.check("supplementary sphere: stale coarse id -> SPEC_FAILED self_read.facet_count", v.get("status") == "SPEC_FAILED" and sr.get("passed") is False, [v.get("status"), (v.get("detail") or {}).get("message"), sr])
        await s.call("document_close", {"doc": H})
    os.remove(P)
asyncio.run(main())
