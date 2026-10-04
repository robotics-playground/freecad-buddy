"""TC-11-01: debug_exec is unregistered by default (H1 inline + H2 proxy)."""
import asyncio
import json
import os
import shutil
import subprocess

from tc11lib import *  # noqa: F401,F403
from tc11lib import BOX, EVIDENCE, REPO, Log, Mcp, baseline, closing, fingerprint, h1, sc, short

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TAG = "tc-11-01"
AUDIT = (EVIDENCE / f"{TAG}-audit.jsonl").as_posix()
PAYLOAD = "import FreeCAD\nFreeCAD.newDocument('TC11_PWNED')\n"


async def main():
    log = Log(TAG)
    log.check("Given FREECAD_BUDDY_ALLOW_EXEC unset in this shell", "FREECAD_BUDDY_ALLOW_EXEC" not in os.environ,
              os.environ.get("FREECAD_BUDDY_ALLOW_EXEC"))
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            m = Mcp(s, log)
            doc = await baseline(m, log, TAG)

            # When (1): run_mcp_e2e.py exactly as written
            proc = subprocess.run(["uv", "run", "python", "scripts/automation/run_mcp_e2e.py"], cwd=REPO,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
            shutil.copy(REPO + "/_automation/e2e_report.json", EVIDENCE / f"{TAG}-e2e_report.json")
            rep = json.loads((EVIDENCE / f"{TAG}-e2e_report.json").read_text(encoding="utf-8"))
            tl = [c for c in rep.get("checks", []) if c.get("tool") == "tools/list"]
            log.note(f"run_mcp_e2e.py exit={proc.returncode} tools/list check={tl} all_passed={rep.get('all_passed')}")

            # When (2): H1 inline, clean env, scratch audit log; list tools, call debug_exec by name
            if os.path.exists(AUDIT):
                os.remove(AUDIT)
            async with h1(log, "h1-clean", (EVIDENCE / f"{TAG}-h1.stderr.log").as_posix(),
                          extra={"FREECAD_BUDDY_AUDIT_LOG": AUDIT},
                          drop=("FREECAD_BUDDY_ALLOW_EXEC", "FREECAD_BUDDY_AUTO_APPROVE")) as hm:
                names = sorted(t.name for t in (await hm.session.list_tools()).tools)
                log.write({"h1_tools": names})
                log.check("Then H1 surface lists 44 tools (TC literal)", len(names) == 44, f"actual {len(names)}")
                log.check("Then debug_exec absent from H1 listing", "debug_exec" not in names, len(names))
                h1doc = sc(await hm.call("document_open", {"path": BOX})).get("doc")
                fp_before, _ = await fingerprint(hm, h1doc)
                denied = await hm.call("debug_exec", {"doc": h1doc, "code": PAYLOAD})
                fp_after, _ = await fingerprint(hm, h1doc)
                listing = await hm.call("document_list", {})
                log.check("Then direct call refused: status INVALID_INPUT", denied.get("status") == "INVALID_INPUT", short(denied))
                msg = (denied.get("detail") or {}).get("message")
                log.check("Then detail.message exact", msg == "debug_exec is disabled (set FREECAD_BUDDY_ALLOW_EXEC=1 to enable)", msg)
                log.check("Then no code executed: fingerprint unchanged", fp_before is not None and fp_before == fp_after,
                          f"{str(fp_before)[:16]} -> {str(fp_after)[:16]}")
                log.check("Then (extra) payload doc TC11_PWNED absent from H1 document_list",
                          "TC11_PWNED" not in json.dumps(sc(listing)), [d.get("label") for d in sc(listing).get("documents") or []])
            lines = [json.loads(x) for x in open(AUDIT, encoding="utf-8")] if os.path.exists(AUDIT) else []
            exec_lines = [x for x in lines if x.get("event") == "exec"]
            log.write({"audit_exec_lines": exec_lines})
            log.check("Then denied attempt audited: before/after exec pair",
                      len(exec_lines) == 2 and exec_lines[0].get("tool") == "debug_exec"
                      and "verify_verdict" not in exec_lines[0] and exec_lines[1].get("verify_verdict") == "INVALID_INPUT",
                      [(x.get("event"), x.get("tool"), x.get("verify_verdict")) for x in exec_lines])

            # Proxy surface
            pnames = sorted(t.name for t in (await s.list_tools()).tools)
            log.write({"proxy_tools": pnames})
            log.check("Then proxy tools/list returns 44 tools (TC literal)", len(pnames) == 44, f"actual {len(pnames)}")
            log.check("Then proxy listing has no debug_exec", "debug_exec" not in pnames, len(pnames))
            log.check("Then H1 and proxy surfaces identical", pnames == names,
                      {"only_h1": sorted(set(names) - set(pnames)), "only_proxy": sorted(set(pnames) - set(names))})
            # Extra: direct call against the GUI proxy too (the visual target)
            gdenied = await m.call("debug_exec", {"doc": doc, "code": PAYLOAD})
            log.check("Then (extra) proxy direct debug_exec refused", gdenied.get("status") == "INVALID_INPUT" or gdenied.get("_isError"),
                      short(gdenied))
            glist = await m.call("document_list", {})
            log.check("Then (extra) GUI document_list has no TC11_PWNED",
                      "TC11_PWNED" not in json.dumps(sc(glist)), [d.get("label") for d in sc(glist).get("documents") or []])
            await closing(m, log, doc, TAG)
    log.save()


asyncio.run(main())
