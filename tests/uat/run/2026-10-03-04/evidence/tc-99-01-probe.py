"""TC-99-01 probes: unauthenticated curl, unauthenticated MCP session, wrong-bearer session, mutation."""
import asyncio, json, subprocess, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:8765/mcp"
H = sys.argv[1]
out = {}


def curl(args):
    r = subprocess.run(["curl", "-s"] + args, capture_output=True, text=True, timeout=30)
    return r.stdout


body = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
hdr = ["-H", "Content-Type: application/json", "-H", "Accept: application/json, text/event-stream"]
out["curl_status"] = curl(["-o", "NUL", "-w", "%{http_code}", "-X", "POST", URL] + hdr + ["-d", body])
out["curl_follow"] = curl(["-L", "-i", "-X", "POST", URL] + hdr + ["-d", body])[:800]
out["curl_slash_status_body"] = curl(["-i", "-X", "POST", URL + "/"] + hdr + ["-d", body])[:800]


async def call(s, t, a):
    r = await s.call_tool(t, a)
    txt = "".join(b.text for b in r.content if hasattr(b, "text"))
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return {"_raw": txt}


async def session(headers, mutate):
    res = {}
    async with streamablehttp_client(URL, headers=headers) as (r, w, get_sid):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            res["session_id"] = get_sid()
            res["server"] = init.serverInfo.name
            names = sorted(t.name for t in (await s.list_tools()).tools)
            res["tool_count"] = len(names)
            res["tools_sample"] = names[:5]
            if mutate:
                before = await call(s, "query_tree_summary", {"doc": H})
                res["tree_before"] = before.get("structured_content")
                p = await call(s, "preview_dry_run", {"doc": H, "operation": {"tool": "feature_body_create", "args": {"name": "UnauthBody"}}})
                res["preview_status"] = p.get("status")
                m = await call(s, "feature_body_create", {"doc": H, "name": "UnauthBody", "confirm": {"preview_id": p["structured_content"]["preview_id"], "elicitation_action": "accept"}})
                res["mutation_status"] = m.get("status")
                res["mutation_detail"] = m.get("detail")
                res["mutation_fp"] = {k: (m.get("structured_content") or {}).get("mutation", {}).get(k) for k in ("fingerprint_before", "fingerprint_after", "committed")} if isinstance(m.get("structured_content"), dict) else None
                after = await call(s, "query_tree_summary", {"doc": H})
                res["tree_after"] = after.get("structured_content")
    return res


async def main():
    try:
        out["unauth_session"] = await session(None, True)
    except Exception as exc:  # noqa: BLE001
        out["unauth_session"] = {"error": repr(exc)}
    try:
        out["wrong_bearer_session"] = await session({"Authorization": "Bearer garbage-not-a-token-0000"}, False)
    except Exception as exc:  # noqa: BLE001
        out["wrong_bearer_session"] = {"error": repr(exc)}


asyncio.run(main())
print(json.dumps(out, indent=1, default=str))
