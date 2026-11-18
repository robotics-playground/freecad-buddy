"""Raw stdout check: every byte the proxy writes to stdout must be a JSON-RPC line (container up)."""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(sys.argv[1])
for server, call in (("freecad-buddy-docker", "query_capabilities"), ("cua-driver-docker", "list_windows")):
    config = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"][server]
    process = subprocess.Popen(
        [config["command"], *config["args"]], cwd="C:\\",
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    stderr_lines: list[bytes] = []
    threading.Thread(target=lambda: stderr_lines.extend(process.stderr), daemon=True).start()
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "raw", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": call, "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "no_such_tool", "arguments": {}}},
    ]
    for message in messages:
        process.stdin.write((json.dumps(message) + "\n").encode())
        process.stdin.flush()
    out: list[bytes] = []
    threading.Thread(target=lambda: out.extend(process.stdout), daemon=True).start()
    time.sleep(10)
    process.stdin.close()
    process.wait(timeout=20)
    time.sleep(0.5)
    bad = []
    ids = []
    for line in out:
        try:
            parsed = json.loads(line)
            assert parsed.get("jsonrpc") == "2.0"
            ids.append(parsed.get("id", parsed.get("method")))
        except Exception:
            bad.append(line[:120])
    print(f"{server}: stdout lines={len(out)} non-JSON-RPC={len(bad)} {bad} ids/methods={ids} "
          f"stderr lines={len(stderr_lines)} exit={process.returncode}")
    for line in stderr_lines[:6]:
        print("   stderr:", line.decode(errors="replace").rstrip()[:200])
