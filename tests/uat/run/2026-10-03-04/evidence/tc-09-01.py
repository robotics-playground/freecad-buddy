import shutil
import subprocess

from tc09lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    doc, op = await open_shown(m, log)
    log.check("Given document_open box-10-20-30 OK", op.get("status") == "OK", doc)
    await frame_shot(m, doc, "tc-09-01-before.png")

    proc = subprocess.run(["uv", "run", "python", "scripts/automation/run_mcp_edge_cases.py"], cwd=PROJECT,
                          capture_output=True, text=True, encoding="utf-8", timeout=900)
    log.write({"sweep_exit": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]})
    shutil.copy(PROJECT + "/_automation/edge_report.json", EV + "/tc-09-01-edge_report.json")
    shutil.copy(PROJECT + "/_automation/edge.stderr.log", EV + "/tc-09-01-edge.stderr.log")
    rep = json.loads(open(EV + "/tc-09-01-edge_report.json", encoding="utf-8").read())
    log.check("sweep all_passed True", rep.get("all_passed") is True, rep.get("all_passed"))
    log.check("total == 14", rep.get("total") == 14, rep.get("total"))
    log.check("passed == total, failed 0", rep.get("passed") == rep.get("total") and rep.get("failed") == 0,
              (rep.get("passed"), rep.get("total"), rep.get("failed")))
    ret = [c for c in rep.get("checks", []) if c.get("tool") == "retired_max_nodes_rejected"]
    log.check("retired_max_nodes_rejected present, status SCHEMA_ERROR", len(ret) == 1 and ret[0].get("status") == "SCHEMA_ERROR", ret)
    faults = {c.get("tool"): c.get("ok") for c in rep.get("checks", []) if str(c.get("tool")).startswith("fault_shape:")}
    log.check("fault_shape:wrong-volume and :non-watertight-open-shell ok", faults.get("fault_shape:wrong-volume") is True
              and faults.get("fault_shape:non-watertight-open-shell") is True, faults)
    log.check("exit code 0", proc.returncode == 0, proc.returncode)
    import re
    err = open(EV + "/tc-09-01-edge.stderr.log", encoding="utf-8", errors="replace").read()
    hits = [ln for ln in err.splitlines() if re.search(r"access violation|swig|segfault|fatal", ln, re.I)]
    log.check("no crash signature in stderr", hits == [], hits[:5])
    await frame_shot(m, doc, "tc-09-01-after.png")
    print("DOC", doc)


go("tc-09-01", body)
