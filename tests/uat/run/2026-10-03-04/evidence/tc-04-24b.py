import importlib.util

from tc04lib import *  # noqa: F401,F403

spec = importlib.util.spec_from_file_location("tc0424", str(EVIDENCE / "tc-04-24.py").replace("go(\"tc-04-24\", body)", ""))


async def body(m, log):
    src = (EVIDENCE / "tc-04-24.py").read_text(encoding="utf-8").replace('go("tc-04-24", body)', "")
    ns = {}
    exec(compile(src, "tc-04-24.py", "exec"), ns)
    h = sc(await m.call("document_create", {"label": "RecomputeErrorEdge3"})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    f = await m.call("feature_fillet", {"doc": h, "body": "PlateBody", "base": "PlatePad", "name": "EdgeFillet",
                                        "edges": [sel("PlatePad", "Edge3")], "radius": q(1)})
    log.note(f"chain: PlatePad -> EdgeFillet r=1 on Edge3 (60 mm bottom edge; TC-04-16 showed r=20 there fails in OCCT): {short(f)}")
    await ns["drive"](m, log, "EdgeFillet Radius 20", h, "EdgeFillet", "Radius", q(20), "tc-04-24-edge3")
    log.write({"doc": h})


go("tc-04-24b", body)
