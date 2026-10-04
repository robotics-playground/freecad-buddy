from tc14lib import *

H = "fcb-doc:KPtFSwPWdsAzCfYBXZv4BA"
OUT = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04/evidence/tc-14-16-box-saved.FCStd"


def title():
    pid, win = ids()
    for w in cua("list_windows", {"pid": pid}).get("windows", []):
        if w["window_id"] == win:
            return w["title"]


async def body(m, log):
    s = await m.call("document_save", {"doc": H, "path": OUT})
    if s.get("status") != "OK":
        s = await m.mutate(H, "document_save", {"path": OUT})
    log.note(f"save {s.get('status')} {json.dumps(s.get('detail'))[:200]}")
    t0 = title()
    log.check("Given saved doc is clean (no '*' in title)", t0 and not t0.startswith("*"), t0)
    menu(["View", "Zoom", "Zoom In"])
    f = await m.call("view_fit_viewport", {"doc": H})
    t1 = title()
    log.note(f"fit {f.get('status')}")
    log.check("Then fit does not mark the document modified", t1 == t0, f"{t0!r} -> {t1!r}")
    shot("tc-14-16-after.png")


go("tc-14-16b", body)
