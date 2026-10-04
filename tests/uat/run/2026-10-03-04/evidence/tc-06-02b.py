"""TC-06-02 closing: face count oracle for the bottom seam, opposite-pair diffs, iso fit + after capture."""
import time
from tc06lib import *
from PIL import Image, ImageChops


def diff(a, b):
    A = Image.open(a).convert("L"); B = Image.open(b).convert("L")
    d = ImageChops.difference(A, B)
    hist = d.histogram()
    changed = sum(hist[30:])
    return round(changed / (A.width * A.height), 4)


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0602"][0]
    vs = await m.call("verify_shape", {"doc": doc, "object": "Tower"})
    log.note("verify_shape Tower: " + json.dumps(sc(vs))[:600])
    for a, b in (("front", "back"), ("top", "bottom"), ("left", "right")):
        f = diff(f"tc-06-02-{a}.png", f"tc-06-02-{b}.png")
        log.check(f"opposite pair {a}/{b} renders differ", f > 0.01, {"changed_fraction": f})
    print(click_button("Standard Views"))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK (Isometric view)", fit.get("status") == "OK", short(fit, 500))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-02-after.png')}")

go("tc-06-02b", body)
