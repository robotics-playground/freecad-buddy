"""TC-09 helpers on top of tc08lib: golden open, schema-reject detection, results file upsert."""

import os

from tc08lib import *  # noqa: F401,F403
from tc08lib import EVIDENCE, Log, Mcp, close_all, frame_shot, go, json, msg, sc, short  # noqa: F401

PROJECT = "D:/Work/Personal/Sources/freecad-buddy"
GOLDEN = PROJECT + "/benchmarks/g0/golden-models"
EV = EVIDENCE.as_posix()
RESULTS = EVIDENCE / "tc-09-results.json"


def is_reject(envelope):
    """MCP input-schema rejection: isError set, structuredContent null, no envelope status."""
    return envelope.get("_isError") is True and "status" not in envelope and envelope.get("_sc") is False


def status(envelope):
    return envelope.get("status") or ("SCHEMA_REJECT" if is_reject(envelope) else "NO_STATUS")


def raw(envelope):
    return (envelope.get("_raw") or "")[:300]


async def open_golden(m, name="box-10-20-30"):
    env = await m.call("document_open", {"path": f"{GOLDEN}/{name}.FCStd"})
    return sc(env).get("doc"), env


async def roots(m, doc):
    tr = await m.call("query_tree_summary", {"doc": doc})
    return [n.get("name") for n in sc(tr).get("tree") or []], tr


def record(tc_id, priority, verdict, evidence, note):
    data = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else []
    data = [r for r in data if r["id"] != tc_id]
    data.append({"id": tc_id, "priority": priority, "verdict": verdict, "evidence": evidence, "note": note})
    data.sort(key=lambda r: r["id"])
    RESULTS.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def show_all(log):
    """FreeCAD's own View > Visibility > Show All Objects: golden fixtures open with Box hidden (harness fact)."""
    import time as _t
    pid, win = ids()
    r = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Visibility", "Show All Objects"]})
    _t.sleep(1.0)
    log.note(f"golden opens hidden: View>Visibility>Show All Objects -> {r.get('effect')} {r.get('route')} {r.get('error') or ''}")
    return r


async def open_shown(m, log, name="box-10-20-30"):
    doc, op = await open_golden(m, name)
    show_all(log)
    return doc, op


async def scene(m, log, tag, golden="box-10-20-30"):
    """close_all, open a golden shown, resolve its sole root object, fit, capture before."""
    await close_all(m, log)
    doc, op = await open_shown(m, log, golden)
    log.check(f"Given document_open {golden} OK", op.get("status") == "OK", doc)
    names, _ = await roots(m, doc)
    log.note(f"roots {names}")
    await frame_shot(m, doc, f"{tag}-before.png")
    return doc, (names[0] if names else None)



class Mcp9(Mcp):
    """Mcp that also records whether the MCP result carried structuredContent (None on a schema reject)."""

    async def call(self, tool, args):
        import time as _t
        started = _t.time()
        result = await self.session.call_tool(tool, args)
        text = "".join(block.text for block in result.content if hasattr(block, "text"))
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError:
            envelope = {"_raw": text}
        if not isinstance(envelope, dict):
            envelope = {"_value": envelope}
        is_error = bool(getattr(result, "isError", False))
        has_sc = result.structuredContent is not None
        self.log.write({"tool": tool, "args": args if len(json.dumps(args)) < 4000 else "<large args elided>",
                        "isError": is_error, "structuredContent_present": has_sc,
                        "seconds": round(_t.time() - started, 3), "envelope": envelope})
        envelope["_isError"] = is_error
        envelope["_sc"] = has_sc
        return envelope


def go(name, body):
    import asyncio
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _run():
        log = Log(name)
        async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await body(Mcp9(session, log), log)
        log.save()

    asyncio.run(_run())


ADDON_LOG = os.path.expandvars(r"%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log")


def addon_mark():
    return os.path.getsize(ADDON_LOG) if os.path.exists(ADDON_LOG) else 0


def addon_since(mark):
    with open(ADDON_LOG, "rb") as handle:
        handle.seek(mark)
        return handle.read().decode("utf-8", "replace")


def count_nodes(nodes):
    return sum(1 + count_nodes(n.get("children")) for n in nodes or [])


def raw_call(tool, args, log=None, timeout=120):
    """tools/call over raw streamable HTTP (httpx), bypassing the client's pydantic serializer.

    Needed for payloads the mcp client refuses to serialize (pydantic depth limit on 100-level nesting).
    Returns {"isError", "structuredContent_present", "envelope" or "_raw", "http_status"}.
    """
    import httpx
    url = "http://127.0.0.1:8765/mcp"
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}

    def parse(resp):
        ctype = resp.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            for line in resp.text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[5:].strip())
            return {"_raw": resp.text[:2000]}
        try:
            return resp.json()
        except Exception:  # noqa: BLE001
            return {"_raw": resp.text[:2000]}

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        init = client.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tc09-raw", "version": "0"}}})
        sid = init.headers.get("mcp-session-id")
        h2 = dict(headers)
        if sid:
            h2["mcp-session-id"] = sid
        client.post(url, headers=h2, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        body = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": args}})
        resp = client.post(url, headers=h2, content=body)
        msg_ = parse(resp)
    result = msg_.get("result") or {}
    text = "".join(b.get("text", "") for b in result.get("content") or [] if isinstance(b, dict))
    try:
        env = json.loads(text)
    except Exception:  # noqa: BLE001
        env = {"_raw": text or json.dumps(msg_)[:2000]}
    if not isinstance(env, dict):
        env = {"_value": env}
    out = {"tool": tool, "transport": "raw-httpx", "http_status": resp.status_code, "isError": bool(result.get("isError")),
           "structuredContent_present": result.get("structuredContent") is not None, "jsonrpc_error": msg_.get("error"),
           "envelope": env}
    if log:
        log.write(dict(out, args_bytes=len(body)))
    env["_isError"] = out["isError"]
    env["_sc"] = out["structuredContent_present"]
    env["_rpcerr"] = msg_.get("error")
    return env
