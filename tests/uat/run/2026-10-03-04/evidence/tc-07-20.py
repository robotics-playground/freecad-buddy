import asyncio, json, os, importlib.util, yaml
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
FI = lib.ROOT + "/benchmarks/g0/fault-injection"
def checks_of(c): return yaml.safe_load(open(f"{FI}/{c}/case.yaml"))["assertions"]["checks"]
async def main():
    async with lib.Session("tc-07-20") as s:
        s.check("given: fixtures and case.yaml present", os.path.exists(FI + "/wrong-volume/fixture.FCStd") and os.path.exists(FI + "/non-watertight-open-shell/case.yaml"))
        cw, co, cc = checks_of("wrong-volume"), checks_of("non-watertight-open-shell"), checks_of("clean-control")
        print("checks", cw, co, cc)
        H, O = await s.open(FI + "/wrong-volume/fixture.FCStd")
        H2, O2 = await s.open(FI + "/non-watertight-open-shell/fixture.FCStd")
        print(H, O, H2, O2)
        v1 = await s.call("verify_shape", {"doc": H, "object": O, "checks": cw})
        s.check("wrong-volume SPEC_FAILED", v1.get("status") == "SPEC_FAILED", v1.get("status"))
        ev = lib.checks(v1).get("assert.expect_volume", {})
        s.check("expect_volume passed false, measured ~7200, expected 6000", ev.get("passed") is False and abs(ev.get("measured", 0) - 7200) < 1 and ev.get("expected") == 6000, ev)
        v2 = await s.call("verify_shape", {"doc": H2, "object": O2, "checks": co})
        s.check("open-shell SPEC_FAILED", v2.get("status") == "SPEC_FAILED", v2.get("status"))
        w = lib.checks(v2).get("shape.watertight", {})
        s.check("shape.watertight passed false measured false expected true", w.get("passed") is False and w.get("measured") is False and w.get("expected") is True, w)
        sc = lib.checks(v2).get("shape.solid_count", {})
        s.check("shape.solid_count measured 0", sc.get("measured") == 0, sc)
        b = await s.call("verify_shape", {"doc": H, "object": O})
        s.check("bare checks on wrong-volume -> OK", b.get("status") == "OK", b.get("status"))
        d1, d2 = v1.get("detail") or {}, v2.get("detail") or {}
        failed1 = [c["id"] for c in lib.sc(v1)["checks"] if not c["passed"]]; failed2 = [c["id"] for c in lib.sc(v2)["checks"] if not c["passed"]]
        s.check("detail.message lists failed ids, detail.code SPEC_FAILED", d1.get("code") == "SPEC_FAILED" and d2.get("code") == "SPEC_FAILED" and all(i in d1.get("message", "") for i in failed1) and all(i in d2.get("message", "") for i in failed2), [d1, d2, failed1, failed2])
        H3, O3 = await s.open(FI + "/clean-control/fixture.FCStd")
        v3 = await s.call("verify_shape", {"doc": H3, "object": O3, "checks": cc})
        s.check("clean control with its checks -> OK", v3.get("status") == "OK", [v3.get("status"), v3.get("detail")])
        for doc, obj, name in ((H, O, "wrong-volume"), (H2, O2, "open-shell")):
            e = await s.call("export_stl", {"doc": doc, "path": lib.EV + f"/tc-07-20-{name}.stl", "objects": [obj]})
            print("export", name, e.get("status"), (e.get("detail") or {}).get("message"), lib.sc(e))
        await s.call("document_close", {"doc": H3})
        open("tc-07-20-handle.txt", "w").write(f"{H} {H2}")
asyncio.run(main())
