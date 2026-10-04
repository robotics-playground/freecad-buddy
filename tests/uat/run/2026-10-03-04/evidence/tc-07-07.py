import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
P = lib.EV + "/tc-07-07-rt.step"
async def main():
    if os.path.exists(P): os.remove(P)
    async with lib.Session("tc-07-07") as s:
        s.check("given: no stale target", not os.path.exists(P))
        H, OBJ = await s.open(lib.GOLD + "/box40-hole-r5.FCStd"); print(H, OBJ)
        e = await s.call("export_step", {"doc": H, "path": P, "objects": [OBJ]})
        EID = lib.sc(e).get("export_id"); print("export", e["status"], EID)
        v = await s.call("verify_export_step", {"doc": H, "export_id": EID})
        c = lib.checks(v); scv = lib.sc(v)
        s.check("status OK and verdict OK", v["status"] == "OK" and scv.get("verdict") == "OK", [v["status"], scv.get("verdict"), v.get("detail")])
        s.check("exactly three check ids", sorted(c) == sorted(["export_step.volume", "export_step.valid", "export_step.topology_counts"]) and len(scv.get("checks", [])) == 3, list(c))
        s.check("volume tolerance {rel:0.001}", c.get("export_step.volume", {}).get("tolerance") == {"rel": 0.001}, c.get("export_step.volume"))
        mv = c.get("export_step.volume", {}).get("measured")
        s.check("volume within 0.1% of 15214.6018", isinstance(mv, (int, float)) and abs(mv - 15214.6018) <= 15.2146, mv)
        vc = c.get("export_step.valid", {})
        s.check("valid measured true passed", vc.get("measured") is True and vc.get("passed") is True, vc)
        tc = c.get("export_step.topology_counts", {})
        mm, ee = tc.get("measured") or {}, tc.get("expected") or {}
        s.check("topology counts equal for faces/edges/solids", all(k in mm and mm.get(k) == ee.get(k) for k in ("faces", "edges", "solids")), tc)
        sub = scv.get("subject", {})
        s.check("subject export_id/path", sub.get("export_id") == EID and sub.get("path") == P, sub)
        dl = await s.call("document_list", {})
        names = [(d["name"], d["label"]) for d in lib.sc(dl)["documents"]]
        s.check("no FCB_TMP_ doc left", not any(n.startswith("FCB_TMP_") or l.startswith("FCB_TMP_") for n, l in names), names)
        open("tc-07-07-handle.txt", "w").write(H)
asyncio.run(main())
