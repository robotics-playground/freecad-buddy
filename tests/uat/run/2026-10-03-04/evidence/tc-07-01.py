import asyncio, json, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def main():
    async with lib.Session("tc-07-01") as s:
        dl = await s.call("document_list", {})
        s.check("given: box not open", not any("box-10-20-30" in json.dumps(d) for d in lib.sc(dl)["documents"]), lib.sc(dl))
        env = await s.call("document_open", {"path": lib.GOLD + "/box-10-20-30.FCStd"})
        s.check("given: document_open OK", env["status"] == "OK", env["status"])
        H = lib.sc(env)["doc"]
        tree = await s.call("query_tree_summary", {"doc": H})
        OBJ = lib.sc(tree)["tree"][0]["name"]; print("H", H, "OBJ", OBJ, "tree", lib.sc(tree)["tree"])
        v = await s.call("verify_shape", {"doc": H, "object": OBJ, "checks": [
            {"fn": "expect_volume", "expect": 6000.0, "tol": {"rel": 0.001}},
            {"fn": "expect_bbox", "expect": [10.0, 20.0, 30.0], "tol": {"abs": 0.05}},
            {"fn": "expect_solid_count", "expect": 1},
            {"fn": "expect_valid", "expect": True},
            {"fn": "expect_watertight", "expect": True}]})
        c = lib.checks(v)
        s.check("status OK, detail null", v["status"] == "OK" and v["detail"] is None, [v["status"], v["detail"]])
        want = ["assert.expect_volume", "assert.expect_bbox", "shape.solid_count", "shape.valid", "shape.watertight"]
        s.check("five check ids", sorted(c) == sorted(want) and len(lib.sc(v)["checks"]) == 5, list(c))
        s.check("every check passed", all(x["passed"] for x in c.values()), [(k, x["passed"]) for k, x in c.items()])
        s.check("volume measured 6000.0", c.get("assert.expect_volume", {}).get("measured") == 6000.0, c.get("assert.expect_volume"))
        s.check("verdict OK == status", lib.sc(v).get("verdict") == "OK" == v["status"], lib.sc(v).get("verdict"))
        u = await s.call("verify_shape", {"doc": H, "object": OBJ, "checks": [{"fn": "expect_genus", "expect": 0}]})
        msg = (u.get("detail") or {}).get("message")
        s.check("unknown fn refused", u.get("status") == "INVALID_INPUT" and msg == "unknown assertion fn: 'expect_genus'", [u.get("status"), msg, u.get("_raw")])
        f = await s.call("view_fit_viewport", {"doc": H})
        s.check("view_fit_viewport OK", f["status"] == "OK", [f["status"], lib.sc(f)])
        open("tc-07-01-handle.txt", "w").write(H)
asyncio.run(main())
