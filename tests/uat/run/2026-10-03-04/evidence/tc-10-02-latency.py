"""TC-10-02 supplement: the e2e report records no duration_s, so time the read-only profile per call
(tool-call entry to envelope return) on one H1 connection over the five golden models."""
import asyncio
import json
import re
import statistics

from tc10lib import E, GOLD, REPO, Log, h1

log = Log("tc-10-02.jsonl")
MODELS = ["box-10-20-30", "cylinder-r5-h20", "sphere-r10", "box40-hole-r5", "two-box-compound"]


def timeouts():
    """tool name -> timeout_s, read from tool_catalog.py ToolSpec blocks."""
    src = (REPO / "src/freecad_buddy/hosts/tool_catalog.py").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'name="(\w+)".*?timeout_s=([\w.]+)', src, re.S):
        out.setdefault(m.group(1), m.group(2))
    return out


async def main():
    rows = []
    async with h1(log, "02-latency", str(E / "tc-10-02-latency.stderr.log")) as s:
        async def timed(tool, args):
            env = await s.call(tool, args)
            rec = json.loads(log.path.read_text(encoding="utf-8").splitlines()[-1])
            rows.append({"tool": tool, "status": env.get("status"), "duration_s": rec["seconds"]})
            return env

        await timed("query_capabilities", {})
        await timed("document_list", {})
        for name in MODELS:
            o = await s.call("document_open", {"path": str(GOLD / f"{name}.FCStd")})
            h = o["structured_content"]["doc"]
            tree = (await timed("query_tree_summary", {"doc": h}))["structured_content"]["tree"]
            obj = tree[0]["name"]
            await timed("query_object", {"doc": h, "object": obj})
            await timed("query_mass_properties", {"doc": h, "object": obj})
            await timed("query_placement", {"doc": h, "object": obj})
            await timed("query_dependencies", {"doc": h, "object": obj})
            await timed("verify_shape", {"doc": h, "object": obj})
            await timed("verify_recompute", {"doc": h})
            await timed("query_screenshot", {"doc": h, "view": {"camera": "iso"}})
            await s.call("document_close", {"doc": h})
        await timed("document_list", {})
    t = timeouts()
    d = [r["duration_s"] for r in rows if r["tool"].startswith(("query_", "verify_", "document_list"))]
    over = [r for r in rows if r["duration_s"] >= float(t.get(r["tool"], "30.0").replace("timeout", "30"))]
    summary = {"n": len(d), "median_s": statistics.median(d), "max_s": max(d),
               "timeouts_status": sum(1 for r in rows if r["status"] == "TIMEOUT"),
               "non_ok": [r for r in rows if r["status"] != "OK"],
               "screenshot": [r for r in rows if r["tool"] == "query_screenshot"],
               "declared_timeouts": {k: t.get(k) for k in sorted({r['tool'] for r in rows})},
               "over_budget": over, "rows": rows}
    (E / "tc-10-02-latency.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ("n", "median_s", "max_s", "timeouts_status", "non_ok",
                                              "declared_timeouts", "over_budget")}, indent=1))
    print("screenshot", [(r["status"], r["duration_s"]) for r in summary["screenshot"]])


asyncio.run(main())
