from tc08lib import *  # noqa

EV = str(EVIDENCE).replace("\\", "/")
GATED = sorted(["sketch_create", "sketch_add_geometry", "sketch_remove_geometry", "sketch_add_constraint",
                "sketch_remove_constraint", "sketch_set_datum", "sketch_toggle_construction", "sketch_add_external_geometry",
                "feature_pad", "feature_pocket", "feature_revolve", "feature_hole", "feature_fillet", "feature_chamfer",
                "feature_pattern", "feature_mirror", "feature_datum", "feature_body_create", "feature_set_parameters"])


def listed(message):
    if "(previewable: " not in message:
        return None
    inner = message.split("(previewable: ", 1)[1].rstrip(")")
    return [x.strip() for x in inner.split(",")]


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0819")
    log.check("Given no stale preview TempDocs", prev_dirs() == [], prev_dirs())
    await frame_shot(m, doc, "tc-08-19-before.png")
    r_save = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "document_save",
                                                                        "args": {"path": EV + "/tc-08-19-save.FCStd"}}})
    r_exec = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "debug_exec", "args": {"code": "1"}}})
    r_none = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "no_such_tool", "args": {}}})
    r_m1 = await m.call("preview_dry_run", {"doc": doc, "operation": {"args": {"name": "Pad"}}})
    r_m2 = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_pad", "args": "not an object"}})
    dirs_after5 = prev_dirs()
    r_noop = await m.call("preview_dry_run", {"doc": doc})
    for t, r in (("save", r_save), ("exec", r_exec), ("none", r_none), ("m1", r_m1), ("m2", r_m2), ("noop", r_noop)):
        print(t, r.get("status"), msg(r)[:260])
    ms = msg(r_save)
    lst = listed(ms)
    log.check("document_save -> \"not a previewable mutation tool: 'document_save' (previewable: <sorted list>\"",
              r_save.get("status") != "OK" and ms.startswith("not a previewable mutation tool: 'document_save' (previewable: ")
              and lst == sorted(lst or []), ms[:400])
    log.check("previewable list is exactly the 19 gated tools", lst == GATED, {"listed": lst, "extra": sorted(set(lst or []) - set(GATED)),
                                                                              "missing": sorted(set(GATED) - set(lst or []))})
    log.check("debug_exec refused the same way", r_exec.get("status") != "OK"
              and msg(r_exec).startswith("not a previewable mutation tool: 'debug_exec' (previewable: "), msg(r_exec)[:200])
    log.check("no_such_tool -> same message form with its own name",
              r_none.get("status") != "OK" and msg(r_none).startswith("not a previewable mutation tool: 'no_such_tool' (previewable: "),
              msg(r_none)[:200])
    log.check("missing tool -> 'preview_dry_run requires operation.tool'",
              r_m1.get("status") != "OK" and "preview_dry_run requires operation.tool" in msg(r_m1), msg(r_m1)[:300])
    log.check("non-object args -> 'operation.args must be an object'",
              r_m2.get("status") != "OK" and "operation.args must be an object" in msg(r_m2), msg(r_m2)[:300])
    log.check("no FCB_TMP_prev_ dir after the five calls", dirs_after5 == [], dirs_after5)
    log.check("missing operation rejected by the schema (operation is required)",
              r_noop.get("status") != "OK" and "required" in msg(r_noop), msg(r_noop)[:300])
    log.check("no save file written by the refused document_save preview", not os.path.exists(EV + "/tc-08-19-save.FCStd"),
              os.path.exists(EV + "/tc-08-19-save.FCStd"))
    tr = await names(m, doc)
    log.check("tree unchanged: Body + Sketch only", tr == ["Body", "Sketch"], tr)
    await frame_shot(m, doc, "tc-08-19-after.png")
    print("DOC", doc)


go("tc-08-19", body)
