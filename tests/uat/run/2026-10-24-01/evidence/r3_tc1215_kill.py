"""TC-12-15: start document_open of the bundled ArchDetail.FCStd on a worker thread, wait 1.5 s, then
Stop-Process -Force the FreeCAD pid from this shell. Records the call outcome and elapsed time."""
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))
import mcp_client  # noqa: E402

PID = int(sys.argv[1])
EVIDENCE = Path(__file__).resolve().parent
outcome = {}


def call(client):
    start = time.time()
    outcome["call_start"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    try:
        outcome["result"] = str(client.call("document_open", {"path": "C:/Program Files/FreeCAD 1.1/data/examples/ArchDetail.FCStd"}))[:600]
    except BaseException as exc:
        outcome["exception"] = repr(exc)[:600]
    outcome["call_elapsed_s"] = round(time.time() - start, 2)
    outcome["call_end"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]


with mcp_client.McpClient() as client:
    worker = threading.Thread(target=call, args=(client,))
    worker.start()
    time.sleep(1.5)
    outcome["kill_time"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    kill = subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {PID} -Force"], capture_output=True, text=True)
    outcome["kill_rc"] = kill.returncode
    outcome["kill_stderr"] = kill.stderr[:200]
    worker.join(90)
    outcome["worker_alive_after_90s"] = worker.is_alive()
(EVIDENCE / "tc-12-15-kill.json").write_text(json.dumps(outcome, indent=1), encoding="utf-8")
print(json.dumps(outcome, indent=1))
