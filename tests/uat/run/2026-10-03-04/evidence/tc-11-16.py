"""TC-11-16: the session token never appears in results, artifacts or reports. The token stays in memory; only the mask and verdicts are written."""
import asyncio
import glob
import json
import os
import shutil
import time

from tc11lib import *  # noqa: F401,F403
from tc11lib import EVIDENCE, Log, Mcp, apply, baseline, closing, mask, sc, short
from tc03lib import ids
from tc11rpc import APPDIR, Rpc, proxy_start, proxy_stop, read_record

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-16"
AUDIT_SRC = os.environ.get("FREECAD_BUDDY_AUDIT_LOG", "")


async def session(fn):
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


def contains(path, token):
    with open(path, "rb") as f:
        return token.encode() in f.read()


def walk_values(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_values(v)
    else:
        yield obj


async def main():
    log = Log(TAG)
    pid, _ = ids()
    token = read_record(pid)["token"]
    log.check("Given session token held in memory (masked)", bool(token), mask(token))
    audit_start = os.path.getsize(AUDIT_SRC) if os.path.exists(AUDIT_SRC) else 0
    envelopes = []

    async def run(s):
        m = Mcp(s, log)
        doc = await baseline(m, log, TAG)
        calls = [("query_capabilities", {}), ("query_tree_summary", {"doc": doc}), ("query_object", {"doc": doc, "object": "Box"}),
                 ("query_mass_properties", {"doc": doc, "object": "Box"}), ("query_placement", {"doc": doc, "object": "Box"}),
                 ("query_dependencies", {"doc": doc}), ("verify_shape", {"doc": doc, "object": "Box"}), ("verify_recompute", {"doc": doc}),
                 ("query_screenshot", {"doc": doc})]
        for tool, args in calls:
            envelopes.append({"tool": tool, "envelope": await m.call(tool, args)})
        step = (EVIDENCE / f"{TAG}-box.step").as_posix()
        ex = await m.call("export_step", {"doc": doc, "path": step})
        envelopes.append({"tool": "export_step", "envelope": ex})
        envelopes.append({"tool": "verify_export_step", "envelope": await m.call("verify_export_step", {"doc": doc, "export_id": sc(ex).get("export_id")})})
        scratch = sc(await m.call("document_create", {"label": "tc11-16-scratch"})).get("doc")
        p, mu = await apply(m, scratch, "feature_body_create", {"name": "Body"})
        envelopes.extend([{"tool": "preview_dry_run", "envelope": p}, {"tool": "feature_body_create", "envelope": mu}])
        envelopes.append({"tool": "document_close", "envelope": await m.call("document_close", {"doc": scratch})})
        return doc
    doc = await session(run)
    report = EVIDENCE / f"{TAG}-e2e-report.json"
    report.write_text(json.dumps(envelopes, indent=1), encoding="utf-8")
    log.note("statuses: " + str([(e["tool"], e["envelope"].get("status")) for e in envelopes]))
    shot_env = next(e["envelope"] for e in envelopes if e["tool"] == "query_screenshot")
    link = ((sc(shot_env).get("render") or {}).get("resource_link"))
    log.note(f"query_screenshot render: {json.dumps(sc(shot_env).get('render'))[:300]}")
    if link and os.path.exists(link.replace("file:///", "").replace("file://", "")):
        shutil.copy(link.replace("file:///", "").replace("file://", ""), EVIDENCE / f"{TAG}-render.png")
    if os.path.exists(AUDIT_SRC):
        with open(AUDIT_SRC, "rb") as f:
            f.seek(audit_start)
            (EVIDENCE / f"{TAG}-audit.jsonl").write_bytes(f.read())
    caps = next(e["envelope"] for e in envelopes if e["tool"] == "query_capabilities")

    log.note("stop proxy for a direct rpc_hello -> " + proxy_stop().replace("\n", " | "))
    c = Rpc(log, TAG, "hello")
    hello = c.hello()
    c.close()
    log.note(f"proxy restart: {proxy_start(TAG)}")

    log.check("Then no envelope carries the token (tc-11-16-e2e-report.json)", not contains(report, token), "verdict only")
    pngs = sorted(glob.glob(str(EVIDENCE / f"{TAG}-*.png")))
    log.check("Then no render artifact carries it (tc-11-16-*.png)", not any(contains(p, token) for p in pngs), [os.path.basename(p) for p in pngs])
    log.check("Then the audit log does not carry it (scenario slice + whole inherited audit file)",
              not contains(EVIDENCE / f"{TAG}-audit.jsonl", token) and not contains(AUDIT_SRC, token),
              {"slice_bytes": os.path.getsize(EVIDENCE / f"{TAG}-audit.jsonl"), "file": AUDIT_SRC})
    log.check("Then addon.log does not carry it", not contains(f"{APPDIR}/addon.log", token), "")
    log.check("Then mcp-proxy.log does not carry it", not contains(f"{APPDIR}/mcp-proxy.log", token), "")
    res = (hello or {}).get("result") or {}
    log.check("Then rpc_hello result has exactly keys contract_version, freecad_version, capabilities",
              sorted(res) == ["capabilities", "contract_version", "freecad_version"], sorted(res))
    log.check("Then query_capabilities structured_content has no value equal to the token",
              token not in [v for v in walk_values(sc(caps))] and token not in json.dumps(caps), "verdict only")
    leaks = [os.path.basename(p) for p in glob.glob(str(EVIDENCE / "*")) if os.path.isfile(p) and contains(p, token)]
    log.check("Then (extra) no file in the run evidence folder contains the live token", not leaks, leaks)
    time.sleep(1)

    async def close_visual(s):
        await closing(Mcp(s, log), log, doc, TAG)
    await session(close_visual)
    log.check("Then (extra) after.png does not carry the token bytes", not contains(EVIDENCE / f"{TAG}-after.png", token), "")
    log.save()


asyncio.run(main())
