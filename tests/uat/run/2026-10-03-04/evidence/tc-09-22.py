import re
import shutil
import subprocess

from tc09lib import *  # noqa


def sweep(script):
    return subprocess.run(["uv", "run", "python", f"scripts/automation/{script}"], cwd=PROJECT, capture_output=True, text=True,
                          encoding="utf-8", timeout=1200)


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-22")
    e2e = sweep("run_mcp_e2e.py")
    shutil.copy(PROJECT + "/_automation/e2e_report.json", EV + "/tc-09-22-e2e_report.json")
    shutil.copy(PROJECT + "/_automation/server.stderr.log", EV + "/tc-09-22-server.stderr.log")
    edge = sweep("run_mcp_edge_cases.py")
    shutil.copy(PROJECT + "/_automation/edge_report.json", EV + "/tc-09-22-edge_report.json")
    shutil.copy(PROJECT + "/_automation/edge.stderr.log", EV + "/tc-09-22-edge.stderr.log")
    log.note(f"e2e exit {e2e.returncode}; edge exit {edge.returncode}; edge stderr copied to tc-09-22-edge.stderr.log (fresh run of the log TC names tc-09-01-edge.stderr.log)")
    logs = {n: open(EV + f"/{n}", encoding="utf-8", errors="replace").read() for n in ("tc-09-22-server.stderr.log", "tc-09-22-edge.stderr.log", "tc-09-01-edge.stderr.log")}
    sig = {n: [ln[:160] for ln in t.splitlines() if re.search(r"access violation|swig|segfault|fatal", ln, re.I)] for n, t in logs.items()}
    log.check("no crash signature in any log", all(v == [] for v in sig.values()), sig)
    log.check("access violation absent in server log", not re.search("access violation", logs["tc-09-22-server.stderr.log"], re.I), "")
    log.check("swig absent", not any(re.search("swig", t, re.I) for t in logs.values()), "")
    log.check("segfault and fatal absent", not any(re.search("segfault|fatal", t, re.I) for t in logs.values()), "")
    for n in ("tc-09-22-edge.stderr.log", "tc-09-01-edge.stderr.log"):
        t = logs[n]
        log.note(f"{n}: ^Traceback={len(re.findall(r'(?m)^Traceback', t))} ValidationError={t.count('ValidationError')}")
    tbs = re.findall(r"(?ms)^Traceback.*?(?=^\S|\Z)", logs["tc-09-22-edge.stderr.log"])
    log.check("every Traceback in edge log followed by ValidationError", all("ValidationError" in x for x in tbs), f"{len(tbs)} tracebacks")
    srv_tbs = re.findall(r"(?ms)^Traceback.*?(?=^\S|\Z)", logs["tc-09-22-server.stderr.log"])
    bad = [x[-300:] for x in srv_tbs + tbs if re.search(r"mcp_server\.py|rpc_listener\.py", x.splitlines()[-2] if len(x.splitlines()) > 1 else x)]
    log.check("no traceback terminates in mcp_server.py or rpc_listener.py", bad == [], {"server_tracebacks": len(srv_tbs), "bad": bad})
    r1 = json.loads(open(EV + "/tc-09-22-e2e_report.json").read())
    r2 = json.loads(open(EV + "/tc-09-22-edge_report.json").read())
    log.check("both sweep gates all_passed True", r1.get("all_passed") is True and r2.get("all_passed") is True,
              {"e2e": (r1.get("passed"), r1.get("total")), "edge": (r2.get("passed"), r2.get("total"))})
    await frame_shot(m, doc, "tc-09-22-after.png")


go("tc-09-22", body)
