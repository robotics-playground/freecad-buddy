"""TC-10-04 When/Then: A full session, B skips the handshake, C handshakes afresh."""
import json
import time

from tc10lib import Log, Rpc

log = Log("tc-10-04.jsonl")
out = {}
a = Rpc(log, "04", "A")
ha = a.hello()
out["A_hello_result_keys"] = sorted((ha or {}).get("result") or {})
out["A_document_list"] = a.call("document_list", {}).get("status")
a.close()

b = Rpc(log, "04", "B")
b.send("document_list", {})
fb = b.recv_frame(timeout=10)
out["B_frame"] = fb
out["B_error_message"] = ((fb or {}).get("error") or {}).get("message")
try:
    nxt = b.sock.recv(65536)
    out["B_next_recv"] = f"{len(nxt)} bytes"
except OSError as exc:
    out["B_next_recv"] = f"{type(exc).__name__}: {exc}"
b.close()
t_b_refused = time.time()

c = Rpc(log, "04", "C")
t_c = time.time()
hc = c.hello()
out["C_connected_after_B_refused"] = t_c > t_b_refused
out["C_contract_version"] = ((hc or {}).get("result") or {}).get("contract_version")
out["C_document_list"] = c.call("document_list", {}).get("status")
c.close()
print(json.dumps(out, indent=1))
open("tc-10-04-checks.json", "w").write(json.dumps(out, indent=1))
