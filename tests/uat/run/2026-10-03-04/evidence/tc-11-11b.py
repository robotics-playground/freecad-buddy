"""TC-11-11 addendum: a preview whose op really fails recompute (oversized fillet), same counting as tc-11-11.py."""
import asyncio
import json

from tc11lib import EVIDENCE, Log, Mcp, closing, h1, sc
from tc05lib import apply, body_sketch, q, sel
import importlib.util
spec = importlib.util.spec_from_file_location("t11", str(EVIDENCE / "tc-11-11.py"))
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import glob, os
from tc11lib import TEMP

TAG = "tc-11-11b"
WORK = (EVIDENCE / "tc-11-11-workdir").as_posix()


def prev_dirs():
    return sorted(p.replace("\\", "/") for base in (TEMP, WORK + "/tmp") for p in glob.glob(os.path.join(base, "FCB_TMP_prev_*")))


async def main():
    log = Log(TAG)
    async with h1(log, "h1", (EVIDENCE / f"{TAG}-h1.stderr.log").as_posix(), extra={"FREECAD_BUDDY_WORKDIR": WORK},
                  drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE")) as hm:
        hdoc = await body_sketch(hm, "tc11-11b-preview", pad=5)
        base = prev_dirs()
        env = await hm.call("preview_dry_run", {"doc": hdoc, "operation": {"tool": "feature_fillet", "args": {
            "body": "Body", "base": "Pad", "name": "BigFillet", "edges": [sel("Pad", "Edge1")], "radius": q(50)}}})
        now = prev_dirs()
        lst = await hm.call("document_list", {})
        labels = [(d.get("label"), d.get("name")) for d in sc(lst).get("documents") or []]
        v = (sc(env).get("diff") or {}).get("validity") or {}
        log.note(f"oversized fillet preview: envelope status={env.get('status')} detail={env.get('detail')} validity={json.dumps(v)}")
        log.check("Then failure path leaves nothing: FCB_TMP_prev_* unchanged", now == base, {"count": len(now), "new": sorted(set(now) - set(base))})
        log.check("Then no FCB_TMP_prev_ handle in document_list", "FCB_TMP_prev_" not in str(labels), labels)
        log.check("Then failing preview: envelope status SPEC_FAILED or RECOMPUTE_ERROR (TC literal)",
                  env.get("status") in ("SPEC_FAILED", "RECOMPUTE_ERROR"), env.get("status"))
        log.check("Then (merits) failure reported as an envelope, not raised: diff.validity.status RECOMPUTE_ERROR with the real cause",
                  not env.get("_isError") and v.get("status") in ("SPEC_FAILED", "RECOMPUTE_ERROR") and "Fillet" in (v.get("explanation") or "")
                  and "cleanup" not in (v.get("explanation") or "").lower(), v.get("explanation"))
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            docs = sc(await m.call("document_list", {})).get("documents") or []
            await closing(m, log, docs[0]["doc"], "tc-11-11")
    log.save()

asyncio.run(main())
