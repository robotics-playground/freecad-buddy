"""TC-10-13 When/Then on the listener (proxy stopped): a request with no trailing newline, then close."""
import json, time
from tc10lib import Log, Rpc, addon_log_lines, addon_log_since, cua, fc_ids
log = Log("tc-10-13.jsonl")
out = {}
n0 = addon_log_lines()
a = Rpc(log, "13", "A"); out["A_hello"] = "result" in (a.hello() or {})
a.send_raw(b'{"jsonrpc":"2.0","id":2,"method":"document_list","params":{}}', note="no trailing newline")
a.close()
time.sleep(1.0)
lines = addon_log_since(n0)
out["addon_log_new"] = [ln.rstrip() for ln in lines if "Traceback" not in ln][:12]
out["frame_read_failed_line"] = [ln.rstrip() for ln in lines if "frame read failed; closing connection" in ln]
out["closed_mid_frame_in_traceback"] = any("connection closed mid-frame" in ln for ln in lines)
try:
    c = Rpc(log, "13", "C"); out["fresh_connect"] = "ok"
    out["fresh_contract_version"] = ((c.hello() or {}).get("result") or {}).get("contract_version")
    out["fresh_document_list"] = c.call("document_list", {}).get("status")
    c.close()
except OSError as exc:
    out["fresh_connect"] = f"FAILED {exc}"
out["document_suspect_in_log"] = [ln.rstrip() for ln in addon_log_since(n0) if "document-suspect" in ln]
pid, win = fc_ids()
st = cua("get_window_state", {"pid": pid, "window_id": win, "include_screenshot": False})
out["menu_query"] = sorted({e.get("label") for e in st.get("elements", []) if e.get("role") in ("MenuItem", "MenuBarItem") and e.get("label") in ("File", "Edit", "View", "Tools", "Help")})
print(json.dumps(out, indent=1)); open("tc-10-13-checks.json", "w").write(json.dumps(out, indent=1))
