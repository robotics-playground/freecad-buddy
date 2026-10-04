import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def main():
    async with lib.Session("tc-07-04") as s:
        s.check("given: box40-hole-r5 present", os.path.exists(lib.GOLD + "/box40-hole-r5.FCStd"))
        H, OBJ = await s.open(lib.GOLD + "/box40-hole-r5.FCStd"); print(H, OBJ)
        m0 = await s.call("query_mass_properties", {"doc": H, "object": OBJ})
        v = await s.call("verify_recompute", {"doc": H})
        m1 = await s.call("query_mass_properties", {"doc": H, "object": OBJ})
        s.check("status OK, detail null", v["status"] == "OK" and v["detail"] is None, [v["status"], v["detail"]])
        ch = lib.sc(v).get("checks") or []
        s.check("exactly one check recompute.clean passed", len(ch) == 1 and ch[0]["id"] == "recompute.clean" and ch[0]["passed"] is True, ch)
        s.check("failing_objects empty", lib.sc(v).get("subject", {}).get("failing_objects") == [], lib.sc(v).get("subject"))
        s.check("text 'Recompute clean: no errors.'", v.get("text") == "Recompute clean: no errors.", v.get("text"))
        vol0 = lib.sc(m0).get("volume", {}).get("value"); vol1 = lib.sc(m1).get("volume", {}).get("value")
        s.check("read-only: volume same before/after", vol0 is not None and vol0 == vol1, [vol0, vol1, m0["status"]])
        b = lib.sc(v).get("banner", {})
        s.check("banner freecad_version non-empty, element_map_version int|null", bool(b.get("freecad_version")) and (b.get("element_map_version") is None or isinstance(b.get("element_map_version"), int)), b)
        open("tc-07-04-handle.txt", "w").write(H)
asyncio.run(main())
