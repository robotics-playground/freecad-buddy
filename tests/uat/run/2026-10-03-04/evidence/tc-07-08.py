import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = lib.EV + "/tc-07-08-legs.stl"
async def main():
    if os.path.exists(P): os.remove(P)
    async with lib.Session("tc-07-08") as s:
        try:
            import trimesh; s.check("given: trimesh importable", True, trimesh.__version__)
        except Exception as e:
            s.check("given: trimesh importable", False, repr(e))
        s.check("given: no stale target", not os.path.exists(P))
        H, OBJ = await s.open(lib.GOLD + "/box-10-20-30.FCStd"); print(H, OBJ)
        e = await s.call("export_stl", {"doc": H, "path": P, "objects": [OBJ]})
        EID = lib.sc(e).get("export_id"); print("export", e["status"], json.dumps(lib.sc(e)))
        v = await s.call("verify_export_stl", {"doc": H, "export_id": EID})
        c = lib.checks(v); scv = lib.sc(v)
        s.check("status OK", v["status"] == "OK", [v["status"], v.get("detail")])
        t5 = ["trimesh_stl.watertight", "trimesh_stl.winding_consistent", "trimesh_stl.is_volume", "trimesh_stl.volume_band", "trimesh_stl.euler"]
        s.check("trimesh leg five ids", all(k in c for k in t5), [k for k in c if k.startswith("trimesh")])
        s4 = ["stl2.facets", "stl2.manifold_edge_pairing", "stl2.local_winding", "stl2.non_degenerate"]
        s.check("stdlib leg four ids", all(k in c for k in s4), [k for k in c if k.startswith("stl2")])
        s.check("self_read facet/vertex passed", all(c.get(k, {}).get("passed") is True for k in ("self_read.facet_count", "self_read.vertex_count")), [c.get("self_read.facet_count"), c.get("self_read.vertex_count")])
        ag = c.get("oracle.agreement", {})
        s.check("oracle.agreement passed, measured {trimesh_stl:true, stdlib_stl:true}", ag.get("passed") is True and ag.get("measured") == {"trimesh_stl": True, "stdlib_stl": True}, ag)
        tess = scv.get("tess"); band = scv.get("volume_band")
        area = 2 * (10 * 20 + 20 * 30 + 10 * 30)
        expect_band = (2 / 3) * (tess or {}).get("linear", 0.1) * area
        vb = c.get("trimesh_stl.volume_band", {})
        s.check("volume_band == (2/3)*linear*area and tolerance has abs not rel", band is not None and abs(band - expect_band) < 1e-6 and "abs" in (vb.get("tolerance") or {}) and "rel" not in (vb.get("tolerance") or {}), [band, expect_band, vb.get("tolerance")])
        s.check("tess echoed {linear:0.1, angular:0.5}", tess == {"linear": 0.1, "angular": 0.5}, tess)
        print("all check ids:", list(c))
        # corrupt
        raw = open(P, "rb").read()
        open(P, "r+b").truncate(100)
        vc = await s.call("verify_export_stl", {"doc": H, "export_id": EID})
        s.check("truncated to 100 bytes -> SPEC_FAILED (not INVALID_INPUT, no crash)", vc.get("status") == "SPEC_FAILED", [vc.get("status"), vc.get("detail"), vc.get("_raw", "")[:200], os.path.getsize(P)])
        e2 = await s.call("export_stl", {"doc": H, "path": P, "objects": [OBJ]})
        print("re-export", e2["status"], os.path.getsize(P), len(raw))
        m = trimesh.load(P)
        s.check("outside trimesh: True True, volume within band of 6000", m.is_watertight and m.is_winding_consistent and abs(m.volume - 6000.0) <= (band or 0), [m.is_watertight, m.is_winding_consistent, m.volume, band])
        open("tc-07-08-handle.txt", "w").write(H)
asyncio.run(main())
