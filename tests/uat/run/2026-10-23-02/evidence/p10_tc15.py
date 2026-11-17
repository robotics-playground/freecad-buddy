"""TC-12-15 When for phase P10: an MCP document_open of ArchDetail.FCStd in flight, then a forced kill of
FreeCAD about 1.5 s later. Logs to evidence/tc-12-15-mcp.jsonl and prints each step with its time.

    p10_tc15.py <freecad pid>
"""
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from p5_lib import Run5

EVIDENCE = Path(__file__).resolve().parent
ARCH = "C:/Program Files/FreeCAD 1.1/data/examples/ArchDetail.FCStd"
pid = int(sys.argv[1])
outcome = {}


def stamp():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def open_heavy(run):
    start = time.monotonic()
    outcome["start"] = stamp()
    try:
        outcome["result"] = run.call("document_open", {"path": ARCH}, "when long call (in flight at the kill)")
    except BaseException as exc:  # a transport failure is the expected outcome
        outcome["exception"] = f"{type(exc).__name__}: {exc}"[:600]
    outcome["elapsed_s"] = round(time.monotonic() - start, 3)
    outcome["end"] = stamp()


try:
    with Run5("tc-12-15") as run:
        worker = threading.Thread(target=open_heavy, args=(run,), daemon=True)
        worker.start()
        time.sleep(1.5)
        outcome["kill_at"] = stamp()
        kill = subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"],
                              capture_output=True, text=True)
        outcome["kill_rc"] = kill.returncode
        outcome["kill_err"] = kill.stderr.strip()[:300]
        worker.join(90)
        outcome["joined"] = not worker.is_alive()
except BaseException as exc:
    outcome["client_exit_exception"] = f"{type(exc).__name__}: {exc}"[:600]
(EVIDENCE / "tc-12-15-kill.json").write_text(json.dumps(outcome, indent=1, default=str), encoding="utf-8")
print(json.dumps(outcome, default=str)[:1500])
