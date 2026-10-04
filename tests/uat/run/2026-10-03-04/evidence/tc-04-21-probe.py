from tc04lib import *  # noqa: F401,F403


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "ReadOnlyProbe"})).get("doc")
    await m.call("feature_body_create", {"doc": h, "name": "ShaftBody"})
    await sketch(m, h, "ShaftProfile", "ShaftBody", rect_profile(0, 0, 5, 20), plane="XZ")
    await m.call("feature_revolve", {"doc": h, "body": "ShaftBody", "profile": "ShaftProfile", "name": "ShaftRev",
                                     "axis": sel("ShaftProfile", "V_Axis"), "angle": q(360, "deg")})
    for prop, val in (("Base", 1), ("Axis", 1)):
        e = await m.call("feature_set_parameters", {"doc": h, "feature": "ShaftRev", "parameters": {prop: val}})
        log.note(f"ShaftRev {prop}={val!r} -> {short(e, 300)} rolled_back={mut(e).get('rolled_back')} snapshot={mut(e).get('snapshot_path')}")
    await m.call("document_close", {"doc": h})


go("tc-04-21-probe", body)
