"""Repro: verify_sketch on a freshly opened under-constrained sketch file reports dof=0."""
import asyncio, json, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
async def main():
    async with lib.Session("tc-07-03-repro") as s:
        o = await s.call("document_open", {"path": lib.EV + "/tc-07-03-underconstrained.FCStd"})
        H = lib.sc(o)["doc"]
        for i in range(2):
            v = await s.call("verify_sketch", {"doc": H, "sketch": "Sketch"})
            print(i, v["status"], json.dumps(lib.sc(v)["subject"]), lib.checks(v)["sketch.fully_constrained"]["detail"])
        await s.call("document_close", {"doc": H})
asyncio.run(main())
