"""TC-11-08: auto-approve warns at startup and audits every auto-approved mutation (H1 inline)."""
import asyncio
import json
import os

from tc11lib import *  # noqa: F401,F403
from tc11lib import BOX, EVIDENCE, Log, Mcp, baseline, closing, h1, sc, short

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-08"
AUDIT = (EVIDENCE / f"{TAG}-approve.jsonl").as_posix()
WARN = "SECURITY: mutation auto-approve ENABLED by operator flag"
REFUSAL = "this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id"
OP = ("feature_body_create", {"name": "Tc11Body"})


async def run(log, value):
    err = (EVIDENCE / f"{TAG}-h1-{value}.stderr.log").as_posix()
    async with h1(log, f"AUTO_APPROVE={value}", err, extra={"FREECAD_BUDDY_AUTO_APPROVE": value, "FREECAD_BUDDY_AUDIT_LOG": AUDIT},
                  drop=("FREECAD_BUDDY_ALLOW_EXEC",)) as hm:
        doc = sc(await hm.call("document_open", {"path": BOX})).get("doc")
        env = await hm.call(OP[0], dict(OP[1], doc=doc))
    return env, open(err, encoding="utf-8", errors="replace").read()


async def main():
    log = Log(TAG)
    log.note("Operator acceptance: mutations without confirm only on separate H1 headless processes (authorized by the run brief); GUI never auto-approve here.")
    if os.path.exists(AUDIT):
        os.remove(AUDIT)
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            env1, err1 = await run(log, "1")
            lines_after_1 = [json.loads(x) for x in open(AUDIT, encoding="utf-8")]
            env2, err2 = await run(log, "true")
            lines = [json.loads(x) for x in open(AUDIT, encoding="utf-8")]
            log.write({"audit_lines": lines})
            log.check("Then stderr (=1) contains the auto-approve SECURITY warning", WARN in err1, "")
            msg1 = (env1.get("detail") or {}).get("message") or ""
            log.check("Then mutation runs without confirm: status OK, no confirm-required message",
                      env1.get("status") == "OK" and "requires a confirm" not in json.dumps(env1), short(env1))
            appr = [x for x in lines if x.get("event") == "approval"]
            raw = open(AUDIT, encoding="utf-8").read()
            log.check("Then grep -c '\"event\": \"approval\"' == 1", raw.count('"event": "approval"') == 1, raw.count('"event": "approval"'))
            a = appr[0] if appr else {}
            log.check("Then approval names the mutating tool", a.get("tool") == OP[0], a.get("tool"))
            mut1 = [x for x in lines_after_1 if x.get("tool") == OP[0] and x.get("event") == "mutation"]
            before = next((x for x in mut1 if "verify_verdict" not in x), {})
            after = next((x for x in mut1 if "verify_verdict" in x), {})
            log.check("Then approval fingerprint_before == mutation before line fingerprint_before",
                      a.get("fingerprint_before") is not None and a.get("fingerprint_before") == before.get("fingerprint_before"),
                      {"approval": str(a.get("fingerprint_before"))[:16], "before": str(before.get("fingerprint_before"))[:16],
                       "after_line": str(after.get("fingerprint_before"))[:16]})
            log.check("Then approval params_digest == before/after digest",
                      a.get("params_digest") and a.get("params_digest") == before.get("params_digest") == after.get("params_digest"),
                      {"approval": str(a.get("params_digest"))[:16], "before": str(before.get("params_digest"))[:16],
                       "after": str(after.get("params_digest"))[:16]})
            msg2 = (env2.get("detail") or {}).get("message") or env2.get("_raw") or ""
            log.check("Then AUTO_APPROVE=true: no warning in stderr", WARN not in err2, "")
            log.check("Then AUTO_APPROVE=true: unconfirmed mutation refused with exact message", msg2 == REFUSAL,
                      {"status": env2.get("status"), "message": msg2})
            log.note(f"approval record keys: {sorted(a)}; approval block: {a.get('approval')}")
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
