import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P242 = lib.EV + "/tc-07-05-ap242.step"; P214 = lib.EV + "/tc-07-05-ap214.step"
async def main():
    for p in (P242, P214):
        if os.path.exists(p): os.remove(p)
    async with lib.Session("tc-07-05") as s:
        s.check("given: no stale targets", not os.path.exists(P242) and not os.path.exists(P214))
        H, OBJ = await s.open(lib.GOLD + "/box-10-20-30.FCStd"); print(H, OBJ)
        a = await s.call("export_step", {"doc": H, "path": P242, "objects": [OBJ], "ap": "AP242"})
        b = await s.call("export_step", {"doc": H, "path": P214, "objects": [OBJ], "ap": "AP214"})
        s.check("both OK", a["status"] == "OK" and b["status"] == "OK", [a["status"], b["status"], a.get("detail"), b.get("detail")])
        s.check("both verified false", lib.sc(a).get("verified") is False and lib.sc(b).get("verified") is False, [lib.sc(a).get("verified"), lib.sc(b).get("verified")])
        ea, eb = lib.sc(a).get("export_id", ""), lib.sc(b).get("export_id", "")
        s.check("distinct fcb-export: ids", ea.startswith("fcb-export:") and eb.startswith("fcb-export:") and ea != eb, [ea, eb])
        sz = os.path.getsize(P242)
        s.check("bytes == stat size (AP242)", sz == lib.sc(a).get("bytes"), [sz, lib.sc(a).get("bytes"), os.path.getsize(P214), lib.sc(b).get("bytes")])
        t242 = open(P242, encoding="latin-1").read(); t214 = open(P214, encoding="latin-1").read()
        n242 = t242.count("AP242"); n214 = t214.count("AP214")
        hdr242 = [l for l in t242.splitlines() if "FILE_SCHEMA" in l or "AP2" in l][:3]; hdr214 = [l for l in t214.splitlines() if "FILE_SCHEMA" in l or "AP2" in l][:3]
        s.check("AP schema pinned per call (grep -c AP242 / AP214 non-zero)", n242 > 0 and n214 > 0, [n242, n214, hdr242, hdr214])
        x = await s.call("export_step", {"doc": H, "path": lib.EV + "/tc-07-05-ap203.step", "objects": [OBJ], "ap": "AP203"})
        s.check("AP203 -> protocol rejection (isError, no envelope)", x.get("_isError") is True and "status" not in x, [x.get("_isError"), x.get("_raw", "")[:200], x.get("status")])
        s.check("AP203 wrote no file", not os.path.exists(lib.EV + "/tc-07-05-ap203.step"))
        want = f"STEP export written -> {P242}."
        s.check("text equals 'STEP export written -> <path>.'", a.get("text") == want, [a.get("text"), want])
        r = await s.call("document_open", {"path": P242}); HRT = lib.sc(r).get("doc")
        t = await s.call("query_tree_summary", {"doc": HRT}); print("RT tree", lib.sc(t).get("tree"))
        m = await s.call("query_mass_properties", {"doc": HRT})
        vol = (lib.sc(m).get("volume") or {}).get("value")
        if vol is None and lib.sc(t).get("tree"):
            m = await s.call("query_mass_properties", {"doc": HRT, "object": lib.sc(t)["tree"][0]["name"]}); vol = (lib.sc(m).get("volume") or {}).get("value")
        s.check("re-import volume within 0.1% of 6000", vol is not None and abs(vol - 6000) <= 6.0, [r["status"], m["status"], vol, m.get("detail")])
        open("tc-07-05-handle.txt", "w").write(f"{H} {HRT}")
asyncio.run(main())
