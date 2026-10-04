from tc09lib import *  # noqa


async def body(m, log):
    before = sorted(d["doc"] for d in sc(await m.call("document_list", {})).get("documents") or [])
    e = await m.call("document_open", {"path": PROJECT + "/AGENTS.md"})
    after = sorted(d["doc"] for d in sc(await m.call("document_list", {})).get("documents") or [])
    log.check("extra: absolute existing AGENTS.md (not FCStd) refused, no new handle", e.get("status") != "OK" and after == before,
              (status(e), msg(e)[:200], before, after))


go("tc-09-16b", body)
