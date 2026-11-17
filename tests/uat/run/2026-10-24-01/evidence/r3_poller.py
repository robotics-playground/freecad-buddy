"""Timed MCP poller for TC-12-12: calls query_capabilities every 0.5 s and appends one JSON line per call to
evidence/tc-12-12-poller.jsonl (start/end wall clock, duration, status or exception). Stops when the file
tc-12-12-poller.stop exists. One session; a call that blocks is logged when it returns."""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))
import mcp_client  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
stop = EVIDENCE / "tc-12-12-poller.stop"
out = (EVIDENCE / "tc-12-12-poller.jsonl").open("a", encoding="utf-8")
with mcp_client.McpClient() as client:
    while not stop.exists():
        start = time.time()
        begin = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        try:
            result = client.call("query_capabilities", {})
            status = result.get("status") if isinstance(result, dict) else str(result)[:60]
            error = None
        except BaseException as exc:  # logged, not hidden
            status, error = None, repr(exc)[:200]
        out.write(json.dumps({"begin": begin, "duration_s": round(time.time() - start, 3), "status": status, "error": error}) + "\n")
        out.flush()
        time.sleep(0.5)
