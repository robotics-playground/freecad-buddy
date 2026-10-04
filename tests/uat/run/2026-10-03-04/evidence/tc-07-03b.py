"""TC-07-03 on an under-constrained sketch opened from file (fixture built by tc-07-03-build-fixture.py)."""
import asyncio, json, re, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def mutate(s, H, tool, args):
    p = await s.call("preview_dry_run", {"doc": H, "operation": {"tool": tool, "args": args}, "render": "off"})
    print("preview", tool, p.get("status"), p.get("detail") or "")
    return await s.call(tool, {"doc": H, **args, "confirm": {"preview_id": lib.sc(p).get("preview_id"), "elicitation_action": "accept"}})
async def main():
    async with lib.Session("tc-07-03") as s:
        o = await s.call("document_open", {"path": lib.EV + "/tc-07-03-underconstrained.FCStd"})
        H = lib.sc(o)["doc"]; open("tc-07-03-handle.txt", "w").write(H)
        t = await s.call("query_tree_summary", {"doc": H}); print("tree", lib.sc(t)["tree"])
        v1 = await s.call("verify_sketch", {"doc": H, "sketch": "Sketch"})
        c1 = lib.checks(v1).get("sketch.fully_constrained", {})
        s.check("under-constrained -> SPEC_FAILED with failed sketch.fully_constrained", v1["status"] == "SPEC_FAILED" and c1.get("passed") is False, [v1["status"], c1])
        dof = lib.sc(v1).get("subject", {}).get("dof")
        s.check("subject.dof positive int", isinstance(dof, int) and dof > 0, dof)
        msg = (c1.get("detail") or {}).get("message", "")
        s.check("detail.message format", re.fullmatch(r"dof=\d+, conflicting=0, malformed=0, evaluate_bad=False, degenerate=0", msg) is not None, msg)
        cons = [{"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
                {"type": "Horizontal", "first": 0},
                {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": 10, "unit": "mm"}}]
        a = await mutate(s, H, "sketch_add_constraint", {"sketch": "Sketch", "constraints": cons})
        s.check("note: constraints added (Coincident origin, Horizontal, DistanceX)", a["status"] == "OK", [a["status"], a.get("detail"), lib.sc(a).get("sketch_state")])
        v2 = await s.call("verify_sketch", {"doc": H, "sketch": "Sketch"})
        s.check("fully constrained -> OK", v2["status"] == "OK", v2["status"])
        sub = lib.sc(v2).get("subject", {})
        s.check("dof 0 and fully_constrained true", sub.get("dof") == 0 and sub.get("fully_constrained") is True, sub)
        r = await mutate(s, H, "sketch_add_constraint", {"sketch": "Sketch", "constraints": [{"type": "Horizontal", "first": 0}]})
        print("dup Horizontal mutation:", r["status"], r.get("detail"), json.dumps(lib.sc(r).get("sketch_state")))
        v3 = await s.call("verify_sketch", {"doc": H, "sketch": "Sketch"})
        w = lib.sc(v3).get("warnings") or []
        s.check("duplicate Horizontal -> verify OK + sketch.redundant in warnings not checks",
                v3["status"] == "OK" and any(x.get("id") == "sketch.redundant" for x in w) and "sketch.redundant" not in lib.checks(v3),
                [r["status"], (r.get("detail") or {}), v3["status"], w, list(lib.checks(v3))])
        b = await s.call("document_open", {"path": lib.GOLD + "/box-10-20-30.FCStd"}); HB = lib.sc(b)["doc"]
        n = await s.call("verify_sketch", {"doc": HB, "sketch": "Box"})
        s.check("non-sketch refused", n.get("status") == "INVALID_INPUT" and (n.get("detail") or {}).get("message") == "object is not a sketch: Box", [n.get("status"), (n.get("detail") or {}).get("message")])
        await s.call("document_close", {"doc": HB})
asyncio.run(main())
