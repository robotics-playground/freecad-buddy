from tc05lib import *

COPY = "C:/Users/thuan/AppData/Local/Temp/claude/D--Work-Personal-Sources-freecad-buddy/3a96e4e8-1193-4f20-8730-69bd46a68309/scratchpad/box-copy-b.FCStd"


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    ha = [d for d in docs if d["label"].startswith("box")][0]["doc"]
    log.note("second document_open of the same path returned the SAME handle (FreeCAD reuses an open document). "
             "Compensating step: open a byte-identical copy of box-10-20-30.FCStd from a second path, a truly independent document.")
    b = await m.call("document_open", {"path": COPY})
    hb = sc(b).get("doc")
    log.note(f"copy open -> {short(b)} handle={hb} name={sc(b).get('name')}")
    log.check("independent handle for the copy", bool(hb) and hb != ha, [ha, hb])
    pa = await m.call("preview_dry_run", {"doc": ha, "operation": {"tool": "feature_body_create", "args": {"name": "Probe2"}}})
    pb = await m.call("preview_dry_run", {"doc": hb, "operation": {"tool": "feature_body_create", "args": {"name": "Probe"}}})
    da = (sc(pa).get("diff") or {}).get("fingerprint_before")
    db = (sc(pb).get("diff") or {}).get("fingerprint_before")
    log.note("handle-a already holds the committed empty Body 'Probe'; compare the copy against a fresh state instead:")
    pb2 = await m.call("preview_dry_run", {"doc": hb, "operation": {"tool": "feature_body_create", "args": {"name": "Probe"}}})
    log.check("same-handle repeat digest stable", (sc(pb2).get("diff") or {}).get("fingerprint_before") == db, [db, (sc(pb2).get("diff") or {}).get("fingerprint_before")])
    log.write({"a_after_probe": da, "copy_b": db})
    log.check("byte-identical documents (fresh copy vs. first open's pre-mutation digest 33e870c0...) give identical digests",
              db == "33e870c051cd2fe4846c52b78a1dae3a033720012ffa97bcf6efaaa56af9dc7c", db)
    c = await m.call("document_close", {"doc": hb})
    log.note(f"copy closed -> {c.get('status')}")


go("tc-05-13b", body)
