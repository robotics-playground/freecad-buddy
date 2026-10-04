import glob

from tc09lib import *  # noqa


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-04")
    calls = [
        ("depth as string", "query_tree_summary", {"doc": doc, "depth": "1"}),
        ("path as number", "export_step", {"doc": doc, "path": 42, "objects": [obj]}),
        ("objects as object", "export_step", {"doc": doc, "path": f"{EV}/tc-09-04-t.step", "objects": {"0": obj}}),
        ("linear as string", "export_stl", {"doc": doc, "path": f"{EV}/tc-09-04-t.stl", "linear": "0.1"}),
    ]
    res = []
    for name, tool, args in calls:
        e = await m.call(tool, args)
        res.append(e)
        log.check(f"{name} -> protocol rejection", is_reject(e), raw(e) or short(e))
    log.check("no coercion: none OK", all(e.get("status") != "OK" for e in res), [status(e) for e in res])
    files = glob.glob(f"{EV}/tc-09-04-t.*")
    log.check("nothing written tc-09-04-t.*", files == [], files)
    await frame_shot(m, doc, "tc-09-04-after.png")


go("tc-09-04", body)
