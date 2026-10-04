from tc05lib import *


def names(tr):
    out = []
    def walk(nodes):
        for n in nodes or []:
            out.append(n["name"]); walk(n.get("children"))
    walk(sc(tr).get("tree"))
    return set(out)


async def body(m, log):
    doc = await body_sketch(m, "TC0504", pad=30)
    before = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    nb = names(before)
    log.check("Given tree lists Body, Sketch, Pad", {"Body", "Sketch", "Pad"} <= nb, sorted(nb))
    args = {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)}
    preview, env = await apply(m, doc, "feature_fillet", args)
    after = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    na = names(after)
    t = mut(env).get("touched") or []
    log.note(f"feature_fillet -> {short(env)} touched={t}")
    log.check("touched contains 'Fillet'", "Fillet" in t, t)
    log.check("'Sketch' absent from touched", "Sketch" not in t, t)
    new_in_tree = na - nb
    new_in_touched = set(t) - nb
    log.check("tree diff (after-before) == new names in touched", new_in_tree == new_in_touched, {"tree_new": sorted(new_in_tree), "touched_new": sorted(new_in_touched)})
    dt = (sc(preview).get("diff") or {}).get("touched")
    log.check("preview diff.touched == mutation.touched", sorted(dt or []) == sorted(t), {"preview": dt, "apply": t})
    log.check("post_verify.is_valid true", pv(env).get("is_valid") is True, pv(env).get("is_valid"))
    log.check("status OK", env.get("status") == "OK", short(env))
    fit, rec = await capture(m, doc, "tc-05-04-after.png")
    log.note(f"fit={fit}")
    log.write({"doc": doc})


go("tc-05-04", body)
