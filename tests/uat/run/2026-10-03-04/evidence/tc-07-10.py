import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
C = lib.EV + "/tc-07-10-coarse.stl"; F = lib.EV + "/tc-07-10-fine.stl"; FL = lib.EV + "/tc-07-10-floor.stl"
async def main():
    for p in (C, F, FL):
        if os.path.exists(p): os.remove(p)
    async with lib.Session("tc-07-10") as s:
        s.check("given: no stale targets", not os.path.exists(C) and not os.path.exists(F))
        H, OBJ = await s.open(lib.GOLD + "/sphere-r10.FCStd"); print(H, OBJ)
        ec = await s.call("export_stl", {"doc": H, "path": C, "objects": [OBJ], "linear": 0.5, "angular": 1.0})
        ef = await s.call("export_stl", {"doc": H, "path": F, "objects": [OBJ], "linear": 0.01, "angular": 0.1})
        print("coarse", ec["status"], json.dumps(lib.sc(ec))); print("fine", ef["status"], json.dumps(lib.sc(ef)))
        vc = await s.call("verify_export_stl", {"doc": H, "export_id": lib.sc(ec)["export_id"]})
        vf = await s.call("verify_export_stl", {"doc": H, "export_id": lib.sc(ef)["export_id"]})
        fc, ff = lib.sc(ec).get("facets"), lib.sc(ef).get("facets")
        s.check("fine facets > coarse facets", isinstance(fc, int) and isinstance(ff, int) and ff > fc, [fc, ff])
        s.check("both verifies OK", vc["status"] == "OK" and vf["status"] == "OK", [vc["status"], vf["status"], vc.get("detail"), vf.get("detail")])
        bc, bf = lib.sc(vc).get("volume_band"), lib.sc(vf).get("volume_band")
        s.check("coarse band = 50x fine band", bc and bf and abs(bc / bf - 50) < 1e-6, [bc, bf, bc / bf if bc and bf else None])
        tf = lib.checks(vf).get("trimesh_stl.volume_band", {})
        s.check("fine band far below 0.1% (4.1888) and tolerance abs no rel", bf is not None and bf < 0.001 * 4188.7902 and "abs" in (tf.get("tolerance") or {}) and "rel" not in (tf.get("tolerance") or {}), [bf, 0.001 * 4188.7902, tf.get("tolerance")])
        tcv = lib.checks(vc).get("trimesh_stl.volume_band", {})
        s.check("coarse measured < 4188.7902 and passed", isinstance(tcv.get("measured"), (int, float)) and tcv["measured"] < 4188.7902 and tcv.get("passed") is True, tcv)
        z = await s.call("export_stl", {"doc": H, "path": FL, "objects": [OBJ], "linear": 0.00001})
        msg = (z.get("detail") or {}).get("message", "")
        s.check("linear 1e-5 -> INVALID_INPUT 'deflection out of range:' and no file", z.get("status") == "INVALID_INPUT" and msg.startswith("deflection out of range:") and not os.path.exists(FL), [z.get("status"), msg, os.path.exists(FL)])
        import trimesh
        n1, n2 = len(trimesh.load(C).faces), len(trimesh.load(F).faces)
        s.check("outside trimesh: coarse < fine", n1 < n2, [n1, n2])
        open("tc-07-10-handle.txt", "w").write(H)
asyncio.run(main())
