from tc09lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    sc0 = await m.call("document_create", {"label": "TC0909Scratch"})
    log.check("Given scratch document_create OK", sc0.get("status") == "OK", sc(sc0).get("doc"))
    doc, op = await open_shown(m, log)
    log.check("Given golden open OK", op.get("status") == "OK", doc)
    await frame_shot(m, doc, "tc-09-09-before.png")
    mark = addon_mark()
    label = "a" * 4096
    cr = await m.call("document_create", {"label": label})
    path = f"{EV}/tc-09-09-" + "b" * 8192 + ".FCStd"
    opn = await m.call("document_open", {"path": path})
    name = "c" * 65536
    qo = await m.call("query_object", {"doc": doc, "object": name})
    log.check("long label -> real envelope OK or INVALID_INPUT", cr.get("status") in ("OK", "INVALID_INPUT") and cr.get("_sc"), short(cr, 200))
    dl = await m.call("document_list", {})
    docs = sc(dl).get("documents") or []
    long_docs = [d for d in docs if d.get("doc") == sc(cr).get("doc")]
    if cr.get("status") == "OK":
        got = long_docs[0].get("label") if long_docs else None
        log.check("accepted label not truncated: document_list label length == 4096", got is not None and len(got) == 4096 and got == label,
                  {"len": len(got) if got else None, "keys": list(long_docs[0].keys()) if long_docs else None,
                   "name_len": len(long_docs[0].get("name") or "") if long_docs else None})
    else:
        log.check("accepted label not truncated", None, "label refused, assertion not applicable")
    m_open = msg(opn)
    log.check("long nonexistent path -> INVALID_INPUT naming the path", opn.get("status") == "INVALID_INPUT" and ("b" * 8192) in m_open,
              {"status": opn.get("status"), "msg_len": len(m_open), "msg_head": m_open[:120]})
    m_q = msg(qo)
    log.check("long object name -> INVALID_INPUT 'unknown object: ccc...'", qo.get("status") == "INVALID_INPUT" and m_q.startswith("unknown object: ccc"),
              {"status": qo.get("status"), "msg_len": len(m_q), "head": m_q[:40]})
    tbs = [(len(((e.get("detail") or {}).get("data") or {}).get("traceback") or "")) for e in (opn, qo)]
    log.check("detail.data.traceback <= 4000 chars", all(0 < n <= 4000 for n in tbs), tbs)
    cap = await m.call("query_capabilities", {})
    log.check("server survives: query_capabilities OK", cap.get("status") == "OK", cap.get("status"))
    since = addon_since(mark)
    (EVIDENCE / "tc-09-09-addonlog.txt").write_text(since[:20000], encoding="utf-8")
    bad = [ln[:200] for ln in since.splitlines() if "handshake required" in ln or "frame" in ln.lower()]
    log.check("no handshake/frame-size error in addon log", bad == [], bad)
    log.note(f"document_list after: {[(d.get('label') or '')[:30] + '..' + str(len(d.get('label') or '')) for d in docs]}")
    await frame_shot(m, doc, "tc-09-09-after.png")


go("tc-09-09", body)
