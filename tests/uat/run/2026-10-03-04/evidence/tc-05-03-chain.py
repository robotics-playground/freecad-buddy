from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0503"][0]["doc"]
    preview, env = await apply(m, doc, "feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad001", "length": q(5)})
    p = pv(env)
    log.note(f"repeat with invalid 'Bad' Part::Box present: feature_pad Pad001 -> status={env.get('status')} rolled_back={mut(env).get('rolled_back')} proof={mut(env).get('rollback_proven')}")
    log.check("chain: recompute_clean false, is_valid false, explanation starts 'recompute left '",
              p.get("recompute_clean") is False and p.get("is_valid") is False and str(p.get("explanation") or "").startswith("recompute left "),
              {k: p.get(k) for k in ("recompute_clean", "is_valid", "fully_constrained", "explanation")})
    log.check("chain: status RECOMPUTE_ERROR", env.get("status") == "RECOMPUTE_ERROR", short(env))
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("chain: Pad001 not in tree", not tree_has(tr, "Pad001"), "")
    c = await m.call("document_close", {"doc": doc})
    log.note(f"cleanup TC0503 close -> {c.get('status')} (state captured in evidence before cleanup)")


go("tc-05-03-chain", body)
