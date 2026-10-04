import asyncio, json, os, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
PA = lib.EV + "/tc-07-19-own.step"; PB = lib.EV + "/tc-07-19-own-b.step"
async def main():
    for p in (PA, PB):
        if os.path.exists(p): os.remove(p)
    async with lib.Session("tc-07-19") as s:
        s.check("given: fixtures present", os.path.exists(lib.GOLD + "/box-10-20-30.FCStd") and os.path.exists(lib.GOLD + "/sphere-r10.FCStd"))
        HA, OA = await s.open(lib.GOLD + "/box-10-20-30.FCStd"); HB, OB = await s.open(lib.GOLD + "/sphere-r10.FCStd")
        dl = await s.call("document_list", {}); hs = [d["doc"] for d in lib.sc(dl)["documents"]]
        s.check("given: both handles listed", HA in hs and HB in hs, hs)
        e = await s.call("export_step", {"doc": HA, "path": PA, "objects": [OA]}); EA = lib.sc(e).get("export_id")
        x = await s.call("verify_export_step", {"doc": HB, "export_id": EA})
        s.check("cross-document verify INVALID_INPUT", x.get("status") == "INVALID_INPUT", x.get("status"))
        s.check("message names id and wrong doc", (x.get("detail") or {}).get("message") == f"export_id {EA} does not belong to document {HB}", [(x.get("detail") or {}).get("message")])
        s.check("no checks and no subject", not lib.sc(x).get("checks") and not lib.sc(x).get("subject"), lib.sc(x))
        ok = await s.call("verify_export_step", {"doc": HA, "export_id": EA})
        s.check("correct pairing OK", ok.get("status") == "OK", ok.get("status"))
        eb = await s.call("export_step", {"doc": HB, "path": PB, "objects": [OB]}); EB = lib.sc(eb).get("export_id")
        y = await s.call("verify_export_step", {"doc": HA, "export_id": EB})
        s.check("symmetric refusal", y.get("status") == "INVALID_INPUT" and (y.get("detail") or {}).get("message") == f"export_id {EB} does not belong to document {HA}", [y.get("status"), (y.get("detail") or {}).get("message")])
        ra = await s.call("verify_recompute", {"doc": HA}); rb = await s.call("verify_recompute", {"doc": HB})
        s.check("verify_recompute both OK", ra.get("status") == "OK" and rb.get("status") == "OK", [ra.get("status"), rb.get("status")])
asyncio.run(main())
