"""TC-06-03 repro: explicit include of a PartDesign::Body yields OK + blank PNG?"""
from tc06lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0603"][0]
    for i, view in enumerate([{"include": ["BodyA"]}, {"include": ["BodyA"], "camera": "front"}, {"include": ["BodyB"]}]):
        r, out = await render(m, doc, view, f"tc-06-03-repro-body-{i}.png")
        log.check(f"repro {view}: image has non-background pixels", bool(out) and png_stats(out)["fill"] > 0.01,
                  {"status": r.get("status"), "objs": objs(r), "empty_scene": (sc(r).get("render") or {}).get("empty_scene"), "stats": png_stats(out) if out else None})

go("tc-06-03b", body)
