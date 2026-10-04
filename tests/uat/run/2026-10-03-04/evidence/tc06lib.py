"""TC-06 helpers on top of tc05lib: query_screenshot renders copied into evidence, PNG facts."""

import shutil as _shutil

from tc05lib import *  # noqa: F401,F403
from tc05lib import (  # noqa: F401
    EVIDENCE, Log, Mcp, apply, capture, close_all, cua, fitall, go, ids, json, mut, q, rect_profile, sc,
    shot, short, snapshot, find, click_button, model_items,
)


def link(envelope):
    return ((sc(envelope).get("render") or {}).get("resource_link"))


def objs(envelope):
    return (sc(envelope).get("scene") or {}).get("rendered_objects")


def detail_text(envelope):
    d = envelope.get("detail")
    if isinstance(d, dict):
        return json.dumps(d, ensure_ascii=False)
    return str(d if d is not None else (envelope.get("_raw") or ""))


async def render(m, doc, view=None, png=None):
    """query_screenshot; copy the returned PNG to evidence/<png>. Returns (envelope, copied path or None)."""
    args = {"doc": doc}
    if view is not None:
        args["view"] = view
    envelope = await m.call("query_screenshot", args)
    src = link(envelope)
    out = None
    if png and src:
        out = (EVIDENCE / png).as_posix()
        try:
            _shutil.copyfile(src, out)
        except OSError as exc:
            m.log.note(f"copy {src} -> {png} failed: {exc}")
            out = None
    m.log.write({"render": png, "status": envelope.get("status"), "resource_link": src,
                 "rendered_objects": objs(envelope), "copied": out})
    return envelope, out


def png_size(path):
    from PIL import Image
    with Image.open(path) as image:
        return image.size


def png_stats(path):
    """Fraction of non-background pixels and the bbox of non-near-white/black-bg pixels."""
    from PIL import Image
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        w, h = rgb.size
        px = rgb.load()
        corner = px[2, 2]
        xs, ys, n = [], [], 0
        step = max(1, min(w, h) // 400)
        for y in range(0, h, step):
            for x in range(0, w, step):
                p = px[x, y]
                if sum(abs(p[i] - corner[i]) for i in range(3)) > 30:
                    n += 1
                    xs.append(x)
                    ys.append(y)
        total = ((h + step - 1) // step) * ((w + step - 1) // step)
        bbox = [min(xs), min(ys), max(xs), max(ys)] if xs else None
        return {"size": [w, h], "bg": corner, "fill": round(n / total, 4), "bbox": bbox}


def gui_fit():
    """FreeCAD's own Fit All toolbar button (touches none of the code under test)."""
    import time as _t
    r = fitall()
    _t.sleep(1.0)
    return r
