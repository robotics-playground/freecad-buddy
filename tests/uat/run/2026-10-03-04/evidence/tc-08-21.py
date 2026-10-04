import sys
import time
from tc08lib import *  # noqa
from tc03lib import expand, find, model_items, snapshot

STAGE = sys.argv[1] if len(sys.argv) > 1 else "main"


async def main_stage(m, log):
    await close_all(m, log)
    cr = await m.call("document_create", {"label": "UndoProbe"})
    doc = sc(cr).get("doc")
    log.check("Given document_create UndoProbe returns a handle", bool(doc), short(cr))
    log.check("second document whose undo stack cannot be enabled", None,
              "NOT RUN: shim.enable_undo (shim.py:366-378) writes UndoMode=1 and the 1.1.4 GUI build honours it; "
              "no wire path leaves a document at UndoMode 0")
    await frame_shot(m, doc, "tc-08-21-before.png")
    u0 = await m.call("document_undo", {"doc": doc})
    _, bc = await apply(m, doc, "feature_body_create", {"name": "Body"})
    u1 = await m.call("document_undo", {"doc": doc})
    u2 = await m.call("document_undo", {"doc": doc})
    log.write({"u0": u0, "u1": u1, "u2": u2, "body_create": {"status": bc.get("status")}})
    name = "UndoProbe"
    empty = f"nothing to undo on {name}: the undo stack is empty"
    log.check("empty stack refused with exact message", u0.get("status") != "OK" and msg(u0) == empty, msg(u0)[:200])
    log.check("first real undo OK, undone == 'buddy: <body-create label>'",
              u1.get("status") == "OK" and str(sc(u1).get("undone") or "").startswith("buddy: ")
              and "Body" in str(sc(u1).get("undone")), {"status": u1.get("status"), "undone": sc(u1).get("undone")})
    log.check("exhausting the stack refused with the same empty-stack message", u2.get("status") != "OK" and msg(u2) == empty,
              msg(u2)[:200])
    fab = [k for k in ("matches_pre_op", "fingerprint_after", "undone") for u in (u0, u2) if k in sc(u)]
    log.check("neither refusal carries matches_pre_op / fingerprint_after / undone", not fab,
              {"u0_sc": sc(u0), "u2_sc": sc(u2)})
    log.check("undo_count is 0 after the successful undo", sc(u1).get("undo_count") == 0, sc(u1).get("undo_count"))
    log.check("undo leaving an object in error state -> RECOMPUTE_ERROR naming it", None,
              "NOT RUN: no deterministic wire-only recipe for an undo whose recompute leaves an object invalid "
              "(every bridge mutation rolls back on an invalid recompute, so no such undo target can be committed)")
    log.check("tree after: no Body", "Body" not in await names(m, doc), await names(m, doc))
    await frame_shot(m, doc, "tc-08-21-after.png")
    (EVIDENCE / "tc-08-21-doc.json").write_text(json.dumps({"doc": doc}), encoding="utf-8")
    print("DOC", doc)


async def opentx_setup(m, log):
    """Separate document with a Pad, so FreeCAD's own Pad edit (double-click) leaves a transaction open."""
    t = await body_sketch(m, "TC0821T", pad=30)
    (EVIDENCE / "tc-08-21-opentx.json").write_text(json.dumps({"doc": t}), encoding="utf-8")
    await m.fit(t)
    print("DOC", t)


async def opentx_check(m, log):
    t = json.loads((EVIDENCE / "tc-08-21-opentx.json").read_text())["doc"]
    r = await m.call("document_undo", {"doc": t})
    want = ("TC0821T has an open transaction; undo would commit it and revert the transaction beneath it. "
            "Commit or abort it first.")
    log.check("open GUI transaction refused with exact message", r.get("status") != "OK" and msg(r) == want,
              {"status": r.get("status"), "message": msg(r)[:300], "sc": sc(r)})
    shot("tc-08-21-opentx.png")


async def body(m, log):
    if STAGE == "main":
        await main_stage(m, log)
    elif STAGE == "opentx-setup":
        await opentx_setup(m, log)
    elif STAGE == "opentx-check":
        await opentx_check(m, log)


go("tc-08-21-" + STAGE, body)
