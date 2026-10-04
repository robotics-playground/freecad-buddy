"""Probe for a call that reaches rpc_dispatch's final `except Exception` (RECOMPUTE_ERROR, unexpected:true)."""
from tc09lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    doc, _ = await open_golden(m)
    probes = [
        ("export_stl", {"doc": doc, "path": f"{EV}/tc-09-21-probe.stl", "linear": 0}),
        ("export_stl", {"doc": doc, "path": f"{EV}/tc-09-21-probe.stl", "linear": -1}),
        ("export_stl", {"doc": doc, "path": "Z:/no/such/drive/x.stl"}),
        ("export_step", {"doc": doc, "path": "Z:/no/such/drive/x.step"}),
        ("query_screenshot", {"doc": doc, "view": {"camera": "iso"}, "width": 1, "height": 1}),
        ("document_save", {"doc": doc, "path": "Z:/no/such/drive/x.FCStd"}),
    ]
    for tool, args in probes:
        e = await m.call(tool, args)
        d = e.get("detail") if isinstance(e.get("detail"), dict) else {}
        print(tool, status(e), (d.get("message") or raw(e))[:90], (d.get("data") or {}).get("unexpected"), (d.get("data") or {}).get("exception"))
    await m.call("document_close", {"doc": doc})


go("tc-09-21-unexpected-probe", body)
