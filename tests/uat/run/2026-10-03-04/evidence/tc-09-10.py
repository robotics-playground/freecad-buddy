from tc09lib import *  # noqa


def nest(depth):
    node = {"a": 1}
    for _ in range(depth - 1):
        node = {"a": node}
    return node


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-10")
    mark = addon_mark()
    log.note("mcp client refuses to serialize the 100-deep payload (pydantic: Circular reference detected (depth exceeded)); sent over raw httpx")
    a = raw_call("verify_shape", {"doc": doc, "object": obj, "checks": [{"fn": nest(100)}]}, log)
    b = await m.call("verify_shape", {"doc": doc, "object": obj, "checks": ["expect_volume"]})
    c = await m.call("verify_shape", {"doc": doc, "object": obj, "checks": [
        {"fn": "expect_volume", "expect": 6000, "tol": {"rel": {"deep": {"deeper": 0.001}}}}]})
    log.check("100-deep fn -> handler INVALID_INPUT 'unknown assertion fn:'", a.get("status") == "INVALID_INPUT" and msg(a).startswith("unknown assertion fn:"),
              {"status": status(a), "msg": msg(a)[:120], "raw": raw(a)[:200]})
    log.check("non-object check -> INVALID_INPUT \"check must be an object, got 'expect_volume'\"",
              b.get("status") == "INVALID_INPUT" and msg(b) == "check must be an object, got 'expect_volume'", {"status": status(b), "msg": msg(b)[:160], "raw": raw(b)[:200]})
    log.check("nested tol -> real envelope (INVALID_INPUT via TypeError/ValueError, not unhandled)", c.get("_sc") is True and "status" in c,
              {"status": status(c), "msg": msg(c)[:160], "exc": ((c.get("detail") or {}).get("data") or {}).get("exception"),
               "unexpected": ((c.get("detail") or {}).get("data") or {}).get("unexpected")})
    log.check("no protocol rejection among the three", all(e.get("_sc") is True and "status" in e for e in (a, b, c)), [status(e) for e in (a, b, c)])
    ok = await m.call("verify_shape", {"doc": doc, "object": obj})
    log.check("server survives: bare verify_shape OK", ok.get("status") == "OK", ok.get("status"))
    import pathlib
    since = addon_since(mark)
    (EVIDENCE / "tc-09-10-addonlog.txt").write_text(since, encoding="utf-8")
    edge = pathlib.Path(EV + "/tc-09-01-edge.stderr.log").read_text(encoding="utf-8", errors="replace")
    log.check("no RecursionError in edge stderr or addon log", "RecursionError" not in since and "RecursionError" not in edge, "")
    await frame_shot(m, doc, "tc-09-10-after.png")


go("tc-09-10", body)
