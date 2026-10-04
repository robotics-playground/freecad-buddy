import os

from tc09lib import *  # noqa


async def body(m, log):
    p1, p2 = f"{EV}/tc-09-16-nope-missing.FCStd", f"{EV}/tc-09-16-no_such_dir/x.FCStd"
    log.check("Given target paths do not exist", not os.path.exists(p1) and not os.path.exists(p2), "")
    doc, obj = await scene(m, log, "tc-09-16")
    before = sorted(d["doc"] for d in sc(await m.call("document_list", {})).get("documents") or [])
    res = [(p, await m.call("document_open", {"path": p})) for p in (p1, p2, "", "README.md")]
    for (p, e), name in zip(res, ("missing file", "missing dir", "empty path", "README.md")):
        log.check(f"{name} -> non-OK", e.get("status") != "OK", (status(e), msg(e)[:160] or raw(e)))
    log.check("missing file/dir/empty -> INVALID_INPUT envelope", all(e.get("status") == "INVALID_INPUT" for _, e in res[:3]), [status(e) for _, e in res])
    log.check("each message contains the path sent", all(p in msg(e) for p, e in res), [(p[-30:], msg(e)[:120]) for p, e in res])
    after = sorted(d["doc"] for d in sc(await m.call("document_list", {})).get("documents") or [])
    log.check("README.md refused, document_list names no new handle", res[3][1].get("status") != "OK" and after == before, (before, after))
    log.check("no structured_content.doc on any refused open", all(not sc(e).get("doc") for _, e in res), "")
    rep = json.loads((EVIDENCE / "tc-09-01-edge_report.json").read_text())
    hit = [c for c in rep["checks"] if c["tool"] == "open_bad_path"]
    log.check("edge report open_bad_path passed", len(hit) == 1 and hit[0]["ok"] is True, hit)
    await frame_shot(m, doc, "tc-09-16-after.png")


go("tc-09-16", body)
