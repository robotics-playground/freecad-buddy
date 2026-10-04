"""Send a pad length encoded as the JSON number 1e999 (parses to IEEE infinity) over the MCP HTTP endpoint.

The python MCP client serialises float('inf') as null, so the raw JSON-RPC body is written by hand here.
Only the public MCP endpoint is used. Usage: python tc-04-19-inf.py <doc-handle>
"""
import json
import sys

import httpx

URL = "http://127.0.0.1:8765/mcp/"
HEAD = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def parse(resp):
    text = resp.text
    if "text/event-stream" in resp.headers.get("content-type", ""):
        datas = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        return [json.loads(d) for d in datas if d]
    return [json.loads(text)] if text.strip() else []


with httpx.Client(timeout=60, follow_redirects=True) as c:
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "tc-04-19-inf", "version": "1"}}}
    r = c.post(URL, headers=HEAD, content=json.dumps(init))
    sid = r.headers.get("mcp-session-id")
    h = dict(HEAD, **({"mcp-session-id": sid} if sid else {}))
    c.post(URL, headers=h, content=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
    body = ('{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"feature_pad","arguments":'
            '{"doc":"%s","body":"BlockBody","profile":"BlockProfile","name":"InfPad","length":{"value":1e999,"unit":"mm"}}}}' % sys.argv[1])
    print("REQUEST", body)
    r = c.post(URL, headers=h, content=body)
    print("STATUS", r.status_code, r.headers.get("content-type"), repr(r.text[:1500]))
    for msg in parse(r):
        print("RESPONSE", json.dumps(msg)[:1500])
