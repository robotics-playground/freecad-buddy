import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = lib.EV + "/tc-07-13-genus.stl"
async def main():
    if os.path.exists(P): os.remove(P)
    async with lib.Session("tc-07-13") as s:
        s.check("given: fixtures present", os.path.exists(lib.GOLD + "/box40-hole-r5.FCStd") and os.path.exists(lib.GOLD + "/two-box-compound.FCStd"))
        H1, O1 = await s.open(lib.GOLD + "/box40-hole-r5.FCStd"); H2, O2 = await s.open(lib.GOLD + "/two-box-compound.FCStd"); print(H1, O1, H2, O2)
        g = await s.call("verify_shape", {"doc": H1, "object": O1, "checks": [
            {"fn": "expect_volume", "expect": 15214.6018, "tol": {"rel": 0.001}}, {"fn": "expect_solid_count", "expect": 1}, {"fn": "expect_watertight", "expect": True}]})
        mv = lib.checks(g).get("assert.expect_volume", {}).get("measured")
        s.check("genus-1 grade OK, volume within 0.1%", g["status"] == "OK" and abs(mv - 15214.6018) <= 15.21, [g["status"], mv])
        e = await s.call("export_stl", {"doc": H1, "path": P, "objects": [O1]})
        v = await s.call("verify_export_stl", {"doc": H1, "export_id": lib.sc(e).get("export_id")})
        s.check("through-hole STL verify OK", v["status"] == "OK", [e["status"], v["status"], v.get("detail")])
        eu = lib.checks(v).get("trimesh_stl.euler", {})
        s.check("trimesh_stl.euler measured 0 passed", eu.get("measured") == 0 and eu.get("passed") is True, eu)
        c = await s.call("verify_shape", {"doc": H2, "object": O2, "checks": [{"fn": "expect_volume", "expect": 2000.0, "tol": {"rel": 0.001}}, {"fn": "expect_solid_count", "expect": 2}]})
        cc = lib.checks(c)
        s.check("compound OK with shape.solid_count measured 2", c["status"] == "OK" and cc.get("shape.solid_count", {}).get("measured") == 2, [c["status"], cc.get("shape.solid_count")])
        s.check("compound volume within 0.001 of 2000", abs(cc.get("assert.expect_volume", {}).get("measured", 0) - 2000.0) <= 0.001, cc.get("assert.expect_volume"))
        m = await s.call("query_mass_properties", {"doc": H2, "object": O2})
        s.check("compound mass props OK, com null", m["status"] == "OK" and "com" in lib.sc(m) and lib.sc(m)["com"] is None, [m["status"], {k: lib.sc(m).get(k) for k in ("com", "volume")}])
        w = await s.call("verify_shape", {"doc": H2, "object": O2, "checks": [{"fn": "expect_watertight", "expect": True}]})
        s.check("compound expect_watertight -> SPEC_FAILED", w.get("status") == "SPEC_FAILED", [w.get("status"), w.get("detail"), lib.checks(w).get("shape.watertight")])
        open("tc-07-13-handle.txt", "w").write(f"{H1} {H2}")
asyncio.run(main())
