"""TC-11-04: typed tools are the only mutation path (H1 inline)."""
import asyncio
import json
import re
import subprocess

from tc11lib import *  # noqa: F401,F403
from tc11lib import BOX, EVIDENCE, REPO, Log, Mcp, baseline, closing, h1, sc, short

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-04"
PREFIX = "not a previewable mutation tool:"


def msg(e):
    return (e.get("detail") or {}).get("message") or e.get("_raw") or ""


async def main():
    log = Log(TAG)
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)
            grep = subprocess.run(["grep", "-niE", '"(exec|eval|script|run_python|run_code)"',
                                   "src/freecad_buddy/hosts/tool_catalog.py"], cwd=REPO, capture_output=True, text=True)
            log.note("grep exec/eval/script names in tool_catalog.py:\n" + grep.stdout)
            hits = [x for x in grep.stdout.splitlines() if x.strip()]
            log.check("Then no generic script/eval tool: grep matches only the gated debug_exec spec",
                      all("debug_exec" in x or "audit_event" in x for x in hits), hits)
            from freecad_buddy.hosts.tool_catalog import tool_specs  # noqa: PLC0415
            mutating = sorted(sp.name for sp in tool_specs() if sp.mutating)
            log.write({"mutating_specs": mutating})
            async with h1(log, "h1-clean", (EVIDENCE / f"{TAG}-h1.stderr.log").as_posix(),
                          drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE")) as hm:
                tools = (await hm.session.list_tools()).tools
                names = sorted(t.name for t in tools)
                other = [n for n in mutating if n in names and not re.match(r"^(document|sketch|feature|export)_", n)]
                log.check("Then every mutating listed tool is document_/sketch_/feature_/export_ (listed count %d)" % len(names),
                          not other, {"non_matching_mutating": other, "listed": len(names)})
                h1doc = sc(await hm.call("document_open", {"path": BOX})).get("doc")
                p1 = await hm.call("preview_dry_run", {"doc": h1doc, "operation": {"tool": "debug_exec",
                                                                                   "args": {"code": "result=1"}}})
                p2 = await hm.call("preview_dry_run", {"doc": h1doc, "operation": {"tool": "run_python",
                                                                                   "args": {}}})
                log.check("Then debug_exec preview: INVALID_INPUT, message starts prefix",
                          p1.get("status") == "INVALID_INPUT" and msg(p1).startswith(PREFIX), msg(p1)[:160])
                lst = re.search(r"\(previewable: (.*)\)", msg(p1))
                prev = [x.strip() for x in lst.group(1).split(",")] if lst else []
                log.check("Then refusal lists previewable sketch_/feature_ names only",
                          bool(prev) and all(re.match(r"^(sketch|feature)_", x) for x in prev), prev)
                log.check("Then unknown name refused the same way",
                          p2.get("status") == "INVALID_INPUT" and msg(p2).startswith(PREFIX), msg(p2)[:80])
                closed = {t.name: (t.inputSchema or {}).get("additionalProperties") for t in tools}
                (EVIDENCE / f"{TAG}-tool-surface.json").write_text(
                    json.dumps([{"name": t.name, "input_schema": t.inputSchema} for t in tools], indent=1), encoding="utf-8")
                log.check("Then every input schema closed (additionalProperties False) — from live H1 tools/list",
                          all(v is False for v in closed.values()), [k for k, v in closed.items() if v is not False])
                extra = await hm.call("query_capabilities", {"bogus_key": 1})
                extra2 = await hm.call("document_list", {"script": "print(1)"})
                rej = lambda e: e.get("_isError") is True and "status" not in e and "validation" in (e.get("_raw") or "").lower()  # noqa: E731
                log.check("Then undeclared key -> MCP protocol rejection, not envelope", rej(extra) and rej(extra2),
                          [short(extra), short(extra2)])
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
