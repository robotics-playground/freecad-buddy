import os

from tc09lib import *  # noqa
from tc08h1 import h1

UNW = EV + "/tc-09-19-unwritable_dir"
GOOD = EV + "/tc-09-19-audit.jsonl"


async def drive(log, tag, audit, errlog):
    out = {}
    async with h1(log, tag, errlog, extra={"FREECAD_BUDDY_AUDIT_LOG": audit}) as s:
        out["create"] = await s.call("document_create", {"label": "TC0919Audit"})
        d = sc(out["create"]).get("doc")
        out["close"] = await s.call("document_close", {"doc": d}) if d else {"status": "NO_DOC"}
        out["caps"] = await s.call("query_capabilities", {})
        out["tools"] = len((await s.session.list_tools()).tools)
    return out


async def body(m, log):
    os.makedirs(UNW, exist_ok=True)
    log.check("Given unwritable target: a directory used as the log file path", os.path.isdir(UNW), UNW)
    doc, obj = await scene(m, log, "tc-09-19")
    a = await drive(log, "h1-unwritable", UNW, EV + "/tc-09-19-unwritable.stderr.log")
    log.check("mutating call returns a real envelope with closed-set status", a["create"].get("status") in
              ("OK", "SPEC_FAILED", "RECOMPUTE_ERROR", "TIMEOUT", "OOM_KILLED", "WORKER_CRASHED", "INVALID_INPUT"),
              (status(a["create"]), msg(a["create"])[:160], raw(a["create"])))
    log.check("document_create still OK (audit sink does not turn it into an error)", a["create"].get("status") == "OK", status(a["create"]))
    log.note(f"document_close under unwritable sink -> {status(a['close'])} {msg(a['close'])[:120]}")
    log.check("read-only query_capabilities OK", a["caps"].get("status") == "OK", status(a["caps"]))
    err = open(EV + "/tc-09-19-unwritable.stderr.log", encoding="utf-8", errors="replace").read()
    hits = [ln[:220] for ln in err.splitlines() if "audit" in ln.lower() or "PermissionError" in ln or "IsADirectory" in ln]
    log.check("audit write failure visible in server stderr", len(hits) > 0, hits[:6])
    log.check("server survives: tools/list answered after the calls", a["tools"] > 0, a["tools"])
    if os.path.exists(GOOD):
        os.remove(GOOD)
    b = await drive(log, "h1-writable", GOOD, EV + "/tc-09-19-writable.stderr.log")
    recs = [json.loads(ln) for ln in open(GOOD, encoding="utf-8")] if os.path.exists(GOOD) else []
    phases = [(r.get("phase") or r.get("stage") or r.get("kind") or "?", r.get("tool")) for r in recs]
    log.note(f"writable audit records: {phases}; keys: {sorted(recs[0].keys()) if recs else None}")
    log.check("writable path restores auditing: before and after records", b["create"].get("status") == "OK" and len(recs) >= 2
              and any("verify_verdict" in r for r in recs) and any("verify_verdict" not in r for r in recs), {"n": len(recs), "phases": phases})
    await frame_shot(m, doc, "tc-09-19-after.png")


go("tc-09-19", body)
