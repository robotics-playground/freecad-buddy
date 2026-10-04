"""TC-10-03 When/Then: client A holds the listener; client B connects, hellos, waits; A closes."""
import json
import socket
import time

from tc10lib import Log, Rpc, addon_log_lines, addon_log_since, discovery

log = Log("tc-10-03.jsonl")
out = {}
rec = discovery()
print("discovery host/port:", rec["host"], rec["port"], "token: <present>" if rec.get("token") else "MISSING")
n0 = addon_log_lines()
h = json.loads(open("tc-10-03-state.json").read())["handle"]

a = Rpc(log, "03", "A")
out["A_hello"] = "result" in (a.hello() or {})
t = time.time()
r = a.call("query_screenshot", {"doc": h, "view": {"camera": "iso"}}, timeout=60)
out["A_long_read"] = {"status": r.get("status"), "seconds": round(time.time() - t, 3)}

try:
    b = Rpc(log, "03", "B", timeout=10)
    out["B_connect"] = "ok"
except OSError as exc:
    out["B_connect"] = f"raised {type(exc).__name__}: {exc}"
    raise
b.send("rpc_hello", {"token": b.rec["token"], "contract_version": b.rec["contract_version"]})
t_b = time.time()
try:
    b.sock.settimeout(5)
    data = b.sock.recv(65536)
    out["B_recv_while_A"] = f"GOT {len(data)} bytes: {data[:200]!r}"
    b.buf = data
except socket.timeout:
    out["B_recv_while_A"] = "timed out after 5 s, 0 bytes"
log.write({"tag": "03", "check": "B_recv_while_A", "value": out["B_recv_while_A"]})

a.close()
t_close = time.time()
fr = b.recv_frame(timeout=30)
out["B_hello_after_A_close"] = {"seconds_after_A_close": round(time.time() - t_close, 3),
                                "seconds_since_B_hello": round(time.time() - t_b, 3),
                                "contract_version": ((fr or {}).get("result") or {}).get("contract_version"),
                                "error": (fr or {}).get("error")}
out["B_ever_minus_32000"] = '"code": -32000' in json.dumps(fr)
dl = b.call("document_list", {})
out["B_document_list"] = dl.get("status")
b.close()
lines = addon_log_since(n0)
out["addon_log_new_lines"] = len(lines)
out["connection_handler_crashed"] = [ln.strip() for ln in lines if "connection handler crashed" in ln.lower()]
print(json.dumps(out, indent=1))
open("tc-10-03-checks.json", "w").write(json.dumps(out, indent=1))
