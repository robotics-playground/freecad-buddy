"""TC-10-14 When/Then on the listener: >16 MiB with no newline; then a non-UTF-8 frame; then a normal client."""
import json, socket, subprocess, sys, time
from tc10lib import Log, Rpc, addon_log_lines, addon_log_since, fc_ids
log = Log("tc-10-14.jsonl")
pid, _ = fc_ids()
ws = lambda: int(subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-Process -Id {pid}).WorkingSet64"], capture_output=True, text=True).stdout.strip())
h = json.loads(open("tc-10-14-state.json").read())["handle"]
out = {"ws_before": ws()}
n0 = addon_log_lines()
a = Rpc(log, "14", "A", timeout=30); out["A_hello"] = "result" in (a.hello() or {})
try:
    a.sock.sendall(b'{"x":"' + b'A' * (17 * 1024 * 1024))
    out["A_send"] = "17 MiB sent"
except OSError as exc:
    out["A_send"] = f"send stopped: {type(exc).__name__}: {exc}"
try:
    d = a.sock.recv(65536); out["A_next_recv"] = f"{len(d)} bytes"
except OSError as exc:
    out["A_next_recv"] = f"{type(exc).__name__}: {exc}"
a.close()
time.sleep(1.0)
out["ws_after"] = ws()
out["ws_delta"] = out["ws_after"] - out["ws_before"]
b = Rpc(log, "14", "B", timeout=10); out["B_hello"] = "result" in (b.hello() or {})
b.send_raw(b'{"jsonrpc":"2.0","id":2,"method":"document_list","params":{"x":"\xff\xfe\xc3\x28"}}\n', note="invalid UTF-8 bytes")
try:
    d = b.sock.recv(65536); out["B_next_recv"] = f"{len(d)} bytes {d[:120]!r}"
except OSError as exc:
    out["B_next_recv"] = f"{type(exc).__name__}: {exc}"
b.close()
time.sleep(0.5)
c = Rpc(log, "14", "C"); out["C_contract_version"] = ((c.hello() or {}).get("result") or {}).get("contract_version")
out["C_document_list"] = c.call("document_list", {}).get("status")
f = c.call("view_fit_viewport", {"doc": h})
out["mutating_view_fit_on_open_doc"] = {"status": f.get("status"), "message": (f.get("detail") or {}).get("message")}
c.close()
lines = addon_log_since(n0)
out["log_cap_line"] = [ln.rstrip() for ln in lines if "frame exceeds 16 MiB cap" in ln]
out["log_frame_read_failed"] = [ln.rstrip() for ln in lines if "frame read failed" in ln]
out["log_utf8"] = [ln.rstrip() for ln in lines if "UnicodeDecodeError" in ln][:2]
out["ws_end"] = ws()
print(json.dumps(out, indent=1)); open("tc-10-14-checks.json", "w").write(json.dumps(out, indent=1))
