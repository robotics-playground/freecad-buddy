from tc09lib import *  # noqa
from tc05lib import body_sketch  # noqa


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0914", w=20, h=20, pad=10)
    vs = await m.call("verify_sketch", {"doc": doc, "sketch": "Sketch"})
    log.check("Given verify_sketch on real sketch returns envelope", "status" in vs, status(vs))
    names0 = await names(m, doc)
    t0 = await m.call("query_tree_summary", {"doc": doc})
    n0 = sc(t0).get("total_objects")
    log.note(f"Given node count total_objects={n0} names={names0}")
    await frame_shot(m, doc, "tc-09-14-before.png")
    mark = addon_mark()
    a = await m.call("verify_sketch", {"doc": doc, "sketch": "NoSuchSketch"})
    b = await m.call("query_sketch_info", {"doc": doc, "sketch": "NoSuchSketch"})
    c = await m.call("verify_sketch", {"doc": doc, "sketch": "Body"})
    fargs = {"feature": "NoSuchFeature", "parameters": {"Length": {"value": 50, "unit": "mm"}}}
    pv_ = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_set_parameters", "args": fargs}})
    P = sc(pv_).get("preview_id") or "fcb-preview:placeholder"
    log.note(f"preview of NoSuchFeature op -> {status(pv_)} {msg(pv_)[:80]}; <P>={P[:40]}")
    d = await m.call("feature_set_parameters", dict(fargs, doc=doc, confirm={"preview_id": P, "elicitation_action": "accept"}))
    log.check("unknown sketch -> INVALID_INPUT 'unknown object: NoSuchSketch'", a.get("status") == "INVALID_INPUT" and msg(a) == "unknown object: NoSuchSketch",
              (status(a), msg(a)))
    log.check("query_sketch_info same refusal", b.get("status") == "INVALID_INPUT", (status(b), msg(b)))
    log.check("non-sketch object -> 'object is not a sketch: Body'", c.get("status") == "INVALID_INPUT" and msg(c) == "object is not a sketch: Body",
              (status(c), msg(c)))
    log.check("unknown feature -> INVALID_INPUT, not RECOMPUTE_ERROR", d.get("status") == "INVALID_INPUT", (status(d), msg(d)[:120]))
    vr = await m.call("verify_recompute", {"doc": doc})
    t1 = await m.call("query_tree_summary", {"doc": doc})
    log.check("no mutation: verify_recompute OK and same node count", vr.get("status") == "OK" and sc(t1).get("total_objects") == n0,
              (status(vr), n0, sc(t1).get("total_objects")))
    since = addon_since(mark)
    (EVIDENCE / "tc-09-14-addonlog.txt").write_text(since, encoding="utf-8")
    info = [ln for ln in since.splitlines() if " INFO " in ln and "INVALID_INPUT" in ln]
    log.check("addon log: one INFO line per refusal, no traceback", len(info) >= 4 and "Traceback" not in since,
              {"info_lines": len(info), "lines": [ln[24:140] for ln in info]})
    await frame_shot(m, doc, "tc-09-14-after.png")


go("tc-09-14", body)
