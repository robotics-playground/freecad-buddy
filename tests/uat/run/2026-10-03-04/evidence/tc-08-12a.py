import time
from datetime import datetime, timezone
from tc08lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0812")
    await frame_shot(m, doc, "tc-08-12-before.png")
    t_call = time.time()
    pr = await preview(m, doc, "feature_body_create", {"name": "Probe"})
    t_ret = time.time()
    tok = token(pr)
    exp = sc(pr).get("expires_at")
    exp_ts = datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp()
    log.check("advertised TTL is 900 s (expires_at - call time, within clock skew)",
              abs((exp_ts - t_call) - 900) < 5, {"expires_at": exp, "call": t_call, "ttl_vs_call": round(exp_ts - t_call, 3),
                                                  "ttl_vs_return": round(exp_ts - t_ret, 3)})
    a1 = await call_with(m, doc, "feature_body_create", {"name": "Probe"}, {"preview_id": tok})
    log.check("first apply (spends token) OK", a1.get("status") == "OK", short(a1))
    time.sleep(1.0)
    r1 = await call_with(m, doc, "feature_body_create", {"name": "Probe"}, {"preview_id": tok})
    spent = "confirm.preview_id has already authorized a mutation; re-run preview_dry_run"
    log.check("1 s after apply (spent, not expired) -> already-authorized message", r1.get("status") != "OK" and spent in msg(r1), msg(r1))
    # unexpired unspent token still works: side doc, so TC0812 keeps exactly one Probe
    side = await body_sketch(m, "TC0812b")
    ps = await preview(m, side, "feature_body_create", {"name": "Probe"})
    aps = await call_with(m, side, "feature_body_create", {"name": "Probe"}, {"preview_id": token(ps)})
    log.check("fresh unexpired unspent token applied within TTL -> OK (side doc TC0812b)", aps.get("status") == "OK", short(aps))
    c = await m.call("document_close", {"doc": side})
    log.note(f"side doc TC0812b closed -> {c.get('status')}")
    (EVIDENCE / "tc-08-12-token.json").write_text(json.dumps({"doc": doc, "token": tok, "expires_at": exp, "exp_ts": exp_ts,
                                                             "mint_call_ts": t_call}), encoding="utf-8")
    print("DOC", doc, "expires", exp, "wait until", exp_ts + 2)


go("tc-08-12a", body)
