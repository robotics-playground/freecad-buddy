import re
import shutil
import subprocess

from tc09lib import *  # noqa


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-21")
    p = subprocess.run(["uv", "run", "python", "scripts/automation/run_mcp_edge_cases.py"], cwd=PROJECT, capture_output=True, text=True,
                       encoding="utf-8", timeout=900)
    shutil.copy(PROJECT + "/_automation/edge.stderr.log", EV + "/tc-09-21-edge.stderr.log")
    log.note(f"edge sweep rerun exit {p.returncode}; stderr copied to tc-09-21-edge.stderr.log")
    err = open(EV + "/tc-09-21-edge.stderr.log", encoding="utf-8", errors="replace").read()
    n_inv = err.count("INVALID_INPUT")
    n_tb = len(re.findall(r"(?m)^Traceback", err))
    log.note(f"grep -c INVALID_INPUT = {n_inv}; grep -c ^Traceback = {n_tb}")
    e = await m.call("query_object", {"doc": doc, "object": "NoSuchObject"})
    data = (e.get("detail") or {}).get("data") or {}
    tb = data.get("traceback") or ""
    log.check("INVALID_INPUT envelope retains non-empty detail.data.traceback", e.get("status") == "INVALID_INPUT" and isinstance(tb, str) and len(tb) > 0, len(tb))
    log.check("traceback length <= 4000", len(tb) <= 4000, len(tb))
    log.check("detail.data.exception == ValidationError", data.get("exception") == "ValidationError", data.get("exception"))
    g = subprocess.run(["C:/Program Files/Git/bin/bash.exe", "-c", f'cd "{PROJECT}"; sed -n "28p;68,71p" src/freecad_buddy/adapters/rpc_dispatch.py'],
                       capture_output=True, text=True).stdout
    (EVIDENCE / "tc-09-21-dispatch-lines.txt").write_text(g, encoding="utf-8")
    log.check("INVALID_INPUT/TIMEOUT take logger.info (l.71) via _EXPECTED_CLIENT_STATUSES (l.28)",
              '_EXPECTED_CLIENT_STATUSES = frozenset({"INVALID_INPUT", "TIMEOUT"})' in g and "logger.info" in g, g.strip())
    log.check("stderr traceback only when status outside set or unexpected (l.68-69)", "if unexpected or status not in _EXPECTED_CLIENT_STATUSES" in g
              and "sys.stderr.write(tb)" in g, "")
    u = await m.call("export_stl", {"doc": doc, "path": "Z:/no/such/drive/tc-09-21.stl"})
    ud = (u.get("detail") or {}).get("data") or {}
    log.check("unexpected fault: RECOMPUTE_ERROR from final except carries unexpected:true; INVALID_INPUT has no such key",
              u.get("status") == "RECOMPUTE_ERROR" and ud.get("unexpected") is True and "unexpected" not in data,
              {"status": status(u), "msg": msg(u)[:80], "exception": ud.get("exception"), "unexpected": ud.get("unexpected")})
    log.check("error channel readable: tracebacks far below call count", n_tb < max(1, n_inv), (n_tb, n_inv))
    await frame_shot(m, doc, "tc-09-21-after.png")


go("tc-09-21", body)
